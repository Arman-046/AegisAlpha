import streamlit as st
import pandas as pd
import time
from state.demo_portfolio import demo_portfolio
from execution.engine import DemoExecutionEngine
from risk.hard_limits import calculate_final_position_size, RiskRejection
from config.settings import settings

def render_demo_dashboard():
    # Hero Section
    st.markdown("<h1 style='text-align: center;'>🛡️ AEGISALPHA</h1>", unsafe_allow_html=True)
    st.markdown("<h3 style='text-align: center; color: #888;'>AUTONOMOUS OPTIONS TRADING AGENT</h3>", unsafe_allow_html=True)
    
    st.info("🔵 **DEMO MODE — SIMULATION ONLY** | NO REAL ORDERS • NO API KEYS REQUIRED")
    st.markdown("<p style='text-align: center;'>Try a complete autonomous trading decision in under 30 seconds.</p>", unsafe_allow_html=True)
    st.markdown("---")

    # Main CTA
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        main_start = st.button("▶ START AEGISALPHA DEMO", type="primary", use_container_width=True)
        st.markdown("<p style='text-align: center; font-size: 0.9em; color: #888;'>Watch the AI go from market event → decision → risk check → execution.</p>", unsafe_allow_html=True)
        
    st.markdown("<p style='text-align: center; font-size: 0.9em; margin-top: 20px;'>Explore individual scenarios:</p>", unsafe_allow_html=True)
    scen_col1, scen_col2, scen_col3, scen_col4 = st.columns(4)
    
    with scen_col1:
        start_high = st.button("🟢 Successful Trade", use_container_width=True)
    with scen_col2:
        start_low = st.button("🟡 Low-Quality Opportunity", use_container_width=True)
    with scen_col3:
        start_risk = st.button("🔴 Risk Rejection", use_container_width=True)
    with scen_col4:
        if st.button("↻ Reset", use_container_width=True):
            demo_portfolio.reset_demo()
            st.rerun()

    # Run the selected scenario trace
    if main_start or start_high:
        run_scenario("HIGH_QUALITY")
    elif start_low:
        run_scenario("LOW_QUALITY")
    elif start_risk:
        run_scenario("RISK_REJECTED")
    
    # Portfolio Section at the bottom
    st.markdown("---")
    st.subheader("DEMO PORTFOLIO")
    colA, colB, colC = st.columns(3)
    colA.metric("Starting Equity", f"${demo_portfolio.start_equity:,.2f}")
    colB.metric("Simulated Cash", f"${demo_portfolio.cash:,.2f}")
    
    pnl = demo_portfolio.realized_pl + demo_portfolio.unrealized_pl
    pnl_pct = (pnl / demo_portfolio.start_equity) * 100
    colC.metric("Simulated P&L", f"${pnl:,.2f}", f"{pnl_pct:,.2f}%")
    
    if demo_portfolio.positions:
        pos_data = []
        for sym, p in demo_portfolio.positions.items():
            pos_data.append({
                "Symbol": sym,
                "Qty": p["qty"],
                "Avg Price": f"${p['avg_price']:,.2f}",
                "Market Value": f"${p['market_value']:,.2f}"
            })
        st.dataframe(pd.DataFrame(pos_data), use_container_width=True, hide_index=True)
    else:
        st.caption("No open positions in Demo Portfolio.")

def _delay():
    time.sleep(1.2)

def run_scenario(scenario: str):
    st.markdown("---")
    
    if scenario == "HIGH_QUALITY":
        _animate_high_quality()
    elif scenario == "LOW_QUALITY":
        _animate_low_quality()
    elif scenario == "RISK_REJECTED":
        _animate_risk_rejected()

def _animate_high_quality():
    st.subheader("LIVE PIPELINE TRACE")
    trace_area = st.container()
    
    with trace_area:
        st.info("📡 **EVENT DETECTED:** NVDA moved sharply in a short period. AegisAlpha detected an event worth investigating.")
        _delay()
        st.info("📊 **DATA GATHERED:** Recent price history, volatility, volume and market information were collected.")
        _delay()
        st.info("🐂 **BULL ANALYST:** Potential upside: Momentum and volume support a bullish move.")
        _delay()
        st.info("🐻 **BEAR ANALYST:** Potential downside: Resistance and reversal risk could invalidate the setup.")
        _delay()
        st.info("⚖️ **TRADER:** Both arguments are considered. Bull case is stronger. Choosing Call direction.")
        _delay()
        st.info("🎯 **OPTION SELECTION:** Several contracts were filtered. A liquid 14 DTE contract with tight spread was selected.")
        _delay()
        st.success("🏆 **OPPORTUNITY RANK:** Score: 75/100 (Threshold: 60) ✓ Opportunity qualifies.")
        _delay()
        
        # Risk engine
        st.markdown("### 🛡️ THE AI CAN RECOMMEND. THE RISK ENGINE DECIDES.")
        st.caption("LLM confidence does NOT override mathematical risk limits.")
        risk_cols = st.columns(2)
        risk_cols[0].success("✓ Risk per trade limits OK")
        risk_cols[1].success("✓ Sector exposure OK")
        risk_cols[0].success("✓ Directional exposure OK")
        risk_cols[1].success("✓ Position limits OK")
        _delay()
        
        symbol = "NVDA"
        contract = "NVDA240517C00900000"
        mock_positions = demo_portfolio.get_mock_alpaca_positions()
        try:
            qty, risk = calculate_final_position_size(
                symbol=symbol,
                direction="bullish",
                current_positions=mock_positions,
                equity=demo_portfolio.equity,
                ask_price=5.50
            )
            st.success(f"🟢 **TRADE APPROVED:** Risk approved. Simulated limit order for {qty} contracts submitted.")
            _delay()
            
            engine = DemoExecutionEngine(demo_portfolio)
            order = engine.submit_limit_order(contract, qty, 5.40, 5.50, "BUY")
            st.info("⚡ **EXECUTION:** Simulated limit order filled.")
            _delay()
            
            demo_portfolio.simulate_exit(contract, 6.20)
            st.info("🔄 **MONITOR:** Position monitored and profit target reached. Position closed.")
            _delay()
            
            st.success(f"💰 **RESULT:** SIMULATED P&L +${(6.20 - 5.45)*100*qty:,.2f}")
            st.caption("SIMULATED RESULT — NOT REAL TRADING PERFORMANCE")
            
            st.markdown("---")
            st.info("""
            **WHAT JUST HAPPENED?**
            
            AegisAlpha detected a market event. The Bull and Bear agents debated the opportunity. The Trader selected a direction. The opportunity scored 75/100. The deterministic risk engine approved the trade. A simulated limit order was executed. The position was monitored and exited.
            
            **FINAL RESULT:** 🟢 SIMULATED TRADE COMPLETED
            """)
        except RiskRejection as e:
            st.error(f"Trade unexpectedly rejected: {e}")

def _animate_low_quality():
    st.subheader("LIVE PIPELINE TRACE")
    trace_area = st.container()
    
    with trace_area:
        st.info("📡 **EVENT DETECTED:** TSLA earnings report released.")
        _delay()
        st.info("📊 **DATA GATHERED:** Pricing and macro conditions collected.")
        _delay()
        st.info("🐂 **BULL ANALYST:** Revenue beat, but margins tightening.")
        _delay()
        st.info("🐻 **BEAR ANALYST:** Price cuts are concerning.")
        _delay()
        st.info("⚖️ **TRADER:** Neutral/Bearish lean. Low confidence.")
        _delay()
        st.info("🎯 **OPTION SELECTION:** Spread is too wide, liquidity insufficient.")
        _delay()
        st.error("🏆 **OPPORTUNITY RANK:** Score: 45/100 (Threshold: 60) ❌ Opportunity fails.")
        _delay()
        
        st.warning("🟡 **NO TRADE**")
        
        st.markdown("---")
        st.warning("""
        **WHY DIDN'T AEGISALPHA TRADE?**
        
        ❌ Poor Opportunity Rank.
        
        AegisAlpha does not trade simply because an event occurred. The risk/reward was unattractive, and the system preserved capital by passing on a low-quality setup. This demonstrates that NO-TRADE is an intentional decision.
        """)

def _animate_risk_rejected():
    st.subheader("LIVE PIPELINE TRACE")
    trace_area = st.container()
    
    with trace_area:
        st.info("📡 **EVENT DETECTED:** AAPL product launch announcement detected.")
        _delay()
        st.info("📊 **DATA GATHERED:** Volatility and market context fetched.")
        _delay()
        st.info("🐂 **BULL ANALYST:** High conviction on new product cycle.")
        _delay()
        st.info("🐻 **BEAR ANALYST:** Disagrees on pricing power, but momentum is strong.")
        _delay()
        st.info("⚖️ **TRADER:** Both arguments considered. AI Confidence is extremely high (85%). Direction: Call.")
        _delay()
        st.info("🎯 **OPTION SELECTION:** Liquid contract selected.")
        _delay()
        st.success("🏆 **OPPORTUNITY RANK:** Score: 74/100 (Threshold: 60) ✓ Opportunity qualifies.")
        _delay()
        
        # Risk engine
        st.markdown("### 🛡️ THE AI CAN RECOMMEND. THE RISK ENGINE DECIDES.")
        st.caption("LLM confidence does NOT override mathematical risk limits.")
        risk_cols = st.columns(2)
        risk_cols[0].success("✓ AI Confidence: 85%")
        risk_cols[1].success("✓ Rank Score: 74/100")
        risk_cols[0].error("❌ Sector exposure limit exceeded")
        
        _delay()
        st.error("🔴 **TRADE REJECTED**")
        st.markdown("## THE AI WANTED TO TRADE. THE RISK ENGINE SAID NO.")
        st.caption("The AI cannot override deterministic portfolio constraints.")
        
        st.markdown("---")
        st.warning("""
        **WHY DIDN'T AEGISALPHA TRADE?**
        
        ❌ Sector exposure limit exceeded.
        
        The opportunity itself was strong, but portfolio-level risk made the trade unacceptable. This visually demonstrates AegisAlpha's core philosophy: mathematical safety ALWAYS overrides LLM conviction.
        """)
