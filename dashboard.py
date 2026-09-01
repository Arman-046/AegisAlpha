import streamlit as st
import json
import os
import time
from datetime import datetime
from config.settings import settings
from alpaca.trading.client import TradingClient

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
    
    .status-badge {
        display: inline-block;
        padding: 6px 14px;
        border-radius: 12px;
        font-size: 0.75rem;
        font-weight: 700;
        letter-spacing: 0.05em;
        text-transform: uppercase;
        margin-bottom: 12px;
    }
    
    /* Pipeline Nodes */
    .pipeline-container {
        display: flex;
        align-items: center;
        justify-content: space-between;
        margin: 20px 0;
        flex-wrap: wrap;
    }
    .pipeline-node {
        display: flex;
        flex-direction: column;
        align-items: center;
        margin-bottom: 15px;
        min-width: 70px;
    }
    .node-circle {
        width: 32px;
        height: 32px;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        font-weight: bold;
        font-size: 14px;
        margin-bottom: 8px;
    }
    .node-waiting { background-color: #1e293b; color: #94a3b8; border: 2px solid #334155; }
    .node-processing { background-color: rgba(59, 130, 246, 0.2); color: #60a5fa; border: 2px solid #3b82f6; animation: pulse 1.5s infinite; }
    .node-completed { background-color: rgba(16, 185, 129, 0.2); color: #34d399; border: 2px solid #10b981; }
    .node-failed { background-color: rgba(239, 68, 68, 0.2); color: #f87171; border: 2px solid #ef4444; }
    
    .node-label { font-size: 0.70rem; color: #cbd5e1; font-weight: 600; text-transform: uppercase; }
    
    @keyframes pulse {
        0% { box-shadow: 0 0 0 0 rgba(59, 130, 246, 0.7); }
        70% { box-shadow: 0 0 0 10px rgba(59, 130, 246, 0); }
        100% { box-shadow: 0 0 0 0 rgba(59, 130, 246, 0); }
    }
    
    /* Watchlist tags */
    .tag {
        background-color: #1e293b;
        color: #f8fafc;
        padding: 6px 12px;
        border-radius: 6px;
        margin-right: 8px;
        margin-bottom: 8px;
        font-size: 0.85rem;
        border: 1px solid #334155;
        display: inline-block;
    }
    .tag-active { border-color: #10b981; color: #10b981; }
    
    /* Mobile responsive pipeline */
    @media (max-width: 768px) {
        .pipeline-container { flex-direction: column; align-items: flex-start; }
        .pipeline-node { flex-direction: row; margin-bottom: 10px; width: 100%; }
        .node-circle { margin-bottom: 0; margin-right: 15px; }
        .arrow { display: none; }
    }
</style>
""", unsafe_allow_html=True)

# Initialize Alpaca Client
@st.cache_resource
def get_alpaca_client():
    if settings.APCA_API_KEY_ID == "PK_DUMMY" or not settings.APCA_API_KEY_ID:
        return None
    return TradingClient(settings.APCA_API_KEY_ID, settings.APCA_API_SECRET_KEY, paper=settings.PAPER)

def load_observability():
    obs_file = "state/observability.json"
    if os.path.exists(obs_file):
        try:
            with open(obs_file, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return None

obs = load_observability()

# Helpers
def format_time(ts):
    if not ts: return "Not yet recorded"
    return datetime.fromtimestamp(ts).strftime("%H:%M:%S")

def time_ago(ts):
    if not ts: return "Unknown"
    diff = time.time() - ts
    if diff < 60: return f"{int(diff)} seconds ago"
    return f"{int(diff/60)} minutes ago"

st.markdown("""
<div style="text-align: center; margin-bottom: 2rem;">
    <h1 style="margin-bottom: 0; color: #38bdf8; font-weight: 800; letter-spacing: 2px;">AEGISALPHA</h1>
    <p style="color: #94a3b8; font-size: 1.1rem; margin-top: 0.5rem; text-transform: uppercase; letter-spacing: 1px;">Autonomous Event-Driven AI Trading</p>
</div>
""", unsafe_allow_html=True)

# 1. WHAT IS AEGISALPHA DOING RIGHT NOW?
col1, col2 = st.columns([2, 1])

with col1:
    st.markdown("### SYSTEM STATUS")
    
    is_live = "LIVE PAPER" if settings.PAPER else "LIVE"
    is_demo = settings.APCA_API_KEY_ID == "PK_DUMMY"
    env_badge = "🔵 DEMO MODE — SIMULATION ONLY (NO REAL ORDERS)" if is_demo else f"🟢 {is_live} — REAL ALPACA PAPER ACCOUNT"
    
    agent_status = obs.get("status", "STOPPED") if obs else "STOPPED"
    hb_time = obs.get("last_heartbeat", 0) if obs else 0
    is_stale = (time.time() - hb_time) > 120 if hb_time else True
    
    if is_stale and agent_status != "STOPPED":
        agent_status = "STALE / UNRESPONSIVE"
        agent_color = "#f59e0b"
    elif agent_status == "RUNNING":
        agent_color = "#10b981"
    elif agent_status == "MARKET CLOSED":
        agent_color = "#3b82f6"
    else:
        agent_color = "#ef4444"
        
    ai_status = obs.get("ai_provider_status", "AVAILABLE") if obs else "AVAILABLE"
    ai_color = "#10b981" if ai_status == "AVAILABLE" else "#ef4444"
    
    st.markdown(f"""
    <div class="premium-card">
        <div style="font-weight: 800; margin-bottom: 24px; color: {'#3b82f6' if is_demo else '#10b981'}; font-size: 1.1rem;">{env_badge}</div>
        
        <div style="display: flex; flex-direction: column; gap: 12px; margin-bottom: 24px; font-size: 1.1rem;">
            <div style="display: flex; justify-content: space-between;">
                <span style="color: #94a3b8;">● Agent</span>
                <span style="color: {agent_color}; font-weight: bold;">{agent_status}</span>
            </div>
            <div style="display: flex; justify-content: space-between;">
                <span style="color: #94a3b8;">● Market</span>
                <span style="color: {'#10b981' if agent_status == 'RUNNING' else '#94a3b8'}; font-weight: bold;">{'OPEN' if agent_status == 'RUNNING' else 'CLOSED'}</span>
            </div>
            <div style="display: flex; justify-content: space-between;">
                <span style="color: #94a3b8;">● AI</span>
                <span style="color: {ai_color}; font-weight: bold;">GEMINI — {ai_status}</span>
            </div>
            <div style="display: flex; justify-content: space-between;">
                <span style="color: #94a3b8;">● Alpaca API</span>
                <span style="color: {'#10b981' if not is_demo else '#3b82f6'}; font-weight: bold;">{'CONNECTED' if not is_demo else 'MOCKED'}</span>
            </div>
        </div>
        
        <div style="border-top: 1px solid #1e293b; padding-top: 16px; margin-bottom: 8px; color: #f8fafc; font-weight: 600; font-size: 1.1rem;">
            Activity: <span style="color: #38bdf8;">{obs.get('last_terminal_state', {}).get('status', 'WAITING FOR EVENT') if obs else 'WAITING'}</span>
        </div>
        <div style="font-size: 0.85rem; color: #64748b;">
            Last heartbeat: {format_time(hb_time)} ({time_ago(hb_time)})
        </div>
    </div>
    """, unsafe_allow_html=True)

with col2:
    st.markdown("### 📡 MONITORING")
    st.markdown("""
    <div class="premium-card" style="height: 310px;">
        <div style="font-size: 0.95rem; color: #94a3b8; margin-bottom: 24px; line-height: 1.5;">
            Mode: <strong style="color: #38bdf8;">EVENT-DRIVEN</strong><br><br>
            The agent continuously monitors configured market data streams. The AI reasoning pipeline is invoked <strong>only</strong> when the event detector identifies a qualifying volatility event or breaking news.
        </div>
    """, unsafe_allow_html=True)
    
    tags_html = ""
    for s in settings.WATCHLIST:
        tags_html += f"<span class='tag tag-active'>{s} ●</span>"
    st.markdown(tags_html + "</div>", unsafe_allow_html=True)

# 2. LIVE PIPELINE VISUALIZATION
st.markdown("### LIVE DECISION PIPELINE")

pipeline = obs.get("pipeline", {}) if obs else {}
stages = ["EVENT", "DATA", "BULL", "BEAR", "TRADER", "OPTION", "RANK", "RISK", "EXECUTE", "MONITOR"]

def get_node_class_and_icon(status):
    if status == "COMPLETED": return "node-completed", "✓"
    if status == "PROCESSING": return "node-processing", "◐"
    if status == "FAILED": return "node-failed", "✕"
    return "node-waiting", "○"

nodes_html = "<div class='premium-card'><div class='pipeline-container'>"
for i, stage in enumerate(stages):
    status = pipeline.get(stage, "WAITING")
    n_class, n_icon = get_node_class_and_icon(status)
    nodes_html += f"""
    <div class="pipeline-node">
        <div class="node-circle {n_class}">{n_icon}</div>
        <div class="node-label">{stage}</div>
    </div>
    """
    if i < len(stages) - 1:
        nodes_html += """<div class="arrow" style="color: #334155; font-size: 20px; font-weight: bold; margin-bottom: 20px;">→</div>"""
nodes_html += "</div></div>"

st.markdown(nodes_html, unsafe_allow_html=True)

# 3. CURRENT EVALUATION & WHY DIDN'T IT TRADE?
col3, col4 = st.columns(2)
with col3:
    st.markdown("### CURRENT EVENT")
    sym = obs.get("current_symbol") if obs else None
    evt = obs.get("current_event") if obs else None
    if sym and evt:
        st.markdown(f"""
        <div class="premium-card" style="height: 180px;">
            <h2 style="color: #38bdf8; margin-top: 0; font-size: 2.5rem; margin-bottom: 4px;">{sym}</h2>
            <div style="color: #f1f5f9; font-size: 1.1rem; line-height: 1.5; overflow: hidden; display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical;">{evt}</div>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown("""
        <div class="premium-card" style="height: 180px; display: flex; align-items: center; justify-content: center;">
            <div style="color: #94a3b8; font-style: italic; font-size: 1.2rem;">Waiting for first evaluation...</div>
        </div>
        """, unsafe_allow_html=True)

with col4:
    st.markdown("### OUTCOME / REASON")
    term_state = obs.get("last_terminal_state", {}) if obs else {}
    t_status = term_state.get("status", "WAITING FOR EVENT")
    t_reason = term_state.get("reason", "No qualifying market event has triggered the strategy.")
    
    t_color = "#94a3b8"
    if t_status == "TRADE APPROVED": t_color = "#10b981"
    elif "REJECTED" in t_status or "FAILED" in t_status or "UNAVAILABLE" in t_status: t_color = "#ef4444"
    elif t_status == "PROCESSING": t_color = "#3b82f6"
    
    st.markdown(f"""
    <div class="premium-card" style="height: 180px;">
        <h3 style="color: {t_color}; margin-top: 0; font-size: 1.6rem;">{t_status}</h3>
        <div style="color: #cbd5e1; font-size: 1.1rem; line-height: 1.5;">{t_reason}</div>
    </div>
    """, unsafe_allow_html=True)

# 4. ACTIVITY & ERRORS
col5, col6 = st.columns(2)
with col5:
    st.markdown("### REAL-TIME AGENT ACTIVITY")
    activities = obs.get("recent_activities", []) if obs else []
    if not activities:
        st.markdown("<div class='premium-card' style='color:#94a3b8; height: 350px;'>Not yet recorded</div>", unsafe_allow_html=True)
    else:
        act_html = "<div class='premium-card' style='height: 350px; overflow-y: auto;'>"
        for a in activities[:20]:
            ts = format_time(a.get("timestamp"))
            msg = a.get("message", "")
            act_html += f"<div style='margin-bottom: 12px; border-bottom: 1px solid #1e293b; padding-bottom: 8px;'><span style='color: #38bdf8; font-family: monospace; font-size: 0.85rem; margin-right: 12px;'>{ts}</span> <span style='color: #f1f5f9;'>{msg}</span></div>"
        act_html += "</div>"
        st.markdown(act_html, unsafe_allow_html=True)

with col6:
    st.markdown("### SYSTEM HEALTH & ERRORS")
    errors = obs.get("error_history", []) if obs else []
    if not errors:
        st.markdown("<div class='premium-card' style='height: 350px; display: flex; align-items: center; justify-content: center;'><div style='color:#10b981; font-size: 1.2rem; text-align: center;'>🟢 No recent errors.<br>Safety systems active and healthy.</div></div>", unsafe_allow_html=True)
    else:
        err_html = "<div class='premium-card' style='height: 350px; overflow-y: auto;'>"
        for e in errors[:10]:
            ts = format_time(e.get("timestamp"))
            cat = e.get("category", "SYSTEM")
            msg = e.get("message", "")
            err_html += f"""
            <div style='margin-bottom: 16px; border-left: 3px solid #ef4444; padding-left: 16px; background-color: rgba(239, 68, 68, 0.05); padding: 12px;'>
                <div style='color: #ef4444; font-weight: 800; font-size: 0.85rem; margin-bottom: 4px;'>{cat} FAILURE</div>
                <div style='color: #cbd5e1; font-size: 0.95rem; margin-bottom: 8px;'>{msg}</div>
                <div style='color: #64748b; font-size: 0.8rem; font-family: monospace;'>{ts}</div>
            </div>
            """
        err_html += "</div>"
        st.markdown(err_html, unsafe_allow_html=True)

# 5. SESSION STATS & P&L
col7, col8 = st.columns(2)
with col7:
    st.markdown("### SESSION STATISTICS")
    stats = obs.get("stats", {}) if obs else {}
    st.markdown(f"""
    <div class="premium-card">
        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 24px;">
            <div>
                <div style="font-size: 0.8rem; color: #94a3b8; font-weight: 700;">EVENTS DETECTED</div>
                <div style="font-size: 2rem; font-weight: 800; color: #f8fafc;">{stats.get('events_detected', '0')}</div>
            </div>
            <div>
                <div style="font-size: 0.8rem; color: #94a3b8; font-weight: 700;">TRADES APPROVED</div>
                <div style="font-size: 2rem; font-weight: 800; color: #10b981;">{stats.get('trades_approved', '0')}</div>
            </div>
            <div>
                <div style="font-size: 0.8rem; color: #94a3b8; font-weight: 700;">AI FAILURES</div>
                <div style="font-size: 2rem; font-weight: 800; color: #ef4444;">{stats.get('ai_failures', '0')}</div>
            </div>
            <div>
                <div style="font-size: 0.8rem; color: #94a3b8; font-weight: 700;">RISK REJECTIONS</div>
                <div style="font-size: 2rem; font-weight: 800; color: #f59e0b;">{stats.get('risk_rejections', '0')}</div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

with col8:
    st.markdown("### PORTFOLIO & P&L")
    client = get_alpaca_client()
    if client:
        try:
            account = client.get_account()
            eq = float(account.equity)
            st.markdown(f"""
            <div class="premium-card">
                <div style="font-size: 0.8rem; color: #94a3b8; font-weight: 700;">TOTAL EQUITY</div>
                <div style="font-size: 2.5rem; font-weight: 800; color: #10b981; margin-bottom: 12px;">${eq:,.2f}</div>
                <div style="font-size: 0.95rem; color: #94a3b8; line-height: 1.5; border-top: 1px solid #1e293b; padding-top: 16px;">
                    AegisAlpha does not create trades simply to generate performance. Capital is deployed only after an opportunity passes the complete decision and deterministic risk pipeline.
                </div>
            </div>
            """, unsafe_allow_html=True)
        except:
            st.markdown("<div class='premium-card' style='color:#ef4444'>Failed to fetch Alpaca account</div>", unsafe_allow_html=True)
    else:
        st.markdown("""
        <div class="premium-card">
            <div style="font-size: 0.8rem; color: #94a3b8; font-weight: 700;">TOTAL EQUITY</div>
            <div style="font-size: 2.5rem; font-weight: 800; color: #94a3b8; margin-bottom: 12px;">$0.00</div>
            <div style="font-size: 0.95rem; color: #94a3b8; line-height: 1.5; border-top: 1px solid #1e293b; padding-top: 16px;">
                <strong>Demo Mode: No realized P&L.</strong><br>
                AegisAlpha does not create trades simply to generate performance.
            </div>
        </div>
        """, unsafe_allow_html=True)
