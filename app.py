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
        c1, c

        st.info(
            "แนะนำให้ใช้ Investor Password — เป็นรหัสสิทธิ์อ่านอย่างเดียว "
            "ดูพอร์ตและประวัติได้ แต่ส่งคำสั่งเทรดไม่ได้ ปลอดภัยกว่ารหัสหลักมาก",
            icon="🔒",
        )
เยี่ยมครับ — REST version เหมาะกับ cloud ที่สุด เพราะ **ไม่ต้องใช้ asyncio** (SDK เป็น async ล้วน ซึ่งชนกับ Streamlit บ่อย) และไม่ต้องมี Windows VPS เลย

ผมยืนยัน endpoint จากเอกสารทางการแล้ว: MetaApi ใช้ header `auth-token` [metaapi](https://metaapi.cloud/docs/client/restApi/auth/) และ MetaStats มี endpoint `historical-trades/{start}/{end}` ที่ออกแบบมาเพื่อทำแอปแบบ Myfxbook โดยเฉพาะ [metaapi](https://metaapi.cloud/docs/metastats/restApi/api/getHistoricalTrades/)

## โครงสร้างโปรเจกต์
