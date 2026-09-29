"""
Nobody Trade Journal — Cloud Edition
เชื่อม MT4/MT5 ผ่าน MetaApi + MetaStats แบบ REST
รันบน Streamlit Cloud ได้ทันที ไม่ต้องมี Windows VPS

streamlit run app.py
"""

from __future__ import annotations

import json

import requests
import pandas as pd
import streamlit as st

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
.block-container { padding-top: 1.25rem !important; }
.nj-app-title { font-size:1.05rem; font-weight:800; margin:0; }
.nj-app-sub { color:#8b93a1; font-size:.75rem; margin-top:2px; }
.nj-nav-label { color:#737d8c; text-transform:uppercase; letter-spacing:.08em; font-size:.67rem; font-weight:800; margin:.8rem 0 .35rem; }
.nj-hero { background:linear-gradient(135deg,#232b3a,#181a20); border:1px solid #303744; border-radius:16px; padding:22px 24px; margin-bottom:18px; }
.nj-hero h2 { margin:0 0 6px; font-size:1.5rem; }
.nj-hero p { margin:0; color:#9aa3b2; line-height:1.55; }
.nj-empty-icon { font-size:2.1rem; margin-bottom:4px; }
.nj-status { display:inline-flex; align-items:center; gap:7px; padding:5px 10px; border-radius:999px; background:rgba(14,203,129,.12); color:#0ecb81; border:1px solid rgba(14,203,129,.24); font-size:.74rem; font-weight:700; }
.nj-dot { width:7px; height:7px; border-radius:50%; background:#0ecb81; display:inline-block; }
.nj-side-card { background:#181a20; border:1px solid #2b3139; border-radius:12px; padding:11px 12px; margin:8px 0; }
.nj-side-muted { color:#7f8897; font-size:.72rem; }
.nj-side-value { font-size:.9rem; font-weight:750; margin-top:2px; }
section[data-testid="stSidebar"] { border-right:1px solid #292e38; }
section[data-testid="stSidebar"] .block-container { padding:1.15rem .85rem 1.2rem !important; }
section[data-testid="stSidebar"] [data-testid="stRadio"] label { border-radius:10px; padding:7px 9px !important; }
section[data-testid="stSidebar"] [data-testid="stRadio"] label:hover { background:#20242d; }
section[data-testid="stSidebar"] [data-testid="stRadio"] p { font-size:.9rem; font-weight:650; }
[data-testid="stMetric"] { background:#181a20; border:1px solid #2b3139; border-radius:12px; padding:12px 14px; }
@media (max-width:900px) {
  .block-container { padding:.7rem .65rem 3rem !important; }
  .nj-hero { padding:16px; }
  .nj-hero h2 { font-size:1.2rem; }
  [data-testid="stMetric"] { padding:9px 10px; }
  [data-testid="stMetricValue"] { font-size:1.05rem !important; }
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

NAV = ["📊 Dashboard", "🟡 ไม้ที่เปิดอยู่", "📓 Journal", "🔌 เชื่อมต่อบัญชี"]


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
        if page == NAV[0]:
            page_supabase_dashboard(fetch_latest_mt5_snapshot())
            return
        if page == NAV[1]:
            st.markdown('<div class="nj-section-title">Live Trading Monitor</div>', unsafe_allow_html=True)
            st.caption("Open Positions จาก MT5 → NobodyCollector → Supabase")
            top1, top2 = st.columns([1, 5])
            with top1:
                if st.button("↻ รีเฟรช", use_container_width=True, key="supabase_positions_refresh"):
                    clear_cache()
                    st.rerun()
            snap = fetch_latest_mt5_snapshot()
            if snap and not snap.get("_error"):
                st.caption(f"บัญชี {snap.get('login','-')} · {snap.get('server','-')} · snapshot ล่าสุด {snap.get('collected_at','-')}")
                render_supabase_positions(fetch_mt5_positions_supabase(snap))
            else:
                render_mt5_snapshot(snap)
            return
        if page == NAV[3]:
            st.subheader("🔌 MT5 Collector")
            st.success("Supabase เชื่อมต่อแล้ว — NobodyCollector กำลังส่งข้อมูลจาก MT5", icon="✅")
            st.code("MT5 → NobodyCollector → Supabase → Nobody Trade Journal", language="text")
            st.caption("Account / Positions / Pending / Trade History พร้อมอ่านจาก Supabase")
            return
        st.info(
            "หน้า Journal เดิมยังคงใช้ระบบโน้ตเดิมอยู่ รอบถัดไปค่อยเชื่อม Trade History จาก Supabase เข้ากับ Journal",
            icon="ℹ️",
        )
        return

    if not token:
        st.markdown(
            '<div class="nj-hero"><div class="nj-empty-icon">🔐</div>'
            '<h2>ยังไม่ได้ตั้งค่าแหล่งข้อมูล</h2>'
            '<p>ตั้งค่า SUPABASE_URL + SUPABASE_KEY สำหรับ MT5 Collector หรือ METAAPI_TOKEN สำหรับโหมดเดิม</p></div>',
            unsafe_allow_html=True,
        )
        st.stop()

    if page == NAV[3]:
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
    try:
        if page == NAV[1]:
            page_open(fetch_positions(token, acc_region, aid))
            return
        with st.spinner("กำลังดึงประวัติเทรด..."):
            trades = fetch_history(token, acc_region, aid, days)
        df = merge_notes(trades, store.load(aid))
        if page == NAV[2]:
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
