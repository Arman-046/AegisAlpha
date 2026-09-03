import asyncio
import time
import os
import threading
import json
from datetime import datetime, timezone
from config.settings import settings
from config.preflight import run_preflight_checks
from data.market_clock import is_market_open
from data.clients import trading_client
from data.fetchers import (
    fetch_stock_bars, 
    fetch_news, 
    fetch_option_contracts, 
    fetch_targeted_option_snapshots
)
from data.volatility import calculate_realized_volatility_percentile
from data.events import Event
from reasoning.agent import evaluate_symbol_pipeline
from strategy.contract_selector import select_contract_with_snapshot
from strategy.ranking import rank_opportunities
from strategy.validation import validate_tradeability
from state.memory import memory
from state.recovery import reconcile_state
from risk.hard_limits import (
    calculate_final_position_size, 
    check_circuit_breaker, 
    validate_max_open_positions,
    RiskRejection
)
from execution.engine import ExecutionEngine, LivePaperExecutionEngine
from execution.reconciliation import verify_order_state
from positions.monitor import evaluate_and_exit_positions
from app_logging.logger import get_logger
from state.observability import obs

from alpaca.data.live import StockDataStream, NewsDataStream
from alpaca.trading.stream import TradingStream

log = get_logger(__name__)

# State for Event Detector
price_cache = {}
last_eval_time = {}
evals_this_hour = {}
in_progress_evals = set()

async def process_symbol(event: Event, open_positions: int) -> dict | None:
    """Processes a single symbol and returns an opportunity dict if valid."""
    symbol = event.symbol
    log.info(f"Analyzing {symbol} (Event: {event.market_context})")
    
    obs.update_stage("DATA", "PROCESSING")
    bars = fetch_stock_bars(symbol)
    news = fetch_news(symbol)
    
    bars_summary = f"{len(bars)} days of data" if bars else "No data"
    news_summary = f"{len(news)} recent articles" if news else "No news"
    vol_regime = calculate_realized_volatility_percentile(bars) if bars else "Normal"
    recent_context = memory.get_recent_context()
    
    obs.log_activity(f"Market data gathered for {symbol}. Volatility Regime: {vol_regime}")
    obs.update_stage("DATA", "COMPLETED")
    
    # Run 4-role pipeline
    trader_decision, risk_decision = await evaluate_symbol_pipeline(
        symbol, bars_summary, news_summary, vol_regime, recent_context, 
        memory.current_confidence_threshold, open_positions, event.market_context
    )
    
    if not trader_decision:
        log.error(f"Pipeline failure for {symbol}. Evaluation aborted.")
        mode_val = "DEMO" if event.is_simulated else "LIVE_PAPER"
        memory.add_decision(symbol, "neutral", 0.0, "FAILED", "AI UNAVAILABLE: Gemini API failure", event=event, is_counterfactual=False, mode=mode_val)
        obs.set_terminal_state("AI UNAVAILABLE", "Gemini reasoning failed or returned empty.")
        obs.log_error("AI", f"Gemini API failure during evaluation for {symbol}")
        obs.increment_stat("ai_failures")
        return None
        
    if trader_decision.direction == "neutral":
        log.info(f"Trader passed on {symbol} (Neutral or below threshold)")
        mode_val = "DEMO" if event.is_simulated else "LIVE_PAPER"
        memory.add_decision(symbol, "neutral", trader_decision.confidence, "PASSED", "No strong signal", event=event, trader_synthesis=trader_decision.synthesis, is_counterfactual=True, mode=mode_val)
        obs.set_terminal_state("AI THESIS NEUTRAL", f"Trader decided neutral ({trader_decision.confidence:.2f} confidence).")
        obs.log_activity(f"Trader decided neutral for {symbol}")
        return None
        
    if not risk_decision or not risk_decision.approved:
        log.warning(f"Risk Manager vetoed {symbol} ({risk_decision.rationale if risk_decision else 'No response'})")
        mode_val = "DEMO" if event.is_simulated else "LIVE_PAPER"
        memory.add_decision(symbol, trader_decision.direction, trader_decision.confidence, "VETOED", "Risk manager rejected", event=event, trader_synthesis=trader_decision.synthesis, is_counterfactual=True, mode=mode_val)
        obs.set_terminal_state("RISK LIMIT EXCEEDED", f"Risk engine vetoed: {risk_decision.rationale if risk_decision else 'No response'}")
        obs.log_activity(f"Risk engine vetoed {symbol}")
        obs.increment_stat("risk_rejections")
        return None
        
    log.info(f"Signal for {symbol}: {trader_decision.direction} (Risk-Adjusted Conf: {risk_decision.adjusted_confidence})")
    obs.log_activity(f"AI Decision: {trader_decision.direction.upper()} for {symbol}")
    
    # Contract Selection
    obs.update_stage("OPTION", "PROCESSING")
    contracts = fetch_option_contracts(symbol)
    
    selected_contract, snapshot = select_contract_with_snapshot(contracts, trader_decision.direction)
    
    if not selected_contract or not snapshot:
        log.info(f"No valid contract found for {symbol}")
        mode_val = "DEMO" if event.is_simulated else "LIVE_PAPER"
        memory.add_decision(symbol, trader_decision.direction, risk_decision.adjusted_confidence, "NO_CONTRACT", "Filtered out deterministically", event=event, trader_synthesis=trader_decision.synthesis, is_counterfactual=True, mode=mode_val)
        obs.set_terminal_state("OPTION REJECTED", "Available option contracts did not meet configured requirements.")
        obs.update_stage("OPTION", "FAILED")
        return None
        
    is_valid, reject_reason, quant_metrics = validate_tradeability(symbol, selected_contract, snapshot)
    
    if not is_valid:
        log.info(f"Snapshot validation failed for {selected_contract}: {reject_reason}")
        mode_val = "DEMO" if event.is_simulated else "LIVE_PAPER"
        memory.add_decision(symbol, trader_decision.direction, risk_decision.adjusted_confidence, "VALIDATION_FAILED", f"Quantitative validation failed: {reject_reason}", event=event, trader_synthesis=trader_decision.synthesis, is_counterfactual=True, mode=mode_val)
        obs.set_terminal_state(reject_reason, f"Quantitative validation failed: {reject_reason}")
        obs.update_stage("OPTION", "FAILED")
        return None
        
    obs.update_stage("OPTION", "COMPLETED")
        
    q = snapshot.latest_quote
    bid, ask = q.bid_price, q.ask_price
    spread = ask - bid
    
    # Basic delta distance check for ranking
    delta_dist = 0.5
    if hasattr(snapshot, "greeks") and snapshot.greeks and snapshot.greeks.delta:
        delta_dist = abs(abs(snapshot.greeks.delta) - 0.5)
        
    opp = {
        "symbol": symbol,
        "contract": selected_contract,
        "direction": trader_decision.direction,
        "confidence": risk_decision.adjusted_confidence,
        "synthesis": trader_decision.synthesis,
        "rationale": trader_decision.rationale,
        "vol_regime": vol_regime,
        "bid": bid,
        "ask": ask,
        "spread": spread,
        "delta_dist": delta_dist,
        "quant_metrics": quant_metrics,
        "event": event
    }
    
    # Rank candidate
    obs.update_stage("RANK", "PROCESSING")
    ranked = rank_opportunities([opp])
    if not ranked:
        obs.update_stage("RANK", "FAILED")
        obs.set_terminal_state("NO OPPORTUNITIES RANKED", "Failed ranking evaluation.")
        return None
        
    final_opp = ranked[0]
    score = final_opp.get("rank_score", 0.0)
    
    # Check minimum rank score
    if score < settings.MIN_RANK_SCORE_THRESHOLD:
        log.info(f"Rejected {symbol}: Rank Score {score:.2f} is below threshold {settings.MIN_RANK_SCORE_THRESHOLD}.")
        mode_val = "DEMO" if event.is_simulated else "LIVE_PAPER"
        memory.add_decision(symbol, trader_decision.direction, risk_decision.adjusted_confidence, "RANK_REJECTED", f"Score {score:.2f} < threshold", event=event, trader_synthesis=trader_decision.synthesis, quant_metrics=quant_metrics, rank_score=score, option_candidate=selected_contract, is_counterfactual=True, mode=mode_val)
        obs.set_terminal_state("RANK SCORE TOO LOW", f"Rank score {score:.2f} is below minimum {settings.MIN_RANK_SCORE_THRESHOLD}.")
        obs.update_stage("RANK", "FAILED")
        obs.increment_stat("rank_rejections")
        obs.log_activity(f"Opportunity for {symbol} rejected by ranking (Score: {score:.2f})")
        return None
        
    obs.update_stage("RANK", "COMPLETED")
    log.info(f"Candidate {symbol} passed ranking threshold with score {score:.2f}.")
    return final_opp

async def execute_opportunity(top_opp: dict, engine: ExecutionEngine = None, current_positions=None, current_loop_equity: float = None):
    try:
        obs.update_stage("EXECUTE", "PROCESSING")
        
        event_obj = top_opp.get('event')
        if event_obj is None or not hasattr(event_obj, 'is_simulated'):
            log.error("CRITICAL: Missing or unknown event simulation state. Failing closed.")
            obs.update_stage("EXECUTE", "FAILED")
            obs.set_terminal_state("SAFETY REJECTION", "Missing event simulation state.")
            return
            
        is_simulated_event = event_obj.is_simulated
        
        if settings.TRADING_MODE == "paper" and is_simulated_event:
            log.error("CRITICAL: Simulated event reached PAPER execution path. Failing closed.")
            obs.update_stage("EXECUTE", "FAILED")
            obs.set_terminal_state("SAFETY REJECTION", "Simulated event in paper mode.")
            return
            
        if settings.TRADING_MODE == "demo" and not is_simulated_event:
            log.error("CRITICAL: Live event reached DEMO execution path. Failing closed.")
            obs.update_stage("EXECUTE", "FAILED")
            obs.set_terminal_state("SAFETY REJECTION", "Live event in demo mode.")
            return
            
        mode_val = "DEMO" if settings.TRADING_MODE == "demo" else "LIVE_PAPER"
        
        if engine is None:
            if settings.TRADING_MODE == "demo":
                from execution.engine import DemoExecutionEngine
                from state.demo_portfolio import demo_portfolio
                engine = DemoExecutionEngine(demo_portfolio)
            else:
                engine = LivePaperExecutionEngine()
            
        if current_positions is None:
            if settings.TRADING_MODE == "demo":
                from state.demo_portfolio import demo_portfolio
                current_positions = demo_portfolio.get_mock_alpaca_positions()
            else:
                current_positions = trading_client.get_all_positions()
            
        if not validate_max_open_positions(len(current_positions)):
            log.info("Max positions reached during execution loop. Stopping further executions.")
            obs.update_stage("EXECUTE", "FAILED")
            obs.set_terminal_state("RISK REJECTED", "Max open positions reached.")
            return
            
        log.info(f"Evaluating execution for candidate: {top_opp['contract']}")
        
        if current_loop_equity is None:
            if settings.TRADING_MODE == "demo":
                from state.demo_portfolio import demo_portfolio
                current_loop_equity = demo_portfolio.cash
            else:
                acct_loop = trading_client.get_account()
                current_loop_equity = float(acct_loop.equity)
        
        qty, risk = calculate_final_position_size(
            symbol=top_opp['symbol'],
            direction=top_opp['direction'],
            current_positions=current_positions,
            equity=current_loop_equity,
            ask_price=top_opp['ask']
        )
        
        order = engine.submit_limit_order(
            symbol=top_opp['contract'],
            qty=qty,
            bid=top_opp['bid'],
            ask=top_opp['ask'],
            side="BUY"
        )
        
        if order:
            verify_order_state(order.id)
            memory.add_decision(
                top_opp['symbol'], top_opp['direction'], 
                top_opp['confidence'], "EXECUTED", top_opp['rationale'],
                event=top_opp.get('event'), quant_metrics=top_opp.get('quant_metrics'),
                rank_score=top_opp.get('rank_score'), option_candidate=top_opp.get('contract'),
                trader_synthesis=top_opp.get('synthesis'), is_counterfactual=False,
                mode=mode_val
            )
            obs.update_stage("EXECUTE", "COMPLETED")
            obs.update_stage("MONITOR", "COMPLETED")
            obs.set_terminal_state("TRADE APPROVED", f"Executed order for {top_opp['contract']}")
            obs.log_activity(f"Order submitted: {top_opp['contract']}")
            obs.increment_stat("trades_approved")
            obs.increment_stat("orders_submitted")
        else:
            memory.add_decision(
                top_opp['symbol'], top_opp['direction'], 
                top_opp['confidence'], "FAILED_EXECUTION", "Order rejected or failed",
                event=top_opp.get('event'), quant_metrics=top_opp.get('quant_metrics'),
                rank_score=top_opp.get('rank_score'), option_candidate=top_opp.get('contract'),
                trader_synthesis=top_opp.get('synthesis'), is_counterfactual=True,
                mode=mode_val
            )
            obs.update_stage("EXECUTE", "FAILED")
            obs.set_terminal_state("FAILED EXECUTION", "Order rejected or failed.")
            obs.log_error("EXECUTE", "Failed to submit Alpaca order.")
            
    except RiskRejection as e:
        log.warning(f"Risk Rejection for {top_opp['contract']}: {e}")
        memory.add_decision(
            top_opp['symbol'], top_opp['direction'], 
            top_opp['confidence'], "RISK_REJECTED", str(e),
            event=top_opp.get('event'), quant_metrics=top_opp.get('quant_metrics'),
            rank_score=top_opp.get('rank_score'), option_candidate=top_opp.get('contract'),
            trader_synthesis=top_opp.get('synthesis'), is_counterfactual=True,
            mode=mode_val
        )
        obs.update_stage("EXECUTE", "FAILED")
        obs.set_terminal_state("RISK LIMIT EXCEEDED", f"Risk engine vetoed at execution: {e}")
        obs.increment_stat("risk_rejections")

async def trigger_pipeline(event: Event):
    symbol = event.symbol
    if symbol in in_progress_evals:
        log.info(f"Ignored event for {symbol} - pipeline already in progress.")
        return
        
    try:
        in_progress_evals.add(symbol)
        
        now = time.time()
        # Clean up hourly evals older than 1 hour
        if symbol in evals_this_hour:
            evals_this_hour[symbol] = [t for t in evals_this_hour[symbol] if now - t < 3600]
        else:
            evals_this_hour[symbol] = []
            
        if len(evals_this_hour[symbol]) >= 3:
            log.info(f"Ignored event for {symbol} - max 3 evaluations per hour reached.")
            return
            
        if not is_market_open(trading_client):
            return
            
        open_positions = trading_client.get_all_positions()
        if not validate_max_open_positions(len(open_positions)):
            log.info(f"Ignored event for {symbol} - max open positions reached.")
            return
            
        evals_this_hour[symbol].append(now)
        
        obs.start_evaluation(symbol, event.market_context)
        
        opp = await process_symbol(event, len(open_positions))
        if opp:
            await execute_opportunity(opp)
    except Exception as e:
        log.error(f"Error in pipeline trigger for {symbol}: {e}")
    finally:
        in_progress_evals.discard(symbol)

# Callbacks for Streams - these might be called from synchronous threads by alpaca-py!
# We'll use asyncio.run_coroutine_threadsafe to schedule them onto the main event loop.

main_loop = None

async def handle_bar(bar):
    if not main_loop: return
    try:
        symbol = bar.symbol
        price = bar.close
        
        now = time.time()
        if symbol in price_cache:
            last_price = price_cache[symbol]
            change = abs(price - last_price) / last_price if last_price > 0 else 0
            if change >= 0.005:
                pass # Significant move, proceed
            else:
                return # Do NOT update anchor price! Keep accumulating drift.
        else:
            price_cache[symbol] = price
            return
                    
        price_cache[symbol] = price
        last_eval_time[symbol] = now
        
        event_context = f"Sudden price movement to {price} detected."
        event = Event(
            timestamp=now,
            symbol=symbol,
            event_type="PRICE_SPIKE",
            magnitude=change,
            source="StockDataStream",
            market_context=event_context
        )
        log.info(f"Triggering pipeline for {symbol} due to price event.")
        asyncio.run_coroutine_threadsafe(trigger_pipeline(event), main_loop)
    except Exception as e:
        log.error(f"Error in handle_bar: {e}")

async def handle_news(news):
    if not main_loop: return
    try:
        symbol = news.symbols[0] if news.symbols else "UNKNOWN"
        if symbol not in settings.WATCHLIST:
            return
            
        now = time.time()
        if symbol in last_eval_time and now - last_eval_time[symbol] < 900:
            return
            
        last_eval_time[symbol] = now
        event_context = f"Breaking news headline: {news.headline}"
        event = Event(
            timestamp=now,
            symbol=symbol,
            event_type="BREAKING_NEWS",
            magnitude=0.0,
            source="NewsDataStream",
            market_context=event_context
        )
        log.info(f"Triggering pipeline for {symbol} due to news event.")
        asyncio.run_coroutine_threadsafe(trigger_pipeline(event), main_loop)
    except Exception as e:
        log.error(f"Error in handle_news: {e}")

async def handle_trade(trade):
    log.info(f"Trade update received: {trade}")
    if not main_loop: return
    try:
        # Trigger an async reconciliation
        async def reconcile():
            log.info("Reconciling state from Alpaca REST API after trade execution...")
            reconcile_state()
            
        asyncio.run_coroutine_threadsafe(reconcile(), main_loop)
    except Exception as e:
        log.error(f"Error in handle_trade: {e}")

stock_stream = None
news_stream = None

def start_streams():
    global stock_stream, news_stream
    api_key = settings.APCA_API_KEY_ID
    secret_key = settings.APCA_API_SECRET_KEY
    
    if api_key == "PK_DUMMY" or not api_key:
        log.warning("Dummy credentials found. Streams will not run properly, but we will mock them.")
        return
        
    def run_with_reconnect(stream_func, stream_name):
        while True:
            try:
                log.info(f"Starting {stream_name}...")
                stream_func()
            except Exception as e:
                log.error(f"{stream_name} disconnected: {e}. Reconnecting in 10s...")
                time.sleep(10)
                
    try:
        stock_stream = StockDataStream(api_key, secret_key)
        stock_stream.subscribe_bars(handle_bar, *settings.WATCHLIST)
        threading.Thread(target=run_with_reconnect, args=(stock_stream.run, "StockDataStream"), daemon=True).start()
    except Exception as e:
        log.error(f"Failed to start StockDataStream: {e}")
        
    try:
        news_stream = NewsDataStream(api_key, secret_key)
        news_stream.subscribe_news(handle_news, *settings.WATCHLIST)
        threading.Thread(target=run_with_reconnect, args=(news_stream.run, "NewsDataStream"), daemon=True).start()
    except Exception as e:
        log.error(f"Failed to start NewsDataStream: {e}")
        
    try:
        trading_stream = TradingStream(api_key, secret_key, paper=True)
        trading_stream.subscribe_trade_updates(handle_trade)
        threading.Thread(target=run_with_reconnect, args=(trading_stream.run, "TradingStream"), daemon=True).start()
    except Exception as e:
        log.error(f"Failed to start TradingStream: {e}")


async def heartbeat_loop():
    """Background task to write agent status for the dashboard."""
    while True:
        try:
            status = "RUNNING" if is_market_open(trading_client) else "MARKET CLOSED"
            obs.heartbeat(status)
        except Exception as e:
            log.error(f"Error in heartbeat_loop: {e}")
        
        await asyncio.sleep(60)

async def watchlist_refresh_loop():
    """Background task to dynamically update the AI watchlist."""
    from strategy.screener import generate_watchlist
    
    # Wait 30 seconds after startup before first run to let streams initialize
    await asyncio.sleep(30)
    
    while True:
        try:
            if not is_market_open(trading_client):
                obs.update_watchlist_status("MARKET CLOSED", next_refresh=0)
                await asyncio.sleep(300)
                continue
                
            new_watchlist = await generate_watchlist()
            if new_watchlist and new_watchlist != settings.WATCHLIST:
                old_watchlist = settings.WATCHLIST.copy()
                settings.WATCHLIST = new_watchlist
                
                if stock_stream:
                    try:
                        stock_stream.unsubscribe_bars(*old_watchlist)
                        stock_stream.subscribe_bars(handle_bar, *new_watchlist)
                    except Exception as e:
                        log.error(f"Failed to update stock stream subscriptions: {e}")
                        
                if news_stream:
                    try:
                        news_stream.unsubscribe_news(*old_watchlist)
                        news_stream.subscribe_news(handle_news, *new_watchlist)
                    except Exception as e:
                        log.error(f"Failed to update news stream subscriptions: {e}")
                        
                log.info(f"Successfully migrated data streams to new watchlist: {new_watchlist}")
                
            next_time = time.time() + settings.WATCHLIST_REFRESH_INTERVAL
            obs.update_watchlist_status("ACTIVE", next_refresh=next_time)
            
        except Exception as e:
            log.error(f"Error in watchlist_refresh_loop: {e}")
            
        await asyncio.sleep(settings.WATCHLIST_REFRESH_INTERVAL)

async def check_demo_trigger():
    """Background task to watch for state/demo_trigger.json IPC requests."""
    trigger_file = "state/demo_trigger.json"
    consumed_ids = set()
    
    while True:
        if settings.TRADING_MODE == "demo" and os.path.exists(trigger_file):
            try:
                # Use a lightweight atomic rename approach where possible, or just read carefully
                temp_file = trigger_file + ".tmp_read"
                if os.path.exists(temp_file):
                    os.remove(temp_file)
                # Try rename to acquire lock
                try:
                    os.rename(trigger_file, temp_file)
                except OSError:
                    # File might be locked by writer, skip this cycle
                    pass
                else:
                    with open(temp_file, "r") as f:
                        data = json.load(f)
                    
                    req_id = data.get("request_id")
                    if req_id and req_id not in consumed_ids:
                        req_time_str = data.get("requested_at")
                        
                        # Validate expiration (e.g. 60 seconds)
                        if req_time_str:
                            try:
                                req_time = datetime.fromisoformat(req_time_str.replace("Z", "+00:00")).timestamp()
                                if time.time() - req_time > 60:
                                    log.warning(f"Ignored stale demo trigger {req_id}")
                                    consumed_ids.add(req_id)
                                    os.remove(temp_file)
                                    continue
                            except ValueError:
                                pass
                                
                        scenario = data.get("scenario")
                        log.info(f"Processing DEMO trigger: {scenario} (ID: {req_id})")
                        
                        if scenario in ["approved_trade", "risk_rejection", "data_rejection"]:
                            # Mock portfolio cash injection for Risk Governor testing
                            from state.demo_portfolio import demo_portfolio
                            if scenario == "approved_trade":
                                demo_portfolio.cash = 1000.0
                                sym = "AAPL"
                                magnitude = 0.05
                                ctx = "Simulated positive earnings surprise."
                            elif scenario == "risk_rejection":
                                demo_portfolio.cash = 1000.0  # Too low for the $250 max loss fixture
                                sym = "TSLA"
                                magnitude = -0.05
                                ctx = "Simulated negative guidance."
                            elif scenario == "data_rejection":
                                demo_portfolio.cash = 1000.0
                                sym = "NVDA"
                                magnitude = 0.05
                                ctx = "Simulated AI event."
                                
                            event = Event(
                                timestamp=time.time(),
                                symbol=sym,
                                event_type="DEMO_TRIGGER",
                                magnitude=magnitude,
                                source="DEMO",
                                market_context=ctx,
                                is_simulated=True
                            )
                            asyncio.run_coroutine_threadsafe(trigger_pipeline(event), main_loop)
                            
                        consumed_ids.add(req_id)
                    os.remove(temp_file)
            except Exception as e:
                log.error(f"Error processing demo trigger: {e}")
                
        await asyncio.sleep(2)

async def autonomous_loop():
    global main_loop
    main_loop = asyncio.get_running_loop()
    
    log.info("Starting Tier 3 Autonomous Trading Loop (Event-Driven)")
    
    if not run_preflight_checks():
        log.error("Preflight failed. Exiting.")
        return
        
    if not reconcile_state():
        log.error("State recovery failed. Exiting.")
        return
        
    start_equity = None
    try:
        acct = trading_client.get_account()
        start_equity = float(acct.equity)
    except Exception as e:
        log.error(f"Failed to get account equity: {e}")
        return
        
    log.info(f"Starting Equity: ${start_equity:.2f}")
    
    start_streams()
    
    asyncio.create_task(heartbeat_loop())
    asyncio.create_task(watchlist_refresh_loop())
    if settings.TRADING_MODE == "demo":
        asyncio.create_task(check_demo_trigger())
    
    # Periodic background loop for state reconciliation and position monitoring
    while True:
        try:
            if not is_market_open(trading_client):
                log.info("Market is closed. Sleeping for 5 minutes.")
                await asyncio.sleep(300)
                continue
                
            acct = trading_client.get_account()
            current_equity = float(acct.equity)
            
            if check_circuit_breaker(start_equity, current_equity):
                log.warning("Circuit breaker active. Halting trading for the day.")
                await asyncio.sleep(3600)
                continue
                
            open_positions = trading_client.get_all_positions()
            
            # Monitoring
            active_symbols = [p.symbol for p in open_positions if "us_option" in str(p.asset_class)]
            if active_symbols:
                chain_snapshots = fetch_targeted_option_snapshots(active_symbols)
                evaluate_and_exit_positions(chain_snapshots)
            
            log.info("Periodic position monitor complete. Sleeping for 15 minutes.")
            await asyncio.sleep(900)
            
        except Exception as e:
            log.error(f"Error in periodic loop: {e}")
            await asyncio.sleep(60)

def preflight_check():
    """Validates critical settings before startup."""
    if not settings.PAPER:
        log.error("CRITICAL: Application is not configured for paper trading. Failing fast.")
        raise ValueError("PAPER must be True.")
    
    log.info("=" * 40)
    log.info("TRADING ENVIRONMENT = PAPER")
    log.info("=" * 40)

if __name__ == "__main__":
    preflight_check()
    log.info("Starting Autonomous Agent...")
    
    # We must run autonomous loop in asyncio
    main_loop = asyncio.new_event_loop()
    asyncio.set_event_loop(main_loop)
    
    try:
        main_loop.run_until_complete(autonomous_loop())
    except KeyboardInterrupt:
        log.info("Shutting down manually.")
    except Exception as e:
        log.error(f"Fatal error: {e}")
    finally:
        main_loop.close()
