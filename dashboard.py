import streamlit as st
import pandas as pd
import json
import os
from datetime import datetime
from config.settings import settings
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import GetOrdersRequest
from alpaca.trading.enums import OrderSide, QueryOrderStatus

# Must be the first Streamlit command
st.set_page_config(
    page_title="AegisAlpha | Autonomous Agent",
    page_icon="aegisalpha_logo_v2.png",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Premium CSS Injection
st.markdown("""
<style>
    /* Global Background and Text */
    .stApp {
        background-color: #0b0f19;
        color: #f8fafc;
        font-family: 'Inter', 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
    }
    
    /* Hide some default Streamlit elements */
    header {visibility: hidden;}
    footer {visibility: hidden;}
    
    /* Headers */
    h1, h2, h3, h4, h5, h6 {
        color: #f8fafc;
        font-weight: 600;
        letter-spacing: -0.02em;
    }
    
    /* Cards */
    .premium-card {
        background: linear-gradient(145deg, #111827, #0f172a);
        border: 1px solid #1e293b;
        border-radius: 12px;
        padding: 24px;
        margin-bottom: 24px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
        transition: transform 0.2s ease, box-shadow 0.2s ease;
    }
    .premium-card:hover {
        box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.2), 0 4px 6px -2px rgba(0, 0, 0, 0.1);
    }
    
    /* Specific Status Colors */
    .status-green { color: #10b981; }
    .status-red { color: #ef4444; }
    .status-yellow { color: #f59e0b; }
    .status-blue { color: #3b82f6; }
    .status-gray { color: #94a3b8; }
    
    /* Badges */
    .badge {
        display: inline-block;
        padding: 4px 12px;
        border-radius: 12px;
        font-size: 0.75rem;
        font-weight: 600;
        letter-spacing: 0.05em;
        text-transform: uppercase;
    }
    .badge-live { background-color: rgba(16, 185, 129, 0.2); color: #10b981; border: 1px solid #10b981; }
    .badge-demo { background-color: rgba(59, 130, 246, 0.2); color: #3b82f6; border: 1px solid #3b82f6; }
    
    /* Watchlist tags */
    .tag {
        background-color: #1e293b;
        color: #f8fafc;
        padding: 4px 12px;
        border-radius: 6px;
        margin-right: 8px;
        margin-bottom: 8px;
        font-size: 0.85rem;
        border: 1px solid #334155;
        display: inline-block;
    }
    
    /* Metrics override */
    [data-testid="stMetricValue"] { color: #f8fafc; font-weight: 600; }
    
    /* Tables override */
    .stDataFrame { background-color: #111827; border-radius: 8px; }
    
    /* Data containers */
    .metric-value { font-size: 2rem; font-weight: 700; color: #f8fafc; margin-bottom: 4px; }
    .metric-label { font-size: 0.875rem; color: #94a3b8; text-transform: uppercase; letter-spacing: 0.05em; }
</style>
""", unsafe_allow_html=True)

# Initialize Alpaca Client
@st.cache_resource
def get_trading_client():
    return TradingClient(settings.APCA_API_KEY_ID, settings.APCA_API_SECRET_KEY, paper=True)

trading_client = get_trading_client()

# Data loading functions
def load_system_status():
    status_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "state", "system_status.json")
    if os.path.exists(status_file):
        try:
            with open(status_file, "r") as f:
                return json.load(f)
        except:
            return None
    return None

def load_memory():
    memory_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "state", "memory.json")
    if os.path.exists(memory_file):
        try:
            with open(memory_file, "r") as f:
                return json.load(f)
        except:
            return {"history": []}
    return {"history": []}

@st.fragment(run_every="60s")
def dashboard_content():
    # Fetch Data
    try:
        account = trading_client.get_account()
        positions = trading_client.get_all_positions()
        
        req = GetOrdersRequest(status=QueryOrderStatus.ALL, limit=10)
        orders = trading_client.get_orders(req)
        
        status = load_system_status()
        memory = load_memory()
    except Exception as e:
        st.error(f"Error fetching data from Alpaca API: {e}")
        return

    # Extract state variables safely
    agent_running = status and status.get("status") == "RUNNING"
    market_open = status.get("market_open", False) if status else False
    last_hb = status.get("last_heartbeat", "Not yet recorded") if status else "Not yet recorded"
    if last_hb != "Not yet recorded":
        try:
            last_hb = last_hb.split(".")[0].replace("T", " ")
        except:
            pass
    decisions = memory.get("history", [])
    
    # ----------------------------------------------------------------------
    # 1. HERO / HEADER
    # ----------------------------------------------------------------------
    st.markdown('<div class="premium-card" style="padding: 16px 24px; display: flex; align-items: center; justify-content: space-between;">', unsafe_allow_html=True)
    
    col_logo, col_title, col_badges = st.columns([1, 6, 3])
    with col_logo:
        st.image("aegisalpha_logo_v2.png", width=65)
    with col_title:
        st.markdown("<h2 style='margin:0; padding:0; letter-spacing: 2px;'>AEGISALPHA</h2>", unsafe_allow_html=True)
        st.markdown("<p style='margin:0; color:#94a3b8; font-size: 0.9em; letter-spacing: 1px;'>AUTONOMOUS OPTIONS TRADING AGENT</p>", unsafe_allow_html=True)
        st.markdown("<p style='margin:0; color:#cbd5e1; font-size: 0.8em; margin-top: 4px;'>AI Proposes. Data Informs. Risk Governs. Code Executes.</p>", unsafe_allow_html=True)
    with col_badges:
        st.markdown("""
        <div style="text-align: right;">
            <span class="badge badge-live">🟢 LIVE PAPER</span>
            <div style="margin-top: 8px; font-size: 0.75rem; color: #94a3b8;">REAL ALPACA PAPER ACCOUNT</div>
            <div style="margin-top: 2px; font-size: 0.75rem; color: #94a3b8;">Last updated: """ + datetime.now().strftime('%H:%M:%S') + """</div>
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown('</div>', unsafe_allow_html=True)

    # ----------------------------------------------------------------------
    # 2. LIVE AGENT ACTIVITY
    # ----------------------------------------------------------------------
    st.markdown("### LIVE AGENT ACTIVITY")
    
    activity_col1, activity_col2, activity_col3, activity_col4 = st.columns(4)
    with activity_col1:
        agent_color = "#10b981" if agent_running else "#ef4444"
        agent_text = "RUNNING" if agent_running else "STOPPED"
        st.markdown(f"""
        <div class="premium-card" style="padding: 16px; text-align: center;">
            <div class="metric-label">Agent Status</div>
            <div class="metric-value" style="color: {agent_color}; font-size: 1.5rem;">{agent_text}</div>
            <div style="font-size: 0.8rem; color: #94a3b8; margin-top: 8px;">Heartbeat: {last_hb}</div>
        </div>
        """, unsafe_allow_html=True)
    with activity_col2:
        market_color = "#10b981" if market_open else "#f59e0b"
        market_text = "OPEN" if market_open else "CLOSED"
        st.markdown(f"""
        <div class="premium-card" style="padding: 16px; text-align: center;">
            <div class="metric-label">US Market</div>
            <div class="metric-value" style="color: {market_color}; font-size: 1.5rem;">{market_text}</div>
            <div style="font-size: 0.8rem; color: #94a3b8; margin-top: 8px;">Alpaca: CONNECTED</div>
        </div>
        """, unsafe_allow_html=True)
    with activity_col3:
        st.markdown(f"""
        <div class="premium-card" style="padding: 16px; text-align: center;">
            <div class="metric-label">Monitoring Mode</div>
            <div class="metric-value" style="font-size: 1.2rem; color: #60a5fa; margin-top: 6px;">EVENT-DRIVEN</div>
            <div style="font-size: 0.8rem; color: #94a3b8; margin-top: 8px;">Waiting for next trigger</div>
        </div>
        """, unsafe_allow_html=True)
    with activity_col4:
        evals = len(decisions)
        st.markdown(f"""
        <div class="premium-card" style="padding: 16px; text-align: center;">
            <div class="metric-label">Session Evaluations</div>
            <div class="metric-value" style="font-size: 1.5rem;">{evals}</div>
            <div style="font-size: 0.8rem; color: #94a3b8; margin-top: 8px;">Opportunities Evaluated</div>
        </div>
        """, unsafe_allow_html=True)

    # ----------------------------------------------------------------------
    # 3. WHAT IS HAPPENING NOW? (STATE INTELLIGENCE)
    # ----------------------------------------------------------------------
    st.markdown("### CURRENT INTELLIGENCE")
    
    current_col1, current_col2 = st.columns([2, 1])
    
    with current_col1:
        # Determine the visual state
        has_trade_activity = len(positions) > 0 or len(orders) > 0
        
        if not market_open:
            st.markdown("""
            <div class="premium-card" style="border-left: 4px solid #3b82f6;">
                <h3 style="margin-top:0; color: #3b82f6; display: flex; align-items: center;"><span style="font-size: 1.5rem; margin-right: 12px;">🌙</span> MARKET CLOSED</h3>
                <p style="color: #e2e8f0; font-size: 1.1em; margin-bottom: 8px;">AegisAlpha is connected and healthy.</p>
                <p style="color: #94a3b8; margin: 0;">Autonomous trading is paused because the U.S. market is currently closed. Agent will resume event-driven evaluation when the market opens.</p>
            </div>
            """, unsafe_allow_html=True)
        elif has_trade_activity:
            st.markdown("""
            <div class="premium-card" style="border-left: 4px solid #10b981;">
                <h3 style="margin-top:0; color: #10b981; display: flex; align-items: center;"><span style="font-size: 1.5rem; margin-right: 12px;">📈</span> LIVE TRADE ACTIVE</h3>
                <p style="color: #e2e8f0; font-size: 1.1em; margin-bottom: 8px;">Real Alpaca position is currently open or recently traded.</p>
                <p style="color: #94a3b8; margin: 0;">AegisAlpha successfully passed the deterministic risk pipeline and executed real orders in this session.</p>
            </div>
            """, unsafe_allow_html=True)
        else:
            if not decisions:
                st.markdown("""
                <div class="premium-card" style="border-left: 4px solid #10b981;">
                    <h3 style="margin-top:0; color: #10b981; display: flex; align-items: center;"><span style="font-size: 1.5rem; margin-right: 12px;">🟢</span> MONITORING</h3>
                    <p style="color: #e2e8f0; font-size: 1.1em; margin-bottom: 8px;">Waiting for the next qualifying event.</p>
                    <p style="color: #94a3b8; margin: 0;">AegisAlpha is actively monitoring configured market/news events. No evaluations have been recorded for this session yet.</p>
                </div>
                """, unsafe_allow_html=True)
            else:
                last_decision = decisions[-1]
                action = last_decision.get("action", "")
                reason = last_decision.get("reason", "")
                sym = last_decision.get("symbol", "UNKNOWN")
                
                if action == "VETOED" and "risk" in reason.lower():
                    st.markdown(f"""
                    <div class="premium-card" style="border-left: 4px solid #ef4444;">
                        <h3 style="margin-top:0; color: #ef4444; display: flex; align-items: center;"><span style="font-size: 1.5rem; margin-right: 12px;">🔴</span> RISK ENGINE REJECTED</h3>
                        <p style="color: #e2e8f0; font-size: 1.1em; margin-bottom: 5px;"><strong>AI Wanted to Trade:</strong> {sym} ({last_decision.get('direction', 'unknown')})</p>
                        <p style="color: #f8fafc; font-size: 1.1em; margin-bottom: 12px; border-left: 2px solid #ef4444; padding-left: 10px;">{reason}</p>
                        <p style="color: #94a3b8; font-size: 0.9em; margin: 0;">Deterministic portfolio constraints cannot be overridden by the AI. The system has returned to monitoring.</p>
                    </div>
                    """, unsafe_allow_html=True)
                else:
                    st.markdown(f"""
                    <div class="premium-card" style="border-left: 4px solid #f59e0b;">
                        <h3 style="margin-top:0; color: #f59e0b; display: flex; align-items: center;"><span style="font-size: 1.5rem; margin-right: 12px;">🟡</span> OPPORTUNITY REJECTED</h3>
                        <p style="color: #e2e8f0; font-size: 1.1em; margin-bottom: 5px;"><strong>Evaluated:</strong> {sym} ({last_decision.get('direction', 'unknown')})</p>
                        <p style="color: #f8fafc; font-size: 1.1em; margin-bottom: 12px; border-left: 2px solid #f59e0b; padding-left: 10px;">{reason}</p>
                        <p style="color: #94a3b8; font-size: 0.9em; margin: 0;">AegisAlpha does not trade simply to create activity. The system has returned to monitoring.</p>
                    </div>
                    """, unsafe_allow_html=True)

    with current_col2:
        st.markdown("""
        <div class="premium-card" style="height: 100%;">
            <div class="metric-label" style="margin-bottom: 12px;">📡 Configured Watchlist</div>
        """, unsafe_allow_html=True)
        
        tags_html = "".join([f'<span class="tag">{sym}</span>' for sym in settings.WATCHLIST])
        st.markdown(tags_html, unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

    # ----------------------------------------------------------------------
    # 4. TODAY'S ACTIVITY (TIMELINE)
    # ----------------------------------------------------------------------
    st.markdown("### 🕒 TODAY'S ACTIVITY")
    if not decisions:
        st.markdown("<p style='color: #94a3b8; font-style: italic;'>No recorded evaluations for this session yet.</p>", unsafe_allow_html=True)
    else:
        # Show last 5 decisions as a clean vertical feed
        for d in reversed(decisions[-5:]):
            ts = d.get("timestamp", "Unknown Time").replace("T", " ")[:19]
            sym = d.get("symbol", "Unknown")
            action = d.get("action", "")
            reason = d.get("reason", "")
            conf = d.get("confidence", 0)
            
            outcome_color = "#10b981" if action == "EXECUTED" else ("#ef4444" if "risk" in reason.lower() else "#f59e0b")
            outcome_text = "TRADE EXECUTED" if action == "EXECUTED" else ("RISK REJECTED" if "risk" in reason.lower() else "NO TRADE")
            
            st.markdown(f"""
            <div style="display: flex; margin-bottom: 12px; padding: 12px; background-color: #111827; border-radius: 8px; border-left: 3px solid {outcome_color};">
                <div style="min-width: 150px; color: #94a3b8; font-size: 0.9em; padding-top: 2px;">{ts}</div>
                <div style="flex-grow: 1;">
                    <div style="font-weight: 600; color: #f8fafc; margin-bottom: 4px;">{sym} <span style="font-size: 0.8em; color: #cbd5e1; font-weight: normal;">• {d.get('direction', '').title()}</span></div>
                    <div style="color: #cbd5e1; font-size: 0.9em;">Result: <span style="color: {outcome_color}; font-weight: 500;">{outcome_text}</span></div>
                    <div style="color: #94a3b8; font-size: 0.85em; margin-top: 4px;">Reason: {reason} (Confidence: {conf:.2f})</div>
                </div>
            </div>
            """, unsafe_allow_html=True)

    st.markdown("---")

    # ----------------------------------------------------------------------
    # 5. LIVE PERFORMANCE & POSITIONS
    # ----------------------------------------------------------------------
    st.markdown("### LIVE PERFORMANCE")
    
    equity = float(account.equity)
    cash = float(account.cash)
    buying_power = float(account.buying_power)
    daily_pnl = float(account.equity) - float(account.last_equity)
    
    perf_col1, perf_col2, perf_col3, perf_col4 = st.columns(4)
    with perf_col1:
        st.markdown(f"<div class='premium-card'><div class='metric-label'>Current Equity</div><div class='metric-value'>${equity:,.2f}</div></div>", unsafe_allow_html=True)
    with perf_col2:
        st.markdown(f"<div class='premium-card'><div class='metric-label'>Cash Available</div><div class='metric-value'>${cash:,.2f}</div></div>", unsafe_allow_html=True)
    with perf_col3:
        st.markdown(f"<div class='premium-card'><div class='metric-label'>Buying Power</div><div class='metric-value'>${buying_power:,.2f}</div></div>", unsafe_allow_html=True)
    with perf_col4:
        if daily_pnl == 0.0:
            st.markdown("""
            <div class='premium-card'>
                <div class='metric-label'>Daily P&L</div>
                <div class='metric-value' style='color: #94a3b8;'>$0.00</div>
                <div style='font-size: 0.75rem; color: #94a3b8; margin-top: 4px;'>No qualifying trade approved today.</div>
            </div>
            """, unsafe_allow_html=True)
        else:
            daily_pnl_pct = (daily_pnl / float(account.last_equity)) * 100 if float(account.last_equity) > 0 else 0
            pnl_color = "#10b981" if daily_pnl > 0 else "#ef4444"
            st.markdown(f"""
            <div class='premium-card'>
                <div class='metric-label'>Daily P&L</div>
                <div class='metric-value' style='color: {pnl_color};'>${daily_pnl:,.2f}</div>
                <div style='font-size: 0.85rem; color: {pnl_color}; font-weight: 500; margin-top: 4px;'>{daily_pnl_pct:,.2f}%</div>
            </div>
            """, unsafe_allow_html=True)

    if positions:
        st.markdown("<h4 style='color: #cbd5e1; margin-top: 20px;'>OPEN POSITIONS</h4>", unsafe_allow_html=True)
        pos_data = []
        for p in positions:
            pos_data.append({
                "Symbol": p.symbol,
                "Qty": float(p.qty),
                "Side": p.side.name,
                "Market Value": f"${float(p.market_value):,.2f}",
                "Cost Basis": f"${float(p.cost_basis):,.2f}",
                "Unrealized P&L": f"${float(p.unrealized_pl):,.2f}",
                "Unrealized P&L %": f"{float(p.unrealized_plpc)*100:,.2f}%"
            })
        st.dataframe(pd.DataFrame(pos_data), use_container_width=True, hide_index=True)
    elif has_trade_activity and not positions:
        st.info("No active positions currently open. Trades have been closed.")
        
    if orders:
        st.markdown("<h4 style='color: #cbd5e1; margin-top: 20px;'>RECENT ORDERS</h4>", unsafe_allow_html=True)
        order_data = []
        for o in orders:
            order_data.append({
                "Symbol": o.symbol,
                "Side": o.side.name,
                "Status": o.status.name,
                "Filled Qty": float(o.filled_qty),
                "Limit Price": f"${float(o.limit_price):,.2f}" if o.limit_price else "N/A",
                "Avg Fill Price": f"${float(o.filled_avg_price):,.2f}" if o.filled_avg_price else "N/A",
                "Submitted At": o.submitted_at.strftime("%Y-%m-%d %H:%M") if o.submitted_at else "N/A"
            })
        st.dataframe(pd.DataFrame(order_data), use_container_width=True, hide_index=True)

    st.markdown("---")
    
    # ----------------------------------------------------------------------
    # 6. ARCHITECTURE / SYSTEM PIPELINE
    # ----------------------------------------------------------------------
    st.markdown("### SYSTEM ARCHITECTURE")
    st.markdown("<p style='color: #94a3b8; font-size: 0.9em; margin-bottom: 20px;'>AI reasoning proposes. Deterministic controls govern. Execution follows only after approval.</p>", unsafe_allow_html=True)
    
    st.markdown("""
    <div style="display: flex; flex-wrap: wrap; gap: 10px; align-items: center; justify-content: center; background-color: #0f172a; padding: 30px; border-radius: 12px; border: 1px solid #1e293b;">
        
        <div style="text-align: center; width: 100px;">
            <div style="font-size: 24px; margin-bottom: 8px;">📡</div>
            <div style="font-size: 0.75rem; font-weight: bold; color: #f8fafc;">EVENT</div>
            <div style="font-size: 0.65rem; color: #94a3b8;">Market/News</div>
        </div>
        
        <div style="color: #475569; font-weight: bold;">→</div>
        
        <div style="text-align: center; width: 100px;">
            <div style="font-size: 24px; margin-bottom: 8px;">🧠</div>
            <div style="font-size: 0.75rem; font-weight: bold; color: #f8fafc;">REASONING</div>
            <div style="font-size: 0.65rem; color: #94a3b8;">Bull ↔ Bear</div>
        </div>
        
        <div style="color: #475569; font-weight: bold;">→</div>
        
        <div style="text-align: center; width: 100px;">
            <div style="font-size: 24px; margin-bottom: 8px;">⚖️</div>
            <div style="font-size: 0.75rem; font-weight: bold; color: #f8fafc;">TRADER</div>
            <div style="font-size: 0.65rem; color: #94a3b8;">Decision</div>
        </div>
        
        <div style="color: #475569; font-weight: bold;">→</div>
        
        <div style="text-align: center; width: 100px;">
            <div style="font-size: 24px; margin-bottom: 8px;">🎯</div>
            <div style="font-size: 0.75rem; font-weight: bold; color: #f8fafc;">OPTION</div>
            <div style="font-size: 0.65rem; color: #94a3b8;">Rank Selection</div>
        </div>
        
        <div style="color: #475569; font-weight: bold;">→</div>
        
        <div style="text-align: center; width: 100px; padding: 10px; background-color: rgba(239, 68, 68, 0.1); border: 1px solid rgba(239, 68, 68, 0.3); border-radius: 8px;">
            <div style="font-size: 24px; margin-bottom: 8px;">🛡️</div>
            <div style="font-size: 0.75rem; font-weight: bold; color: #ef4444;">RISK</div>
            <div style="font-size: 0.65rem; color: #fca5a5;">Deterministic</div>
        </div>
        
        <div style="color: #475569; font-weight: bold;">→</div>
        
        <div style="text-align: center; width: 100px;">
            <div style="font-size: 24px; margin-bottom: 8px;">⚡</div>
            <div style="font-size: 0.75rem; font-weight: bold; color: #f8fafc;">EXECUTE</div>
            <div style="font-size: 0.65rem; color: #94a3b8;">Alpaca Paper</div>
        </div>
        
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    risk_cols = st.columns(4)
    with risk_cols[0]:
        st.markdown(f"**Max Trade Risk:** <span style='color:#94a3b8;'>{settings.MAX_RISK_PERCENT * 100}%</span>", unsafe_allow_html=True)
        st.markdown(f"**Max Open Positions:** <span style='color:#94a3b8;'>{settings.MAX_OPEN_POSITIONS}</span>", unsafe_allow_html=True)
    with risk_cols[1]:
        st.markdown(f"**Max Sector Exposure:** <span style='color:#94a3b8;'>{settings.MAX_SECTOR_EXPOSURE_PERCENT * 100}%</span>", unsafe_allow_html=True)
        st.markdown(f"**Daily Loss Limit:** <span style='color:#94a3b8;'>{settings.DAILY_LOSS_LIMIT_PERCENT * 100}%</span>", unsafe_allow_html=True)
    with risk_cols[2]:
        st.markdown(f"**Max Directional Exp:** <span style='color:#94a3b8;'>{settings.MAX_DIRECTIONAL_EXPOSURE_PERCENT * 100}%</span>", unsafe_allow_html=True)
        st.markdown(f"**Min Rank Threshold:** <span style='color:#94a3b8;'>{settings.MIN_RANK_SCORE_THRESHOLD}</span>", unsafe_allow_html=True)
    with risk_cols[3]:
        st.markdown(f"**DTE Range:** <span style='color:#94a3b8;'>{settings.MIN_DTE} - {settings.MAX_DTE} days</span>", unsafe_allow_html=True)
        st.markdown(f"**Max Slippage:** <span style='color:#94a3b8;'>{settings.MAX_SLIPPAGE_PERCENT * 100}%</span>", unsafe_allow_html=True)

# Mode Toggle
mode = st.radio("Environment", ["DEMO MODE", "LIVE PAPER"], horizontal=True, label_visibility="collapsed")

if mode == "LIVE PAPER":
    dashboard_content()
else:
    from dashboard_demo import render_demo_dashboard
    render_demo_dashboard()
