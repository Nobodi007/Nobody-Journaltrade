"""
Nobody Trade Journal — Cloud Edition
เชื่อม MT4/MT5 ผ่าน MetaApi + MetaStats แบบ REST
รันบน Streamlit Cloud ได้ทันที ไม่ต้องมี Windows VPS

streamlit run app.py
"""

from __future__ import annotations

import json
import uuid

import requests
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from core.analytics import (
    by_group,
    equity_series,
    monthly_table,
    plan_discipline,
    summary,
)
from core.charts import (
    equity_chart,
    hour_heat,
    monthly_chart,
    pnl_bars,
    symbol_pie,
)
from core.config import (
    APP_NAME,
    APP_VERSION,
    CSS,
    EMOTIONS,
    MISTAKES,
    REGIONS,
    SETUPS,
    TIMEFRAMES,
    get_region,
    get_token,
    secret,
)
from core.metaapi import MetaApiClient, MetaApiError, default_range
from core.storage import NoteStore, merge_notes
from core.transform import (
    deals_to_trades,
    metastats_trades_to_df,
    positions_to_df,
)

st.set_page_config(
    page_title=APP_NAME,
    page_icon="📓",
    layout="wide",
    initial_sidebar_state="expanded",
)
st.markdown(CSS, unsafe_allow_html=True)

APP_UI_CSS = r"""
<style>
/* =========================================================
   Nobody Trade Journal — UI ONLY
   No data / API / trading logic changes.
   ========================================================= */
:root {
  --nj-bg:#0d1015;
  --nj-panel:#151922;
  --nj-panel-2:#191e28;
  --nj-border:#29303c;
  --nj-border-soft:#202631;
  --nj-text:#eef2f7;
  --nj-muted:#8d97a8;
  --nj-green:#20d68a;
  --nj-red:#ff6174;
  --nj-blue:#78a9ff;
}

/* Main canvas */
.block-container {
  max-width: 1480px !important;
  padding: 1.55rem 2.2rem 3.5rem !important;
}
[data-testid="stAppViewContainer"] { background:var(--nj-bg); }
[data-testid="stHeader"] { background:transparent !important; }

/* Typography */
.nj-app-title { font-size:1.08rem; font-weight:850; letter-spacing:-.02em; margin:0; color:var(--nj-text); }
.nj-app-sub { color:var(--nj-muted); font-size:.72rem; margin-top:3px; }
.nj-section-title { font-size:1.55rem; font-weight:820; letter-spacing:-.025em; margin:.15rem 0 .2rem; color:var(--nj-text); }
.nj-nav-label { color:#697486; text-transform:uppercase; letter-spacing:.11em; font-size:.64rem; font-weight:850; margin:1rem 0 .45rem; }
.nj-muted { color:var(--nj-muted); font-size:.72rem; }

/* Sidebar */
section[data-testid="stSidebar"] {
  background:#10131a !important;
  border-right:1px solid #252b35;
}
section[data-testid="stSidebar"] .block-container {
  padding:1.25rem .85rem 1.4rem !important;
}
section[data-testid="stSidebar"] [data-testid="stRadio"] > div {
  gap:5px !important;
}
section[data-testid="stSidebar"] [data-testid="stRadio"] label {
  min-height:40px !important;
  border:1px solid transparent !important;
  border-radius:11px !important;
  padding:8px 11px !important;
  transition:background .15s ease,border-color .15s ease;
}
section[data-testid="stSidebar"] [data-testid="stRadio"] label:hover {
  background:#1b202a !important;
  border-color:#282f3a !important;
}
section[data-testid="stSidebar"] [data-testid="stRadio"] p {
  font-size:.88rem !important;
  font-weight:680 !important;
}
section[data-testid="stSidebar"] hr { border-color:#272d37 !important; margin:.9rem 0 !important; }

.nj-side-card {
  background:linear-gradient(145deg,#171b23,#13161d);
  border:1px solid var(--nj-border-soft);
  border-radius:12px;
  padding:11px 12px;
  margin:8px 0;
}
.nj-side-muted { color:#737e90; font-size:.66rem; letter-spacing:.08em; font-weight:750; }
.nj-side-value { color:#e8edf4; font-size:.83rem; font-weight:720; margin-top:3px; line-height:1.35; }

/* Cards / hero */

/* Gold Trading Workspace */
.gold-workspace-head {
  display:flex; justify-content:space-between; align-items:center; gap:16px;
  padding:14px 16px; margin:4px 0 12px;
  border:1px solid rgba(148,163,184,.16); border-radius:14px;
  background:linear-gradient(135deg, rgba(22,29,40,.96), rgba(12,17,24,.96));
}
.gold-workspace-title { font-size:1.18rem; font-weight:800; color:#f3f6fa; }
.gold-workspace-subtitle { margin-top:3px; color:#8e9bad; font-size:.82rem; }
.gold-workspace-badge {
  flex:0 0 auto; padding:7px 10px; border-radius:999px;
  border:1px solid rgba(32,214,138,.25); background:rgba(32,214,138,.07);
  color:#9ce9c4; font-size:.74rem; font-weight:750;
}
.gold-workspace-note {
  display:flex; gap:10px; align-items:flex-start; margin:10px 0 18px; padding:11px 14px;
  border:1px solid rgba(148,163,184,.14); border-radius:12px;
  background:rgba(17,24,34,.72); color:#9ba7b7; font-size:.79rem;
}
.gold-workspace-note b { display:block; color:#e5eaf0; margin-bottom:2px; }
.gold-workspace-note span { display:block; }
@media (max-width: 700px) {
  .gold-workspace-head { align-items:flex-start; flex-direction:column; }
  .gold-workspace-badge { width:max-content; }
}

.nj-hero {
  background:radial-gradient(circle at top right,rgba(83,126,205,.14),transparent 38%),linear-gradient(145deg,#1a202b,#12151c);
  border:1px solid #2a3240;
  border-radius:18px;
  padding:25px 27px;
  margin:0 0 20px;
  box-shadow:0 10px 35px rgba(0,0,0,.14);
}
.nj-hero h2 { margin:0 0 7px; font-size:1.48rem; letter-spacing:-.02em; }
.nj-hero p { margin:0; color:#9aa5b6; line-height:1.6; }
.nj-empty-icon { font-size:2rem; margin-bottom:5px; }
.nj-status { display:inline-flex; align-items:center; gap:7px; padding:5px 10px; border-radius:999px; background:rgba(32,214,138,.1); color:var(--nj-green); border:1px solid rgba(32,214,138,.22); font-size:.72rem; font-weight:750; }
.nj-dot { width:7px; height:7px; border-radius:50%; background:var(--nj-green); display:inline-block; box-shadow:0 0 9px rgba(32,214,138,.55); }

/* Metrics */
[data-testid="stMetric"] {
  background:linear-gradient(145deg,#171b23,#141820) !important;
  border:1px solid var(--nj-border) !important;
  border-radius:14px !important;
  padding:13px 15px !important;
  min-height:82px;
}
[data-testid="stMetricLabel"] { color:#8b95a6 !important; font-size:.73rem !important; }
[data-testid="stMetricValue"] { color:#f0f3f8 !important; font-weight:780 !important; letter-spacing:-.025em; }
[data-testid="stMetricDelta"] { font-size:.72rem !important; }

/* Open-position cards */
.nj-card {
  background:#151922;
  border:1px solid #29313e;
  border-radius:14px;
  padding:14px 15px;
  margin:9px 0;
}
.nj-open { transition:transform .12s ease,border-color .12s ease,background .12s ease; }
.nj-open:hover { transform:translateY(-1px); border-color:#394454; background:#171c25; }
.nj-tag {
  display:inline-block;
  padding:3px 7px;
  border-radius:7px;
  background:#202632;
  color:#b9c4d4;
  font-size:.67rem;
  font-weight:750;
}
.nj-pos,.nj-win { color:var(--nj-green) !important; }
.nj-neg,.nj-loss { color:var(--nj-red) !important; }

/* Buttons / controls */
.stButton > button {
  border-radius:10px !important;
  border-color:#303846 !important;
  min-height:38px !important;
  font-weight:680 !important;
}
.stButton > button:hover { border-color:#536176 !important; }
.stTextInput input,.stTextArea textarea,.stSelectbox [data-baseweb="select"] > div,.stMultiSelect [data-baseweb="select"] > div {
  border-radius:10px !important;
}

/* Tables */
[data-testid="stDataFrame"] {
  border:1px solid #28303b;
  border-radius:12px;
  overflow:hidden;
}

/* Reduce excess Streamlit vertical gaps */
[data-testid="stVerticalBlock"] { gap:.55rem; }

/* Mobile */
@media (max-width: 900px) {
  .block-container { padding:.85rem .8rem 4rem !important; }
  .nj-section-title { font-size:1.28rem; }
  .nj-hero { padding:18px 16px; border-radius:15px; }
  .nj-hero h2 { font-size:1.2rem; }
  [data-testid="stMetric"] { min-height:70px; padding:9px 10px !important; }
  [data-testid="stMetricValue"] { font-size:1.02rem !important; }
  [data-testid="stMetricLabel"] { font-size:.66rem !important; }
  .nj-card { padding:12px 11px; }
  .nj-open .stColumn { min-width:0 !important; }
  .nj-open [data-testid="stMarkdownContainer"] { overflow-wrap:anywhere; }
  section[data-testid="stSidebar"] .block-container { padding:.8rem .7rem 1rem !important; }
}

@media (max-width: 640px) {
  .block-container { padding:.65rem .58rem 4rem !important; }
  .nj-app-title { font-size:1rem; }
  .nj-section-title { font-size:1.16rem; }
  .nj-card { border-radius:12px; margin:7px 0; }
  .nj-muted { font-size:.65rem; }
  .nj-tag { font-size:.62rem; padding:3px 6px; }
  .stButton > button { min-height:36px !important; font-size:.82rem !important; }
  [data-testid="stDataFrame"] { font-size:.75rem; }
}
</style>
"""
st.markdown(APP_UI_CSS, unsafe_allow_html=True)


# =========================================================
# CACHED FETCHERS
# =========================================================


@st.cache_resource(show_spinner=False)
def get_client(token: str, region: str) -> MetaApiClient:
    return MetaApiClient(token, region)


@st.cache_resource(show_spinner=False)
def get_store() -> NoteStore:
    return NoteStore()


def get_supabase_config() -> tuple[str, str]:
    """อ่าน Supabase URL + publishable/anon key จาก Streamlit Secrets/env."""
    return (
        secret("SUPABASE_URL", "").strip().rstrip("/"),
        secret("SUPABASE_KEY", "").strip(),
    )


@st.cache_data(ttl=10, show_spinner=False)
def fetch_latest_mt5_snapshot() -> dict:
    """อ่าน snapshot ล่าสุดจาก NobodyCollector -> Supabase."""
    base_url, api_key = get_supabase_config()
    if not base_url or not api_key:
        return {}

    url = (
        f"{base_url}/rest/v1/mt5_account_snapshots"
        "?select=*&order=collected_at.desc&limit=1"
    )
    headers = {
        "apikey": api_key,
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json",
    }
    try:
        r = requests.get(url, headers=headers, timeout=10)
        r.raise_for_status()
        rows = r.json()
        return rows[0] if isinstance(rows, list) and rows else {}
    except Exception as exc:
        return {"_error": str(exc)}



@st.cache_data(ttl=5, show_spinner=False)
def fetch_supabase_rows(table: str, params: tuple[tuple[str, str], ...] = ()) -> list[dict]:
    """อ่านตาราง MT5 จาก Supabase Data API โดยใช้ publishable/anon key."""
    base_url, api_key = get_supabase_config()
    if not base_url or not api_key:
        return []

    query = [("select", "*")] + list(params)
    headers = {
        "apikey": api_key,
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json",
    }
    try:
        r = requests.get(
            f"{base_url}/rest/v1/{table}",
            headers=headers,
            params=query,
            timeout=10,
        )
        r.raise_for_status()
        data = r.json()
        return data if isinstance(data, list) else []
    except Exception as exc:
        st.session_state[f"supabase_error_{table}"] = str(exc)
        return []


def _account_filter(snapshot: dict) -> tuple[tuple[str, str], ...]:
    login = snapshot.get("login")
    server = snapshot.get("server")
    filters: list[tuple[str, str]] = []
    if login not in (None, ""):
        filters.append(("login", f"eq.{login}"))
    if server not in (None, ""):
        filters.append(("server", f"eq.{server}"))
    return tuple(filters)


@st.cache_data(ttl=5, show_spinner=False)
def fetch_mt5_positions_supabase(snapshot: dict) -> pd.DataFrame:
    rows = fetch_supabase_rows(
        "mt5_positions",
        _account_filter(snapshot) + (("order", "last_seen_at.desc"),),
    )
    return pd.DataFrame(rows)


@st.cache_data(ttl=5, show_spinner=False)
def fetch_mt5_pending_supabase(snapshot: dict) -> pd.DataFrame:
    rows = fetch_supabase_rows(
        "mt5_pending_orders",
        _account_filter(snapshot) + (("order", "last_seen_at.desc"),),
    )
    return pd.DataFrame(rows)


@st.cache_data(ttl=10, show_spinner=False)
def fetch_mt5_history_supabase(snapshot: dict) -> pd.DataFrame:
    rows = fetch_supabase_rows(
        "mt5_trade_history",
        _account_filter(snapshot) + (("order", "deal_time.desc"), ("limit", "100")),
    )
    return pd.DataFrame(rows)


def _num(v, default=0.0):
    try:
        if v is None or v == "":
            return default
        return float(v)
    except (TypeError, ValueError):
        return default


def render_supabase_positions(df: pd.DataFrame) -> None:
    """Live open-position monitor from MT5 -> Supabase."""
    st.markdown("### 🟢 Open Positions")
    if df.empty:
        st.info("ไม่มีไม้เปิดอยู่ตอนนี้")
        st.caption("เมื่อมี Position ใน MT5 รายการจะปรากฏที่นี่อัตโนมัติ")
        return

    work = df.copy()
    for col in ("volume", "open_price", "current_price", "stop_loss", "take_profit", "profit", "swap", "commission"):
        if col in work.columns:
            work[col] = pd.to_numeric(work[col], errors="coerce").fillna(0.0)

    side = work.get("side", pd.Series(index=work.index, dtype="object")).astype(str).str.upper()
    buy_mask = side.str.contains("BUY", na=False)
    sell_mask = side.str.contains("SELL", na=False)
    total_profit = float(work.get("profit", pd.Series(dtype=float)).sum())
    total_volume = float(work.get("volume", pd.Series(dtype=float)).sum())
    buy_volume = float(work.loc[buy_mask, "volume"].sum()) if "volume" in work.columns else 0.0
    sell_volume = float(work.loc[sell_mask, "volume"].sum()) if "volume" in work.columns else 0.0
    total_swap = float(work.get("swap", pd.Series(dtype=float)).sum())
    total_commission = float(work.get("commission", pd.Series(dtype=float)).sum())

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Open Positions", f"{len(work)}")
    c2.metric("Floating P&L", f"{total_profit:+,.2f}")
    c3.metric("Exposure (Lots)", f"{total_volume:,.2f}")
    c4.metric("BUY / SELL", f"{buy_volume:.2f} / {sell_volume:.2f}")

    c5, c6, c7 = st.columns(3)
    c5.metric("Swap", f"{total_swap:+,.2f}")
    c6.metric("Commission", f"{total_commission:+,.2f}")
    c7.metric("Net Floating", f"{total_profit + total_swap + total_commission:+,.2f}")

    st.markdown("#### Live Position Monitor")
    for _, row in work.iterrows():
        symbol = str(row.get("symbol") or "-")
        row_side = str(row.get("side") or "-").upper()
        lots = _num(row.get("volume"))
        open_px = _num(row.get("open_price"))
        current_px = _num(row.get("current_price"))
        sl = _num(row.get("stop_loss"), 0.0)
        tp = _num(row.get("take_profit"), 0.0)
        profit = _num(row.get("profit"))
        swap = _num(row.get("swap"))
        commission = _num(row.get("commission"))
        ticket = str(row.get("ticket") or "-")
        comment = str(row.get("comment") or "").strip()
        pnl_class = "#0ecb81" if profit >= 0 else "#f6465d"
        side_icon = "🟢" if "BUY" in row_side else ("🔴" if "SELL" in row_side else "⚪")
        sl_text = f"{sl:,.5f}" if sl else "—"
        tp_text = f"{tp:,.5f}" if tp else "—"
        comment_html = f" · {comment}" if comment else ""
        card = f"""<div style="border:1px solid #2b3139;border-radius:12px;padding:13px 15px;margin:0 0 9px 0;background:#15181e;">
<div style="display:flex;justify-content:space-between;gap:12px;align-items:center;"><div style="font-weight:750;font-size:16px;">{side_icon} {symbol} <span style="opacity:.72;font-size:13px;">{row_side} · {lots:.2f} lot</span></div><div style="font-weight:800;color:{pnl_class};font-size:16px;">{profit:+,.2f}</div></div>
<div style="display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px;margin-top:10px;font-size:12px;"><div><span style="opacity:.55;">Entry</span><br><b>{open_px:,.5f}</b></div><div><span style="opacity:.55;">Current</span><br><b>{current_px:,.5f}</b></div><div><span style="opacity:.55;">SL</span><br><b>{sl_text}</b></div><div><span style="opacity:.55;">TP</span><br><b>{tp_text}</b></div></div>
<div style="margin-top:8px;opacity:.58;font-size:11px;">Ticket {ticket} · Swap {swap:+,.2f} · Commission {commission:+,.2f}{comment_html}</div>
</div>"""
        st.markdown(card, unsafe_allow_html=True)

    with st.expander("รายละเอียด Position ทั้งหมด", expanded=False):
        preferred = ["ticket", "symbol", "side", "volume", "open_price", "current_price", "stop_loss", "take_profit", "profit", "swap", "commission", "open_time", "last_seen_at", "comment"]
        cols = [c for c in preferred if c in work.columns]
        view = work[cols].copy()
        rename = {"ticket":"Ticket", "symbol":"Symbol", "side":"Side", "volume":"Lots", "open_price":"Open", "current_price":"Current", "stop_loss":"SL", "take_profit":"TP", "profit":"Profit", "swap":"Swap", "commission":"Commission", "open_time":"Open Time", "last_seen_at":"Last Seen", "comment":"Comment"}
        st.dataframe(view.rename(columns=rename), use_container_width=True, hide_index=True)


def render_supabase_pending(df: pd.DataFrame) -> None:
    st.markdown("### 🟡 Pending Orders")
    if df.empty:
        st.success("ไม่มี Pending Orders", icon="✅")
        return

    preferred = [
        "ticket", "symbol", "order_type", "volume_initial", "volume_current",
        "price_open", "price_current", "stop_loss", "take_profit",
        "state", "time_setup", "last_seen_at", "comment",
    ]
    cols = [c for c in preferred if c in df.columns]
    view = df[cols].copy()
    rename = {
        "ticket":"Ticket", "symbol":"Symbol", "order_type":"Type",
        "volume_initial":"Lots Initial", "volume_current":"Lots Current",
        "price_open":"Price", "price_current":"Current", "stop_loss":"SL",
        "take_profit":"TP", "state":"State", "time_setup":"Setup Time",
        "last_seen_at":"Last Seen", "comment":"Comment",
    }
    st.dataframe(view.rename(columns=rename), use_container_width=True, hide_index=True)


def render_supabase_history(df: pd.DataFrame) -> None:
    st.markdown("### 📜 Recent Trade History")
    if df.empty:
        st.info("ยังไม่มี Trade / Deal History ใน Supabase")
        return

    preferred = [
        "deal_time", "deal_ticket", "order_ticket", "position_id", "symbol",
        "deal_type", "entry_type", "volume", "price", "profit",
        "commission", "swap", "fee", "comment", "reason",
    ]
    cols = [c for c in preferred if c in df.columns]
    view = df[cols].copy()
    rename = {
        "deal_time":"Time", "deal_ticket":"Deal", "order_ticket":"Order",
        "position_id":"Position", "symbol":"Symbol", "deal_type":"Type",
        "entry_type":"Entry", "volume":"Lots", "price":"Price",
        "profit":"Profit", "commission":"Commission", "swap":"Swap",
        "fee":"Fee", "comment":"Comment", "reason":"Reason",
    }
    st.dataframe(view.rename(columns=rename), use_container_width=True, hide_index=True)


def render_mt5_snapshot(snapshot: dict) -> None:
    """แสดงสถานะ MT5 จาก snapshot โดยไม่แตะ MetaApi."""
    if not snapshot:
        st.info("ยังไม่พบข้อมูล MT5 จาก Supabase")
        return
    if snapshot.get("_error"):
        st.error(f"อ่าน MT5 จาก Supabase ไม่สำเร็จ: {snapshot['_error']}")
        return

    cur = str(snapshot.get("currency") or "")
    collected = str(snapshot.get("collected_at") or "")
    login = str(snapshot.get("login") or "-")
    server = str(snapshot.get("server") or "-")
    balance = float(snapshot.get("balance") or 0)
    equity = float(snapshot.get("equity") or 0)
    margin = float(snapshot.get("margin") or 0)
    free_margin = float(snapshot.get("free_margin") or 0)

    st.markdown("### 🟢 MT5 Live — Supabase")
    st.caption(f"Login {login} · {server} · อัปเดตล่าสุด {collected}")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric(f"Balance ({cur})" if cur else "Balance", f"{balance:,.2f}")
    c2.metric(f"Equity ({cur})" if cur else "Equity", f"{equity:,.2f}")
    c3.metric(f"Margin ({cur})" if cur else "Margin", f"{margin:,.2f}")
    c4.metric(f"Free Margin ({cur})" if cur else "Free Margin", f"{free_margin:,.2f}")


@st.cache_data(ttl=300, show_spinner=False)
def fetch_accounts(token: str, region: str) -> list[dict]:
    return get_client(token, region).list_accounts()


@st.cache_data(ttl=60, show_spinner=False)
def fetch_metrics(token: str, region: str, aid: str) -> dict:
    return get_client(token, region).metrics(aid)


@st.cache_data(ttl=60, show_spinner=False)
def fetch_history(token: str, region: str, aid: str, days: int) -> pd.DataFrame:
    c = get_client(token, region)
    start, end = default_range(days)
    try:
        raw = c.historical_trades(aid, start, end)
        df = metastats_trades_to_df(raw)
        if not df.empty:
            return df
    except MetaApiError as e:
        if e.status not in (403, 404):
            raise
    # fallback: ประกอบไม้จาก deals ดิบ
    return deals_to_trades(c.deals_by_time(aid, start, end))


@st.cache_data(ttl=30, show_spinner=False)
def fetch_positions(token: str, region: str, aid: str) -> pd.DataFrame:
    return positions_to_df(get_client(token, region).positions(aid))


@st.cache_data(ttl=30, show_spinner=False)
def fetch_account_info(token: str, region: str, aid: str) -> dict:
    try:
        return get_client(token, region).account_information(aid)
    except MetaApiError:
        return {}


def clear_cache() -> None:
    for fn in (
        fetch_accounts, fetch_metrics, fetch_history,
        fetch_positions, fetch_account_info,
        fetch_latest_mt5_snapshot, fetch_supabase_rows,
        fetch_mt5_positions_supabase, fetch_mt5_pending_supabase,
        fetch_mt5_history_supabase,
    ):
        fn.clear()


# =========================================================
# GATE
# =========================================================


def gate() -> bool:
    pw = secret("APP_PASSWORD")
    if not pw:
        return True
    if st.session_state.get("authed"):
        return True

    st.markdown(f"## {APP_NAME}")
    entered = st.text_input("รหัสเข้าใช้งาน", type="password")
    if st.button("เข้าสู่ระบบ", type="primary"):
        if entered == pw:
            st.session_state["authed"] = True
            st.rerun()
        else:
            st.error("รหัสไม่ถูกต้อง")
    return False


# =========================================================
# PAGES
# =========================================================


def page_connect(token: str, region: str) -> None:
    st.subheader("เชื่อมต่อบัญชี MetaTrader")

    st.info(
        "แนะนำให้ใช้ **Investor Password** — เป็นรหัสสิทธิ์อ่านอย่างเดียว "
        "ดูพอร์ตและประวัติได้ แต่ส่งคำสั่งเทรดไม่ได้ ปลอดภัยกว่ารหัสหลักมาก",
        icon="🔒",
    )

    with st.form("add_account"):
        c1, c2 = st.columns(2)
        name = c1.text_input("ชื่อเรียกบัญชี", placeholder="Live — IC Markets")
        platform = c2.selectbox("Platform", ["mt5", "mt4"])

        c1, c2, c3 = st.columns(3)
        login = c1.text_input("Login", placeholder="12345678")
        server = c2.text_input("Server", placeholder="ICMarketsSC-Live")
        acc_region = c3.selectbox("Region", REGIONS, index=REGIONS.index(region))

        password = st.text_input("Investor Password", type="password")

        if st.form_submit_button("เพิ่มและเชื่อมต่อ", type="primary", use_container_width=True):
            if not all([name, login, server, password]):
                st.error("กรอกข้อมูลให้ครบทุกช่อง")
            else:
                try:
                    with st.spinner("กำลังสร้างบัญชีบน MetaApi..."):
                        c = get_client(token, region)
                        res = c.create_account(
                            name=name, login=login, password=password,
                            server=server, platform=platform, region=acc_region,
                        )
                        aid = res.get("id") or res.get("_id")

                    with st.spinner("กำลัง deploy และรอเชื่อมต่อโบรกเกอร์ (1–3 นาที)..."):
                        c.deploy(aid)
                        state = c.wait_deployed(aid, timeout_sec=300)

                    clear_cache()
                    if state.get("connectionStatus") == "CONNECTED":
                        st.success(f"เชื่อมต่อสำเร็จ · Account ID: {aid}")
                    else:
                        st.warning(
                            f"สร้างบัญชีแล้ว (ID: {aid}) แต่ยังไม่ CONNECTED — "
                            f"สถานะปัจจุบัน {state.get('state')} / "
                            f"{state.get('connectionStatus')} กดรีเฟรชอีกครั้งในอีกสักครู่"
                        )
                except MetaApiError as e:
                    st.error(f"ไม่สำเร็จ: {e.message}")

    st.divider()
    st.markdown("### บัญชีที่มีอยู่")
    try:
        accs = fetch_accounts(token, region)
    except MetaApiError as e:
        st.error(f"ดึงรายการบัญชีไม่ได้: {e.message}")
        return

    if not accs:
        st.info("ยังไม่มีบัญชีใน MetaApi")
        return

    rows = [
        {
            "Name": a.get("name"),
            "Login": a.get("login"),
            "Server": a.get("server"),
            "Platform": a.get("platform"),
            "State": a.get("state"),
            "Connection": a.get("connectionStatus"),
            "MetaStats": a.get("metastatsApiEnabled"),
            "ID": a.get("_id") or a.get("id"),
        }
        for a in accs
    ]
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    c1, c2, c3 = st.columns(3)
    ids = [r["ID"] for r in rows]
    target = c1.selectbox("เลือกบัญชี", ids, key="mgmt_target")
    if c2.button("เปิด MetaStats", use_container_width=True):
        try:
            get_client(token, region).enable_metastats(target)
            clear_cache()
            st.success("เปิด MetaStats แล้ว")
        except MetaApiError as e:
            st.error(e.message)
    if c3.button("Undeploy (หยุดคิดค่าบริการ)", use_container_width=True):
        try:
            get_client(token, region).undeploy(target)
            clear_cache()
            st.success("undeploy แล้ว")
        except MetaApiError as e:
            st.error(e.message)


def page_supabase_dashboard(snapshot: dict) -> None:
    """Free MT5 dashboard: MT5 -> NobodyCollector -> Supabase -> Streamlit."""
    st.markdown('<div class="nj-section-title">Portfolio Overview</div>', unsafe_allow_html=True)
    st.caption("ข้อมูล MT5 จาก NobodyCollector → Supabase")

    if not snapshot:
        st.warning("ยังไม่พบ Account Snapshot จาก Supabase")
        return
    if snapshot.get("_error"):
        st.error(f"อ่าน MT5 จาก Supabase ไม่สำเร็จ: {snapshot['_error']}")
        return

    render_mt5_snapshot(snapshot)

    pos = fetch_mt5_positions_supabase(snapshot)
    pending = fetch_mt5_pending_supabase(snapshot)
    history = fetch_mt5_history_supabase(snapshot)

    st.divider()
    render_supabase_positions(pos)

    st.divider()
    render_supabase_pending(pending)

    st.divider()
    render_supabase_history(history)

    errors = []
    for table in ("mt5_positions", "mt5_pending_orders", "mt5_trade_history"):
        err = st.session_state.get(f"supabase_error_{table}")
        if err:
            errors.append(f"{table}: {err}")
    if errors:
        st.warning("Supabase Data API บางตารางอ่านไม่ได้: " + " | ".join(errors))

    st.divider()
    st.success(
        "MT5 → NobodyCollector → Supabase → Nobody Trade Journal ทำงานแล้ว",
        icon="✅",
    )
    st.caption("Account / Positions / Pending / Trade History อ่านจาก Supabase โดยตรง — ไม่ใช้ MetaApi")


def page_dashboard(df: pd.DataFrame, metrics: dict, info: dict) -> None:
    s = summary(df, metrics)
    cur = info.get("currency", "")

    st.markdown('<div class="nj-section-title">Portfolio Overview</div>', unsafe_allow_html=True)
    st.caption("ภาพรวมผลการเทรดจากบัญชีที่เชื่อมต่อ")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric(f"Balance ({cur})" if cur else "Balance", f"{s['balance']:,.2f}")
    c2.metric("Equity", f"{s['equity']:,.2f}")
    c3.metric("กำไรสุทธิ", f"{s['net']:+,.2f}")
    c4.metric("Win Rate", f"{s['win_rate']:.1f}%", f"{int(s['wins'])}W / {int(s['losses'])}L")

    if s["n"] == 0:
        st.markdown(
            '<div class="nj-hero"><div class="nj-empty-icon">📊</div>'
            '<h2>ยังไม่มีไม้ที่ปิดในช่วงเวลานี้</h2>'
            '<p>เมื่อมีประวัติการเทรดแล้ว ระบบจะแสดง Equity Curve, P&L, Win Rate และสถิติการเทรดตรงนี้</p></div>',
            unsafe_allow_html=True,
        )
        return

    with st.expander("สถิติเพิ่มเติม", expanded=False):
        c1, c2, c3, c4 = st.columns(4)
        pf = s["profit_factor"]
        c1.metric("Profit Factor", "∞" if pf == float("inf") else f"{pf:.2f}")
        c2.metric("Max Drawdown", f"{s['max_dd_pct']:.2f}%", f"{s['max_dd']:,.2f}")
        c3.metric("Expectancy/ไม้", f"{s['expectancy']:+,.2f}")
        c4.metric("Payoff Ratio", f"{s['payoff']:.2f}")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("ไม้ทั้งหมด", int(s["n"]))
        c2.metric("Sharpe", f"{s['sharpe']:.2f}")
        c3.metric("ค่าธรรมเนียมรวม", f"{s['costs']:,.2f}")
        c4.metric("Lots รวม", f"{s['lots']:,.2f}")

    start_bal = s["balance"] - s["net"] if s["balance"] else 0.0
    st.plotly_chart(equity_chart(equity_series(df, start_bal)), use_container_width=True)
    c1, c2 = st.columns([1.4, 1])
    c1.plotly_chart(pnl_bars(df), use_container_width=True)
    c2.plotly_chart(symbol_pie(df), use_container_width=True)
    st.plotly_chart(monthly_chart(monthly_table(df)), use_container_width=True)
    st.plotly_chart(hour_heat(df), use_container_width=True)

    st.divider()
    st.markdown("### วินัยกับผลลัพธ์")
    pd_tbl = plan_discipline(df)
    if not pd_tbl.empty:
        st.dataframe(pd_tbl, use_container_width=True, hide_index=True)
        if len(pd_tbl) == 2:
            a = pd_tbl.set_index("ประเภท")["Net"]
            if a.get("นอกแผน", 0) < 0 < a.get("ตามแผน", 0):
                st.warning(f"ไม้นอกแผนทำให้เสีย {abs(a['นอกแผน']):,.2f} ขณะที่ไม้ตามแผนได้ {a['ตามแผน']:,.2f} — ตัดไม้นอกแผนออก ผลจะดีขึ้นทันที")

    st.divider()
    c1, c2 = st.columns(2)
    c1.markdown("#### แยกตาม Symbol")
    c1.dataframe(by_group(df, "symbol", "Symbol"), use_container_width=True, hide_index=True)
    c2.markdown("#### แยกตามทิศทาง")
    c2.dataframe(by_group(df, "direction", "ทิศทาง"), use_container_width=True, hide_index=True)
    c1, c2 = st.columns(2)
    c1.markdown("#### แยกตามวันในสัปดาห์")
    c1.dataframe(by_group(df, "weekday", "วัน"), use_container_width=True, hide_index=True)
    c2.markdown("#### แยกตาม Setup ที่บันทึกเอง")
    g = by_group(df[df["setup"].astype(str) != ""], "setup", "Setup")
    if g.empty:
        c2.caption("ยังไม่ได้ติด Setup ให้ไม้ไหน — ไปที่หน้า Journal")
    else:
        c2.dataframe(g, use_container_width=True, hide_index=True)


def page_live_monitor(snapshot: dict) -> None:
    """Live trading monitor using only the existing MT5 -> Supabase data path."""
    st.markdown('<div class="nj-section-title">Live Trading Monitor</div>', unsafe_allow_html=True)
    st.caption("MT5 → NobodyCollector → Supabase · สำหรับดูสถานะบัญชี, Position และ Pending Order")

    top1, top2, top3 = st.columns([1.1, 1.1, 4.8])
    with top1:
        if st.button("↻ รีเฟรช", use_container_width=True, key="live_monitor_refresh"):
            clear_cache()
            st.rerun()
    with top2:
        st.caption("ข้อมูลสดจาก Collector")

    if not snapshot:
        st.warning("ยังไม่พบ Account Snapshot จาก Supabase")
        return
    if snapshot.get("_error"):
        st.error(f"อ่าน MT5 จาก Supabase ไม่สำเร็จ: {snapshot['_error']}")
        return

    cur = str(snapshot.get("currency") or "")
    balance = _num(snapshot.get("balance"))
    equity = _num(snapshot.get("equity"))
    margin = _num(snapshot.get("margin"))
    free_margin = _num(snapshot.get("free_margin"))
    floating = equity - balance
    collected = str(snapshot.get("collected_at") or "-")
    login = str(snapshot.get("login") or "-")
    server = str(snapshot.get("server") or "-")

    status_html = (
        '<div class="nj-card" style="margin:.35rem 0 1rem 0;">'
        '<div style="display:flex;justify-content:space-between;gap:12px;align-items:center;flex-wrap:wrap;">'
        f'<div><b>🟢 MT5 Connected</b><div class="nj-muted">Login {login} · {server}</div></div>'
        f'<div style="text-align:right;"><div class="nj-muted">Snapshot ล่าสุด</div><b>{collected}</b></div>'
        '</div></div>'
    )
    st.markdown(status_html, unsafe_allow_html=True)

    pos = fetch_mt5_positions_supabase(snapshot)
    pending = fetch_mt5_pending_supabase(snapshot)
    history = fetch_mt5_history_supabase(snapshot)

    total_lots = _num(pos["volume"].sum()) if not pos.empty and "volume" in pos.columns else 0.0
    floating_pos = _num(pos["profit"].sum()) if not pos.empty and "profit" in pos.columns else 0.0
    buy_lots = 0.0
    sell_lots = 0.0
    if not pos.empty and "side" in pos.columns and "volume" in pos.columns:
        sides = pos["side"].astype(str).str.upper()
        buy_lots = _num(pos.loc[sides.str.contains("BUY", na=False), "volume"].sum())
        sell_lots = _num(pos.loc[sides.str.contains("SELL", na=False), "volume"].sum())

    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("Balance", f"{balance:,.2f} {cur}".strip())
    c2.metric("Equity", f"{equity:,.2f} {cur}".strip())
    c3.metric("Floating P&L", f"{floating:+,.2f}")
    c4.metric("Margin", f"{margin:,.2f}")
    c5.metric("Free Margin", f"{free_margin:,.2f}")
    c6.metric("Open Lots", f"{total_lots:,.2f}")

    st.divider()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Open Positions", f"{len(pos)}")
    c2.metric("BUY Lots", f"{buy_lots:,.2f}")
    c3.metric("SELL Lots", f"{sell_lots:,.2f}")
    c4.metric("Position P&L", f"{floating_pos:+,.2f}")

    render_supabase_positions(pos)

    st.divider()
    render_supabase_pending(pending)

    st.divider()
    st.markdown("### 📜 Recent Trades")
    if history.empty:
        st.info("ยังไม่มี Trade / Deal History")
    else:
        preferred = ["deal_time", "deal_ticket", "symbol", "deal_type", "entry_type", "volume", "price", "profit", "commission", "swap", "comment"]
        cols = [c for c in preferred if c in history.columns]
        view = history[cols].head(20).copy()
        rename = {
            "deal_time":"Time", "deal_ticket":"Deal", "symbol":"Symbol", "deal_type":"Type",
            "entry_type":"Entry", "volume":"Lots", "price":"Price", "profit":"Profit",
            "commission":"Commission", "swap":"Swap", "comment":"Comment",
        }
        st.dataframe(view.rename(columns=rename), use_container_width=True, hide_index=True)


def page_exposure(snapshot: dict) -> None:
    """Portfolio exposure view from the existing MT5 -> Supabase position feed.
    Uses lots as the common exposure unit; no broker contract-size assumptions.
    """
    st.markdown('<div class="nj-section-title">Portfolio Exposure</div>', unsafe_allow_html=True)
    st.caption("Exposure จาก Position ที่เปิดอยู่ · หน่วยหลักเป็น Lots · ไม่แตะ MT5 / Supabase schema")

    if not snapshot:
        st.warning("ยังไม่พบ Account Snapshot จาก Supabase")
        return
    if snapshot.get("_error"):
        st.error(f"อ่าน MT5 จาก Supabase ไม่สำเร็จ: {snapshot['_error']}")
        return

    pos = fetch_mt5_positions_supabase(snapshot)
    if pos.empty:
        st.markdown(
            '<div class="nj-hero"><div class="nj-empty-icon">📐</div>'
            '<h2>ยังไม่มี Exposure จาก Position ที่เปิดอยู่</h2>'
            '<p>เมื่อมี Position ใน MT5 ระบบจะคำนวณ Gross / Net Exposure แยกตาม Symbol ให้อัตโนมัติ</p></div>',
            unsafe_allow_html=True,
        )
        return

    work = pos.copy()
    work["volume"] = pd.to_numeric(work.get("volume"), errors="coerce").fillna(0.0)
    work["profit"] = pd.to_numeric(work.get("profit"), errors="coerce").fillna(0.0)
    work["swap"] = pd.to_numeric(work.get("swap"), errors="coerce").fillna(0.0)
    work["commission"] = pd.to_numeric(work.get("commission"), errors="coerce").fillna(0.0)
    work["side_norm"] = work.get("side", "").astype(str).str.upper()
    work["buy_lots"] = work["volume"].where(work["side_norm"].str.contains("BUY", na=False), 0.0)
    work["sell_lots"] = work["volume"].where(work["side_norm"].str.contains("SELL", na=False), 0.0)

    gross = float(work["volume"].sum())
    buy = float(work["buy_lots"].sum())
    sell = float(work["sell_lots"].sum())
    net = buy - sell
    pnl = float(work["profit"].sum())
    net_pnl = pnl + float(work["swap"].sum()) + float(work["commission"].sum())

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Gross Exposure", f"{gross:,.2f} lots")
    c2.metric("BUY Exposure", f"{buy:,.2f} lots")
    c3.metric("SELL Exposure", f"{sell:,.2f} lots")
    c4.metric("Net Exposure", f"{net:+,.2f} lots")
    c5.metric("Net Floating P&L", f"{net_pnl:+,.2f}")

    st.divider()
    st.markdown("### Exposure by Symbol")
    grouped = work.groupby("symbol", dropna=False).agg(
        Positions=("volume", "size"),
        Gross_Lots=("volume", "sum"),
        Buy_Lots=("buy_lots", "sum"),
        Sell_Lots=("sell_lots", "sum"),
        Floating_PnL=("profit", "sum"),
        Swap=("swap", "sum"),
        Commission=("commission", "sum"),
    ).reset_index()
    grouped["Net_Lots"] = grouped["Buy_Lots"] - grouped["Sell_Lots"]
    grouped["Net_PnL"] = grouped["Floating_PnL"] + grouped["Swap"] + grouped["Commission"]
    grouped["Gross_Share"] = (grouped["Gross_Lots"] / gross * 100.0) if gross else 0.0
    grouped = grouped.sort_values(["Gross_Lots", "symbol"], ascending=[False, True])

    view = grouped.rename(columns={
        "symbol":"Symbol", "Positions":"Positions", "Gross_Lots":"Gross Lots",
        "Buy_Lots":"BUY Lots", "Sell_Lots":"SELL Lots", "Net_Lots":"Net Lots",
        "Gross_Share":"Gross Share %", "Floating_PnL":"Floating P&L",
        "Swap":"Swap", "Commission":"Commission", "Net_PnL":"Net P&L",
    }).copy()
    for col in ["Gross Lots", "BUY Lots", "SELL Lots", "Net Lots", "Floating P&L", "Swap", "Commission", "Net P&L"]:
        view[col] = view[col].map(lambda x: f"{x:+,.2f}" if "P&L" in col or col in ("Net Lots",) else f"{x:,.2f}")
    view["Gross Share %"] = view["Gross Share %"].map(lambda x: f"{x:.1f}%")
    st.dataframe(view, use_container_width=True, hide_index=True)

    st.divider()
    st.markdown("### Directional Balance")
    left, right = st.columns(2)
    with left:
        if gross:
            buy_pct = buy / gross * 100.0
            sell_pct = sell / gross * 100.0
        else:
            buy_pct = sell_pct = 0.0
        st.metric("BUY share of gross", f"{buy_pct:.1f}%")
        st.progress(min(max(buy_pct / 100.0, 0.0), 1.0))
    with right:
        st.metric("SELL share of gross", f"{sell_pct:.1f}%")
        st.progress(min(max(sell_pct / 100.0, 0.0), 1.0))

    if abs(net) < 1e-12:
        st.info("Exposure ฝั่ง BUY และ SELL สมดุลกันตามจำนวน Lots")
    elif net > 0:
        st.info(f"Net Exposure = +{net:,.2f} lots → ฝั่ง BUY มากกว่า")
    else:
        st.info(f"Net Exposure = {net:,.2f} lots → ฝั่ง SELL มากกว่า")



def _risk_badge(level: str) -> str:
    colors = {
        "OK": ("🟢", "ปกติ"),
        "WATCH": ("🟡", "เฝ้าระวัง"),
        "HIGH": ("🟠", "ความเสี่ยงสูง"),
        "CRITICAL": ("🔴", "วิกฤต"),
    }
    icon, label = colors.get(level, ("⚪", level))
    return f"{icon} {label}"


def _risk_level(value: float, watch: float, high: float, critical: float, higher_is_worse: bool = True) -> str:
    if higher_is_worse:
        if value >= critical:
            return "CRITICAL"
        if value >= high:
            return "HIGH"
        if value >= watch:
            return "WATCH"
        return "OK"
    if value <= critical:
        return "CRITICAL"
    if value <= high:
        return "HIGH"
    if value <= watch:
        return "WATCH"
    return "OK"


def page_risk_engine(snapshot: dict) -> None:
    """Rule-based portfolio risk monitor using the existing MT5 -> Supabase feed."""
    st.markdown('<div class="nj-section-title">Risk Engine</div>', unsafe_allow_html=True)
    st.caption("Rule-based risk monitor · อ่านอย่างเดียว · ไม่ส่งคำสั่งซื้อขาย")

    if not snapshot:
        st.warning("ยังไม่พบ Account Snapshot จาก Supabase")
        return
    if snapshot.get("_error"):
        st.error(f"อ่าน MT5 จาก Supabase ไม่สำเร็จ: {snapshot['_error']}")
        return

    pos = fetch_mt5_positions_supabase(snapshot)
    pending = fetch_mt5_pending_supabase(snapshot)

    balance = _num(snapshot.get("balance"))
    equity = _num(snapshot.get("equity"))
    margin = _num(snapshot.get("margin"))
    free_margin = _num(snapshot.get("free_margin"))
    floating = equity - balance

    work = pos.copy()
    if not work.empty:
        for col in ["volume", "profit", "swap", "commission"]:
            work[col] = pd.to_numeric(work.get(col), errors="coerce").fillna(0.0) if col in work.columns else 0.0
        side = work.get("side", pd.Series(index=work.index, dtype=str)).astype(str).str.upper()
        work["buy_lots"] = work["volume"].where(side.str.contains("BUY", na=False), 0.0)
        work["sell_lots"] = work["volume"].where(side.str.contains("SELL", na=False), 0.0)
    else:
        work = pd.DataFrame(columns=["volume", "profit", "swap", "commission", "buy_lots", "sell_lots", "symbol"])

    gross = float(work["volume"].sum()) if not work.empty else 0.0
    buy = float(work["buy_lots"].sum()) if not work.empty else 0.0
    sell = float(work["sell_lots"].sum()) if not work.empty else 0.0
    net = buy - sell
    margin_util = (margin / equity * 100.0) if equity > 0 else 0.0
    free_ratio = (free_margin / equity * 100.0) if equity > 0 else 0.0
    floating_loss_pct = (max(0.0, -floating) / equity * 100.0) if equity > 0 else 0.0
    directional_pct = (abs(net) / gross * 100.0) if gross > 0 else 0.0

    if not work.empty and "symbol" in work.columns and gross > 0:
        concentration = (work.groupby("symbol")["volume"].sum() / gross * 100.0).max()
        concentration_symbol = str((work.groupby("symbol")["volume"].sum()).idxmax())
    else:
        concentration = 0.0
        concentration_symbol = "-"

    checks = [
        ("Margin Utilization", margin_util, "%", _risk_level(margin_util, 40, 60, 80), "สูงเกินไปเมื่อ Margin กิน Equity มาก"),
        ("Free Margin Ratio", free_ratio, "%", _risk_level(free_ratio, 40, 20, 10, higher_is_worse=False), "ต่ำลงแปลว่า buffer เหลือน้อย"),
        ("Floating Loss", floating_loss_pct, "%", _risk_level(floating_loss_pct, 2, 5, 10), "วัดจาก Equity ปัจจุบัน"),
        ("Directional Imbalance", directional_pct, "%", _risk_level(directional_pct, 60, 80, 95), "สัดส่วน Net Lots ต่อ Gross Lots"),
        ("Largest Symbol", concentration, "%", _risk_level(concentration, 60, 80, 95), f"Symbol หลัก: {concentration_symbol}"),
    ]

    severity = {"OK": 0, "WATCH": 1, "HIGH": 2, "CRITICAL": 3}
    overall = max((x[3] for x in checks), key=lambda x: severity[x]) if checks else "OK"

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Risk Status", _risk_badge(overall))
    c2.metric("Margin Utilization", f"{margin_util:.1f}%")
    c3.metric("Free Margin Ratio", f"{free_ratio:.1f}%")
    c4.metric("Floating Loss", f"{floating_loss_pct:.2f}%")

    st.divider()
    st.markdown("### Risk Checks")
    rows = []
    for name, value, unit, level, note in checks:
        rows.append({"Check": name, "Value": f"{value:.2f}{unit}", "Status": _risk_badge(level), "หมายเหตุ": note})
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    st.divider()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Open Positions", f"{len(pos)}")
    c2.metric("Gross Lots", f"{gross:,.2f}")
    c3.metric("Net Lots", f"{net:+,.2f}")
    c4.metric("Pending Orders", f"{len(pending)}")

    if overall == "CRITICAL":
        st.error("มี Risk Check ระดับวิกฤต — ตรวจสอบ Margin / Exposure / Floating Loss ก่อนดำเนินการต่อ")
    elif overall == "HIGH":
        st.warning("มี Risk Check ระดับความเสี่ยงสูง — ควรตรวจสอบรายการที่ถูกทำเครื่องหมาย")
    elif overall == "WATCH":
        st.info("มีบางตัวชี้วัดเข้าสู่โซนเฝ้าระวัง")
    else:
        st.success("Risk checks ทั้งหมดอยู่ในโซนปกติตามกฎที่ตั้งไว้")

    st.caption("เกณฑ์ในหน้านี้เป็นกฎ monitoring แบบตายตัวของแอป ไม่ใช่การคาดการณ์ตลาด และยังไม่มีการส่งคำสั่งอัตโนมัติ")


def page_decision_engine(snapshot: dict) -> None:
    """Portfolio Decision Engine v1: deterministic alerts from current portfolio state.
    Read-only; does not predict markets or place orders.
    """
    st.markdown('<div class="nj-section-title">Portfolio Decision Engine</div>', unsafe_allow_html=True)
    st.caption("Decision support จากข้อมูลพอร์ตปัจจุบัน · Rule-based · อ่านอย่างเดียว · ไม่ส่งคำสั่งซื้อขาย")

    if not snapshot:
        st.warning("ยังไม่พบ Account Snapshot จาก Supabase")
        return
    if snapshot.get("_error"):
        st.error(f"อ่าน MT5 จาก Supabase ไม่สำเร็จ: {snapshot['_error']}")
        return

    pos = fetch_mt5_positions_supabase(snapshot)
    pending = fetch_mt5_pending_supabase(snapshot)

    balance = _num(snapshot.get("balance"))
    equity = _num(snapshot.get("equity"))
    margin = _num(snapshot.get("margin"))
    free_margin = _num(snapshot.get("free_margin"))
    floating = equity - balance

    work = pos.copy()
    if not work.empty:
        for col in ["volume", "profit", "swap", "commission"]:
            work[col] = pd.to_numeric(work.get(col), errors="coerce").fillna(0.0) if col in work.columns else 0.0
        side = work.get("side", pd.Series(index=work.index, dtype=str)).astype(str).str.upper()
        work["buy_lots"] = work["volume"].where(side.str.contains("BUY", na=False), 0.0)
        work["sell_lots"] = work["volume"].where(side.str.contains("SELL", na=False), 0.0)
    else:
        work = pd.DataFrame(columns=["volume", "profit", "swap", "commission", "buy_lots", "sell_lots", "symbol"])

    gross = float(work["volume"].sum()) if not work.empty else 0.0
    buy = float(work["buy_lots"].sum()) if not work.empty else 0.0
    sell = float(work["sell_lots"].sum()) if not work.empty else 0.0
    net = buy - sell
    margin_util = (margin / equity * 100.0) if equity > 0 else 0.0
    free_ratio = (free_margin / equity * 100.0) if equity > 0 else 0.0
    floating_loss_pct = (max(0.0, -floating) / equity * 100.0) if equity > 0 else 0.0
    directional_pct = (abs(net) / gross * 100.0) if gross > 0 else 0.0

    symbol_conc = 0.0
    concentration_symbol = "-"
    if not work.empty and "symbol" in work.columns and gross > 0:
        by_symbol = work.groupby("symbol")["volume"].sum().sort_values(ascending=False)
        if not by_symbol.empty:
            concentration_symbol = str(by_symbol.index[0])
            symbol_conc = float(by_symbol.iloc[0] / gross * 100.0)

    alerts = []

    def add(level, title, detail, action):
        alerts.append({"level": level, "title": title, "detail": detail, "action": action})

    if len(pos) == 0:
        add("INFO", "ไม่มี Open Position", "ขณะนี้ไม่มี Position ที่เปิดอยู่ให้วิเคราะห์ Exposure", "รอข้อมูล Position ก่อนประเมิน Exposure")
    else:
        if margin_util >= 80:
            add("CRITICAL", "Margin Utilization สูงมาก", f"Margin ใช้ {margin_util:.1f}% ของ Equity", "ตรวจสอบ Margin และ Free Margin ทันที")
        elif margin_util >= 60:
            add("HIGH", "Margin Utilization สูง", f"Margin ใช้ {margin_util:.1f}% ของ Equity", "ตรวจสอบการใช้ Margin และ buffer ที่เหลือ")
        elif margin_util >= 40:
            add("WATCH", "Margin Utilization เริ่มสูง", f"Margin ใช้ {margin_util:.1f}% ของ Equity", "ติดตาม Margin ต่อเนื่อง")

        if free_ratio <= 10:
            add("CRITICAL", "Free Margin ต่ำมาก", f"Free Margin เหลือ {free_ratio:.1f}% ของ Equity", "ตรวจสอบ buffer ของบัญชีทันที")
        elif free_ratio <= 20:
            add("HIGH", "Free Margin ต่ำ", f"Free Margin เหลือ {free_ratio:.1f}% ของ Equity", "ตรวจสอบ buffer ที่เหลือ")
        elif free_ratio <= 40:
            add("WATCH", "Free Margin ลดลง", f"Free Margin เหลือ {free_ratio:.1f}% ของ Equity", "ติดตาม buffer ต่อเนื่อง")

        if floating_loss_pct >= 10:
            add("CRITICAL", "Floating Loss สูง", f"ขาดทุนลอยตัว {floating_loss_pct:.2f}% ของ Equity", "ตรวจสอบ Position ที่เป็นต้นเหตุ")
        elif floating_loss_pct >= 5:
            add("HIGH", "Floating Loss สูงขึ้น", f"ขาดทุนลอยตัว {floating_loss_pct:.2f}% ของ Equity", "ตรวจสอบ Position และความเสี่ยงรวม")
        elif floating_loss_pct >= 2:
            add("WATCH", "มี Floating Loss", f"ขาดทุนลอยตัว {floating_loss_pct:.2f}% ของ Equity", "ติดตาม P&L ของ Position")

        if directional_pct >= 95:
            add("CRITICAL", "Directional Exposure กระจุกตัว", f"Net/Gross = {directional_pct:.1f}%", "ตรวจสอบการกระจุกตัวของฝั่ง BUY/SELL")
        elif directional_pct >= 80:
            add("HIGH", "Directional Exposure สูง", f"Net/Gross = {directional_pct:.1f}%", "ตรวจสอบสมดุลของ Exposure")
        elif directional_pct >= 60:
            add("WATCH", "Directional Exposure เอียง", f"Net/Gross = {directional_pct:.1f}%", "ติดตามสัดส่วน BUY/SELL")

        if symbol_conc >= 95:
            add("CRITICAL", "Symbol Concentration สูงมาก", f"{concentration_symbol} คิดเป็น {symbol_conc:.1f}% ของ Gross Lots", "ตรวจสอบการกระจุกตัวของ Symbol")
        elif symbol_conc >= 80:
            add("HIGH", "Symbol Concentration สูง", f"{concentration_symbol} คิดเป็น {symbol_conc:.1f}% ของ Gross Lots", "ตรวจสอบสัดส่วนของ Symbol หลัก")
        elif symbol_conc >= 60:
            add("WATCH", "Symbol Concentration สูงขึ้น", f"{concentration_symbol} คิดเป็น {symbol_conc:.1f}% ของ Gross Lots", "ติดตามสัดส่วนของ Symbol หลัก")

        if "stop_loss" in work.columns:
            no_sl = work["stop_loss"].fillna(0).astype(float).eq(0).sum()
            if no_sl:
                add("WATCH", "มี Position ไม่มี Stop Loss", f"พบ {int(no_sl)} จาก {len(work)} Position ที่ไม่มี Stop Loss", "ตรวจสอบ Position ที่ไม่มี Stop Loss")

    if len(pending) > 0:
        add("INFO", "มี Pending Orders", f"พบ Pending Orders {len(pending)} รายการ", "ตรวจสอบรายการ Pending และเงื่อนไขที่ตั้งไว้")

    severity = {"INFO":0, "WATCH":1, "HIGH":2, "CRITICAL":3}
    overall = max((a["level"] for a in alerts), key=lambda x: severity[x]) if alerts else "INFO"

    badge = {
        "INFO": "🔵 ข้อมูล",
        "WATCH": "🟡 เฝ้าระวัง",
        "HIGH": "🟠 ความเสี่ยงสูง",
        "CRITICAL": "🔴 วิกฤต",
    }[overall]

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Decision Status", badge)
    c2.metric("Open Positions", len(pos))
    c3.metric("Net Exposure", f"{net:+,.2f} lots")
    c4.metric("Floating P&L", f"{floating:+,.2f}")

    st.divider()
    st.markdown("### Portfolio Alerts")
    if not alerts:
        st.success("ยังไม่พบ Alert จากกฎที่ตั้งไว้")
    else:
        for a in alerts:
            if a["level"] == "CRITICAL":
                st.error(f"{a['title']} — {a['detail']}\n\nตรวจสอบ: {a['action']}")
            elif a["level"] == "HIGH":
                st.warning(f"{a['title']} — {a['detail']}\n\nตรวจสอบ: {a['action']}")
            elif a["level"] == "WATCH":
                st.info(f"{a['title']} — {a['detail']}\n\nตรวจสอบ: {a['action']}")
            else:
                st.caption(f"🔵 {a['title']} — {a['detail']} · {a['action']}")

    st.divider()
    st.markdown("### Decision Snapshot")
    rows = [
        {"Metric":"Margin Utilization", "Value":f"{margin_util:.1f}%", "Interpretation":"สูงขึ้น = ใช้ Margin มากขึ้น"},
        {"Metric":"Free Margin Ratio", "Value":f"{free_ratio:.1f}%", "Interpretation":"ต่ำลง = buffer เหลือน้อยลง"},
        {"Metric":"Floating Loss", "Value":f"{floating_loss_pct:.2f}%", "Interpretation":"วัดขาดทุนลอยตัวเทียบ Equity"},
        {"Metric":"Directional Imbalance", "Value":f"{directional_pct:.1f}%", "Interpretation":"Net Lots เทียบ Gross Lots"},
        {"Metric":"Largest Symbol", "Value":f"{concentration_symbol} ({symbol_conc:.1f}%)", "Interpretation":"สัดส่วน Gross Lots สูงสุด"},
    ]
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    st.caption("Decision Engine v1 ใช้กฎจากสถานะพอร์ตปัจจุบันเท่านั้น ไม่ทำนายราคา ไม่จัดอันดับสินทรัพย์ และไม่ส่งคำสั่งซื้อขายอัตโนมัติ")


def _trade_baseline_rows(history: pd.DataFrame) -> pd.DataFrame:
    """Normalize Supabase deal history for Performance Baseline.

    Only OUT/close deals are counted as completed trades when entry_type is
    available. This avoids counting the IN leg as a winning/losing trade.
    """
    if history is None or history.empty:
        return pd.DataFrame()
    w = history.copy()
    for c in ("profit", "commission", "swap", "fee", "volume", "price"):
        if c in w.columns:
            w[c] = pd.to_numeric(w[c], errors="coerce").fillna(0.0)
    if "deal_time" in w.columns:
        w["deal_time"] = pd.to_datetime(w["deal_time"], errors="coerce", utc=True)

    if "entry_type" in w.columns:
        et = w["entry_type"].astype(str).str.upper()
        out = w[et.isin(["OUT", "OUT_BY", "CLOSE", "CLOSED"])].copy()
        if out.empty:
            out = w.copy()
    else:
        out = w.copy()

    for c in ("profit", "commission", "swap", "fee"):
        if c not in out.columns:
            out[c] = 0.0
    out["net_result"] = out["profit"] + out["commission"] + out["swap"] + out["fee"]
    return out


def _streaks(results: list[float]) -> tuple[int, int]:
    best_w = best_l = cur_w = cur_l = 0
    for x in results:
        if x > 0:
            cur_w += 1; cur_l = 0; best_w = max(best_w, cur_w)
        elif x < 0:
            cur_l += 1; cur_w = 0; best_l = max(best_l, cur_l)
        else:
            cur_w = cur_l = 0
    return best_w, best_l



def _performance_breakdown_rows(history: pd.DataFrame) -> pd.DataFrame:
    """Build completed-trade rows plus a best-effort position direction.

    The baseline counts OUT/close deals. For BUY/SELL breakdown, prefer the
    direction of the original IN deal for the same position_id so a SELL close
    of a BUY position is not mislabeled as a SELL trade. If no matching IN
    deal is available, fall back to the close deal direction.
    """
    trades = _trade_baseline_rows(history)
    if trades.empty:
        return trades

    w = history.copy() if history is not None else pd.DataFrame()
    if not w.empty:
        if "entry_type" in w.columns:
            et = w["entry_type"].astype(str).str.upper()
            ins = w[et.isin(["IN", "INOUT", "OPEN"])].copy()
        else:
            ins = pd.DataFrame()

        direction_map = {}
        if not ins.empty and "position_id" in ins.columns and "deal_type" in ins.columns:
            for _, r in ins.iterrows():
                pid = r.get("position_id")
                if pd.isna(pid):
                    continue
                d = str(r.get("deal_type", "")).upper()
                if d in ("BUY", "SELL"):
                    direction_map[str(pid)] = d

        if "position_id" in trades.columns:
            trades["trade_direction"] = trades["position_id"].apply(
                lambda x: direction_map.get(str(x)) if not pd.isna(x) else None
            )
        else:
            trades["trade_direction"] = None

    if "trade_direction" not in trades.columns:
        trades["trade_direction"] = None
    fallback = trades.get("deal_type", pd.Series(index=trades.index, dtype=object)).astype(str).str.upper()
    trades["trade_direction"] = trades["trade_direction"].where(
        trades["trade_direction"].isin(["BUY", "SELL"]), fallback
    )

    if "deal_time" in trades.columns:
        trades["deal_time"] = pd.to_datetime(trades["deal_time"], errors="coerce", utc=True)
        # The collector stores MT5 server datetime without an explicit timezone.
        # Keep the database timestamp as-is for grouping rather than pretending
        # it is Bangkok local time.
        trades["time_bucket"] = pd.cut(
            trades["deal_time"].dt.hour,
            bins=[-1, 6, 12, 18, 24],
            labels=["00–06", "07–12", "13–18", "19–24"],
        )
        trades["day_of_week"] = trades["deal_time"].dt.day_name()
    else:
        trades["time_bucket"] = "Unknown"
        trades["day_of_week"] = "Unknown"

    return trades


def _breakdown_metrics(df: pd.DataFrame) -> dict:
    if df is None or df.empty:
        return {
            "trades": 0, "wins": 0, "losses": 0, "win_rate": 0.0,
            "gross_profit": 0.0, "gross_loss": 0.0, "net_pnl": 0.0,
            "pf": None, "expectancy": 0.0,
        }
    r = pd.to_numeric(df["net_result"], errors="coerce").fillna(0.0)
    wins = r[r > 0]
    losses = r[r < 0]
    gp = float(wins.sum())
    gl = float(abs(losses.sum()))
    return {
        "trades": int(len(r)),
        "wins": int((r > 0).sum()),
        "losses": int((r < 0).sum()),
        "win_rate": float((r > 0).mean() * 100) if len(r) else 0.0,
        "gross_profit": gp,
        "gross_loss": gl,
        "net_pnl": float(r.sum()),
        "pf": gp / gl if gl > 0 else None,
        "expectancy": float(r.mean()) if len(r) else 0.0,
    }


def _breakdown_table(df: pd.DataFrame, key: str, label: str) -> pd.DataFrame:
    rows = []
    if df.empty or key not in df.columns:
        return pd.DataFrame()
    for value, g in df.groupby(key, dropna=False, observed=False):
        name = "Unknown" if pd.isna(value) else str(value)
        m = _breakdown_metrics(g)
        rows.append({
            label: name,
            "Trades": m["trades"],
            "Win Rate": m["win_rate"],
            "Profit Factor": m["pf"],
            "Net P&L": m["net_pnl"],
            "Expectancy": m["expectancy"],
            "Gross Profit": m["gross_profit"],
            "Gross Loss": -m["gross_loss"],
        })
    out = pd.DataFrame(rows)
    if not out.empty:
        out = out.sort_values("Net P&L", ascending=False, kind="stable")
    return out


def page_performance_breakdown(snapshot: dict) -> None:
    """Step 2: factual performance breakdown from the same completed trades."""
    st.markdown('<div class="nj-section-title">Performance Breakdown</div>', unsafe_allow_html=True)
    st.caption("Step 2 · แยก Performance ตาม Symbol / Direction / Time / Day · ใช้ Closed Trade ชุดเดียวกับ Step 1")

    if not snapshot or snapshot.get("_error"):
        st.warning("ยังไม่พบ Account Snapshot จาก Supabase")
        return

    history = fetch_mt5_history_supabase(snapshot)
    trades = _performance_breakdown_rows(history)
    if trades.empty:
        st.info("ยังไม่มี Closed Trade สำหรับทำ Performance Breakdown")
        return

    st.markdown("### By Symbol")
    symbol = _breakdown_table(trades, "symbol", "Symbol")
    if symbol.empty:
        st.info("ยังไม่มีข้อมูล Symbol")
    else:
        st.dataframe(symbol.style.format({
            "Win Rate": "{:.2f}%",
            "Profit Factor": lambda x: "—" if pd.isna(x) else f"{x:.2f}",
            "Net P&L": "{:+,.2f}",
            "Expectancy": "{:+,.2f}",
            "Gross Profit": "{:+,.2f}",
            "Gross Loss": "{:+,.2f}",
        }), use_container_width=True, hide_index=True)

    st.markdown("### By Direction")
    st.caption("Direction พยายามอ้างจาก IN deal ของ position_id ก่อน; ถ้าจับคู่ไม่ได้จึงใช้ deal_type ของ close deal")
    direction = _breakdown_table(trades, "trade_direction", "Direction")
    if direction.empty:
        st.info("ยังไม่มีข้อมูล Direction")
    else:
        st.dataframe(direction.style.format({
            "Win Rate": "{:.2f}%",
            "Profit Factor": lambda x: "—" if pd.isna(x) else f"{x:.2f}",
            "Net P&L": "{:+,.2f}",
            "Expectancy": "{:+,.2f}",
            "Gross Profit": "{:+,.2f}",
            "Gross Loss": "{:+,.2f}",
        }), use_container_width=True, hide_index=True)

    st.markdown("### By Time of Day")
    st.caption("ใช้ timestamp ที่ Collector เก็บในฐานข้อมูล; ยังไม่แปลงเป็นเวลาไทย เพราะ MT5 collector เดิมไม่ได้บันทึก timezone ของ server")
    time_order = ["00–06", "07–12", "13–18", "19–24"]
    time_df = _breakdown_table(trades, "time_bucket", "Time")
    if not time_df.empty:
        time_df["_order"] = time_df["Time"].map({v:i for i,v in enumerate(time_order)}).fillna(99)
        time_df = time_df.sort_values("_order").drop(columns="_order")
        st.dataframe(time_df.style.format({
            "Win Rate": "{:.2f}%",
            "Profit Factor": lambda x: "—" if pd.isna(x) else f"{x:.2f}",
            "Net P&L": "{:+,.2f}",
            "Expectancy": "{:+,.2f}",
            "Gross Profit": "{:+,.2f}",
            "Gross Loss": "{:+,.2f}",
        }), use_container_width=True, hide_index=True)

    st.markdown("### By Day of Week")
    day_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    day_df = _breakdown_table(trades, "day_of_week", "Day")
    if not day_df.empty:
        day_df["_order"] = day_df["Day"].map({v:i for i,v in enumerate(day_order)}).fillna(99)
        day_df = day_df.sort_values("_order").drop(columns="_order")
        st.dataframe(day_df.style.format({
            "Win Rate": "{:.2f}%",
            "Profit Factor": lambda x: "—" if pd.isna(x) else f"{x:.2f}",
            "Net P&L": "{:+,.2f}",
            "Expectancy": "{:+,.2f}",
            "Gross Profit": "{:+,.2f}",
            "Gross Loss": "{:+,.2f}",
        }), use_container_width=True, hide_index=True)

    st.markdown("### Performance Concentration")
    st.caption("ดูว่ากำไร/ขาดทุนสุทธิถูกสร้างหรือกระจุกอยู่ที่กลุ่มไหน โดยไม่ตีความว่าเป็นเหตุผลเชิงกลยุทธ์")
    if not symbol.empty:
        concentration = symbol[["Symbol", "Trades", "Net P&L", "Gross Profit", "Gross Loss"]].copy()
        total_gp = float(concentration["Gross Profit"].sum())
        total_gl = float(abs(concentration["Gross Loss"].sum()))
        concentration["Gross Profit Share"] = (concentration["Gross Profit"] / total_gp * 100) if total_gp else 0.0
        concentration["Gross Loss Share"] = (abs(concentration["Gross Loss"]) / total_gl * 100) if total_gl else 0.0
        st.dataframe(concentration.style.format({
            "Net P&L": "{:+,.2f}",
            "Gross Profit": "{:+,.2f}",
            "Gross Loss": "{:+,.2f}",
            "Gross Profit Share": "{:.1f}%",
            "Gross Loss Share": "{:.1f}%",
        }), use_container_width=True, hide_index=True)

    st.caption("Step 2 ยังเป็น descriptive statistics จากข้อมูลจริงเท่านั้น · ยังไม่ทำ AI inference, strategy scoring, prediction หรือ recommendation")


def _behavior_analysis(trades: pd.DataFrame) -> dict:
    """Compute descriptive trading-behavior statistics from completed trades.

    This is deliberately descriptive: it does not infer psychology, diagnose
    discipline, score strategies, predict outcomes, or recommend actions.
    """
    if trades is None or trades.empty:
        return {}

    w = trades.copy()
    w["net_result"] = pd.to_numeric(w["net_result"], errors="coerce").fillna(0.0)
    if "deal_time" in w.columns:
        w["deal_time"] = pd.to_datetime(w["deal_time"], errors="coerce", utc=True)
        w = w.sort_values("deal_time", kind="stable").reset_index(drop=True)
    else:
        w["deal_time"] = pd.NaT

    valid_times = w["deal_time"].dropna()
    active_days = int(valid_times.dt.date.nunique()) if not valid_times.empty else 0
    calendar_span = None
    if len(valid_times) >= 2:
        calendar_span = max((valid_times.max() - valid_times.min()).total_seconds() / 86400.0, 0.0)

    gaps_min = w["deal_time"].diff().dt.total_seconds().div(60.0)
    valid_gaps = gaps_min[(gaps_min.notna()) & (gaps_min >= 0)]

    rapid_15 = int((valid_gaps < 15).sum())
    rapid_30 = int((valid_gaps < 30).sum())
    rapid_60 = int((valid_gaps < 60).sum())

    # A factual sequence flag: a trade closed within 30 minutes after a
    # previous losing trade. This is not labelled as revenge trading.
    prior_result = w["net_result"].shift(1)
    after_loss_30 = int(((prior_result < 0) & (gaps_min <= 30) & gaps_min.notna()).sum())
    after_win_30 = int(((prior_result > 0) & (gaps_min <= 30) & gaps_min.notna()).sum())

    same_symbol_60 = 0
    if "symbol" in w.columns:
        prev_symbol = w["symbol"].shift(1).astype(str)
        same_symbol_60 = int(((prev_symbol == w["symbol"].astype(str)) & (gaps_min <= 60) & gaps_min.notna()).sum())

    # Position-size comparison where volume exists.
    if "volume" in w.columns:
        w["volume"] = pd.to_numeric(w["volume"], errors="coerce")
        win_vol = w.loc[w["net_result"] > 0, "volume"].dropna()
        loss_vol = w.loc[w["net_result"] < 0, "volume"].dropna()
        avg_win_volume = float(win_vol.mean()) if len(win_vol) else None
        avg_loss_volume = float(loss_vol.mean()) if len(loss_vol) else None
    else:
        avg_win_volume = avg_loss_volume = None

    # Closed-trade cumulative curve and maximum peak-to-trough drawdown.
    cumulative = w["net_result"].cumsum()
    running_peak = cumulative.cummax()
    drawdown = cumulative - running_peak
    max_drawdown = float(abs(drawdown.min())) if len(drawdown) else 0.0
    max_drawdown_idx = int(drawdown.idxmin()) if len(drawdown) else None

    # Count each run of consecutive wins/losses and expose the sequence table.
    outcomes = w["net_result"].apply(lambda x: "Win" if x > 0 else ("Loss" if x < 0 else "Breakeven"))
    runs = []
    current = None
    start = 0
    for i, outcome in enumerate(outcomes.tolist()):
        if outcome != current:
            if current is not None:
                runs.append((current, start, i - 1, i - start))
            current = outcome
            start = i
    if current is not None:
        runs.append((current, start, len(outcomes) - 1, len(outcomes) - start))

    return {
        "trades": int(len(w)),
        "active_days": active_days,
        "calendar_span_days": calendar_span,
        "trades_per_active_day": (len(w) / active_days) if active_days else None,
        "median_gap_min": float(valid_gaps.median()) if len(valid_gaps) else None,
        "mean_gap_min": float(valid_gaps.mean()) if len(valid_gaps) else None,
        "rapid_15": rapid_15,
        "rapid_30": rapid_30,
        "rapid_60": rapid_60,
        "after_loss_30": after_loss_30,
        "after_win_30": after_win_30,
        "same_symbol_60": same_symbol_60,
        "avg_win_volume": avg_win_volume,
        "avg_loss_volume": avg_loss_volume,
        "max_drawdown": max_drawdown,
        "max_drawdown_idx": max_drawdown_idx,
        "runs": runs,
        "ordered": w,
    }


def page_behavior_analysis(snapshot: dict) -> None:
    """Step 3: descriptive trading-behavior analysis from closed trades."""
    st.markdown('<div class="nj-section-title">Trading Behavior Analysis</div>', unsafe_allow_html=True)
    st.caption("Step 3 · วิเคราะห์รูปแบบพฤติกรรมที่สังเกตได้จากลำดับ Trade History · ไม่วินิจฉัยอารมณ์และไม่ให้คะแนน")

    if not snapshot or snapshot.get("_error"):
        st.warning("ยังไม่พบ Account Snapshot จาก Supabase")
        return

    history = fetch_mt5_history_supabase(snapshot)
    trades = _trade_baseline_rows(history)
    if trades.empty:
        st.info("ยังไม่มี Closed Trade สำหรับทำ Behavior Analysis")
        return

    a = _behavior_analysis(trades)
    ordered = a["ordered"]

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Completed Trades", f"{a['trades']:,}")
    c2.metric("Active Trading Days", f"{a['active_days']:,}")
    c3.metric("Trades / Active Day", f"{a['trades_per_active_day']:.2f}" if a["trades_per_active_day"] is not None else "—")
    c4.metric("Max Closed-Trade Drawdown", f"-{a['max_drawdown']:,.2f}")

    st.markdown("### Trade Frequency")
    c1, c2, c3 = st.columns(3)
    c1.metric("Median Gap", f"{a['median_gap_min']:.1f} min" if a["median_gap_min"] is not None else "—")
    c2.metric("Average Gap", f"{a['mean_gap_min']:.1f} min" if a["mean_gap_min"] is not None else "—")
    c3.metric("Data Span", f"{a['calendar_span_days']:.1f} days" if a["calendar_span_days"] is not None else "—")

    freq_rows = pd.DataFrame([
        {"Pattern": "Next trade within 15 min", "Count": a["rapid_15"], "Share of gaps": (a["rapid_15"] / max(len(ordered) - 1, 1) * 100)},
        {"Pattern": "Next trade within 30 min", "Count": a["rapid_30"], "Share of gaps": (a["rapid_30"] / max(len(ordered) - 1, 1) * 100)},
        {"Pattern": "Next trade within 60 min", "Count": a["rapid_60"], "Share of gaps": (a["rapid_60"] / max(len(ordered) - 1, 1) * 100)},
        {"Pattern": "Same symbol again within 60 min", "Count": a["same_symbol_60"], "Share of gaps": (a["same_symbol_60"] / max(len(ordered) - 1, 1) * 100)},
    ])
    st.dataframe(freq_rows.style.format({"Share of gaps": "{:.1f}%"}), use_container_width=True, hide_index=True)

    st.markdown("### Sequence After Wins / Losses")
    st.caption("เป็นเพียงลำดับเวลา: นับว่ามี trade ใหม่ภายใน 30 นาทีหลัง trade ก่อนหน้าที่ปิดกำไรหรือขาดทุน ไม่ได้สรุปว่าเป็น revenge trading หรือสาเหตุทางจิตวิทยา")
    seq = pd.DataFrame([
        {"Previous Result": "Loss", "Next Trade ≤30 min": a["after_loss_30"]},
        {"Previous Result": "Win", "Next Trade ≤30 min": a["after_win_30"]},
    ])
    st.dataframe(seq, use_container_width=True, hide_index=True)

    st.markdown("### Position Size: Winners vs Losers")
    size_rows = pd.DataFrame([
        {"Group": "Winning trades", "Average Volume": a["avg_win_volume"]},
        {"Group": "Losing trades", "Average Volume": a["avg_loss_volume"]},
    ])
    st.dataframe(size_rows.style.format({"Average Volume": lambda x: "—" if pd.isna(x) else f"{x:.4f}"}), use_container_width=True, hide_index=True)

    st.markdown("### Outcome Sequence")
    runs = a["runs"]
    if runs:
        run_rows = []
        for outcome, start, end, length in runs:
            run_rows.append({
                "Outcome": outcome,
                "Start Trade": start + 1,
                "End Trade": end + 1,
                "Length": length,
                "Net P&L": float(ordered.iloc[start:end + 1]["net_result"].sum()),
            })
        run_df = pd.DataFrame(run_rows)
        st.dataframe(run_df.style.format({"Net P&L": "{:+,.2f}"}), use_container_width=True, hide_index=True)

    st.markdown("### Closed-Trade Equity Curve")
    curve = ordered[[c for c in ["deal_ticket", "symbol", "deal_time", "net_result"] if c in ordered.columns]].copy()
    curve["Cumulative P&L"] = ordered["net_result"].cumsum().values
    st.line_chart(curve["Cumulative P&L"], height=280, use_container_width=True)

    st.caption("Step 3 เป็น descriptive analysis จาก Trade History เท่านั้น · ยังไม่ทำ AI inference, psychology diagnosis, strategy scoring, prediction หรือ auto-trading")


def _trading_dna_rows(trades: pd.DataFrame) -> pd.DataFrame:
    """Create descriptive pattern rows for Step 4 without scoring or prediction."""
    if trades is None or trades.empty:
        return pd.DataFrame()
    w = trades.copy()
    w["net_result"] = pd.to_numeric(w.get("net_result"), errors="coerce").fillna(0.0)
    if "deal_time" in w.columns:
        w["deal_time"] = pd.to_datetime(w["deal_time"], errors="coerce", utc=True)
        w = w.sort_values("deal_time", kind="stable").reset_index(drop=True)
    else:
        w["deal_time"] = pd.NaT

    # Use the same best-effort direction logic as Performance Breakdown.
    if "trade_direction" not in w.columns:
        w["trade_direction"] = w.get("deal_type", "Unknown").astype(str).str.upper()
    if "symbol" not in w.columns:
        w["symbol"] = "Unknown"
    w["symbol"] = w["symbol"].astype(str)
    w["time_bucket"] = pd.cut(
        w["deal_time"].dt.hour,
        bins=[-1, 6, 12, 18, 24],
        labels=["00–06", "07–12", "13–18", "19–24"],
    )
    w["day_of_week"] = w["deal_time"].dt.day_name()
    return w


def _dna_group_table(w: pd.DataFrame, key: str, label: str) -> pd.DataFrame:
    if w.empty or key not in w.columns:
        return pd.DataFrame()
    rows = []
    for value, g in w.groupby(key, dropna=False, observed=False):
        r = pd.to_numeric(g["net_result"], errors="coerce").fillna(0.0)
        wins = int((r > 0).sum())
        losses = int((r < 0).sum())
        gp = float(r[r > 0].sum())
        gl = float(abs(r[r < 0].sum()))
        rows.append({
            label: "Unknown" if pd.isna(value) else str(value),
            "Trades": int(len(r)),
            "Win Rate": (wins / len(r) * 100.0) if len(r) else 0.0,
            "Net P&L": float(r.sum()),
            "Profit Factor": (gp / gl) if gl > 0 else None,
            "Expectancy": float(r.mean()) if len(r) else 0.0,
        })
    return pd.DataFrame(rows)


def page_trading_dna(snapshot: dict) -> None:
    """Step 4: Trading DNA / recurring descriptive patterns."""
    st.markdown('<div class="nj-section-title">Trading DNA</div>', unsafe_allow_html=True)
    st.caption("Step 4 · รวม Performance + Breakdown + Behavior เพื่อหา Pattern ที่เกิดซ้ำ · ไม่ใช่คะแนน ไม่ใช่คำทำนาย และไม่ใช่คำแนะนำซื้อขาย")

    if not snapshot or snapshot.get("_error"):
        st.warning("ยังไม่พบ Account Snapshot จาก Supabase")
        return

    history = fetch_mt5_history_supabase(snapshot)
    trades = _performance_breakdown_rows(history)
    if trades.empty:
        st.info("ยังไม่มี Closed Trade สำหรับสร้าง Trading DNA")
        return

    w = _trading_dna_rows(trades)
    total = len(w)
    result = pd.to_numeric(w["net_result"], errors="coerce").fillna(0.0)

    # Descriptive dominant dimensions.
    def dominant(key):
        x = w[key].dropna().astype(str) if key in w.columns else pd.Series(dtype=str)
        return x.value_counts().index[0] if len(x) else "Unknown"

    dominant_symbol = dominant("symbol")
    dominant_direction = dominant("trade_direction")
    dominant_session = dominant("time_bucket")
    dominant_day = dominant("day_of_week")

    gaps = w["deal_time"].diff().dt.total_seconds().div(60.0)
    valid_gaps = gaps[(gaps.notna()) & (gaps >= 0)]
    median_gap = float(valid_gaps.median()) if len(valid_gaps) else None

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Closed Trades", f"{total:,}")
    c2.metric("Most Frequent Symbol", dominant_symbol)
    c3.metric("Most Frequent Direction", dominant_direction)
    c4.metric("Median Gap", f"{median_gap:.0f} min" if median_gap is not None else "—")

    st.markdown("### Pattern Snapshot")
    snapshot_rows = [
        {"Dimension": "Most frequent symbol", "Observed pattern": dominant_symbol, "Measure": int((w["symbol"] == dominant_symbol).sum())},
        {"Dimension": "Most frequent direction", "Observed pattern": dominant_direction, "Measure": int((w["trade_direction"] == dominant_direction).sum())},
        {"Dimension": "Most frequent time bucket", "Observed pattern": dominant_session, "Measure": int((w["time_bucket"].astype(str) == dominant_session).sum())},
        {"Dimension": "Most frequent day", "Observed pattern": dominant_day, "Measure": int((w["day_of_week"] == dominant_day).sum())},
    ]
    st.dataframe(pd.DataFrame(snapshot_rows), use_container_width=True, hide_index=True)

    st.markdown("### Symbol Fingerprint")
    by_symbol = _dna_group_table(w, "symbol", "Symbol")
    if not by_symbol.empty:
        by_symbol = by_symbol.sort_values(["Trades", "Net P&L"], ascending=[False, False], kind="stable")
        st.dataframe(by_symbol.style.format({
            "Win Rate": "{:.2f}%",
            "Net P&L": "{:+,.2f}",
            "Profit Factor": lambda x: "—" if pd.isna(x) else f"{x:.2f}",
            "Expectancy": "{:+,.2f}",
        }), use_container_width=True, hide_index=True)

    st.markdown("### Session Fingerprint")
    by_session = _dna_group_table(w, "time_bucket", "Time")
    if not by_session.empty:
        order = {"00–06": 0, "07–12": 1, "13–18": 2, "19–24": 3}
        by_session["_order"] = by_session["Time"].map(order).fillna(99)
        by_session = by_session.sort_values("_order", kind="stable").drop(columns="_order")
        st.dataframe(by_session.style.format({
            "Win Rate": "{:.2f}%",
            "Net P&L": "{:+,.2f}",
            "Profit Factor": lambda x: "—" if pd.isna(x) else f"{x:.2f}",
            "Expectancy": "{:+,.2f}",
        }), use_container_width=True, hide_index=True)

    st.markdown("### Size / Outcome Pattern")
    if "volume" in w.columns:
        w["volume"] = pd.to_numeric(w["volume"], errors="coerce")
        size_rows = []
        for name, mask in [("Winning", w["net_result"] > 0), ("Losing", w["net_result"] < 0), ("All", w["net_result"].notna())]:
            vals = w.loc[mask, "volume"].dropna()
            size_rows.append({
                "Group": name,
                "Trades": int(len(vals)),
                "Average Volume": float(vals.mean()) if len(vals) else None,
                "Median Volume": float(vals.median()) if len(vals) else None,
            })
        st.dataframe(pd.DataFrame(size_rows).style.format({
            "Average Volume": lambda x: "—" if pd.isna(x) else f"{x:.4f}",
            "Median Volume": lambda x: "—" if pd.isna(x) else f"{x:.4f}",
        }), use_container_width=True, hide_index=True)
    else:
        st.info("Trade History ชุดนี้ไม่มี volume สำหรับวิเคราะห์ขนาด Position")

    st.markdown("### Repeating Sequences")
    seq = []
    for i in range(1, len(w)):
        gap = gaps.iloc[i]
        if pd.isna(gap):
            continue
        prev = w.iloc[i - 1]
        cur = w.iloc[i]
        if gap <= 30:
            seq.append({
                "Pattern": f"{str(prev['net_result'] > 0 and 'Win' or 'Loss')} → next trade ≤30 min",
                "Count": 1,
                "Symbol": cur.get("symbol", "Unknown"),
            })
    if seq:
        seq_df = pd.DataFrame(seq).groupby(["Pattern", "Symbol"], as_index=False)["Count"].sum().sort_values("Count", ascending=False)
        st.dataframe(seq_df, use_container_width=True, hide_index=True)
    else:
        st.info("ยังไม่พบ sequence ภายใน 30 นาทีจากข้อมูลชุดนี้")

    st.markdown("### Current Data Limits")
    st.info("Trading DNA ตอนนี้เป็น pattern detection จาก Closed Trade เท่านั้น · ยังไม่มี Entry→Exit pairing ที่สมบูรณ์สำหรับ RR/MAE/MFE และยังไม่ตีความเป็นเหตุผลทางจิตวิทยา")
    st.caption("Step 4 · descriptive pattern detection เท่านั้น · ไม่มี strategy score, prediction, auto-trading หรือ recommendation")

# =========================================================
# GOLD TECHNICAL MODEL v1 — PRE-TRADE SETUP
# =========================================================

GOLD_SYMBOLS = ("XAUUSD", "GOLD", "XAUUSDm", "XAUUSD.")

def _supabase_headers(api_key: str, content_type: bool = False) -> dict:
    h = {
        "apikey": api_key,
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json",
    }
    if content_type:
        h["Content-Type"] = "application/json"
        h["Prefer"] = "return=representation"
    return h


def _gold_symbol_allowed(symbol: str) -> bool:
    s = str(symbol or "").upper().strip()
    return s in GOLD_SYMBOLS


def _planned_rr(direction: str, entry: float, sl: float, tp: float):
    try:
        entry, sl, tp = float(entry), float(sl), float(tp)
    except (TypeError, ValueError):
        return None
    if direction == "LONG":
        risk = entry - sl
        reward = tp - entry
    else:
        risk = sl - entry
        reward = entry - tp
    if risk <= 0 or reward < 0:
        return None
    return reward / risk


def _setup_post(row: dict) -> tuple[bool, str, dict | None]:
    base_url, api_key = get_supabase_config()
    if not base_url or not api_key:
        return False, "ยังไม่ได้ตั้งค่า SUPABASE_URL / SUPABASE_KEY", None
    try:
        r = requests.post(
            f"{base_url}/rest/v1/trade_setup_plans",
            headers=_supabase_headers(api_key, True),
            json=row,
            timeout=10,
        )
        if r.status_code not in (200, 201):
            return False, f"Supabase HTTP={r.status_code}: {r.text[:500]}", None
        data = r.json()
        return True, "บันทึก Trade Setup แล้ว", data[0] if isinstance(data, list) and data else row
    except Exception as exc:
        return False, str(exc), None


def _setup_patch_locked(setup_id: str) -> tuple[bool, str]:
    base_url, api_key = get_supabase_config()
    if not base_url or not api_key:
        return False, "ยังไม่ได้ตั้งค่า Supabase"
    try:
        r = requests.patch(
            f"{base_url}/rest/v1/trade_setup_plans",
            params={"setup_id": f"eq.{setup_id}", "status": "eq.PLANNED"},
            headers=_supabase_headers(api_key, True),
            json={"status": "LOCKED", "locked_at": pd.Timestamp.now(tz="UTC").isoformat()},
            timeout=10,
        )
        if r.status_code not in (200, 204):
            return False, f"Supabase HTTP={r.status_code}: {r.text[:500]}"
        return True, "ล็อกแผนแล้ว — แก้ไขไม่ได้ในระบบ"
    except Exception as exc:
        return False, str(exc)


@st.cache_data(ttl=5, show_spinner=False)
def fetch_trade_setup_plans(snapshot: dict) -> list[dict]:
    base_url, api_key = get_supabase_config()
    if not base_url or not api_key:
        return []
    params = [("select", "*"), ("order", "created_at.desc"), ("limit", "50")]
    if snapshot.get("login") not in (None, ""):
        params.append(("login", f"eq.{snapshot.get('login')}"))
    if snapshot.get("server") not in (None, ""):
        params.append(("server", f"eq.{snapshot.get('server')}"))
    try:
        r = requests.get(
            f"{base_url}/rest/v1/trade_setup_plans",
            headers=_supabase_headers(api_key),
            params=params,
            timeout=10,
        )
        r.raise_for_status()
        data = r.json()
        return data if isinstance(data, list) else []
    except Exception as exc:
        st.session_state["supabase_error_trade_setup_plans"] = str(exc)
        return []


@st.cache_data(ttl=5, show_spinner=False)
def fetch_gold_m5_candles(limit: int = 600) -> list[dict]:
    """Read XAUUSD M5 candles server-side so the workspace does not depend on CDN JS."""
    base_url, api_key = get_supabase_config()
    if not base_url or not api_key:
        return []
    headers = {"apikey": api_key, "Authorization": f"Bearer {api_key}", "Accept": "application/json"}
    params = {
        "select": "time_unix,open,high,low,close,volume",
        "symbol": "eq.XAUUSD",
        "timeframe": "eq.M5",
        "order": "time_unix.desc",
        "limit": str(limit),
    }
    try:
        r = requests.get(f"{base_url}/rest/v1/mt5_gold_m5_candles", headers=headers, params=params, timeout=10)
        r.raise_for_status()
        rows = r.json()
        if not isinstance(rows, list):
            return []
        out = []
        for x in reversed(rows):
            try:
                out.append({"time": int(x["time_unix"]), "open": float(x["open"]), "high": float(x["high"]), "low": float(x["low"]), "close": float(x["close"]), "volume": float(x.get("volume") or 0)})
            except Exception:
                pass
        return out
    except Exception:
        return []


def render_gold_tradingview_chart() -> None:
    """Gold-only TradingView Advanced Chart with the full dark analysis UI."""
    st.markdown(
        """
        <div class="gold-workspace-head">
          <div>
            <div class="gold-workspace-title">📈 Gold Trading Workspace</div>
            <div class="gold-workspace-subtitle">XAUUSD · M5 · TradingView สำหรับวิเคราะห์ X / IDM / BOS / FVG</div>
          </div>
          <div class="gold-workspace-badge">● PEPPERSTONE · XAUUSD</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Official TradingView Advanced Chart widget settings.
    chart_html = r'''
    <div id="tv-gold-workspace" style="width:100%;height:560px;background:#0b0d10;border:1px solid #242a33;border-radius:14px;overflow:hidden;">
      <div class="tradingview-widget-container" style="width:100%;height:100%;">
        <div class="tradingview-widget-container__widget" style="width:100%;height:100%;"></div>
        <script type="text/javascript" src="https://s3.tradingview.com/external-embedding/embed-widget-advanced-chart.js?v=gold-workspace-v3" async>
        {
          "autosize": true,
          "symbol": "PEPPERSTONE:XAUUSD",
          "interval": "5",
          "timezone": "Asia/Bangkok",
          "theme": "dark",
          "style": "1",
          "locale": "en",
          "backgroundColor": "#0b0d10",
          "gridColor": "rgba(70,78,90,0.24)",
          "allow_symbol_change": false,
          "hide_side_toolbar": false,
          "hide_top_toolbar": false,
          "hide_legend": false,
          "hide_volume": false,
          "withdateranges": true,
          "calendar": false,
          "details": false,
          "hotlist": false,
          "watchlist": [],
          "compareSymbols": [],
          "save_image": true,
          "show_popup_button": false,
          "studies": ["MAExp@tv-basicstudies"],
          "support_host": "https://www.tradingview.com"
        }
        </script>
      </div>
    </div>
    '''

    components.html(chart_html, height=560, scrolling=False)

    st.markdown(
        """
        <div class="gold-workspace-note">
          <span>🧠</span>
          <div>
            <b>Gold Technical Model v1</b>
            <span>M5 Close → EMA200 → X/IDM → BOS → BOS Swing → FVG → Retrace → Entry</span>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

def fetch_gold_position_price(snapshot: dict) -> float | None:
    """Best-effort MT5 current price from an open GOLD/XAUUSD position."""
    try:
        df = fetch_mt5_positions_supabase(snapshot)
        if df.empty:
            return None
        work = df.copy()
        if "symbol" not in work.columns or "price_current" not in work.columns:
            return None
        work["_gold"] = work["symbol"].astype(str).str.upper().isin(GOLD_SYMBOLS)
        work = work[work["_gold"]]
        if work.empty:
            return None
        vals = pd.to_numeric(work["price_current"], errors="coerce").dropna()
        if vals.empty:
            return None
        return float(vals.iloc[0])
    except Exception:
        return None


def page_new_trade_setup(snapshot: dict) -> None:
    """Gold-only M5 pre-trade plan. Plan can be created, then explicitly locked."""
    st.markdown('<div class="nj-section-title">📝 New Trade Setup</div>', unsafe_allow_html=True)
    st.caption("Gold Technical Model v1 · XAUUSD/GOLD เท่านั้น · M5 เท่านั้น · Pre-trade plan ก่อนเข้าออเดอร์")

    if not snapshot or snapshot.get("_error"):
        st.warning("ยังไม่พบ Account Snapshot จาก Supabase")
        return

    st.warning("🔒 Technical Model นี้ใช้ได้เฉพาะ GOLD / XAUUSD และ M5 เท่านั้น — สินทรัพย์อื่นไม่อนุญาต")

    render_gold_tradingview_chart()

    st.markdown("### 🎯 MT5 Price Helper")
    current_gold_price = fetch_gold_position_price(snapshot)
    if current_gold_price is not None:
        st.caption(f"ราคาทองล่าสุดที่อ่านได้จาก mt5_positions: {current_gold_price:,.2f}")
        if st.button("📍 ใช้ราคา MT5 เป็น Planned Entry", key="use_mt5_gold_price", use_container_width=False):
            st.session_state["gold_entry_price_prefill"] = current_gold_price
            st.rerun()
    else:
        st.info("ยังไม่มี Open GOLD/XAUUSD position ใน mt5_positions จึงยังไม่มี current price จาก MT5 ให้ดึงมาใส่ Entry — กราฟ TradingView ใช้วิเคราะห์ได้ตามปกติ")

    plans = fetch_trade_setup_plans(snapshot)
    if plans:
        st.markdown("### แผนที่บันทึกไว้")
        view = pd.DataFrame(plans)
        cols = [c for c in ["setup_id", "symbol", "direction", "timeframe", "trend_state", "planned_rr", "status", "created_at", "locked_at"] if c in view.columns]
        st.dataframe(view[cols], use_container_width=True, hide_index=True)
        for p in plans[:10]:
            sid = str(p.get("setup_id", ""))
            status = str(p.get("status", ""))
            if status == "PLANNED" and sid:
                if st.button(f"🔒 Lock {sid}", key=f"lock_setup_{sid}", use_container_width=False):
                    ok, msg = _setup_patch_locked(sid)
                    if ok:
                        st.success(msg)
                        fetch_trade_setup_plans.clear()
                        st.rerun()
                    else:
                        st.error(msg)
    else:
        st.info("ยังไม่มี Trade Setup ที่บันทึกไว้")

    st.markdown("### สร้างแผนใหม่")
    with st.form("gold_trade_setup_form", clear_on_submit=False):
        c1, c2, c3 = st.columns(3)
        symbol = c1.selectbox("สินทรัพย์", ["XAUUSD"], index=0)
        direction = c2.selectbox("Direction", ["LONG", "SHORT"])
        timeframe = c3.selectbox("Timeframe", ["M5"], index=0)

        st.markdown("#### 1. Trend Change / Market Regime")
        c1, c2 = st.columns(2)
        trend_state = c1.selectbox(
            "สถานะ Trend",
            ["Trend Change Confirmed", "Trend Change Candidate", "Existing Trend"],
            index=0,
        )
        ema200_break_price = c2.number_input(
            "EMA200 Break — ราคาปิด M5",
            min_value=0.0,
            value=0.0,
            step=1.0,
            format="%.2f",
            help="ราคาทองใช้ทศนิยม 2 ตำแหน่ง และปุ่ม +/- ขยับทีละ 1.00"
        )
        st.caption("Candidate = ราคาปิดข้าม EMA200 แล้ว แต่ยังไม่ยืนยัน · Confirmed = มี X/IDM + Valid BOS ครบแล้ว")

        st.markdown("#### 2. Structure")
        c1, c2, c3 = st.columns(3)
        x_price = c1.number_input("X / IDM Price", min_value=0.0, value=0.0, step=1.0, format="%.2f")
        bos_price = c2.number_input("BOS Price", min_value=0.0, value=0.0, step=1.0, format="%.2f")
        bos_swing_high = c3.number_input("BOS Swing High", min_value=0.0, value=0.0, step=1.0, format="%.2f")
        c1, c2, c3 = st.columns(3)
        bos_swing_low = c1.number_input("BOS Swing Low", min_value=0.0, value=0.0, step=1.0, format="%.2f")
        fvg_high = c2.number_input("FVG High", min_value=0.0, value=0.0, step=1.0, format="%.2f")
        fvg_low = c3.number_input("FVG Low", min_value=0.0, value=0.0, step=1.0, format="%.2f")
        st.caption("กฎ: X/IDM → BOS และ FVG ต้องอยู่ภายใน BOS Swing")

        st.markdown("#### 3. Trade Plan")
        c1, c2, c3 = st.columns(3)
        entry = c1.number_input(
            "Planned Entry",
            min_value=0.0,
            value=float(st.session_state.get("gold_entry_price_prefill") or 0.0),
            step=1.0,
            format="%.2f",
            key="gold_entry_price",
        )
        sl = c2.number_input("Stop Loss", min_value=0.0, value=0.0, step=1.0, format="%.2f")
        tp = c3.number_input("Take Profit", min_value=0.0, value=0.0, step=1.0, format="%.2f")
        rr = _planned_rr(direction, entry, sl, tp)
        st.metric("Planned RR", f"1 : {rr:.2f}" if rr is not None else "—")

        st.markdown("#### 4. Evidence")
        screenshot_url = st.text_input("ลิงก์ Screenshot กราฟ (optional)", placeholder="https://...")
        notes = st.text_area("Trade Thesis / Notes", height=110, placeholder="เหตุผลของแผนก่อนเข้าเทรด...")

        submitted = st.form_submit_button("💾 Save Trade Plan", type="primary", use_container_width=True)

    if submitted:
        errors = []
        if not _gold_symbol_allowed(symbol):
            errors.append("Technical Model อนุญาตเฉพาะ GOLD / XAUUSD")
        if timeframe != "M5":
            errors.append("Technical Model อนุญาตเฉพาะ M5")
        if trend_state == "Trend Change Confirmed" and (x_price <= 0 or bos_price <= 0):
            errors.append("Trend Change Confirmed ต้องมี X/IDM และ BOS price")
        if fvg_high > 0 and fvg_low > 0 and bos_swing_high > 0 and bos_swing_low > 0:
            if not (bos_swing_low <= fvg_low <= fvg_high <= bos_swing_high):
                errors.append("FVG ต้องอยู่ภายใน BOS Swing")
        if rr is None:
            errors.append("Entry / SL / TP ไม่สอดคล้องกับ Direction จึงคำนวณ RR ไม่ได้")

        if errors:
            for e in errors:
                st.error(e)
        else:
            row = {
                "setup_id": f"GOLD-{uuid.uuid4().hex[:10].upper()}",
                "login": snapshot.get("login"),
                "server": snapshot.get("server"),
                "symbol": "XAUUSD",
                "direction": direction,
                "timeframe": "M5",
                "trend_state": trend_state,
                "ema200_break_price": ema200_break_price or None,
                "x_price": x_price or None,
                "bos_price": bos_price or None,
                "bos_swing_high": bos_swing_high or None,
                "bos_swing_low": bos_swing_low or None,
                "fvg_high": fvg_high or None,
                "fvg_low": fvg_low or None,
                "entry_price": entry or None,
                "stop_loss": sl or None,
                "take_profit": tp or None,
                "planned_rr": rr,
                "screenshot_url": screenshot_url.strip() or None,
                "notes": notes.strip() or None,
                "status": "PLANNED",
            }
            ok, msg, saved = _setup_post(row)
            if ok:
                st.success(f"{msg} · {saved.get('setup_id', row['setup_id'])}")
                fetch_trade_setup_plans.clear()
                st.rerun()
            else:
                st.error(msg)

    st.markdown("### Model Rules — Locked v1")
    st.code("""GOLD / XAUUSD ONLY
M5 ONLY

M5 candle CLOSE crosses EMA200
        ↓
Trend Change Candidate
        ↓
X / IDM
        ↓
Valid BOS (กฎ BOS เดิมครบ)
        ↓
Trend Change Confirmed
        ↓
Focus New Trend
        ↓
X → BOS → BOS Swing → FVG inside BOS Swing → Retrace → Entry

EMA200 = regime filter, not entry trigger
Wick ผ่าน EMA200 อย่างเดียว = ไม่ยืนยัน Trend Change
""", language="text")



def page_performance_baseline(snapshot: dict) -> None:
    """Step 1: factual trading-performance baseline from MT5 deal history."""
    st.markdown('<div class="nj-section-title">Trading Performance Baseline</div>', unsafe_allow_html=True)
    st.caption("Step 1 · สถิติพื้นฐานจาก Trade History ของ MT5 → Supabase · ยังไม่ทำ Behavior/Quant inference")

    if not snapshot or snapshot.get("_error"):
        st.warning("ยังไม่พบ Account Snapshot จาก Supabase")
        return

    history = fetch_mt5_history_supabase(snapshot)
    trades = _trade_baseline_rows(history)
    if trades.empty:
        st.info("ยังไม่มี Closed Trade ที่ใช้คำนวณ Performance Baseline")
        return

    results = trades["net_result"].astype(float)
    wins = results[results > 0]
    losses = results[results < 0]
    breakeven = int((results == 0).sum())
    total = len(results)
    gross_profit = float(wins.sum())
    gross_loss_abs = float(abs(losses.sum()))
    net_pnl = float(results.sum())
    win_rate = float(len(wins) / total * 100) if total else 0.0
    loss_rate = float(len(losses) / total * 100) if total else 0.0
    pf = gross_profit / gross_loss_abs if gross_loss_abs > 0 else None
    avg_win = float(wins.mean()) if len(wins) else 0.0
    avg_loss = float(losses.mean()) if len(losses) else 0.0
    expectancy = float(results.mean()) if total else 0.0
    ws, ls = _streaks(results.tolist())

    c1,c2,c3,c4 = st.columns(4)
    c1.metric("Total Trades", f"{total:,}")
    c2.metric("Win Rate", f"{win_rate:.2f}%")
    c3.metric("Profit Factor", f"{pf:.2f}" if pf is not None else "—")
    c4.metric("Net P&L", f"{net_pnl:+,.2f}")

    c1,c2,c3,c4 = st.columns(4)
    c1.metric("Winning Trades", f"{len(wins):,}")
    c2.metric("Losing Trades", f"{len(losses):,}")
    c3.metric("Breakeven", f"{breakeven:,}")
    c4.metric("Expectancy / Trade", f"{expectancy:+,.2f}")

    st.markdown("### Average Results")
    c1,c2,c3 = st.columns(3)
    c1.metric("Average Win", f"{avg_win:+,.2f}")
    c2.metric("Average Loss", f"{avg_loss:+,.2f}")
    c3.metric("Gross Profit / Gross Loss", f"{gross_profit:,.2f} / -{gross_loss_abs:,.2f}")

    st.markdown("### Streaks")
    c1,c2 = st.columns(2)
    c1.metric("Max Winning Streak", f"{ws}")
    c2.metric("Max Losing Streak", f"{ls}")

    st.markdown("### RR / Holding Time")
    st.info("Average RR และ Average Holding Time ยังไม่ถูกคำนวณใน Step 1 เพราะ mt5_trade_history ที่มีอยู่ยังไม่มีข้อมูล Entry→Exit pair พร้อม SL/TP ที่เพียงพอสำหรับคำนวณอย่างถูกต้อง")

    view_cols = [c for c in ["deal_ticket","order_ticket","position_id","symbol","deal_type","entry_type","volume","price","net_result","deal_time"] if c in trades.columns]
    if view_cols:
        st.markdown("### Closed Trade Data ที่ใช้คำนวณ")
        st.dataframe(trades[view_cols].head(100), use_container_width=True, hide_index=True)

    st.caption("หมายเหตุ: ค่าทั้งหมดคำนวณจากข้อมูลที่ Collector เก็บจริง และยังไม่มีการให้คะแนนว่าเทรดดีหรือแย่")

def page_open(pos: pd.DataFrame) -> None:
    st.subheader("ไม้ที่เปิดอยู่")
    if pos.empty:
        st.info("ไม่มีไม้เปิดอยู่ตอนนี้")
        return

    total = pos["unrealized"].sum()
    c1, c2, c3 = st.columns(3)
    c1.metric("จำนวนไม้", len(pos))
    c2.metric("Lots รวม", f"{pos['volume'].sum():,.2f}")
    c3.metric("กำไรลอยตัว", f"{total:+,.2f}")

    for _, r in pos.iterrows():
        tone = "nj-pos" if r["unrealized"] >= 0 else "nj-neg"
        st.markdown('<div class="nj-card nj-open">', unsafe_allow_html=True)
        c1, c2, c3, c4, c5 = st.columns([1.2, 1, 1, 1, 1.4])
        c1.markdown(
            f"**{r['symbol']}** &nbsp; <span class='nj-tag'>{r['direction']}</span>",
            unsafe_allow_html=True,
        )
        c2.markdown(f"<span class='nj-muted'>Lots</span><br>{r['volume']:,.2f}", unsafe_allow_html=True)
        c3.markdown(
            f"<span class='nj-muted'>เข้า → ปัจจุบัน</span><br>"
            f"{r['open_price']:,.5g} → {r['current_price']:,.5g}",
            unsafe_allow_html=True,
        )
        sl = f"{r['stop_loss']:,.5g}" if r["stop_loss"] else "—"
        tp = f"{r['take_profit']:,.5g}" if r["take_profit"] else "—"
        c4.markdown(f"<span class='nj-muted'>SL / TP</span><br>{sl} / {tp}", unsafe_allow_html=True)
        c5.markdown(
            f"<span class='nj-muted'>กำไรลอยตัว</span><br>"
            f"<span class='{tone}'>{r['unrealized']:+,.2f}</span>",
            unsafe_allow_html=True,
        )
        if not r["stop_loss"]:
            st.markdown(
                "<span class='nj-tag'>⚠️ ไม่มี Stop Loss</span>", unsafe_allow_html=True
            )
        st.markdown("</div>", unsafe_allow_html=True)


def _parse_mistakes(raw) -> list[str]:
    if isinstance(raw, list):
        return raw
    try:
        v = json.loads(raw or "[]")
        return [m for m in v if m in MISTAKES] if isinstance(v, list) else []
    except (TypeError, ValueError):
        return []


def _pick(options: list[str], value: str, blank: bool = True) -> int:
    opts = ([""] if blank else []) + options
    return opts.index(value) if value in opts else 0


def page_journal(df: pd.DataFrame, store: NoteStore, aid: str) -> None:
    st.subheader("Journal — บันทึกเหตุผลและบทเรียนรายไม้")
    st.caption(f"ที่เก็บโน้ต: {store.backend}")
    if store.remote is False:
        st.warning(
            "ตอนนี้ใช้ SQLite ชั่วคราว โน้ตจะหายเมื่อ Streamlit Cloud restart — "
            "ตั้ง SUPABASE_URL / SUPABASE_KEY ใน secrets เพื่อเก็บถาวร"
        )
    if store.last_error:
        st.error(store.last_error)

    if df.empty:
        st.info("ยังไม่มีไม้ที่ปิดในช่วงเวลาที่เลือก")
        return

    only_missing = st.checkbox("แสดงเฉพาะไม้ที่ยังไม่ได้บันทึก", value=False)
    view = df[~df["has_note"]] if only_missing else df
    if view.empty:
        st.success("บันทึกครบทุกไม้แล้ว 🎉")
        return

    view = view.head(200)
    labels = {
        r["trade_id"]: (
            f"{r['close_time']:%Y-%m-%d %H:%M} · {r['symbol']} {r['direction']} · "
            f"{r['net']:+,.2f}{' · ✍️' if r['has_note'] else ''}"
        )
        for _, r in view.iterrows()
    }
    tid = st.selectbox("เลือกไม้", list(labels), format_func=labels.get)
    row = df[df["trade_id"] == tid].iloc[0]

    tone = "nj-win" if row["net"] > 0 else "nj-loss"
    st.markdown(f'<div class="nj-card {tone}">', unsafe_allow_html=True)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Symbol", f"{row['symbol']} {row['direction']}")
    c2.metric("Net", f"{row['net']:+,.2f}")
    c3.metric("Lots", f"{row['volume']:,.2f}")
    c4.metric("ถือนาน (นาที)", f"{row['duration_min']:,.0f}")
    st.markdown("</div>", unsafe_allow_html=True)

    note = store.get(tid, aid)

    with st.form(f"note_{tid}"):
        c1, c2, c3 = st.columns(3)
        setup = c1.selectbox("Setup", [""] + SETUPS, index=_pick(SETUPS, note["setup"]))
        tf = c2.selectbox("Timeframe", [""] + TIMEFRAMES, index=_pick(TIMEFRAMES, note["timeframe"]))
        conf = c3.slider("ความมั่นใจ", 1, 5, int(note["confidence"] or 3))

        c1, c2, c3 = st.columns(3)
        emo_in = c1.selectbox("อารมณ์ตอนเข้า", [""] + EMOTIONS, index=_pick(EMOTIONS, note["emotion_in"]))
        emo_out = c2.selectbox("อารมณ์ตอนออก", [""] + EMOTIONS, index=_pick(EMOTIONS, note["emotion_out"]))
        followed = c3.checkbox("ทำตามแผน", value=bool(int(note["followed_plan"] or 0)))

        mistakes = st.multiselect("ข้อผิดพลาด", MISTAKES, default=_parse_mistakes(note["mistakes"]))
        thesis = st.text_area("เหตุผลที่เข้า (thesis)", value=str(note["thesis"] or ""), height=90)
        lesson = st.text_area("บทเรียน", value=str(note["lesson"] or ""), height=90)
        c1, c2 = st.columns(2)
        tags = c1.text_input("Tags (คั่นด้วย ,)", value=str(note["tags"] or ""))
        shot = c2.text_input("ลิงก์ภาพกราฟ", value=str(note["screenshot_url"] or ""))

        if st.form_submit_button("บันทึก", type="primary", use_container_width=True):
            ok = store.save(
                tid, aid,
                setup=setup, timeframe=tf, confidence=conf,
                emotion_in=emo_in, emotion_out=emo_out, followed_plan=followed,
                mistakes=mistakes, thesis=thesis, lesson=lesson,
                tags=tags, screenshot_url=shot,
            )
            if ok:
                st.success("บันทึกแล้ว")
                st.rerun()
            else:
                st.error(store.last_error or "บันทึกไม่สำเร็จ")

    if str(note["screenshot_url"]).startswith("http"):
        st.image(note["screenshot_url"], use_container_width=True)


# =========================================================
# MAIN
# =========================================================

NAV = ["📊 Dashboard", "📝 New Trade Setup", "🛡️ Setup Compliance", "📈 Trading Performance", "📊 Performance Breakdown", "🧠 Trading Behavior", "🧬 Trading DNA", "📐 Portfolio Exposure", "🛡️ Risk Engine", "🧠 Decision Engine", "🟡 ไม้ที่เปิดอยู่", "📓 Journal", "🔌 เชื่อมต่อบัญชี"]


# =========================================================
# GOLD SETUP COMPLIANCE ENGINE v1
# =========================================================

def _compliance_direction(deal_type: str) -> str:
    s = str(deal_type or '').upper()
    if 'BUY' in s:
        return 'LONG'
    if 'SELL' in s:
        return 'SHORT'
    return ''


def _entry_inside_fvg(price, fvg_high, fvg_low) -> bool | None:
    try:
        hi, lo, px = float(fvg_high), float(fvg_low), float(price)
    except (TypeError, ValueError):
        return None
    if hi < lo:
        hi, lo = lo, hi
    return lo <= px <= hi


def _evaluate_setup_plan(plan: dict, deal: dict) -> tuple[str, str]:
    planned_dir = str(plan.get('direction') or '').upper()
    actual_dir = _compliance_direction(deal.get('deal_type'))
    actual_entry = _num(deal.get('price'), None)
    if planned_dir and actual_dir and planned_dir != actual_dir:
        return 'DEVIATION', f'Direction mismatch: plan={planned_dir}, actual={actual_dir}'
    inside = _entry_inside_fvg(actual_entry, plan.get('fvg_high'), plan.get('fvg_low')) if actual_entry is not None else None
    if inside is False:
        return 'DEVIATION', 'Actual entry is outside the planned FVG zone'
    if inside is True:
        return 'COMPLIANT', 'Direction matches and actual entry is inside planned FVG'
    return 'PENDING', 'Direction matches; FVG bounds are not available for automatic entry-zone verification'


def _fetch_compliance_rows(snapshot: dict) -> list[dict]:
    base_url, api_key = get_supabase_config()
    if not base_url or not api_key:
        return []
    params = [('select', '*'), ('order', 'evaluated_at.desc.nullslast,created_at.desc'), ('limit', '100')]
    if snapshot.get('login') not in (None, ''):
        params.append(('login', f"eq.{snapshot.get('login')}"))
    if snapshot.get('server') not in (None, ''):
        params.append(('server', f"eq.{snapshot.get('server')}"))
    try:
        r = requests.get(f'{base_url}/rest/v1/trade_setup_compliance', headers=_supabase_headers(api_key), params=params, timeout=10)
        r.raise_for_status()
        data = r.json()
        return data if isinstance(data, list) else []
    except Exception as exc:
        st.session_state['supabase_error_trade_setup_compliance'] = str(exc)
        return []


def _save_compliance(row: dict) -> tuple[bool, str]:
    base_url, api_key = get_supabase_config()
    if not base_url or not api_key:
        return False, 'ยังไม่ได้ตั้งค่า Supabase'
    try:
        r = requests.post(
            f'{base_url}/rest/v1/trade_setup_compliance',
            headers=_supabase_headers(api_key, True),
            params={'on_conflict': 'setup_id,deal_ticket'},
            json=row,
            timeout=10,
        )
        if r.status_code not in (200, 201, 204):
            return False, f'Supabase HTTP={r.status_code}: {r.text[:500]}'
        return True, 'บันทึก Compliance แล้ว'
    except Exception as exc:
        return False, str(exc)


def _patch_compliance(setup_id: str, deal_ticket, patch: dict) -> tuple[bool, str]:
    """Update one existing compliance row without creating a duplicate."""
    base_url, api_key = get_supabase_config()
    if not base_url or not api_key:
        return False, 'ยังไม่ได้ตั้งค่า Supabase'
    try:
        params = {
            'setup_id': f'eq.{setup_id}',
            'deal_ticket': f'eq.{int(float(deal_ticket))}',
        }
        r = requests.patch(
            f'{base_url}/rest/v1/trade_setup_compliance',
            headers=_supabase_headers(api_key, True),
            params=params,
            json=patch,
            timeout=10,
        )
        if r.status_code not in (200, 204):
            return False, f'Supabase HTTP={r.status_code}: {r.text[:500]}'
        return True, 'อัปเดต lifecycle แล้ว'
    except Exception as exc:
        return False, str(exc)


def _entry_deal_rows(history: pd.DataFrame) -> list[dict]:
    if history is None or history.empty:
        return []
    rows = history.to_dict('records')
    out = []
    for deal in rows:
        if not _gold_symbol_allowed(deal.get('symbol')):
            continue
        entry = str(deal.get('entry_type') or '').upper()
        if entry not in ('IN', 'ENTRY', 'INOUT'):
            continue
        if not str(deal.get('deal_ticket') or '').strip():
            continue
        out.append(deal)
    return out


def _exit_deal_rows(history: pd.DataFrame) -> list[dict]:
    if history is None or history.empty:
        return []
    rows = history.to_dict('records')
    out = []
    for deal in rows:
        if not _gold_symbol_allowed(deal.get('symbol')):
            continue
        entry = str(deal.get('entry_type') or '').upper()
        if entry not in ('OUT', 'EXIT'):
            continue
        if not str(deal.get('deal_ticket') or '').strip():
            continue
        out.append(deal)
    return out


def _find_position_snapshot(snapshot: dict, position_id) -> dict | None:
    """Return current MT5 position when the trade is still open."""
    if position_id in (None, ''):
        return None
    df = fetch_mt5_positions_supabase(snapshot)
    if df.empty or 'ticket' not in df.columns:
        return None
    try:
        pid = int(float(position_id))
    except (TypeError, ValueError):
        return None
    for row in df.to_dict('records'):
        try:
            if int(float(row.get('ticket'))) == pid:
                return row
        except (TypeError, ValueError):
            continue
    return None


def _lifecycle_for_entry(entry: dict, exits: list[dict], position_snapshot: dict | None, plan: dict) -> dict:
    """Build exit/lifecycle information for one matched entry position."""
    position_id = entry.get('position_id')
    entry_time = pd.to_datetime(entry.get('deal_time'), utc=True, errors='coerce')
    candidates = []
    for ex in exits:
        if str(ex.get('symbol') or '').upper() != str(entry.get('symbol') or '').upper():
            continue
        if str(ex.get('position_id') or '') != str(position_id or ''):
            continue
        ex_time = pd.to_datetime(ex.get('deal_time'), utc=True, errors='coerce')
        if pd.isna(ex_time):
            continue
        if pd.notna(entry_time) and ex_time < entry_time:
            continue
        candidates.append((ex_time, ex))
    candidates.sort(key=lambda x: x[0])

    actual_sl = None
    actual_tp = None
    if position_snapshot:
        actual_sl = position_snapshot.get('stop_loss')
        actual_tp = position_snapshot.get('take_profit')

    # No exit yet: keep lifecycle OPEN if the current position still exists.
    if not candidates:
        if position_snapshot:
            return {
                'lifecycle_status': 'OPEN',
                'exit_deal_ticket': None,
                'exit_price': None,
                'exit_time': None,
                'actual_stop_loss': actual_sl,
                'actual_take_profit': actual_tp,
                'realized_r': None,
            }
        return {
            'lifecycle_status': 'PENDING_EXIT',
            'exit_deal_ticket': None,
            'exit_price': None,
            'exit_time': None,
            'actual_stop_loss': None,
            'actual_take_profit': None,
            'realized_r': None,
        }

    # If there are partial exits, use volume-weighted exit price and sum realized result.
    total_vol = 0.0
    weighted_price = 0.0
    realized_profit = 0.0
    last_ticket = None
    last_time = None
    for ex_time, ex in candidates:
        vol = _num(ex.get('volume'), 0.0)
        px = _num(ex.get('price'), None)
        if px is not None and vol > 0:
            weighted_price += px * vol
            total_vol += vol
        realized_profit += _num(ex.get('profit'), 0.0)
        realized_profit += _num(ex.get('commission'), 0.0)
        realized_profit += _num(ex.get('swap'), 0.0)
        realized_profit += _num(ex.get('fee'), 0.0)
        last_ticket = ex.get('deal_ticket')
        last_time = ex_time

    exit_price = (weighted_price / total_vol) if total_vol > 0 else _num(candidates[-1][1].get('price'), None)

    # Planned R is based on the locked plan's entry and stop, not on P&L.
    planned_entry = _num(plan.get('entry_price'), None)
    planned_sl = _num(plan.get('stop_loss'), None)
    realized_r = None
    if planned_entry is not None and planned_sl is not None and exit_price is not None:
        direction = str(plan.get('direction') or '').upper()
        risk = (planned_entry - planned_sl) if direction == 'LONG' else (planned_sl - planned_entry)
        if risk > 0:
            move = (exit_price - planned_entry) if direction == 'LONG' else (planned_entry - exit_price)
            realized_r = move / risk

    return {
        'lifecycle_status': 'CLOSED',
        'exit_deal_ticket': int(float(last_ticket)) if str(last_ticket or '').strip() else None,
        'exit_price': exit_price,
        'exit_time': last_time.isoformat() if last_time is not None else None,
        'actual_stop_loss': actual_sl,
        'actual_take_profit': actual_tp,
        'realized_r': realized_r,
        '_realized_profit': realized_profit,
    }


def _match_locked_plans(snapshot: dict) -> tuple[int, int, int]:
    """Match LOCKED Gold/M5 plans to MT5 entries and then follow each position lifecycle."""
    plans = fetch_trade_setup_plans(snapshot)
    locked = [
        p for p in plans
        if str(p.get('status') or '').upper() == 'LOCKED'
        and _gold_symbol_allowed(p.get('symbol'))
        and str(p.get('timeframe') or '').upper() == 'M5'
    ]
    if not locked:
        return 0, 0, 0

    history = fetch_mt5_history_supabase(snapshot)
    if history.empty:
        return len(locked), 0, 0

    existing_rows = _fetch_compliance_rows(snapshot)
    existing_by_setup = {str(x.get('setup_id')): x for x in existing_rows if x.get('setup_id')}
    rows = history.to_dict('records')
    entries = _entry_deal_rows(history)
    exits = _exit_deal_rows(history)

    # A plan consumes one entry deal. Existing compliance rows are authoritative.
    used_entry_tickets = {
        str(x.get('deal_ticket')) for x in existing_rows if str(x.get('deal_ticket') or '').strip()
    }
    matched = 0
    lifecycle_updates = 0

    for plan in locked:
        setup_id = str(plan.get('setup_id') or '')
        if not setup_id:
            continue

        # If already matched, refresh lifecycle instead of assigning another entry.
        existing = existing_by_setup.get(setup_id)
        if existing:
            entry_ticket = existing.get('deal_ticket')
            entry = next((d for d in entries if str(d.get('deal_ticket')) == str(entry_ticket)), None)
            if entry:
                lifecycle = _lifecycle_for_entry(
                    entry, exits, _find_position_snapshot(snapshot, existing.get('position_id')), plan
                )
                patch = {
                    'actual_stop_loss': lifecycle.get('actual_stop_loss'),
                    'actual_take_profit': lifecycle.get('actual_take_profit'),
                    'lifecycle_status': lifecycle.get('lifecycle_status'),
                    'exit_deal_ticket': lifecycle.get('exit_deal_ticket'),
                    'exit_price': lifecycle.get('exit_price'),
                    'exit_time': lifecycle.get('exit_time'),
                    'realized_r': lifecycle.get('realized_r'),
                    'evaluated_at': pd.Timestamp.now(tz='UTC').isoformat(),
                }
                ok, _ = _patch_compliance(setup_id, entry_ticket, patch)
                if ok:
                    lifecycle_updates += 1
            continue

        lock_time = pd.to_datetime(plan.get('locked_at'), utc=True, errors='coerce')
        candidates = []
        for deal in entries:
            ticket = str(deal.get('deal_ticket') or '')
            if not ticket or ticket in used_entry_tickets:
                continue
            deal_time = pd.to_datetime(deal.get('deal_time'), utc=True, errors='coerce')
            if pd.isna(deal_time):
                continue
            if pd.notna(lock_time) and deal_time < lock_time:
                continue
            if not _gold_symbol_allowed(deal.get('symbol')):
                continue
            candidates.append((deal_time, deal))
        candidates.sort(key=lambda x: x[0])
        if not candidates:
            continue

        deal = candidates[0][1]
        deal_ticket = str(deal.get('deal_ticket'))
        status, reason = _evaluate_setup_plan(plan, deal)
        lifecycle = _lifecycle_for_entry(deal, exits, _find_position_snapshot(snapshot, deal.get('position_id')), plan)
        row = {
            'setup_id': setup_id,
            'login': plan.get('login') or snapshot.get('login'),
            'server': plan.get('server') or snapshot.get('server'),
            'deal_ticket': int(float(deal_ticket)) if deal_ticket else None,
            'position_id': int(float(deal.get('position_id'))) if str(deal.get('position_id') or '').strip() else None,
            'symbol': str(deal.get('symbol') or 'XAUUSD'),
            'planned_direction': plan.get('direction'),
            'actual_direction': _compliance_direction(deal.get('deal_type')),
            'planned_entry': plan.get('entry_price'),
            'actual_entry': deal.get('price'),
            'planned_stop_loss': plan.get('stop_loss'),
            'actual_stop_loss': lifecycle.get('actual_stop_loss'),
            'planned_take_profit': plan.get('take_profit'),
            'actual_take_profit': lifecycle.get('actual_take_profit'),
            'planned_rr': plan.get('planned_rr'),
            'compliance_status': status,
            'deviation_reason': reason,
            'trade_profit': deal.get('profit'),
            'trade_commission': deal.get('commission'),
            'trade_swap': deal.get('swap'),
            'trade_fee': deal.get('fee'),
            'lifecycle_status': lifecycle.get('lifecycle_status'),
            'exit_deal_ticket': lifecycle.get('exit_deal_ticket'),
            'exit_price': lifecycle.get('exit_price'),
            'exit_time': lifecycle.get('exit_time'),
            'realized_r': lifecycle.get('realized_r'),
            'evaluated_at': pd.Timestamp.now(tz='UTC').isoformat(),
        }
        ok, _ = _save_compliance(row)
        if ok:
            matched += 1
            used_entry_tickets.add(deal_ticket)
            existing_by_setup[setup_id] = row

    return len(locked), matched, lifecycle_updates

def page_setup_compliance(snapshot: dict) -> None:
    st.markdown('<div class="nj-section-title">🛡️ Setup Compliance</div>', unsafe_allow_html=True)
    st.caption('Gold Technical Model v1 · Locked Plan ↔ MT5 Trade · Compliance แยกจาก P&L · Full lifecycle v2')
    if not snapshot or snapshot.get('_error'):
        st.warning('ยังไม่พบ Account Snapshot จาก Supabase')
        return

    if st.button('↻ ตรวจสอบ Trade ใหม่ / Refresh Lifecycle', key='run_setup_compliance'):
        with st.spinner('กำลังจับคู่ Locked Plan → Entry → Exit...'):
            total, matched, updated = _match_locked_plans(snapshot)
        st.success(f'Locked Plan {total} รายการ · จับคู่ใหม่ {matched} · อัปเดต Lifecycle {updated}')
        fetch_mt5_history_supabase.clear()
        fetch_mt5_positions_supabase.clear()
        st.rerun()

    plans = fetch_trade_setup_plans(snapshot)
    locked = [p for p in plans if str(p.get('status') or '').upper() == 'LOCKED' and _gold_symbol_allowed(p.get('symbol')) and str(p.get('timeframe') or '').upper() == 'M5']
    history = fetch_mt5_history_supabase(snapshot)
    entries = _entry_deal_rows(history)
    rows = _fetch_compliance_rows(snapshot)

    # Diagnostic counters make it obvious why a plan is still unmatched.
    c1, c2, c3, c4 = st.columns(4)
    c1.metric('Locked Plans', len(locked))
    c2.metric('Gold Entry Deals', len(entries))
    c3.metric('Matched', len(rows))
    lifecycle_counts = pd.Series([str(x.get('lifecycle_status') or 'PENDING') for x in rows]).value_counts() if rows else pd.Series(dtype=int)
    c4.metric('Closed', int(lifecycle_counts.get('CLOSED', 0)))

    if not rows:
        st.info('ยังไม่มี Trade ที่จับคู่กับ Locked Trade Plan')
        if locked:
            latest_entries = sorted(entries, key=lambda d: pd.to_datetime(d.get('deal_time'), utc=True, errors='coerce'), reverse=True)
            st.markdown('### 🔎 ทำไมยังไม่จับคู่')
            for plan in locked[:10]:
                lock_time = pd.to_datetime(plan.get('locked_at'), utc=True, errors='coerce')
                eligible = [
                    d for d in latest_entries
                    if pd.notna(lock_time) and pd.notna(pd.to_datetime(d.get('deal_time'), utc=True, errors='coerce'))
                    and pd.to_datetime(d.get('deal_time'), utc=True, errors='coerce') >= lock_time
                    and _gold_symbol_allowed(d.get('symbol'))
                ]
                if eligible:
                    d = eligible[0]
                    st.warning(f"Plan {plan.get('setup_id')} พบ Gold Entry หลัง LOCK แล้ว: Deal {d.get('deal_ticket')} · {d.get('symbol')} · {d.get('deal_time')}")
                else:
                    st.caption(f"Plan {plan.get('setup_id')} · LOCK {plan.get('locked_at')} → ยังไม่มี GOLD Entry หลัง LOCK")
        else:
            st.caption('ยังไม่มี LOCKED Plan ที่เป็น GOLD/XAUUSD + M5')
        st.caption('ระบบจะจับคู่เฉพาะ GOLD/XAUUSD และ Entry deal ที่เกิดหลัง Plan ถูก LOCK')
        return

    df = pd.DataFrame(rows)
    counts = df['compliance_status'].value_counts() if 'compliance_status' in df.columns else pd.Series(dtype=int)
    lifecycle = df['lifecycle_status'].value_counts() if 'lifecycle_status' in df.columns else pd.Series(dtype=int)
    a1, a2, a3, a4, a5 = st.columns(5)
    a1.metric('Matched Trades', len(df))
    a2.metric('🟢 Compliant', int(counts.get('COMPLIANT', 0)))
    a3.metric('🟡 Deviation', int(counts.get('DEVIATION', 0)))
    a4.metric('🟢 Open', int(lifecycle.get('OPEN', 0)))
    a5.metric('🔵 Closed', int(lifecycle.get('CLOSED', 0)))

    preferred = [
        'setup_id','deal_ticket','position_id','symbol','planned_direction','actual_direction',
        'planned_entry','actual_entry','planned_stop_loss','actual_stop_loss',
        'planned_take_profit','actual_take_profit','planned_rr','exit_price','realized_r',
        'compliance_status','lifecycle_status','trade_profit','deviation_reason','evaluated_at'
    ]
    cols = [c for c in preferred if c in df.columns]
    st.dataframe(df[cols], use_container_width=True, hide_index=True)

    st.markdown('### Lifecycle')
    st.caption('OPEN = ยังมี position ใน MT5 · PENDING_EXIT = พบ Entry แต่ยังไม่พบ Exit และ position snapshot ไม่อยู่แล้ว · CLOSED = พบ Exit deal จาก position_id เดียวกัน')
    st.info('Realized R คำนวณจาก Entry/SL/Exit ตามแผนที่ LOCKED ไม่ได้ใช้กำไร/ขาดทุนเป็นเกณฑ์ตัดสิน Compliance')
    st.warning('ข้อจำกัด v2: Actual SL/TP ของออเดอร์ที่ปิดไปแล้วจะยังยืนยันย้อนหลังไม่ได้จากข้อมูล collector ปัจจุบัน เพราะ mt5_trade_history เก็บ deal แต่ไม่ได้เก็บ SL/TP ณ ตอนเปิดออเดอร์; ถ้า position ยังเปิดอยู่ ระบบอ่าน SL/TP ปัจจุบันจาก mt5_positions ได้')
    st.info('X/IDM, BOS และ FVG structure ยังคงมาจาก Trade Plan ที่บันทึกเอง ระบบจะไม่แกล้งอนุมานโครงสร้างจาก deal history')


def main() -> None:
    if not gate():
        st.stop()

    with st.sidebar:
        st.markdown(
            f'<div class="nj-app-title">📓 {APP_NAME}</div>'
            f'<div class="nj-app-sub">Trading journal · v{APP_VERSION}</div>',
            unsafe_allow_html=True,
        )
        st.markdown('<div class="nj-nav-label">Navigation</div>', unsafe_allow_html=True)
        page = st.radio("เมนู", NAV, label_visibility="collapsed")
        st.divider()

        default_region = secret("METAAPI_REGION", "new-york")
        if not secret("METAAPI_TOKEN"):
            sb_url, sb_key = get_supabase_config()
            if sb_url and sb_key:
                st.markdown('<div class="nj-nav-label">MT5 Data</div>', unsafe_allow_html=True)
                st.markdown('<div class="nj-side-card"><div class="nj-side-muted">SOURCE</div><div class="nj-side-value">🟢 Supabase / NobodyCollector</div></div>', unsafe_allow_html=True)
            else:
                st.markdown('<div class="nj-nav-label">MetaApi</div>', unsafe_allow_html=True)
                st.text_input("MetaApi Token", type="password", key="mapi_token")
        st.selectbox(
            "Region เริ่มต้น", REGIONS,
            index=REGIONS.index(default_region) if default_region in REGIONS else 0,
            key="mapi_region",
        )

    token, region = get_token(), get_region()
    supabase_url, supabase_key = get_supabase_config()

    # Free architecture: ถ้าไม่มี MetaApi ให้ใช้ MT5 -> Supabase เป็นแหล่งข้อมูลหลัก
    if not token and supabase_url and supabase_key:
        if page == "📊 Dashboard":
            page_supabase_dashboard(fetch_latest_mt5_snapshot())
            return
        if page == "📝 New Trade Setup":
            page_new_trade_setup(fetch_latest_mt5_snapshot())
            return
        if page == "🛡️ Setup Compliance":
            page_setup_compliance(fetch_latest_mt5_snapshot())
            return
        if page == "📈 Trading Performance":
            page_performance_baseline(fetch_latest_mt5_snapshot())
            return
        if page == "📊 Performance Breakdown":
            page_performance_breakdown(fetch_latest_mt5_snapshot())
            return
        if page == "🧠 Trading Behavior":
            page_behavior_analysis(fetch_latest_mt5_snapshot())
            return
        if page == "🧬 Trading DNA":
            page_trading_dna(fetch_latest_mt5_snapshot())
            return
        if page == "📐 Portfolio Exposure":
            page_exposure(fetch_latest_mt5_snapshot())
            return
        if page == "🛡️ Risk Engine":
            page_risk_engine(fetch_latest_mt5_snapshot())
            return
        if page == "🧠 Decision Engine":
            page_decision_engine(fetch_latest_mt5_snapshot())
            return
        if page == "🟡 ไม้ที่เปิดอยู่":
            page_live_monitor(fetch_latest_mt5_snapshot())
            return
        if page == "🔌 เชื่อมต่อบัญชี":
            st.subheader("🔌 MT5 Collector")
            st.success("Supabase เชื่อมต่อแล้ว — NobodyCollector กำลังส่งข้อมูลจาก MT5", icon="✅")
            st.code("MT5 → NobodyCollector → Supabase → Nobody Trade Journal", language="text")
            st.caption("Account / Positions / Pending / Trade History พร้อมอ่านจาก Supabase")
            return
        if page == "📓 Journal":
            st.info(
                "Journal เดิมยังใช้ระบบโน้ตเดิมอยู่ · การเชื่อม Trade History จาก Supabase เข้ากับ Journal จะทำในขั้นถัดไป",
                icon="ℹ️",
            )
            return
        st.info("ยังไม่มีเนื้อหาสำหรับเมนูนี้")
        return

    if not token:
        st.markdown(
            '<div class="nj-hero"><div class="nj-empty-icon">🔐</div>'
            '<h2>ยังไม่ได้ตั้งค่าแหล่งข้อมูล</h2>'
            '<p>ตั้งค่า SUPABASE_URL + SUPABASE_KEY สำหรับ MT5 Collector หรือ METAAPI_TOKEN สำหรับโหมดเดิม</p></div>',
            unsafe_allow_html=True,
        )
        st.stop()

    if page == "📓 Journal":
        page_connect(token, region)
        return

    try:
        accs = fetch_accounts(token, region)
    except MetaApiError as e:
        st.markdown(
            f'<div class="nj-hero"><div class="nj-empty-icon">⚠️</div>'
            f'<h2>เชื่อมต่อ MetaApi ไม่สำเร็จ</h2><p>{e.message}</p></div>',
            unsafe_allow_html=True,
        )
        st.stop()

    if not accs:
        with st.sidebar:
            st.markdown(
                '<div class="nj-side-card"><div class="nj-side-muted">ACCOUNT</div>'
                '<div class="nj-side-value">ยังไม่มีบัญชีเชื่อมต่อ</div></div>',
                unsafe_allow_html=True,
            )
        st.markdown(
            '<div class="nj-hero"><div class="nj-status"><span class="nj-dot"></span> MetaApi พร้อมใช้งาน</div>'
            '<div style="height:10px"></div><div class="nj-empty-icon">🔌</div>'
            '<h2>เชื่อมบัญชี MetaTrader เพื่อเริ่มต้น</h2>'
            '<p>ตอนนี้ยังไม่มีบัญชี MT4/MT5 ในระบบ เมื่อเชื่อมแล้ว Dashboard จะแสดง Balance, Equity, P&L, Open Trades และ Journal ให้อัตโนมัติ</p></div>',
            unsafe_allow_html=True,
        )
        st.info("ไปที่เมนู ‘🔌 เชื่อมต่อบัญชี’ ทางซ้ายเพื่อเพิ่มบัญชี MT5/MT4")
        st.stop()

    by_id = {(a.get("_id") or a.get("id")): a for a in accs}
    with st.sidebar:
        st.markdown('<div class="nj-nav-label">Account</div>', unsafe_allow_html=True)
        aid = st.selectbox(
            "บัญชี", list(by_id),
            format_func=lambda i: f"{by_id[i].get('name')} ({by_id[i].get('login')})",
            label_visibility="collapsed",
        )
        days = st.select_slider("ช่วงข้อมูลย้อนหลัง (วัน)", [30, 90, 180, 365, 730], value=365)
        if st.button("↻  รีเฟรชข้อมูล", use_container_width=True):
            clear_cache()
            st.rerun()
        acc = by_id[aid]
        state = acc.get("state") or "UNKNOWN"
        conn = acc.get("connectionStatus") or "UNKNOWN"
        st.markdown(
            f'<div class="nj-side-card"><div class="nj-side-muted">STATUS</div>'
            f'<div class="nj-side-value">{state} · {conn}</div></div>',
            unsafe_allow_html=True,
        )
        if state != "DEPLOYED":
            st.warning("บัญชีนี้ยังไม่ deploy — ไปที่เมนู เชื่อมต่อบัญชี")

    acc_region = acc.get("region") or region
    store = get_store()
    if page in ("📈 Trading Performance", "📊 Performance Breakdown", "🧠 Trading Behavior", "🧬 Trading DNA", "📐 Portfolio Exposure", "🛡️ Risk Engine"):
        st.info("หน้านี้ใช้ข้อมูล MT5 → Supabase ในโหมด Free Architecture; กรุณาใช้โหมด Supabase")
        return
    try:
        if page == "🧠 Decision Engine":
            page_open(fetch_positions(token, acc_region, aid))
            return
        with st.spinner("กำลังดึงประวัติเทรด..."):
            trades = fetch_history(token, acc_region, aid, days)
        df = merge_notes(trades, store.load(aid))
        if page == "🟡 ไม้ที่เปิดอยู่":
            page_journal(df, store, aid)
            return
        try:
            metrics = fetch_metrics(token, acc_region, aid)
        except MetaApiError as e:
            st.warning(f"ดึง metrics ไม่ได้ ({e.message}) — ใช้ค่าจากประวัติแทน")
            metrics = {}
        info = fetch_account_info(token, acc_region, aid)
        merged = {**metrics, **{k: info[k] for k in ("balance", "equity") if k in info}}
        page_dashboard(df, merged, info)
    except MetaApiError as e:
        st.error(f"เกิดข้อผิดพลาดจาก MetaApi: {e.message}")


main()
