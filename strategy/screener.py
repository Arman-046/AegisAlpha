import time
from typing import List, Dict
from config.settings import settings
from app_logging.logger import get_logger
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockLatestQuoteRequest, StockLatestBarRequest

log = get_logger(__name__)

def quantitative_prescreen() -> List[Dict]:
    """
    Fetches latest bars for the entire UNIVERSE and sorts them by a quantitative metric
    (e.g. absolute percentage change or volume) to find the top candidates.
    Returns a list of dicts with symbol data.
    """
    if not settings.APCA_API_KEY_ID or settings.APCA_API_KEY_ID == "PK_DUMMY":
        log.warning("Dummy credentials. Returning mock pre-screen data.")
        return [{"symbol": s, "price": 100.0, "change_pct": 1.5, "volume": 1000000} for s in settings.UNIVERSE[:settings.MAX_SCREEN_CANDIDATES]]
        
    try:
        client = StockHistoricalDataClient(settings.APCA_API_KEY_ID, settings.APCA_API_SECRET_KEY)
        req = StockLatestBarRequest(symbol_or_symbols=settings.UNIVERSE)
        latest_bars = client.get_stock_latest_bar(req)
        
        # We don't have historical previous day close easily here without another API call.
        # But we can use the latest bar's volatility/volume to sort.
        # To make it simple, we'll sort by relative volume or just pure volume.
        # Actually, let's sort by VWAP vs Close (momentum) or just pure trade volume.
        
        candidates = []
        for symbol, bar in latest_bars.items():
            # Basic momentum approximation: close vs vwap
            momentum = abs((bar.close - bar.vwap) / bar.vwap) if bar.vwap > 0 else 0
            candidates.append({
                "symbol": symbol,
                "price": bar.close,
                "volume": bar.volume,
                "momentum": momentum
            })
            
        # Sort by momentum (highest volatility/movement in the current bar)
        candidates.sort(key=lambda x: x["momentum"], reverse=True)
        
        top_candidates = candidates[:settings.MAX_SCREEN_CANDIDATES]
        log.info(f"Quantitative pre-screen completed. Selected top {len(top_candidates)} candidates out of {len(candidates)}.")
        return top_candidates
        
    except Exception as e:
        log.error(f"Error in quantitative pre-screen: {e}")
        return []

def format_candidates_for_ai(candidates: List[Dict]) -> str:
    """Formats the quantitative candidates into a text string for Groq."""
    lines = ["Candidate Universe Snapshot:"]
    for c in candidates:
        lines.append(f"Symbol: {c['symbol']}, Price: ${c['price']:.2f}, Volume: {c['volume']}, Momentum: {c['momentum']:.4f}")
    return "\n".join(lines)

async def generate_watchlist() -> List[str]:
    """
    Executes the full Tier 4 Asset Screener Pipeline:
    1. Quantitative Pre-screen
    2. AI Portfolio Manager evaluation
    3. Update Observability
    """
    from state.observability import obs
    from reasoning.agent import evaluate_screener_candidates
    
    log.info("Starting Autonomous AI Watchlist Generation...")
    obs.update_watchlist_status("REFRESHING")
    
    # 1. Quant Pre-screen
    candidates = quantitative_prescreen()
    if not candidates:
        log.warning("Quant pre-screen yielded no candidates. Falling back to existing watchlist.")
        obs.update_watchlist_status("FAILED", error="Pre-screen failed or market data unavailable.")
        return settings.WATCHLIST
        
    # 2. Format for AI
    candidates_data = format_candidates_for_ai(candidates)
    
    # 3. AI Evaluation
    log.info(f"Sending top {len(candidates)} candidates to Groq Portfolio Manager...")
    ai_results = await evaluate_screener_candidates(candidates_data)
    
    if not ai_results:
        log.warning("Groq evaluation failed. Falling back to existing watchlist.")
        obs.update_watchlist_status("FAILED", error="GROQ UNAVAILABLE")
        return settings.WATCHLIST
        
    # 4. Process Results
    # Sort by score descending and take top WATCHLIST_SIZE
    ai_results.sort(key=lambda x: x["score"], reverse=True)
    top_picks = ai_results[:settings.WATCHLIST_SIZE]
    
    new_watchlist = [pick["symbol"] for pick in top_picks]
    
    log.info(f"New Dynamic Watchlist generated: {new_watchlist}")
    
    # Update Observability
    obs.update_watchlist_stats(
        scanned=len(settings.UNIVERSE),
        candidates=len(candidates),
        ai_reviewed=len(ai_results),
        size=len(new_watchlist),
        picks=top_picks
    )
    obs.update_watchlist_status("ACTIVE")
    
    return new_watchlist

