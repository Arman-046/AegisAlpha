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
    fetch_targeted_option_snapshots,
    validate_option_snapshot
)
from data.volatility import calculate_realized_volatility_percentile
from reasoning.agent import evaluate_symbol_pipeline
from strategy.contract_selector import select_contract_with_snapshot
from strategy.ranking import rank_opportunities
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

from alpaca.data.live import StockDataStream, NewsDataStream
from alpaca.trading.stream import TradingStream

log = get_logger(__name__)

# State for Event Detector
price_cache = {}
last_eval_time = {}
evals_this_hour = {}
in_progress_evals = set()

async def process_symbol(symbol: str, open_positions: int, event_context: str = "") -> dict | None:
    """Processes a single symbol and returns an opportunity dict if valid."""
    log.info(f"Analyzing {symbol} (Event: {event_context})")
    
    bars = fetch_stock_bars(symbol)
    news = fetch_news(symbol)
    
    bars_summary = f"{len(bars)} days of data" if bars else "No data"
    news_summary = f"{len(news)} recent articles" if news else "No news"
    vol_regime = calculate_realized_volatility_percentile(bars) if bars else "Normal"
    recent_context = memory.get_recent_context()
    
    # Run 4-role pipeline
    trader_decision, risk_decision = await evaluate_symbol_pipeline(
        symbol, bars_summary, news_summary, vol_regime, recent_context, 
        memory.current_confidence_threshold, open_positions, event_context
    )
    
    if not trader_decision:
        log.error(f"Pipeline failure for {symbol}. Evaluation aborted.")
        memory.add_decision(symbol, "neutral", 0.0, "FAILED", "AI UNAVAILABLE: Anthropic API failure")
        return None
        
    if trader_decision.direction == "neutral":
        log.info(f"Trader passed on {symbol} (Neutral or below threshold)")
        memory.add_decision(symbol, "neutral", trader_decision.confidence, "PASSED", "No strong signal")
        return None
        
    if not risk_decision or not risk_decision.approved:
        log.warning(f"Risk Manager vetoed {symbol} ({risk_decision.rationale if risk_decision else 'No response'})")
        memory.add_decision(symbol, trader_decision.direction, trader_decision.confidence, "VETOED", "Risk manager rejected")
        return None
        
    log.info(f"Signal for {symbol}: {trader_decision.direction} (Risk-Adjusted Conf: {risk_decision.adjusted_confidence})")
    
    # Contract Selection
    contracts = fetch_option_contracts(symbol)
    
    selected_contract, snapshot = select_contract_with_snapshot(contracts, trader_decision.direction)
    
    if not selected_contract or not snapshot:
        log.info(f"No valid contract found for {symbol}")
        memory.add_decision(symbol, trader_decision.direction, risk_decision.adjusted_confidence, "NO_CONTRACT", "Filtered out deterministically")
        return None
        
    if not validate_option_snapshot(snapshot):
        log.info(f"Snapshot validation failed for {selected_contract}")
        return None
        
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
        "rationale": trader_decision.rationale,
        "vol_regime": vol_regime,
        "bid": bid,
        "ask": ask,
        "spread": spread,
        "delta_dist": delta_dist
    }
    
    # Rank candidate
    ranked = rank_opportunities([opp])
    if not ranked:
        return None
        
    final_opp = ranked[0]
    score = final_opp.get("rank_score", 0.0)
    
    # Check minimum rank score
    if score < settings.MIN_RANK_SCORE_THRESHOLD:
        log.info(f"Rejected {symbol}: Rank Score {score:.2f} is below threshold {settings.MIN_RANK_SCORE_THRESHOLD}.")
        memory.add_decision(symbol, trader_decision.direction, risk_decision.adjusted_confidence, "RANK_REJECTED", f"Score {score:.2f} < threshold")
        return None
        
    log.info(f"Candidate {symbol} passed ranking threshold with score {score:.2f}.")
    return final_opp

async def execute_opportunity(top_opp: dict, engine: ExecutionEngine = None, current_positions=None, current_loop_equity: float = None):
    try:
        if engine is None:
            engine = LivePaperExecutionEngine()
            
        if current_positions is None:
            current_positions = trading_client.get_all_positions()
            
        if not validate_max_open_positions(len(current_positions)):
            log.info("Max positions reached during execution loop. Stopping further executions.")
            return
            
        log.info(f"Evaluating execution for candidate: {top_opp['contract']}")
        
        if current_loop_equity is None:
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
                top_opp['confidence'], "EXECUTED", top_opp['rationale']
            )
        else:
            memory.add_decision(
                top_opp['symbol'], top_opp['direction'], 
                top_opp['confidence'], "FAILED_EXECUTION", "Order rejected or failed"
            )
            
    except RiskRejection as e:
        log.warning(f"Risk Rejection for {top_opp['contract']}: {e}")
        memory.add_decision(
            top_opp['symbol'], top_opp['direction'], 
            top_opp['confidence'], "RISK_REJECTED", str(e)
        )

async def trigger_pipeline(symbol: str, event_context: str):
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
        
        opp = await process_symbol(symbol, len(open_positions), event_context)
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
                price_cache[symbol] = price
                return
        else:
            price_cache[symbol] = price
            return
                    
        price_cache[symbol] = price
        last_eval_time[symbol] = now
        
        event_context = f"Sudden price movement to {price} detected."
        log.info(f"Triggering pipeline for {symbol} due to price event.")
        asyncio.run_coroutine_threadsafe(trigger_pipeline(symbol, event_context), main_loop)
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
        log.info(f"Triggering pipeline for {symbol} due to news event.")
        asyncio.run_coroutine_threadsafe(trigger_pipeline(symbol, event_context), main_loop)
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

def start_streams():
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
    status_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "state", "system_status.json")
    os.makedirs(os.path.dirname(status_file), exist_ok=True)
    while True:
        try:
            status = {
                "status": "RUNNING",
                "last_heartbeat": datetime.now(timezone.utc).isoformat(),
                "market_open": is_market_open(trading_client)
            }
            with open(status_file, "w") as f:
                json.dump(status, f)
        except Exception as e:
            log.error(f"Error in heartbeat_loop: {e}")
        
        await asyncio.sleep(60)

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
