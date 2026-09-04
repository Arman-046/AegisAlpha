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
    page_icon="premium_logo.png",
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
        background: linear-gradient(145deg, #0f172a, #0b0f19);
        border: 1px solid #1e293b;
        border-radius: 16px;
        padding: 24px;
        margin-bottom: 24px;
        box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.5), 0 4px 6px -2px rgba(0, 0, 0, 0.3), inset 0 1px 0 rgba(255, 255, 255, 0.05);
        transition: transform 0.3s cubic-bezier(0.4, 0, 0.2, 1), box-shadow 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    }
    .premium-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.5), 0 10px 10px -5px rgba(0, 0, 0, 0.3), inset 0 1px 0 rgba(255, 255, 255, 0.1);
        border-color: #334155;
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

    /* Active Monitoring Animations */
    .node-listening {
        background-color: rgba(56, 189, 248, 0.1);
        color: #38bdf8;
        border: 2px solid rgba(56, 189, 248, 0.3);
        animation: listenPulse 2s ease-in-out infinite;
    }

    @keyframes listenPulse {
        0% { box-shadow: 0 0 0 0 rgba(56, 189, 248, 0.4); border-color: rgba(56, 189, 248, 0.8); }
        50% { box-shadow: 0 0 0 8px rgba(56, 189, 248, 0); border-color: rgba(56, 189, 248, 0.2); }
        100% { box-shadow: 0 0 0 0 rgba(56, 189, 248, 0); border-color: rgba(56, 189, 248, 0.8); }
    }

    .blinking-dot {
        animation: breathe 2s infinite alternate;
    }
    @keyframes breathe {
        0% { opacity: 0.3; text-shadow: none; }
        100% { opacity: 1; text-shadow: 0 0 8px #10b981; }
    }

    .blinking-cursor {
        animation: blink 1s step-end infinite;
        color: #38bdf8;
    }
    @keyframes blink {
        0%, 100% { opacity: 1; }
        50% { opacity: 0; }
    }

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


# Helpers
def format_time(ts):
    if not ts: return "Not yet recorded"
    return datetime.fromtimestamp(ts).strftime("%H:%M:%S")

def time_ago(ts):
    if not ts: return "Unknown"
    diff = time.time() - ts
    if diff < 60: return f"{int(diff)} seconds ago"
    return f"{int(diff/60)} minutes ago"

import base64
def get_base64_of_bin_file(bin_file):
    try:
        with open(bin_file, 'rb') as f:
            data = f.read()
        return base64.b64encode(data).decode()
    except:
        return ""

logo_base64 = get_base64_of_bin_file("premium_logo.png")
logo_html = f'<img src="data:image/png;base64,{logo_base64}" width="180" style="margin-bottom: 1rem; filter: drop-shadow(0 0 15px rgba(16, 185, 129, 0.4)); border-radius: 12px;" />' if logo_base64 else ''

st.markdown(f"""
<div style="text-align: center; margin-bottom: 3rem; margin-top: 1rem;">
{logo_html}
<h1 style="margin-bottom: 0; color: #10b981; font-weight: 800; letter-spacing: 3px; text-shadow: 0 0 20px rgba(16, 185, 129, 0.3); font-size: 3rem;">AEGISALPHA</h1>
<p style="color: #94a3b8; font-size: 1.1rem; margin-top: 0.5rem; text-transform: uppercase; letter-spacing: 2px; font-weight: 600;">Autonomous Event-Driven AI Trading</p>
<div style="width: 100px; height: 3px; background: linear-gradient(90deg, transparent, #10b981, transparent); margin: 1.5rem auto 0 auto;"></div>
</div>
""", unsafe_allow_html=True)

@st.fragment(run_every="2s")
def render_dashboard_body():
    obs = load_observability()

    # 1. WHAT IS AEGISALPHA DOING RIGHT NOW?
    col1, col2 = st.columns([2, 1])

    with col1:
        st.markdown("### SYSTEM STATUS")

        is_live = "LIVE PAPER" if settings.PAPER else "LIVE"
        is_demo = settings.TRADING_MODE == "demo"
        env_badge = "🔵 DEMO MODE — SIMULATION ONLY (NO REAL ORDERS)" if is_demo else f"🟢 {is_live} — REAL ALPACA PAPER ACCOUNT"

        agent_status = obs.get("status", "STOPPED") if obs else "STOPPED"
        hb_time = obs.get("last_heartbeat", 0) if obs else 0
        is_stale = (time.time() - hb_time) > 120 if hb_time else True

        if is_stale and agent_status != "STOPPED":
            agent_status = "STALE / UNRESPONSIVE"
            agent_color = "#f59e0b"
        elif agent_status == "RUNNING":
            agent_color = "#10b981"
        elif agent_status in ["MARKET CLOSED", "SLEEPING"]:
            agent_status = "SLEEPING"
            agent_color = "#3b82f6"
        else:
            agent_color = "#ef4444"

        ai_status = obs.get("ai_provider_status", "AVAILABLE") if obs else "AVAILABLE"
        ai_color = "#10b981" if ai_status == "AVAILABLE" else "#ef4444"

        html_content = f"""
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
                    <span style="color: {ai_color}; font-weight: bold;">GROQ — {ai_status}</span>
                </div>
                <div style="display: flex; justify-content: space-between;">
                    <span style="color: #94a3b8;">● Alpaca API</span>
                    <span style="color: {'#10b981' if not is_demo else '#3b82f6'}; font-weight: bold;">{'CONNECTED' if not is_demo else 'MOCKED'}</span>
                </div>
            </div>

            <div style="border-top: 1px solid #1e293b; padding-top: 16px; margin-bottom: 8px; color: #f8fafc; font-weight: 600; font-size: 1.1rem;">
                Activity: <span style="color: #38bdf8;">
                {'Monitoring Market Data Streams <span class="blinking-cursor">█</span>' if obs and obs.get('last_terminal_state', {}).get('status') == 'WAITING FOR EVENT' else obs.get('last_terminal_state', {}).get('status', 'Monitoring Market Data Streams <span class="blinking-cursor">█</span>') if obs else 'Monitoring Market Data Streams <span class="blinking-cursor">█</span>'}
                </span>
            </div>
            <div style="font-size: 0.85rem; color: #64748b;">
                Last heartbeat: {format_time(hb_time)} ({time_ago(hb_time)})
            </div>
        </div>
        """
        st.markdown(html_content.replace('\n', ''), unsafe_allow_html=True)

    with col2:
        st.markdown("### 📡 MONITORING")
        html_content = """
        <div class="premium-card" style="height: 310px;">
            <div style="font-size: 0.95rem; color: #94a3b8; margin-bottom: 24px; line-height: 1.5;">
                Mode: <strong style="color: #38bdf8;">EVENT-DRIVEN</strong><br><br>
                The agent continuously monitors configured market data streams. The AI reasoning pipeline is invoked <strong>only</strong> when the event detector identifies a qualifying volatility event or breaking news.
            </div>
        """

        wl_state = obs.get("watchlist", {}) if obs else {}
        wl_status = wl_state.get("status", "UNKNOWN")
        wl_last = wl_state.get("last_refresh", 0)
        wl_next = wl_state.get("next_refresh", 0)
        wl_picks = wl_state.get("picks", [])

        active_symbols = [p.get("symbol") for p in wl_picks] if wl_picks else settings.WATCHLIST

        tags_html = ""
        for s in active_symbols:
            tags_html += f"<span class='tag tag-active'>{s} <span class='blinking-dot'>●</span></span>"
        st.markdown((html_content + tags_html + "</div>").replace('\n', ''), unsafe_allow_html=True)

    # 2. INTELLIGENT WATCHLIST

    st.markdown("### AEGISALPHA INTELLIGENT WATCHLIST")

    # Funnel stats
    scanned = wl_state.get("scanned", len(settings.UNIVERSE))
    quant = wl_state.get("candidates", 0)
    ai_rev = wl_state.get("ai_reviewed", 0)
    wl_size = wl_state.get("size", len(settings.WATCHLIST))

    funnel_html = f"""
    <div class="premium-card" style="margin-bottom: 24px;">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; border-bottom: 1px solid #1e293b; padding-bottom: 12px;">
            <div style="font-size: 0.9rem; color: #94a3b8;">
                Updated: <span style="color:#f8fafc;">{format_time(wl_last) if wl_last > 0 else 'Never'}</span> |
                Next refresh: <span style="color:#38bdf8;">{format_time(wl_next) if wl_next > 0 else 'Market Closed'}</span>
            </div>
            <div style="font-size: 0.85rem; padding: 4px 8px; border-radius: 4px; background: {'rgba(16, 185, 129, 0.1)' if wl_status == 'ACTIVE' else 'rgba(56, 189, 248, 0.1)'}; color: {'#10b981' if wl_status == 'ACTIVE' else '#38bdf8'};">
                STATUS: {wl_status}
            </div>
        </div>

        <div style="display: flex; justify-content: space-between; text-align: center; margin-bottom: 24px;">
            <div style="flex: 1;">
                <div style="font-size: 1.5rem; font-weight: 800; color: #f1f5f9;">{scanned}</div>
                <div style="font-size: 0.75rem; color: #64748b; font-weight: 700; letter-spacing: 1px;">UNIVERSE</div>
            </div>
            <div style="color: #334155; font-size: 1.5rem; display: flex; align-items: center;">→</div>
            <div style="flex: 1;">
                <div style="font-size: 1.5rem; font-weight: 800; color: #f1f5f9;">{quant}</div>
                <div style="font-size: 0.75rem; color: #64748b; font-weight: 700; letter-spacing: 1px;">QUANT SCREEN</div>
            </div>
            <div style="color: #334155; font-size: 1.5rem; display: flex; align-items: center;">→</div>
            <div style="flex: 1;">
                <div style="font-size: 1.5rem; font-weight: 800; color: #f1f5f9;">{ai_rev}</div>
                <div style="font-size: 0.75rem; color: #64748b; font-weight: 700; letter-spacing: 1px;">GROQ ANALYSIS</div>
            </div>
            <div style="color: #334155; font-size: 1.5rem; display: flex; align-items: center;">→</div>
            <div style="flex: 1;">
                <div style="font-size: 1.5rem; font-weight: 800; color: #38bdf8;">{wl_size}</div>
                <div style="font-size: 0.75rem; color: #38bdf8; font-weight: 700; letter-spacing: 1px;">WATCHLIST</div>
            </div>
        </div>
    """

    if wl_picks:
        funnel_html += "<div style='display: flex; flex-direction: column; gap: 8px;'>"
        for i, pick in enumerate(wl_picks):
            sym = pick.get('symbol', 'UNK')
            score = pick.get('score', 0)
            reason = pick.get('reason', '')

            # Color coding score
            s_color = "#10b981" if score >= 85 else "#f59e0b" if score >= 70 else "#94a3b8"
            s_label = "HIGH INTEREST" if score >= 85 else "WATCH"

            funnel_html += f"""
            <div style="display: flex; align-items: center; background: rgba(15, 23, 42, 0.4); padding: 12px; border-radius: 6px; border-left: 3px solid {s_color};">
                <div style="width: 30px; color: #64748b; font-size: 0.8rem;">{i+1:02d}</div>
                <div style="width: 80px; font-weight: 800; color: #f1f5f9; font-size: 1.1rem;">{sym}</div>
                <div style="width: 60px; font-weight: 800; color: {s_color}; font-size: 1.1rem;">{score}</div>
                <div style="width: 140px; font-size: 0.75rem; color: {s_color}; font-weight: 700;">{s_label}</div>
                <div style="flex: 1; font-size: 0.9rem; color: #cbd5e1; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">{reason}</div>
            </div>
            """
        funnel_html += "</div>"
    else:
        funnel_html += f"""
        <div style="text-align: center; padding: 20px; color: #64748b;">
            {"Waiting for first AI watchlist generation..." if not wl_state.get('error') else f"Error generating watchlist: {wl_state.get('error')}"}
        </div>
        """

    funnel_html += "</div>"
    st.markdown(funnel_html.replace('\n', ''), unsafe_allow_html=True)

    # 3. LIVE PIPELINE VISUALIZATION
    st.markdown("### LIVE DECISION PIPELINE")

    pipeline = obs.get("pipeline", {}) if obs else {}
    stages = ["EVENT", "DATA", "BULL", "BEAR", "TRADER", "OPTION", "RANK", "RISK", "EXECUTE", "MONITOR"]

    global_status = obs.get("last_terminal_state", {}).get("status", "") if obs else ""

    def get_node_class_and_icon(status, stage, global_status):
        if status == "COMPLETED": return "node-completed", "✓"
        if status == "PROCESSING": return "node-processing", "◐"
        if status == "FAILED": return "node-failed", "✕"
        if stage == "EVENT" and global_status == "WAITING FOR EVENT":
            return "node-listening", "⚡"
        return "node-waiting", "○"

    nodes_html = "<div class='premium-card'><div class='pipeline-container'>"
    for i, stage in enumerate(stages):
        status = pipeline.get(stage, "WAITING")
        n_class, n_icon = get_node_class_and_icon(status, stage, global_status)
        nodes_html += f"""
        <div class="pipeline-node">
            <div class="node-circle {n_class}">{n_icon}</div>
            <div class="node-label">{stage}</div>
        </div>
        """
        if i < len(stages) - 1:
            nodes_html += """<div class="arrow" style="color: #334155; font-size: 20px; font-weight: bold; margin-bottom: 20px;">→</div>"""
    nodes_html += "</div></div>"

    st.markdown(nodes_html.replace('\n', ''), unsafe_allow_html=True)

    # 4. CURRENT EVALUATION & WHY DIDN'T IT TRADE?
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
            """.replace('\n', ''), unsafe_allow_html=True)
        else:
            st.markdown("""
            <div class="premium-card" style="height: 180px; display: flex; align-items: center; justify-content: center;">
                <div style="color: #94a3b8; font-style: italic; font-size: 1.2rem;">Waiting for first evaluation...</div>
            </div>
            """.replace('\n', ''), unsafe_allow_html=True)

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
        """.replace('\n', ''), unsafe_allow_html=True)

    # 5. ACTIVITY & ERRORS
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
            st.markdown(act_html.replace('\n', ''), unsafe_allow_html=True)

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
            st.markdown(err_html.replace('\n', ''), unsafe_allow_html=True)

    # 6. SESSION STATS & P&L
    col7, col8 = st.columns(2)
    with col7:
        st.markdown("### SESSION STATISTICS")
        stats = obs.get("stats", {}) if obs else {}
        
        ev = int(stats.get('events_detected', 0))
        tr = int(stats.get('trades_approved', 0))
        af = int(stats.get('ai_failures', 0))
        rr = int(stats.get('risk_rejections', 0))
        osub = int(stats.get('orders_submitted', 0))
        
        # Calculate how many were intentionally passed on (not an error, not a trade, not a risk block)
        passed = max(0, ev - tr - af - rr)

        st.markdown(f"""
        <div class="premium-card">
            <div style="display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 24px;">
                <div>
                    <div style="font-size: 0.8rem; color: #94a3b8; font-weight: 700;">EVENTS DETECTED</div>
                    <div style="font-size: 2rem; font-weight: 800; color: #f8fafc;">{ev}</div>
                </div>
                <div>
                    <div style="font-size: 0.8rem; color: #94a3b8; font-weight: 700;">OPPORTUNITIES PASSED</div>
                    <div style="font-size: 2rem; font-weight: 800; color: #38bdf8;">{passed}</div>
                </div>
                <div>
                    <div style="font-size: 0.8rem; color: #94a3b8; font-weight: 700;">TRADES APPROVED</div>
                    <div style="font-size: 2rem; font-weight: 800; color: #10b981;">{tr}</div>
                </div>
                <div>
                    <div style="font-size: 0.8rem; color: #94a3b8; font-weight: 700;">AI FAILURES</div>
                    <div style="font-size: 2rem; font-weight: 800; color: #ef4444;">{af}</div>
                </div>
                <div>
                    <div style="font-size: 0.8rem; color: #94a3b8; font-weight: 700;">RISK REJECTIONS</div>
                    <div style="font-size: 2rem; font-weight: 800; color: #f59e0b;">{rr}</div>
                </div>
                <div>
                    <div style="font-size: 0.8rem; color: #94a3b8; font-weight: 700;">ORDERS SUBMITTED</div>
                    <div style="font-size: 2rem; font-weight: 800; color: #8b5cf6;">{osub}</div>
                </div>
            </div>
        </div>
        """.replace('\n', ''), unsafe_allow_html=True)

    with col8:
        st.markdown("### PORTFOLIO & P&L")
        client = get_alpaca_client()
        if client:
            try:
                account = client.get_account()
                eq = float(account.equity)
                last_eq = float(account.last_equity)
                today_pnl = eq - last_eq
                today_pnl_pct = (today_pnl / last_eq) * 100 if last_eq > 0 else 0

                pnl_color = "#10b981" if today_pnl >= 0 else "#ef4444"
                pnl_sign = "+" if today_pnl >= 0 else ""

                st.markdown(f"""
                <div class="premium-card">
                    <div style="display: flex; justify-content: space-between; align-items: flex-end; margin-bottom: 12px;">
                        <div>
                            <div style="font-size: 0.8rem; color: #94a3b8; font-weight: 700;">TOTAL EQUITY</div>
                            <div style="font-size: 2.5rem; font-weight: 800; color: #f8fafc;">${eq:,.2f}</div>
                        </div>
                        <div style="text-align: right;">
                            <div style="font-size: 0.8rem; color: #94a3b8; font-weight: 700;">TODAY'S P&L</div>
                            <div style="font-size: 1.5rem; font-weight: 800; color: {pnl_color};">{pnl_sign}${today_pnl:,.2f} ({pnl_sign}{today_pnl_pct:.2f}%)</div>
                        </div>
                    </div>
                    <div style="font-size: 0.95rem; color: #94a3b8; line-height: 1.5; border-top: 1px solid #1e293b; padding-top: 16px;">
                        AegisAlpha does not create trades simply to generate performance. Capital is deployed only after an opportunity passes the complete decision and deterministic risk pipeline.
                    </div>
                </div>
                """.replace('\n', ''), unsafe_allow_html=True)
            except:
                st.markdown("<div class='premium-card' style='color:#ef4444'>Failed to fetch Alpaca account</div>", unsafe_allow_html=True)
        else:
            st.markdown("""
            <div class="premium-card">
                <div style="display: flex; justify-content: space-between; align-items: flex-end; margin-bottom: 12px;">
                    <div>
                        <div style="font-size: 0.8rem; color: #94a3b8; font-weight: 700;">TOTAL EQUITY</div>
                        <div style="font-size: 2.5rem; font-weight: 800; color: #94a3b8;">$0.00</div>
                    </div>
                    <div style="text-align: right;">
                        <div style="font-size: 0.8rem; color: #94a3b8; font-weight: 700;">TODAY'S P&L</div>
                        <div style="font-size: 1.5rem; font-weight: 800; color: #94a3b8;">+$0.00 (+0.00%)</div>
                    </div>
                </div>
                <div style="font-size: 0.95rem; color: #94a3b8; line-height: 1.5; border-top: 1px solid #1e293b; padding-top: 16px;">
                    <strong>Demo Mode: No realized P&L.</strong><br>
                    AegisAlpha does not create trades simply to generate performance.
                </div>
            </div>
            """.replace('\n', ''), unsafe_allow_html=True)

    # 7. DECISION JOURNAL & COUNTERFACTUALS
    st.markdown("### 🗂️ DECISION JOURNAL (TRANSPARENCY LOG)")

    def load_memory():
        mem_file = "state/memory.json"
        if os.path.exists(mem_file):
            try:
                with open(mem_file, "r") as f:
                    return json.load(f).get("history", [])
            except:
                pass
        return []

    history = load_memory()

    if not history:
        st.markdown("<div class='premium-card' style='text-align: center; color: #94a3b8;'>No decisions recorded yet.</div>", unsafe_allow_html=True)
    else:
        live_actions = ["EXECUTED", "FAILED_EXECUTION"]
        cf_actions = ["PASSED", "VETOED", "NO_CONTRACT", "VALIDATION_FAILED", "RANK_REJECTED", "RISK_REJECTED"]

        live_executed = [h for h in history if h.get("action") in live_actions and h.get("mode") == "LIVE_PAPER"]
        counterfactuals = [h for h in history if h.get("action") in cf_actions and h.get("mode") != "DEMO"]
        failures = [h for h in history if h.get("action") not in live_actions and h.get("action") not in cf_actions and h.get("mode") != "DEMO"]

        tab1, tab3, tab4 = st.tabs(["🔴 LIVE PAPER EXECUTIONS", "🟡 COUNTERFACTUALS (WHAT-IF)", "⚙️ SYSTEM FAILURES"])

        with tab1:
            if not live_executed:
                st.markdown("<div style='padding: 20px; color: #94a3b8; text-align: center;'>No live trades executed yet.</div>", unsafe_allow_html=True)
            else:
                for item in reversed(live_executed):
                    ts = format_time(item.get("timestamp"))
                    sym = item.get("symbol", "")
                    dir_color = "#10b981" if item.get("direction") == "bullish" else "#ef4444" if item.get("direction") == "bearish" else "#94a3b8"
                    st.markdown(f"""
                    <div class='premium-card' style='border-left: 4px solid {dir_color};'>
                        <div style='display: flex; justify-content: space-between;'>
                            <strong style='font-size: 1.2rem; color: #f8fafc;'>{sym} - {item.get('action')}</strong>
                            <span style='color: #64748b;'>{ts}</span>
                        </div>
                        <div style='color: #38bdf8; font-size: 0.9rem; margin-top: 8px;'>Event: {item.get('event', 'Unknown')}</div>
                        <div style='color: #cbd5e1; margin-top: 8px; font-size: 0.95rem;'><strong>Synthesis:</strong> {item.get('trader_synthesis', item.get('reason'))}</div>
                        <div style='margin-top: 8px; font-size: 0.85rem; color: #94a3b8;'>
                            Option: {item.get('option_candidate', 'N/A')} | Rank Score: {item.get('rank_score', 0):.1f}/100 | AI Conf: {item.get('confidence', 0):.2f}
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

        with tab3:
            st.markdown("<div style='background-color: rgba(245, 158, 11, 0.1); border: 1px solid rgba(245, 158, 11, 0.3); color: #f59e0b; padding: 12px; border-radius: 6px; margin-bottom: 20px; font-size: 0.9rem;'><strong>NOTE:</strong> Counterfactuals are strictly separated from live statistics. These represent rejected candidates, fail-closed validations, and AI logic paths that did not result in trades.</div>", unsafe_allow_html=True)
            if not counterfactuals:
                st.markdown("<div style='padding: 20px; color: #94a3b8; text-align: center;'>No counterfactuals recorded yet.</div>", unsafe_allow_html=True)
            else:
                for item in reversed(counterfactuals):
                    ts = format_time(item.get("timestamp"))
                    sym = item.get("symbol", "")
                    action = item.get("action", "")
                    reason = item.get("reason", "")

                    action_color = "#ef4444"
                    if "NEUTRAL" in action or "PASSED" in action: action_color = "#94a3b8"

                    st.markdown(f"""
                    <div class='premium-card' style='border-left: 2px dashed {action_color}; opacity: 0.85;'>
                        <div style='display: flex; justify-content: space-between;'>
                            <strong style='font-size: 1.1rem; color: #cbd5e1;'>{sym} - {action}</strong>
                            <span style='color: #64748b;'>{ts}</span>
                        </div>
                        <div style='color: #ef4444; font-size: 0.9rem; margin-top: 8px;'><strong>Rejection:</strong> {reason}</div>
                        <div style='color: #38bdf8; font-size: 0.85rem; margin-top: 4px;'>Event: {item.get('event', 'Unknown')}</div>
                        <div style='color: #94a3b8; margin-top: 8px; font-size: 0.9rem;'><em>Synthesis: {item.get('trader_synthesis', 'No synthesis')}</em></div>
                    </div>
                    """, unsafe_allow_html=True)

        with tab4:
            st.markdown("<div style='background-color: rgba(239, 68, 68, 0.1); border: 1px solid rgba(239, 68, 68, 0.3); color: #ef4444; padding: 12px; border-radius: 6px; margin-bottom: 20px; font-size: 0.9rem;'><strong>NOTE:</strong> System Failures (e.g. AI API timeouts, stale data, malformed schema) are aborted evaluations. They are neither live trades nor counterfactual considerations.</div>", unsafe_allow_html=True)
            if not failures:
                st.markdown("<div style='padding: 20px; color: #94a3b8; text-align: center;'>No system failures recorded.</div>", unsafe_allow_html=True)
            else:
                for item in reversed(failures):
                    ts = format_time(item.get("timestamp"))
                    sym = item.get("symbol", "")
                    action = item.get("action", "")
                    reason = item.get("reason", "")
                    st.markdown(f"""
                    <div class='premium-card' style='border-left: 2px solid #ef4444;'>
                        <div style='display: flex; justify-content: space-between;'>
                            <strong style='font-size: 1.1rem; color: #cbd5e1;'>{sym} - {action}</strong>
                            <span style='color: #64748b;'>{ts}</span>
                        </div>
                        <div style='color: #ef4444; font-size: 0.9rem; margin-top: 8px;'><strong>Error:</strong> {reason}</div>
                        <div style='color: #38bdf8; font-size: 0.85rem; margin-top: 4px;'>Event: {item.get('event', 'Unknown')}</div>
                    </div>
                    """, unsafe_allow_html=True)


render_dashboard_body()
