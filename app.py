"""
Nobody Trade Journal — Cloud Edition
เชื่อม MT4/MT5 ผ่าน MetaApi + MetaStats แบบ REST
รันบน Streamlit Cloud ได้ทันที ไม่ต้องมี Windows VPS

streamlit run app.py
"""

from __future__ import annotations

import json

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


# =========================================================
# CACHED FETCHERS
# =========================================================


@st.cache_resource(show_spinner=False)
def get_client(token: str, region: str) -> MetaApiClient:
    return MetaApiClient(token, region)


@st.cache_resource(show_spinner=False)
def get_store() -> NoteStore:
    return NoteStore()


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


def page_dashboard(df: pd.DataFrame, metrics: dict, info: dict) -> None:
    s = summary(df, metrics)
    cur = info.get("currency", "")

    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric(f"Balance ({cur})" if cur else "Balance", f"{s['balance']:,.2f}")
    c2.metric("Equity", f"{s['equity']:,.2f}")
    c3.metric("กำไรสุทธิ", f"{s['net']:+,.2f}")
    c4.metric("Win Rate", f"{s['win_rate']:.1f}%", f"{int(s['wins'])}W / {int(s['losses'])}L")
    pf = s["profit_factor"]
    c5.metric("Profit Factor", "∞" if pf == float("inf") else f"{pf:.2f}")
    c6.metric("Max Drawdown", f"{s['max_dd_pct']:.2f}%", f"{s['max_dd']:,.2f}")

    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("ไม้ทั้งหมด", int(s["n"]))
    c2.metric("Expectancy/ไม้", f"{s['expectancy']:+,.2f}")
    c3.metric("Payoff Ratio", f"{s['payoff']:.2f}")
    c4.metric("Sharpe", f"{s['sharpe']:.2f}")
    c5.metric("ค่าธรรมเนียมรวม", f"{s['costs']:,.2f}")
    c6.metric("Lots รวม", f"{s['lots']:,.2f}")

    if s["n"] == 0:
        st.info("ยังไม่มีไม้ที่ปิดในช่วงเวลาที่เลือก")
        return

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
                st.warning(
                    f"ไม้นอกแผนทำให้เสีย {abs(a['นอกแผน']):,.2f} "
                    f"ขณะที่ไม้ตามแผนได้ {a['ตามแผน']:,.2f} — "
                    "ตัดไม้นอกแผนออก ผลจะดีขึ้นทันที"
                )

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
        st.markdown(f"### 📓 {APP_NAME}")
        st.caption(f"v{APP_VERSION}")

        if not secret("METAAPI_TOKEN"):
            st.text_input("MetaApi Token", type="password", key="mapi_token")

        default_region = secret("METAAPI_REGION", "new-york")
        st.selectbox(
            "Region เริ่มต้น", REGIONS,
            index=REGIONS.index(default_region) if default_region in REGIONS else 0,
            key="mapi_region",
        )
        page = st.radio("เมนู", NAV, label_visibility="collapsed")

    token, region = get_token(), get_region()
    if not token:
        st.info("ใส่ MetaApi Token ที่แถบด้านซ้าย (หรือตั้ง METAAPI_TOKEN ใน secrets)")
        st.stop()

    if page == NAV[3]:
        page_connect(token, region)
        return

    try:
        accs = fetch_accounts(token, region)
    except MetaApiError as e:
        st.error(f"ดึงรายการบัญชีไม่ได้: {e.message}")
        st.stop()

    if not accs:
        st.info("ยังไม่มีบัญชี — ไปที่เมนู เชื่อมต่อบัญชี")
        st.stop()

    by_id = {(a.get("_id") or a.get("id")): a for a in accs}
    with st.sidebar:
        aid = st.selectbox(
            "บัญชี", list(by_id),
            format_func=lambda i: f"{by_id[i].get('name')} ({by_id[i].get('login')})",
        )
        days = st.select_slider("ช่วงข้อมูลย้อนหลัง (วัน)", [30, 90, 180, 365, 730], value=365)
        if st.button("🔄 รีเฟรชข้อมูล", use_container_width=True):
            clear_cache()
            st.rerun()

        acc = by_id[aid]
        st.caption(f"{acc.get('state')} / {acc.get('connectionStatus')}")
        if acc.get("state") != "DEPLOYED":
            st.warning("บัญชีนี้ยังไม่ deploy — ไปที่เมนู เชื่อมต่อบัญชี")

    # ใช้ region ของบัญชีนั้นจริง ไม่ใช่ค่าจาก sidebar
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
