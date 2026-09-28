"""
Nobody Trade Journal — Cloud Edition
เชื่อม MT4/MT5 ผ่าน MetaApi + MetaStats แบบ REST
รันบน Streamlit Cloud ได้ทันที ไม่ต้องมี Windows VPS

streamlit run app.py
"""

from __future__ import annotations

import io
import json
from datetime import datetime, timedelta, timezone

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
    c1.metric("Balance", f"{s['balance']:,.2f}", cur or None)
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
        c1, c2, c3 = st.columns([2, 2, 1.2])
        c1.markdown(
            f"**{r['symbol']}** · {r['direction']} · {r['volume']:g} lots  \n"
            f"<span class='nj-muted'>เปิด {r['open_time']}</span>",
            unsafe_allow_html=True,
        )
        c2.markdown(
            f"Open `{r['open_price']:,.5f}` → Now `{r['current_price']:,.5f}`  \n"
            f"<span class='nj-muted'>SL {r['stop_loss']:,.5f} · "
            f"TP {r['take_profit']:,.5f}</span>",
            unsafe_allow_html=True,
        )
        c3.markdown(
            f"<span class='{tone}' style='font-size:1.2rem'>"
            f"{r['unrealized']:+,.2f}</span>",
            unsafe_allow_html=True,
        )
        st.markdown("</div>", unsafe_allow_html=True)


def page_journal(df: pd.DataFrame, store: NoteStore, aid: str) -> None:
    st.subheader("บันทึก Journal ทับไม้จริง")
    st.caption(
        "MT5 ให้ข้อมูลราคาและกำไรมาแล้ว — ส่วนที่ต้องเติมเองคือเหตุผล อารมณ์ และบทเรียน"
    )

    if df.empty:
        st.info("ยังไม่มีไม้ให้บันทึก")
        return

    c1, c2, c3 = st.columns(3)
    f_sym = c1.multiselect("Symbol", sorted(df["symbol"].dropna().unique()))
    f_res = c2.selectbox("ผลลัพธ์", ["ทั้งหมด", "กำไร", "ขาดทุน"])
    f_note = c3.selectbox("สถานะบันทึก", ["ทั้งหมด", "ยังไม่บันทึก", "บันทึกแล้ว"])

    v = df.copy()
    if f_sym:
        v = v[v["symbol"].isin(f_sym)]
    if f_res == "กำไร":
        v = v[v["is_win"]]
    elif f_res == "ขาดทุน":
        v = v[v["is_loss"]]
    if f_note == "ยังไม่บันทึก":
        v = v[~v["has_note"]]
    elif f_note == "บันทึกแล้ว":
        v = v[v["has_note"]]

    st.caption(f"แสดง {min(len(v), 50)} จาก {len(v)} ไม้")

    for _, r in v.head(50).iterrows():
        mark = "✅" if r["has_note"] else "⚪"
        tone = "nj-win" if r["net"] > 0 else "nj-loss"
        title = (
            f"{mark} {r['symbol']} · {r['direction']} · "
            f"{r['net']:+,.2f} · {str(r['close_time'])[:16]}"
        )

        with st.expander(title):
            st.markdown(f'<div class="nj-card {tone}">', unsafe_allow_html=True)

            c1, c2, c3 = st.columns(3)
            c1.markdown(
                f"**Open** {r['open_price']:,.5f}  \n"
                f"**Close** {r['close_price']:,.5f}  \n"
                f"**Volume** {r['volume']:g}"
            )
            c2.markdown(
                f"**Net** {r['net']:+,.2f}  \n"
                f"**Pips** {r['pips']:+.1f}  \n"
                f"**Gain** {r['gain']:+.2f}%"
            )
            c3.markdown(
                f"**Duration** {r['duration_min']:,.0f} นาที  \n"
                f"**Costs** {r['costs']:,.2f}  \n"
                f"**Magic** {r['magic']}"
            )

            tid = r["trade_id"]
            with st.form(f"note_{tid}"):
                c1, c2, c3 = st.columns(3)
                setup = c1.selectbox(
                    "Setup", [""] + SETUPS,
                    index=(SETUPS.index(r["setup"]) + 1) if r["setup"] in SETUPS else 0,
                    key=f"su_{tid}",
                )
                tf = c2.selectbox(
                    "Timeframe", [""] + TIMEFRAMES,
                    index=(TIMEFRAMES.index(r["timeframe"]) + 1)
                    if r["timeframe"] in TIMEFRAMES else 0,
                    key=f"tf_{tid}",
                )
                conf = c3.slider("ความมั่นใจ", 1, 5, int(r["confidence"] or 3), key=f"cf_{tid}")

                c1, c2, c3 = st.columns(3)
                ein = c1.selectbox(
                    "อารมณ์ตอนเข้า", [""] + EMOTIONS,
                    index=(EMOTIONS.index(r["emotion_in"]) + 1)
                    if r["emotion_in"] in EMOTIONS else 0,
                    key=f"ei_{tid}",
                )
                eout = c2.selectbox(
                    "อารมณ์ตอนออก", [""] + EMOTIONS,
                    index=(EMOTIONS.index(r["emotion_out"]) + 1)
                    if r["emotion_out"] in EMOTIONS else 0,
                    key=f"eo_{tid}",
                )
                plan = c3.checkbox(
                    "เทรดตามแผน", value=bool(int(r["followed_plan"] or 1)), key=f"pl_{tid}"
                )

                try:
                    cur_mis = json.loads(r["mistakes"] or "[]")
                except Exception:
                    cur_mis = []
                mis = st.multiselect(
                    "ข้อผิดพลาด", MISTAKES,
                    default=[m for m in cur_mis if m in MISTAKES], key=f"mi_{tid}",
                )

                thesis = st.text_area(
                    "เหตุผลที่เข้า", value=str(r["thesis"] or ""),
                    height=80, key=f"th_{tid}",
                )
                lesson = st.text_area(
                    "บทเรียน", value=str(r["lesson"] or ""),
                    height=80, key=f"ls_{tid}",
                )

                c1, c2 = st.columns(2)
                tags = c1.text_input("Tags", value=str(r["tags"] or ""), key=f"tg_{tid}")
                shot = c2.text_input(
                    "Screenshot URL", value=str(r["screenshot_url"] or ""), key=f"sc_{tid}"
                )

                if st.form_submit_button("บันทึก", type="primary", use_container_width=True):
                    ok = store.save(
                        tid, aid,
                        setup=setup, timeframe=tf, confidence=conf,
                        emotion_in=ein, emotion_out=eout,
                        followed_plan=int(plan), mistakes=mis,
                        thesis=thesis, lesson=lesson,
                        tags=tags, screenshot_url=shot,
                    )
                    if ok:
                        st.success("บันทึกแล้ว")
                        st.rerun()
                    else:
                        st.error("บันทึกไม่สำเร็จ")

            if r["screenshot_url"]:
                st.image(r["screenshot_url"], use_container_width=True)

            st.markdown("</div>", unsafe_allow_html=True)


def page_export(df: pd.DataFrame, metrics: dict) -> None:
    st.subheader("ส่งออกข้อมูล")
    if df.empty:
        st.info("ยังไม่มีข้อมูล")
        return

    c1, c2 = st.columns(2)

    csv = df.to_csv(index=False).encode("utf-8-sig")
    c1.download_button(
        "ดาวน์โหลด CSV", csv,
        file_name=f"journal_{datetime.now():%Y%m%d}.csv",
        mime="text/csv", use_container_width=True,
    )

    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as xw:
        df.to_excel(xw, sheet_name="Trades", index=False)
        monthly_table(df).to_excel(xw, sheet_name="Monthly", index=False)
        for key, label in (
            ("symbol", "BySymbol"), ("direction", "ByDirection"),
            ("weekday", "ByWeekday"), ("setup", "BySetup"),
        ):
            g = by_group(df, key)
            if not g.empty:
                g.to_excel(xw, sheet_name=label, index=False)
        if metrics:
            pd.DataFrame([metrics]).T.reset_index().to_excel(
                xw, sheet_name="Metrics", index=False, header=["Metric", "Value"]
            )
    c2.download_button(
        "ดาวน์โหลด Excel", buf.getvalue(),
        file_name=f"journal_{datetime.now():%Y%m%d}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )

    st.divider()
    st.dataframe(df, use_container_width=True, hide_index=True)


# =========================================================
# MAIN
# =========================================================


def main() -> None:
    if not gate():
        return

    with st.sidebar:
        st.markdown(f"## {APP_NAME}")
        st.caption(f"v{APP_VERSION}")

        token = get_token()
        region = get_region()

        if not token:
            with st.expander("ตั้งค่า MetaApi", expanded=True):
                t = st.text_input("MetaApi Token", type="password")
                r = st.selectbox("Region", REGIONS)
                if st.button("บันทึก", use_container_width=True):
                    st.session_state["mapi_token"] = t
                    st.session_state["mapi_region"] = r
                    st.rerun()
            st.warning("ยังไม่ได้ใส่ Token")
            st.stop()

        try:
            accounts = fetch_accounts(token, region)
        except MetaApiError as e:
            st.error(e.message)
            accounts = []

        options = {
            f"{a.get('name')} · {a.get('login')}": (a.get("_id") or a.get("id"))
            for a in accounts
        }

        pinned = secret("METAAPI_ACCOUNT_ID")
        aid = None
        if options:
            label = st.selectbox("บัญชี", list(options.keys()))
            aid = options[label]
        elif pinned:
            aid = pinned

        days = st.select_slider(
            "ช่วงเวลา (วัน)", [7, 30, 90, 180, 365, 730, 1825], value=365
        )

        page = st.radio(
            "เมนู",
            ["Dashboard", "ไม้ที่เปิดอยู่", "Journal", "ส่งออก", "เชื่อมต่อบัญชี"],
            label_visibility="collapsed",
        )

        if st.button("รีเฟรชข้อมูล", use_container_width=True):
            clear_cache()
            st.rerun()

        st.divider()
        st.caption(f"Region: {region}")
        st.caption(f"Notes: {get_store().backend}")

    if page == "เชื่อมต่อบัญชี":
        page_connect(token, region)
        return

    if not aid:
        st.warning("ยังไม่มีบัญชี — ไปที่เมนู “เชื่อมต่อบัญชี” เพื่อเพิ่ม")
        return

    try:
        with st.spinner("กำลังดึงข้อมูลจากโบรกเกอร์..."):
            info = fetch_account_info(token, region, aid)
            metrics = fetch_metrics(token, region, aid)
            trades = fetch_history(token, region, aid, days)
            positions = fetch_positions(token, region, aid)
    except MetaApiError as e:
        st.error(f"ดึงข้อมูลไม่สำเร็จ: {e.message}")
        return

    store = get_store()
    df = merge_notes(trades, store.load(aid))

    badge = "nj-live" if not info.get("isDemo", False) else "nj-demo"
    st.markdown(
        f"### {info.get('name', '—')} "
        f"<span class='nj-pill {badge}'>"
        f"{'DEMO' if info.get('isDemo') else 'LIVE'}</span>  \n"
        f"<span class='nj-muted'>{info.get('broker', '')} · "
        f"{info.get('server', '')} · Leverage 1:{info.get('leverage', '—')} · "
        f"{info.get('currency', '')}</span>",
        unsafe_allow_html=True,
    )
    st.divider()

    if page == "Dashboard":
        page_dashboard(df, metrics, info)
    elif page == "ไม้ที่เปิดอยู่":
        page_open(positions)
    elif page == "Journal":
        page_journal(df, store, aid)
    else:
        page_export(df, metrics)


if __name__ == "__main__":
    main()
