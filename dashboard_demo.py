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
    st.caption("SIMULATED — NOT REAL TRADING PERFORMANCE")
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

def draw_step(icon, title, desc, completed=True, failed=False):
    if failed:
        color = "#ef4444"
        symbol = "❌"
    else:
        color = "#10b981" if completed else "#64748b"
        symbol = "✓" if completed else "●"
        
    st.markdown(f"""
    <div style="border-left: 3px solid {color}; padding-left: 15px; margin-bottom: 15px;">
        <h4 style="margin: 0; color: {color}; font-size: 1.1em;">{symbol} {icon} {title}</h4>
        <p style="margin: 5px 0 0 0; color: #cbd5e1; font-size: 0.95em;">{desc}</p>
    </div>
    """, unsafe_allow_html=True)
    if not (completed or failed):
        _delay()

def _animate_high_quality():
    st.subheader("LIVE PIPELINE TRACE")
    trace_area = st.container()
    
    with trace_area:
        draw_step("📡", "EVENT DETECTED", "An unusual market movement was detected. AegisAlpha investigates before deciding whether to trade.")
        draw_step("📊", "DATA GATHERED", "Price history, volatility, volume and market information are evaluated.")
        draw_step("🐂", "BULL ANALYST", "Builds the strongest case for the trade.")
        draw_step("🐻", "BEAR ANALYST", "Builds the strongest case against the trade.")
        draw_step("⚖️", "TRADER", "Compares both perspectives and chooses a direction.")
        draw_step("🎯", "OPTION SELECTION", "Filters contracts for quality, liquidity, DTE and spread.")
        draw_step("🏆", "OPPORTUNITY RANK", f"Scores the opportunity against the configured quality threshold. Score: 75/100 (Threshold: {settings.MIN_RANK_SCORE_THRESHOLD})")
        
        # Risk engine
        st.markdown("""
        <div style="background-color: #0f172a; padding: 20px; border-radius: 8px; border: 1px solid #1e293b; margin: 20px 0;">
            <h3 style="margin-top: 0; color: #f8fafc;">🛡️ AI PROPOSES. RISK DECIDES.</h3>
            <p style="color: #94a3b8; font-size: 0.9em; margin-bottom: 20px;">Deterministic portfolio constraints cannot be overridden by the AI.</p>
        """, unsafe_allow_html=True)
        draw_step("🛡️", "RISK ENGINE", "Deterministic portfolio rules decide whether the trade is allowed.")
        risk_cols = st.columns(2)
        risk_cols[0].success(f"✓ Max trade risk: {settings.MAX_RISK_PERCENT*100}% OK")
        risk_cols[1].success(f"✓ Sector exposure: {settings.MAX_SECTOR_EXPOSURE_PERCENT*100}% OK")
        risk_cols[0].success(f"✓ Directional exposure: {settings.MAX_DIRECTIONAL_EXPOSURE_PERCENT*100}% OK")
        risk_cols[1].success(f"✓ Min rank: {settings.MIN_RANK_SCORE_THRESHOLD} OK")
        st.markdown("</div>", unsafe_allow_html=True)
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
            draw_step("⚡", "EXECUTION", "Only an approved opportunity can reach execution. Simulated limit order submitted.")
            
            engine = DemoExecutionEngine(demo_portfolio)
            order = engine.submit_limit_order(contract, qty, 5.40, 5.50, "BUY")
            
            demo_portfolio.simulate_exit(contract, 6.20)
            draw_step("🔄", "MONITOR", "Approved positions are monitored according to the existing strategy. Profit target reached, position closed.")
            
            st.success(f"💰 **SIMULATED RESULT:** P&L +${(6.20 - 5.45)*100*qty:,.2f}")
            st.caption("SIMULATED RESULT — NOT REAL TRADING PERFORMANCE")
            
            st.markdown("---")
            st.info("""
            **WHAT JUST HAPPENED?**
            
            AegisAlpha detected an event, evaluated opposing Bull and Bear arguments, selected an option, passed the opportunity threshold, passed deterministic risk checks, and simulated execution.
            
            **FINAL RESULT:** 🟢 SIMULATED TRADE COMPLETED
            """)
        except RiskRejection as e:
            st.error(f"Trade unexpectedly rejected: {e}")

def _animate_low_quality():
    st.subheader("LIVE PIPELINE TRACE")
    trace_area = st.container()
    
    with trace_area:
        draw_step("📡", "EVENT DETECTED", "An unusual market movement was detected. AegisAlpha investigates before deciding whether to trade.")
        draw_step("📊", "DATA GATHERED", "Price history, volatility, volume and market information are evaluated.")
        draw_step("🐂", "BULL ANALYST", "Builds the strongest case for the trade.")
        draw_step("🐻", "BEAR ANALYST", "Builds the strongest case against the trade.")
        draw_step("⚖️", "TRADER", "Compares both perspectives and chooses a direction.")
        draw_step("🎯", "OPTION SELECTION", "Filters contracts for quality, liquidity, DTE and spread. Spread is too wide, liquidity insufficient.")
        draw_step("🏆", "OPPORTUNITY RANK", f"Scores the opportunity against the configured quality threshold. Score: 45/100 (Minimum: {settings.MIN_RANK_SCORE_THRESHOLD})", completed=False, failed=True)
        
        st.warning("🟡 **NO TRADE**")
        
        st.markdown("---")
        st.warning("""
            **WHAT JUST HAPPENED?**
            
            AegisAlpha does not trade simply because an opportunity exists. The risk/reward was unattractive, and the system preserved capital by passing on a low-quality setup.
            
            **FINAL RESULT:** 🟡 NO TRADE
        """)

def _animate_risk_rejected():
    st.subheader("LIVE PIPELINE TRACE")
    trace_area = st.container()
    
    with trace_area:
        draw_step("📡", "EVENT DETECTED", "An unusual market movement was detected. AegisAlpha investigates before deciding whether to trade.")
        draw_step("📊", "DATA GATHERED", "Price history, volatility, volume and market information are evaluated.")
        draw_step("🐂", "BULL ANALYST", "Builds the strongest case for the trade.")
        draw_step("🐻", "BEAR ANALYST", "Builds the strongest case against the trade.")
        draw_step("⚖️", "TRADER", "Compares both perspectives and chooses a direction. AI CONFIDENCE: 85% ✓")
        draw_step("🎯", "OPTION SELECTION", "Filters contracts for quality, liquidity, DTE and spread.")
        draw_step("🏆", "OPPORTUNITY RANK", f"Scores the opportunity against the configured quality threshold. RANK SCORE: 74/100 ✓ (Minimum: {settings.MIN_RANK_SCORE_THRESHOLD})")
        
        # Risk engine
        st.markdown("""
        <div style="background-color: #0f172a; padding: 20px; border-radius: 8px; border: 1px solid #1e293b; margin: 20px 0;">
            <h3 style="margin-top: 0; color: #f8fafc;">🛡️ AI PROPOSES. RISK DECIDES.</h3>
            <p style="color: #94a3b8; font-size: 0.9em; margin-bottom: 20px;">Deterministic portfolio constraints cannot be overridden by the AI.</p>
        """, unsafe_allow_html=True)
        draw_step("🛡️", "RISK ENGINE", "Deterministic portfolio rules decide whether the trade is allowed.", completed=False, failed=True)
        
        risk_cols = st.columns(2)
        risk_cols[0].success("✓ AI CONFIDENCE: 85%")
        risk_cols[1].success("✓ RANK SCORE: 74/100")
        risk_cols[0].error(f"❌ HARD LIMIT FAILED: Sector exposure limit ({settings.MAX_SECTOR_EXPOSURE_PERCENT*100}%) exceeded")
        
        st.markdown("</div>", unsafe_allow_html=True)
        
        _delay()
        
        st.markdown("""
        <div style="background-color: #450a0a; border-left: 6px solid #ef4444; padding: 25px; border-radius: 8px; text-align: center; margin: 30px 0;">
            <h2 style="color: #ef4444; margin-top: 0; font-size: 2em; letter-spacing: 2px;">🔴 TRADE REJECTED</h2>
            <h3 style="color: #f8fafc; font-size: 1.5em; margin: 15px 0;">THE AI WANTED TO TRADE.<br>THE RISK ENGINE SAID NO.</h3>
            <p style="color: #fca5a5; font-size: 1.1em; margin-bottom: 0;">Deterministic portfolio constraints cannot be overridden by the AI.</p>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown("---")
        st.error("""
            **WHAT JUST HAPPENED?**
            
            AegisAlpha identified an opportunity, but the deterministic risk engine prevented execution because a hard constraint failed.
            
            **FINAL RESULT:** 🔴 TRADE REJECTED
        """)
