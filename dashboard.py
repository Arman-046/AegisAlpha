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

    # Header
    col1, col2 = st.columns([3, 1])
    with col1:
        logo_col, title_col = st.columns([1, 8])
        with logo_col:
            st.image("aegisalpha_logo_v2.png", width=60)
        with title_col:
            st.title("AegisAlpha")
            st.caption("AUTONOMOUS OPTIONS TRADING AGENT • AI Proposes. Data Informs. Risk Governs. Code Executes.")
    with col2:
        st.markdown("<div style='text-align: right; padding-top: 20px;'><span style='background-color: #2563eb; padding: 5px 10px; border-radius: 5px; font-weight: bold;'>🟢 LIVE PAPER</span><br><span style='font-size: 0.8em; color: #94a3b8;'>REAL ALPACA PAPER ACCOUNT</span></div>", unsafe_allow_html=True)
        st.caption(f"<div style='text-align: right;'>Last Refreshed: {datetime.now().strftime('%H:%M:%S')}</div>", unsafe_allow_html=True)

    st.markdown("---")

    # 1. LIVE AGENT ACTIVITY
    st.markdown("### 🟢 LIVE AGENT ACTIVITY")
    status_cols = st.columns(4)
    agent_running = "RUNNING" if status and status.get("status") == "RUNNING" else "STOPPED"
    agent_color = "#10b981" if agent_running == "RUNNING" else "#ef4444"
    market_open = status.get("market_open", False) if status else False
    market_color = "#10b981" if market_open else "#f59e0b"
    
    with status_cols[0]:
        st.markdown(f"**Agent:** <span style='color: {agent_color};'>{agent_running}</span>", unsafe_allow_html=True)
        st.markdown(f"**Market:** <span style='color: {market_color};'>{'OPEN' if market_open else 'CLOSED'}</span>", unsafe_allow_html=True)
    with status_cols[1]:
        st.markdown("**Alpaca:** <span style='color: #10b981;'>CONNECTED</span>", unsafe_allow_html=True)
        last_hb = status.get("last_heartbeat", "Unknown") if status else "Unknown"
        if last_hb != "Unknown":
            try:
                last_hb = last_hb.split(".")[0].replace("T", " ")
            except:
                pass
        st.markdown(f"**Last Heartbeat:** {last_hb}", unsafe_allow_html=True)
    with status_cols[2]:
        st.markdown("**Monitoring Mode:** EVENT-DRIVEN")
        decisions = memory.get("history", [])
        st.markdown(f"**Opportunities Evaluated:** {len(decisions)}")
    with status_cols[3]:
        trades_approved = len([d for d in decisions if d.get("action") == "EXECUTED"])
        risk_rejections = len([d for d in decisions if "risk" in str(d.get("reason")).lower()])
        st.markdown(f"**Trades Approved:** {trades_approved}")
        st.markdown(f"**Risk Rejections:** {risk_rejections}")

    st.markdown("---")

    st.markdown("### 📡 MONITORING")
    watchlist_badges = " ".join([f"<span style='background-color: #1e293b; color: #f8fafc; padding: 4px 12px; border-radius: 12px; margin-right: 8px; font-size: 0.9em; border: 1px solid #334155;'>{sym}</span>" for sym in settings.WATCHLIST])
    st.markdown(f"{watchlist_badges}", unsafe_allow_html=True)
    st.caption("EVENT-DRIVEN MONITORING")
    
    st.markdown("---")

    # 2. ACCOUNT OVERVIEW & 3. PERFORMANCE
    st.subheader("Account Overview")
    equity = float(account.equity)
    cash = float(account.cash)
    buying_power = float(account.buying_power)
    
    metric_cols = st.columns(4)
    metric_cols[0].metric("Current Equity", f"${equity:,.2f}")
    metric_cols[1].metric("Cash", f"${cash:,.2f}")
    metric_cols[2].metric("Buying Power", f"${buying_power:,.2f}")
    
    daily_pnl = float(account.equity) - float(account.last_equity)
    
    if daily_pnl == 0.0:
        metric_cols[3].metric("Daily P&L", "$0.00")
        metric_cols[3].caption("WHY? No qualifying trade has been approved during the current session.")
    else:
        daily_pnl_pct = (daily_pnl / float(account.last_equity)) * 100 if float(account.last_equity) > 0 else 0
        metric_cols[3].metric("Daily P&L", f"${daily_pnl:,.2f}", f"{daily_pnl_pct:,.2f}%")
    
    st.markdown("---")
    
    has_trade_activity = len(positions) > 0 or len(orders) > 0 or daily_pnl != 0.0
    
    if not has_trade_activity:
        if not market_open:
            st.markdown("""
            <div style="background-color: #0f172a; border-left: 4px solid #3b82f6; padding: 20px; border-radius: 8px; margin-bottom: 20px;">
                <h3 style="margin-top:0; color: #3b82f6;">🌙 MARKET CLOSED</h3>
                <p style="color: #e2e8f0; font-size: 1.1em;">AegisAlpha is connected and healthy.</p>
                <p style="color: #94a3b8; margin: 0;">Autonomous trading is paused until the market reopens.</p>
            </div>
            """, unsafe_allow_html=True)
        else:
            if not decisions:
                st.markdown("""
                <div style="background-color: #0f172a; border-left: 4px solid #f59e0b; padding: 20px; border-radius: 8px; margin-bottom: 20px;">
                    <h3 style="margin-top:0; color: #f59e0b;">🟡 WAITING FOR QUALIFYING OPPORTUNITY</h3>
                    <p style="color: #94a3b8; font-size: 1.1em; margin: 0;">No qualifying trade has been approved. The agent is monitoring the market.</p>
                </div>
                """, unsafe_allow_html=True)
            else:
                last_decision = decisions[-1]
                action = last_decision.get("action", "")
                reason = last_decision.get("reason", "")
                if action == "VETOED" and "risk" in reason.lower():
                    st.markdown(f"""
                    <div style="background-color: #0f172a; border-left: 4px solid #ef4444; padding: 20px; border-radius: 8px; margin-bottom: 20px;">
                        <h3 style="margin-top:0; color: #ef4444;">🔴 RISK ENGINE REJECTED</h3>
                        <p style="color: #e2e8f0; font-size: 1.1em; margin-bottom: 5px;"><strong>AI Recommendation:</strong> {last_decision.get('symbol')} ({last_decision.get('direction')})</p>
                        <p style="color: #e2e8f0; font-size: 1.1em; margin-bottom: 15px;"><strong>Reason:</strong> {reason}</p>
                        <h4 style="color: #f8fafc; margin-bottom: 5px;">THE AI WANTED TO TRADE. THE RISK ENGINE SAID NO.</h4>
                        <p style="color: #94a3b8; font-size: 0.9em; margin: 0;">The AI cannot override portfolio risk constraints.</p>
                    </div>
                    """, unsafe_allow_html=True)
                elif action == "VETOED":
                    st.markdown(f"""
                    <div style="background-color: #0f172a; border-left: 4px solid #f59e0b; padding: 20px; border-radius: 8px; margin-bottom: 20px;">
                        <h3 style="margin-top:0; color: #f59e0b;">🟡 OPPORTUNITY REJECTED</h3>
                        <p style="color: #e2e8f0; font-size: 1.1em; margin-bottom: 5px;"><strong>Symbol:</strong> {last_decision.get('symbol')} ({last_decision.get('direction')})</p>
                        <p style="color: #e2e8f0; font-size: 1.1em; margin-bottom: 15px;"><strong>Reason:</strong> {reason}</p>
                        <p style="color: #94a3b8; font-size: 0.9em; margin: 0;">Not trading is an intentional decision when the opportunity does not pass AegisAlpha's complete decision and risk pipeline.</p>
                    </div>
                    """, unsafe_allow_html=True)
    else:
        st.markdown("""
        <div style="background-color: #0f172a; border-left: 4px solid #10b981; padding: 20px; border-radius: 8px; margin-bottom: 20px;">
            <h3 style="margin-top:0; color: #10b981;">🟢 LIVE TRADE ACTIVE</h3>
            <p style="color: #94a3b8; font-size: 0.9em; margin: 0;">AegisAlpha has successfully passed the deterministic risk pipeline and executed real orders in this session.</p>
        </div>
        """, unsafe_allow_html=True)
        if positions:
            st.markdown("#### CURRENT POSITION(S)")
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
            
        if orders:
            st.markdown("#### RECENT ORDERS")
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
            
        if not positions and not orders:
            # Fallback if P&L != 0 but no orders/positions are retrieved
            st.info("No active positions or recent orders retrieved, but Daily P&L reflects closed trades.")
            
    st.markdown("---")
    
    # 5b. SESSION HISTORY
    st.subheader("Session History")
    if not decisions:
        st.info("No opportunity has been evaluated yet. The agent is currently monitoring for its next event.")
    else:
        dec_data = []
        # show last 5
        for d in reversed(decisions[-5:]):
            dec_data.append({
                "Timestamp": d.get("timestamp", "").replace("T", " ")[:19] if d.get("timestamp") else "N/A",
                "Symbol": d.get("symbol"),
                "Direction": d.get("direction"),
                "Confidence": f"{d.get('confidence', 0):.2f}",
                "Action": d.get("action"),
                "Reason": d.get("reason")
            })
        st.dataframe(pd.DataFrame(dec_data), use_container_width=True, hide_index=True)

    st.markdown("---")

    st.markdown("---")
    
    st.markdown("""
    <div style="background-color: #0f172a; padding: 20px; border-radius: 8px; border: 1px solid #1e293b; margin: 20px 0;">
        <h3 style="margin-top: 0; color: #f8fafc;">🛡️ AI PROPOSES. RISK DECIDES.</h3>
        <p style="color: #94a3b8; font-size: 0.9em; margin-bottom: 20px;">Deterministic portfolio constraints cannot be overridden by the AI.</p>
    """, unsafe_allow_html=True)
    
    risk_cols = st.columns(4)
    with risk_cols[0]:
        st.markdown(f"**Max Trade Risk:** {settings.MAX_RISK_PERCENT * 100}%")
        st.markdown(f"**Max Open Positions:** {settings.MAX_OPEN_POSITIONS}")
    with risk_cols[1]:
        st.markdown(f"**Max Sector Exposure:** {settings.MAX_SECTOR_EXPOSURE_PERCENT * 100}%")
        st.markdown(f"**Daily Loss Limit:** {settings.DAILY_LOSS_LIMIT_PERCENT * 100}%")
    with risk_cols[2]:
        st.markdown(f"**Max Directional Exp:** {settings.MAX_DIRECTIONAL_EXPOSURE_PERCENT * 100}%")
        st.markdown(f"**Min Rank Threshold:** {settings.MIN_RANK_SCORE_THRESHOLD}")
    with risk_cols[3]:
        st.markdown(f"**DTE Range:** {settings.MIN_DTE} - {settings.MAX_DTE} days")
        st.markdown(f"**Max Slippage:** {settings.MAX_SLIPPAGE_PERCENT * 100}%")

    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("---")

    # 7. AGENT ARCHITECTURE
    st.subheader("Agent Architecture")
    st.markdown("""
    <div style="font-family: sans-serif; max-width: 600px;">
        <div style="background-color: #1e293b; padding: 15px; border-radius: 8px; margin-bottom: 10px; text-align: center; border-left: 4px solid #3b82f6;">
            <strong>📡 EVENT</strong><br><span style="color: #94a3b8;">Market + News</span>
        </div>
        <div style="text-align: center; color: #94a3b8; font-size: 20px; margin-bottom: 10px;">↓</div>
        <div style="background-color: #1e293b; padding: 15px; border-radius: 8px; margin-bottom: 10px; text-align: center; border-left: 4px solid #8b5cf6;">
            <strong>🧠 AI REASONING</strong><br><span style="color: #94a3b8;">Bull + Bear</span>
        </div>
        <div style="text-align: center; color: #94a3b8; font-size: 20px; margin-bottom: 10px;">↓</div>
        <div style="background-color: #1e293b; padding: 15px; border-radius: 8px; margin-bottom: 10px; text-align: center; border-left: 4px solid #10b981;">
            <strong>⚖️ TRADER</strong><br><span style="color: #94a3b8;">Decision</span>
        </div>
        <div style="text-align: center; color: #94a3b8; font-size: 20px; margin-bottom: 10px;">↓</div>
        <div style="background-color: #1e293b; padding: 15px; border-radius: 8px; margin-bottom: 10px; text-align: center; border-left: 4px solid #f59e0b;">
            <strong>🎯 OPPORTUNITY</strong><br><span style="color: #94a3b8;">Option + Ranking</span>
        </div>
        <div style="text-align: center; color: #94a3b8; font-size: 20px; margin-bottom: 10px;">↓</div>
        <div style="background-color: #1e293b; padding: 15px; border-radius: 8px; margin-bottom: 10px; text-align: center; border-left: 4px solid #ef4444;">
            <strong>🛡️ RISK ENGINE</strong><br><span style="color: #94a3b8;">Deterministic Controls</span>
        </div>
        <div style="text-align: center; color: #94a3b8; font-size: 20px; margin-bottom: 10px;">↓</div>
        <div style="background-color: #1e293b; padding: 15px; border-radius: 8px; margin-bottom: 10px; text-align: center; border-left: 4px solid #14b8a6;">
            <strong>⚡ EXECUTION</strong><br><span style="color: #94a3b8;">Alpaca Paper</span>
        </div>
        <div style="text-align: center; color: #94a3b8; font-size: 20px; margin-bottom: 10px;">↓</div>
        <div style="background-color: #1e293b; padding: 15px; border-radius: 8px; margin-bottom: 10px; text-align: center; border-left: 4px solid #64748b;">
            <strong>🔄 MONITOR</strong><br><span style="color: #94a3b8;">Position Management</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

# Mode Toggle
mode = st.radio("Environment", ["DEMO MODE", "LIVE PAPER"], horizontal=True, label_visibility="collapsed")

if mode == "LIVE PAPER":
    dashboard_content()
else:
    from dashboard_demo import render_demo_dashboard
    render_demo_dashboard()
