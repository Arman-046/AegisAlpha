import streamlit as st
import pandas as pd
import time
from state.demo_portfolio import demo_portfolio
from execution.engine import DemoExecutionEngine
from risk.hard_limits import calculate_final_position_size, RiskRejection
from config.settings import settings

def render_demo_dashboard():
    # Inject CSS for demo if not already present from main dashboard
    st.markdown("""
    <style>
        .demo-card {
            background-color: #0f172a;
            border: 1px solid #1e293b;
            border-radius: 8px;
            padding: 20px;
            margin-bottom: 16px;
        }
        .demo-step {
            display: flex;
            align-items: center;
            margin-bottom: 12px;
            padding: 12px;
            background-color: #111827;
            border-radius: 8px;
            border-left: 3px solid #3b82f6;
        }
        .demo-step.completed { border-left-color: #10b981; }
        .demo-step.failed { border-left-color: #ef4444; }
        .demo-step-icon {
            font-size: 1.5rem;
            margin-right: 16px;
            width: 32px;
            text-align: center;
        }
        .demo-step-content h4 { margin: 0 0 4px 0; font-size: 1rem; color: #f8fafc; }
        .demo-step-content p { margin: 0; font-size: 0.85rem; color: #94a3b8; }
        
        .simulated-badge {
            display: inline-block;
            background-color: rgba(59, 130, 246, 0.2);
            color: #3b82f6;
            border: 1px solid #3b82f6;
            padding: 4px 12px;
            border-radius: 12px;
            font-size: 0.75rem;
            font-weight: bold;
            margin-bottom: 16px;
        }
    </style>
    """, unsafe_allow_html=True)

    # Hero Section
    st.markdown('<div class="premium-card" style="text-align: center; padding: 40px 20px;">', unsafe_allow_html=True)
    st.markdown("<h2 style='letter-spacing: 2px; margin-bottom: 8px;'>🛡️ AEGISALPHA</h2>", unsafe_allow_html=True)
    st.markdown("<h4 style='color: #94a3b8; font-weight: 400;'>AUTONOMOUS OPTIONS TRADING AGENT</h4>", unsafe_allow_html=True)
    
    st.markdown("""
    <div style="margin-top: 24px; margin-bottom: 16px;">
        <span style="background-color: rgba(59,130,246,0.2); color: #60a5fa; padding: 8px 16px; border-radius: 20px; font-weight: bold; font-size: 0.9rem; border: 1px solid #3b82f6;">
            🔵 DEMO MODE — SIMULATION ONLY
        </span>
    </div>
    """, unsafe_allow_html=True)
    st.markdown("<p style='color: #cbd5e1; font-size: 1.1rem;'>No real orders • No API keys required • Safe simulation</p>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

    # Main CTA
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        main_start = st.button("▶ START AEGISALPHA DEMO", type="primary", use_container_width=True)
        st.markdown("<p style='text-align: center; font-size: 0.85em; color: #94a3b8; margin-top: 8px;'>Watch the AI go from market event → decision → risk check → execution.</p>", unsafe_allow_html=True)
        
    st.markdown("<p style='text-align: center; font-size: 0.9em; color: #64748b; margin-top: 32px;'>Explore individual simulated scenarios:</p>", unsafe_allow_html=True)
    scen_col1, scen_col2, scen_col3, scen_col4 = st.columns(4)
    
    with scen_col1:
        start_high = st.button("🟢 Successful Trade", use_container_width=True)
    with scen_col2:
        start_low = st.button("🟡 Low-Quality Opportunity", use_container_width=True)
    with scen_col3:
        start_risk = st.button("🔴 Risk Rejection", use_container_width=True)
    with scen_col4:
        if st.button("↻ Reset Simulation", use_container_width=True):
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
    st.markdown("### DEMO PORTFOLIO")
    st.markdown("<div class='simulated-badge'>SIMULATED — NOT REAL TRADING PERFORMANCE</div>", unsafe_allow_html=True)
    
    colA, colB, colC = st.columns(3)
    colA.markdown(f"<div class='demo-card'><div class='metric-label'>Starting Equity</div><div class='metric-value'>${demo_portfolio.start_equity:,.2f}</div></div>", unsafe_allow_html=True)
    colB.markdown(f"<div class='demo-card'><div class='metric-label'>Simulated Cash</div><div class='metric-value'>${demo_portfolio.cash:,.2f}</div></div>", unsafe_allow_html=True)
    
    pnl = demo_portfolio.realized_pl + demo_portfolio.unrealized_pl
    pnl_pct = (pnl / demo_portfolio.start_equity) * 100
    pnl_color = "#10b981" if pnl >= 0 else "#ef4444"
    colC.markdown(f"<div class='demo-card'><div class='metric-label'>Simulated P&L</div><div class='metric-value' style='color: {pnl_color};'>${pnl:,.2f}</div><div style='font-size: 0.85rem; color: {pnl_color};'>{pnl_pct:,.2f}%</div></div>", unsafe_allow_html=True)
    
    if demo_portfolio.positions:
        st.markdown("<h4 style='color: #cbd5e1; margin-top: 20px;'>SIMULATED OPEN POSITIONS</h4>", unsafe_allow_html=True)
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
        st.info("No open positions in Demo Portfolio.")

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
    css_class = "completed" if completed else ("failed" if failed else "")
    st.markdown(f"""
    <div class="demo-step {css_class}">
        <div class="demo-step-icon">{icon}</div>
        <div class="demo-step-content">
            <h4>{title}</h4>
            <p>{desc}</p>
        </div>
    </div>
    """, unsafe_allow_html=True)
    if not (completed or failed):
        _delay()

def _animate_high_quality():
    st.markdown("### LIVE PIPELINE TRACE")
    st.markdown("<div class='simulated-badge'>SIMULATED EXECUTION</div>", unsafe_allow_html=True)
    
    placeholder = st.empty()
    with placeholder.container():
        draw_step("📡", "EVENT DETECTED", "An unusual market movement was detected. AegisAlpha investigates.", completed=False)
    
    with placeholder.container():
        draw_step("📡", "EVENT DETECTED", "An unusual market movement was detected. AegisAlpha investigates.")
        draw_step("📊", "DATA GATHERED", "Price history, volatility, volume and market information evaluated.", completed=False)
        
    with placeholder.container():
        draw_step("📡", "EVENT DETECTED", "An unusual market movement was detected. AegisAlpha investigates.")
        draw_step("📊", "DATA GATHERED", "Price history, volatility, volume and market information evaluated.")
        draw_step("🐂", "BULL ANALYST", "Builds the strongest case for the trade.", completed=False)
        
    with placeholder.container():
        draw_step("📡", "EVENT DETECTED", "An unusual market movement was detected. AegisAlpha investigates.")
        draw_step("📊", "DATA GATHERED", "Price history, volatility, volume and market information evaluated.")
        draw_step("🐂", "BULL ANALYST", "Builds the strongest case for the trade.")
        draw_step("🐻", "BEAR ANALYST", "Builds the strongest case against the trade.", completed=False)
        
    with placeholder.container():
        draw_step("📡", "EVENT DETECTED", "An unusual market movement was detected. AegisAlpha investigates.")
        draw_step("📊", "DATA GATHERED", "Price history, volatility, volume and market information evaluated.")
        draw_step("🐂", "BULL ANALYST", "Builds the strongest case for the trade.")
        draw_step("🐻", "BEAR ANALYST", "Builds the strongest case against the trade.")
        draw_step("⚖️", "TRADER", "Compares both perspectives and chooses a direction.", completed=False)
        
    with placeholder.container():
        draw_step("📡", "EVENT DETECTED", "An unusual market movement was detected. AegisAlpha investigates.")
        draw_step("📊", "DATA GATHERED", "Price history, volatility, volume and market information evaluated.")
        draw_step("🐂", "BULL ANALYST", "Builds the strongest case for the trade.")
        draw_step("🐻", "BEAR ANALYST", "Builds the strongest case against the trade.")
        draw_step("⚖️", "TRADER", "Compares both perspectives and chooses a direction.")
        draw_step("🎯", "OPTION SELECTION", "Filters contracts for quality, liquidity, DTE and spread.", completed=False)
        
    with placeholder.container():
        draw_step("📡", "EVENT DETECTED", "An unusual market movement was detected. AegisAlpha investigates.")
        draw_step("📊", "DATA GATHERED", "Price history, volatility, volume and market information evaluated.")
        draw_step("🐂", "BULL ANALYST", "Builds the strongest case for the trade.")
        draw_step("🐻", "BEAR ANALYST", "Builds the strongest case against the trade.")
        draw_step("⚖️", "TRADER", "Compares both perspectives and chooses a direction.")
        draw_step("🎯", "OPTION SELECTION", "Filters contracts for quality, liquidity, DTE and spread.")
        draw_step("🏆", "OPPORTUNITY RANK", f"Scores the opportunity against the configured quality threshold. Score: 75/100 (Threshold: {settings.MIN_RANK_SCORE_THRESHOLD})", completed=False)
        
    # Risk engine
    st.markdown("""
    <div class="demo-card" style="margin-top: 20px;">
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
        
        st.markdown(f"""
        <div style="background-color: #064e3b; border-left: 6px solid #10b981; padding: 25px; border-radius: 8px; margin: 30px 0;">
            <h2 style="color: #10b981; margin-top: 0; margin-bottom: 8px;">🟢 SIMULATED TRADE COMPLETED</h2>
            <div style="font-size: 1.5rem; color: #f8fafc; font-weight: bold;">P&L +${(6.20 - 5.45)*100*qty:,.2f}</div>
            <p style="color: #6ee7b7; font-size: 0.9rem; margin-top: 8px;">SIMULATED RESULT — NOT REAL TRADING PERFORMANCE</p>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown("---")
        st.info("""
        **WHAT JUST HAPPENED?**
        
        AegisAlpha detected an event, evaluated opposing Bull and Bear arguments, selected an option, passed the opportunity threshold, passed deterministic risk checks, and simulated execution.
        """)
    except RiskRejection as e:
        st.error(f"Trade unexpectedly rejected: {e}")

def _animate_low_quality():
    st.markdown("### LIVE PIPELINE TRACE")
    st.markdown("<div class='simulated-badge'>SIMULATED EXECUTION</div>", unsafe_allow_html=True)
    
    draw_step("📡", "EVENT DETECTED", "An unusual market movement was detected. AegisAlpha investigates.")
    draw_step("📊", "DATA GATHERED", "Price history, volatility, volume and market information evaluated.")
    draw_step("🐂", "BULL ANALYST", "Builds the strongest case for the trade.")
    draw_step("🐻", "BEAR ANALYST", "Builds the strongest case against the trade.")
    draw_step("⚖️", "TRADER", "Compares both perspectives and chooses a direction.")
    draw_step("🎯", "OPTION SELECTION", "Filters contracts for quality, liquidity, DTE and spread. Spread is too wide, liquidity insufficient.")
    draw_step("🏆", "OPPORTUNITY RANK", f"Scores the opportunity against the configured quality threshold. Score: 45/100 (Minimum: {settings.MIN_RANK_SCORE_THRESHOLD})", completed=False, failed=True)
    
    st.markdown("""
    <div style="background-color: #451a03; border-left: 6px solid #f59e0b; padding: 25px; border-radius: 8px; margin: 30px 0;">
        <h2 style="color: #f59e0b; margin-top: 0; margin-bottom: 8px;">🟡 NO TRADE</h2>
        <p style="color: #fcd34d; font-size: 1.1rem; margin-top: 8px;">Opportunity failed to meet rank threshold.</p>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("---")
    st.info("""
        **WHAT JUST HAPPENED?**
        
        AegisAlpha does not trade simply because an opportunity exists. The risk/reward was unattractive, and the system preserved capital by passing on a low-quality setup.
    """)

def _animate_risk_rejected():
    st.markdown("### LIVE PIPELINE TRACE")
    st.markdown("<div class='simulated-badge'>SIMULATED EXECUTION</div>", unsafe_allow_html=True)
    
    draw_step("📡", "EVENT DETECTED", "An unusual market movement was detected. AegisAlpha investigates.")
    draw_step("📊", "DATA GATHERED", "Price history, volatility, volume and market information evaluated.")
    draw_step("🐂", "BULL ANALYST", "Builds the strongest case for the trade.")
    draw_step("🐻", "BEAR ANALYST", "Builds the strongest case against the trade.")
    draw_step("⚖️", "TRADER", "Compares both perspectives and chooses a direction. AI CONFIDENCE: 85% ✓")
    draw_step("🎯", "OPTION SELECTION", "Filters contracts for quality, liquidity, DTE and spread.")
    draw_step("🏆", "OPPORTUNITY RANK", f"Scores the opportunity against the configured quality threshold. RANK SCORE: 74/100 ✓ (Minimum: {settings.MIN_RANK_SCORE_THRESHOLD})")
    
    # Risk engine
    st.markdown("""
    <div class="demo-card" style="margin-top: 20px;">
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
    <div style="background-color: #450a0a; border-left: 6px solid #ef4444; padding: 25px; border-radius: 8px; margin: 30px 0;">
        <h2 style="color: #ef4444; margin-top: 0; margin-bottom: 12px; font-size: 2em; letter-spacing: 2px;">🔴 TRADE REJECTED</h2>
        <h3 style="color: #f8fafc; font-size: 1.5em; margin: 0 0 8px 0;">THE AI WANTED TO TRADE. THE RISK ENGINE SAID NO.</h3>
        <p style="color: #fca5a5; font-size: 1.1em; margin-bottom: 0;">Deterministic portfolio constraints cannot be overridden by the AI.</p>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("---")
    st.error("""
        **WHAT JUST HAPPENED?**
        
        AegisAlpha identified an opportunity, but the deterministic risk engine prevented execution because a hard constraint failed.
    """)
