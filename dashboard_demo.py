import streamlit as st
import pandas as pd
import time
import asyncio
from state.demo_portfolio import demo_portfolio
from execution.engine import DemoExecutionEngine
from main import execute_opportunity
from risk.hard_limits import calculate_final_position_size, RiskRejection
from config.settings import settings
import datetime

def render_demo_dashboard():
    st.error("**DEMO MODE — SIMULATION ONLY. NO REAL ORDERS ARE PLACED.**", icon="🚨")
    st.caption("This environment uses simulated historical data and a local DemoPortfolio.")
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Simulated Equity", f"${demo_portfolio.equity:,.2f}")
    col2.metric("Simulated Cash", f"${demo_portfolio.cash:,.2f}")
    
    pnl = demo_portfolio.realized_pl + demo_portfolio.unrealized_pl
    pnl_pct = (pnl / demo_portfolio.start_equity) * 100
    col3.metric("Simulated P&L", f"${pnl:,.2f}", f"{pnl_pct:,.2f}%")
    
    st.markdown("---")
    
    st.subheader("Simulated Open Positions")
    if not demo_portfolio.positions:
        st.info("No open positions in Demo Portfolio.")
    else:
        pos_data = []
        for sym, p in demo_portfolio.positions.items():
            pos_data.append({
                "Symbol": sym,
                "Qty": p["qty"],
                "Avg Price": f"${p['avg_price']:,.2f}",
                "Market Value": f"${p['market_value']:,.2f}"
            })
        st.dataframe(pd.DataFrame(pos_data), use_container_width=True, hide_index=True)
        
    st.markdown("---")
    
    st.subheader("TRY AEGISALPHA")
    st.write("Trigger deterministic scenarios to see the AI pipeline and deterministic risk engine in action.")
    
    scen_col1, scen_col2, scen_col3, scen_col4 = st.columns(4)
    with scen_col1:
        if st.button("▶ Run Full Demo", type="primary", use_container_width=True):
            run_scenario("HIGH_QUALITY")
    with scen_col2:
        if st.button("🧪 Conservative Trade", use_container_width=True):
            run_scenario("LOW_QUALITY")
    with scen_col3:
        if st.button("🛡️ Risk Rejection", use_container_width=True):
            run_scenario("RISK_REJECTED")
    with scen_col4:
        if st.button("🔄 Reset Demo", use_container_width=True):
            demo_portfolio.reset_demo()
            st.rerun()

def run_scenario(scenario: str):
    st.markdown("---")
    st.subheader("Decision Trace")
    trace_container = st.container()
    
    with trace_container:
        if scenario == "HIGH_QUALITY":
            _animate_high_quality()
        elif scenario == "LOW_QUALITY":
            _animate_low_quality()
        elif scenario == "RISK_REJECTED":
            _animate_risk_rejected()

def _delay():
    time.sleep(1.0)

def _animate_high_quality():
    symbol = "NVDA"
    st.info(f"**EVENT:** Sudden price jump detected in {symbol} (+3.2%) [Historical/Simulation Data]")
    _delay()
    st.info("**BULL ANALYST:** Strong upside momentum, AI chip demand remains robust. Rating: 0.85")
    _delay()
    st.info("**BEAR ANALYST:** Potential overextension, but macro environment is supportive. Rating: 0.40")
    _delay()
    st.success("**TRADER SYNTHESIS:** Bullish consensus. Confidence: 0.78")
    _delay()
    
    contract = "NVDA240517C00900000"
    st.info(f"**CONTRACT SELECTION:** Selected OTM Call {contract}")
    _delay()
    
    st.success("**RANK SCORE:** 85.0 (Passed Threshold > 60.0)")
    _delay()
    
    st.info("**RISK ENGINE:** Evaluating exposure limits...")
    _delay()
    
    # Run real risk logic
    mock_positions = demo_portfolio.get_mock_alpaca_positions()
    try:
        qty, risk = calculate_final_position_size(
            symbol=symbol,
            direction="bullish",
            current_positions=mock_positions,
            equity=demo_portfolio.equity,
            ask_price=5.50
        )
        st.success(f"**APPROVED:** Sizing allowed {qty} contracts. Trade Risk: ${risk:,.2f}")
        _delay()
        
        st.info("**EXECUTION:** Routing to DemoExecutionEngine...")
        _delay()
        
        engine = DemoExecutionEngine(demo_portfolio)
        order = engine.submit_limit_order(contract, qty, 5.40, 5.50, "BUY")
        st.success(f"**SIMULATED FILL:** Bought {qty} {contract} @ $5.45")
        _delay()
        
        st.info("**POSITION MONITORING:** Price rose to $6.20.")
        _delay()
        
        demo_portfolio.simulate_exit(contract, 6.20)
        st.success(f"**SIMULATED PROFITABLE EXIT:** Sold {qty} {contract} @ $6.20. Realized P&L: ${(6.20 - 5.45)*100*qty:,.2f}")
        
        time.sleep(2)
        st.rerun()
        
    except RiskRejection as e:
        st.error(f"**REJECTED:** {e}")

def _animate_low_quality():
    symbol = "TSLA"
    st.info(f"**EVENT:** Earnings report released for {symbol} [Historical/Simulation Data]")
    _delay()
    st.info("**BULL ANALYST:** Revenue beat, but margins are tightening. Rating: 0.55")
    _delay()
    st.info("**BEAR ANALYST:** Cybertruck delays and price cuts are concerning. Rating: 0.65")
    _delay()
    st.warning("**TRADER SYNTHESIS:** Neutral/Bearish lean. Confidence: 0.51")
    _delay()
    
    contract = "TSLA240517P00150000"
    st.info(f"**CONTRACT SELECTION:** Selected Put {contract}")
    _delay()
    
    st.error("**RANK SCORE:** 42.0 (Failed Threshold < 60.0). Weak opportunity score, poor spread.")
    _delay()
    
    st.error("**NO ORDER PLACED.** AegisAlpha rejected the trade to preserve capital.")

def _animate_risk_rejected():
    symbol = "AAPL"
    st.info(f"**EVENT:** Product launch announcement for {symbol} [Historical/Simulation Data]")
    _delay()
    st.info("**BULL ANALYST:** High conviction on new product cycle. Rating: 0.90")
    _delay()
    st.info("**BEAR ANALYST:** Disagrees on pricing power, but momentum is undeniable. Rating: 0.35")
    _delay()
    st.success("**TRADER SYNTHESIS:** Strong Bullish signal. Confidence: 0.88")
    _delay()
    
    contract = "AAPL240517C00180000"
    st.info(f"**CONTRACT SELECTION:** Selected Call {contract}")
    _delay()
    
    st.success("**RANK SCORE:** 89.0 (Passed Threshold > 60.0)")
    _delay()
    
    st.info("**RISK ENGINE:** Evaluating exposure limits...")
    _delay()
    
    # We force a risk rejection by temporarily changing a setting or simulating max exposure
    original_max = settings.MAX_DIRECTIONAL_EXPOSURE_PERCENT
    try:
        # Simulate that we already have max exposure
        settings.MAX_DIRECTIONAL_EXPOSURE_PERCENT = 0.0
        
        mock_positions = demo_portfolio.get_mock_alpaca_positions()
        qty, risk = calculate_final_position_size(
            symbol=symbol,
            direction="bullish",
            current_positions=mock_positions,
            equity=demo_portfolio.equity,
            ask_price=2.00
        )
    except RiskRejection as e:
        st.error(f"**REJECTED BY DETERMINISTIC RISK:** {e}")
        st.markdown("> **THE AI CANNOT BYPASS THE MATH.** Despite high confidence (0.88), the deterministic risk engine rejected the trade due to exposure limits.")
    finally:
        settings.MAX_DIRECTIONAL_EXPOSURE_PERCENT = original_max

