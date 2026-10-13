"""
Nobody Trade Journal v3
MT5 → NobodyCollector → Supabase → Streamlit

streamlit run app.py
"""

from __future__ import annotations

import json

import pandas as pd
import streamlit as st

from core import data, notes, ui
from core.config import (
    APP_NAME, APP_VERSION, EMOTIONS, MISTAKES, SETUPS, TIMEFRAMES, secret,
)
from core.trades import (
    WEEKDAYS, build_trades, daily_pnl, equity_curve, exposure_table,
    group_stats, kpis, positions_view,
)

st.set_page_config(page_title=APP_NAME, page_icon="📓", layout="wide",
                   initial_sidebar_state="expanded")
ui.inject_css()

PAGES = ["Overview", "Performance", "Journal"]
RANGES = ["7D", "30D", "90D", "YTD", "All"]
PLOT_CFG = {"displayModeBar": False}


def _st_version() -> tuple:
    try:
        return tuple(int(x) for x in st.__version__.split(".")[:2])
    except Exception:  # noqa: BLE001
        return (0, 0)


# Streamlit รุ่นใหม่เลิกใช้ use_container_width แล้วให้ใช้ width="stretch" แทน
# (requirements ไม่ได้ pin เวอร์ชัน) จึงลองทั้งสองแบบเรียงตามรุ่นที่ติดตั้ง
_STRETCH = (
    [{"width": "stretch"}, {"use_container_width": True}]
    if _st_version() >= (1, 49)
    else [{"use_container_width": True}, {"width": "stretch"}]
)


def stretch(fn, *args, **kw):
    err = None
    for opt in _STRETCH:
        try:
            return fn(*args, **opt, **kw)
        except Exception as exc:  # noqa: BLE001
            err = exc
    raise err


def plot(fig) -> None:
    stretch(st.plotly_chart, fig, config=PLOT_CFG)


# ====================================================================== helpers

def gate() -> bool:
    pw = secret("APP_PASSWORD")
    if not pw or st.session_state.get("authed"):
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


def fmt_price(v) -> str:
    if v is None or pd.isna(v):
        return "—"
    v = float(v)
    if abs(v) >= 1000:
        return f"{v:,.2f}"
    if abs(v) >= 100:
        return f"{v:,.3f}"
    return f"{v:,.5f}"


def fmt_time(t) -> str:
    return "—" if t is None or pd.isna(t) else t.strftime("%d %b %y %H:%M")


def _pnl_css(v) -> str:
    if isinstance(v, (int, float)) and not pd.isna(v):
        if v > 0:
            return f"color:{ui.POS}"
        if v < 0:
            return f"color:{ui.NEG}"
    return ""


def style(df: pd.DataFrame, formats: dict, pnl_cols: list[str]):
    """ตารางพร้อมฟอร์แมตตัวเลข + สีกำไร/ขาดทุน"""
    sty = df.style.format(formats, na_rep="—")
    cols = [c for c in pnl_cols if c in df.columns]
    if cols:
        sty = sty.map(_pnl_css, subset=cols) if hasattr(sty, "map") else sty.applymap(_pnl_css, subset=cols)
    return sty


def show_table(sty, height: int | None = None, **kw):
    if height is not None:  # Streamlit รุ่นใหม่ไม่รับ height=None
        kw["height"] = height
    return stretch(st.dataframe, sty, hide_index=True, **kw)


def snapshot_age(snap: dict) -> float | None:
    ts = pd.to_datetime(snap.get("collected_at"), errors="coerce", utc=True)
    if pd.isna(ts):
        return None
    return max(0.0, (pd.Timestamp.now(tz="UTC") - ts).total_seconds())


def est_capital(balance: float, trades: pd.DataFrame) -> float:
    """เงินทุนสุทธิโดยประมาณ = balance ปัจจุบัน − กำไรสุทธิที่ปิดแล้ว (ฝาก/ถอนรวมอยู่ในนี้)"""
    if trades.empty:
        return 0.0
    cap = balance - float(trades["net"].sum())
    return cap if cap > 0 else 0.0


def filter_bar(trades: pd.DataFrame, key: str) -> tuple[pd.DataFrame, bool]:
    """ตัวกรองช่วงเวลา + สัญลักษณ์ ในแถวเดียวเหนือกราฟ"""
    c1, c2 = st.columns([3, 4])
    rng = c1.radio("ช่วงเวลา", RANGES, index=len(RANGES) - 1, horizontal=True,
                   key=f"{key}_rng", label_visibility="collapsed")
    symbols = sorted(trades["symbol"].dropna().unique().tolist())
    chosen = c2.multiselect("สัญลักษณ์", symbols, default=[], placeholder="ทุกสัญลักษณ์",
                            key=f"{key}_sym", label_visibility="collapsed")
    out = trades
    now = pd.Timestamp.now(tz="UTC").tz_localize(None)
    cut = {"7D": now - pd.Timedelta(days=7), "30D": now - pd.Timedelta(days=30),
           "90D": now - pd.Timedelta(days=90), "YTD": pd.Timestamp(now.year, 1, 1)}.get(rng)
    if cut is not None:
        out = out[out["close_time"] >= cut]
    if chosen:
        out = out[out["symbol"].isin(chosen)]
    return out, (rng != "All" or bool(chosen))


def kpi_overview(k: dict) -> list[dict]:
    return [
        dict(label="Closed P&L", value=ui.money(k["net"], signed=True), tone=ui.tone(k["net"]),
             sub=f'{k["trades"]} trades'),
        dict(label="Win rate", value=ui.pct(k["win_rate"]), sub=f'{k["wins"]}W · {k["losses"]}L · {k["be"]}BE'),
        dict(label="Profit factor", value=ui.num(k["profit_factor"]), sub="กำไรรวม ÷ ขาดทุนรวม"),
        dict(label="Max drawdown", value=ui.money(k["max_dd"]), tone="neg" if k["max_dd"] < 0 else "",
             sub=ui.pct(k["max_dd_pct"]) if k["max_dd_pct"] is not None else "จากกำไรสะสม"),
    ]


# ====================================================================== pages

def page_overview(snap, pos, pending, trades, capital, cur):
    ui.page_header("Overview", f"บัญชี {snap.get('login', '')} · {snap.get('server', '')}",
                   ui.status_pill(snapshot_age(snap)))

    def f(k: str) -> float:
        v = pd.to_numeric(pd.Series([snap.get(k)]), errors="coerce").iloc[0]
        return 0.0 if pd.isna(v) else float(v)

    balance, equity, margin, free = f("balance"), f("equity"), f("margin"), f("free_margin")
    floating = equity - balance
    level = f"{equity / margin * 100:,.0f}%" if margin > 0 else "—"
    ui.kpi_grid([
        dict(label=f"Balance {cur}".strip(), value=ui.money(balance)),
        dict(label="Equity", value=ui.money(equity)),
        dict(label="Floating P&L", value=ui.money(floating, signed=True), tone=ui.tone(floating),
             sub=f"{len(pos)} open"),
        dict(label="Margin used", value=ui.money(margin), sub=f"Level {level}"),
        dict(label="Free margin", value=ui.money(free)),
    ])

    k = kpis(trades, capital)
    ui.kpi_grid(kpi_overview(k))

    ui.section("Open positions", "ไม้ที่เปิดอยู่ตอนนี้")
    if pos.empty:
        ui.note("ไม่มีไม้ที่เปิดอยู่")
    else:
        d = pd.DataFrame({
            "Symbol": pos["symbol"], "Side": pos["side"], "Lots": pos["volume"],
            "Open": pos["open_price"], "Current": pos["current_price"],
            "SL": pos["stop_loss"].where(pos["stop_loss"] > 0),
            "TP": pos["take_profit"].where(pos["take_profit"] > 0),
            "Floating": pos["floating"], "Opened": pos["open_time"],
            "Risk": pos["stop_loss"].map(lambda v: "No SL" if v <= 0 else ""),
        })
        show_table(style(d, {"Lots": "{:.2f}", "Open": fmt_price, "Current": fmt_price, "SL": fmt_price,
                             "TP": fmt_price, "Floating": "{:+,.2f}", "Opened": fmt_time}, ["Floating"]))
        exp = exposure_table(pos)
        if len(exp) > 1 or (len(exp) == 1 and exp.iloc[0]["buy_lots"] and exp.iloc[0]["sell_lots"]):
            with st.expander("Exposure ตาม symbol"):
                e = exp.rename(columns={"symbol": "Symbol", "positions": "Positions", "buy_lots": "Buy lots",
                                        "sell_lots": "Sell lots", "net_lots": "Net lots", "floating": "Floating"})
                show_table(style(e, {"Buy lots": "{:.2f}", "Sell lots": "{:.2f}", "Net lots": "{:+.2f}",
                                     "Floating": "{:+,.2f}"}, ["Floating"]))

    if not pending.empty:
        ui.section("Pending orders", f"{len(pending)} orders")
        p = pd.DataFrame({
            "Symbol": pending.get("symbol"), "Type": pending.get("order_type"),
            "Lots": pd.to_numeric(pending.get("volume_current"), errors="coerce"),
            "Price": pd.to_numeric(pending.get("price_open"), errors="coerce"),
            "SL": pd.to_numeric(pending.get("stop_loss"), errors="coerce"),
            "TP": pd.to_numeric(pending.get("take_profit"), errors="coerce"),
        })
        show_table(style(p, {"Lots": "{:.2f}", "Price": fmt_price, "SL": fmt_price, "TP": fmt_price}, []))

    if trades.empty:
        ui.empty_state("📭", "ยังไม่มีไม้ที่ปิดแล้ว", "เมื่อ Collector ส่งประวัติเทรดขึ้น Supabase สถิติและกราฟจะปรากฏที่นี่")
        return

    ui.section("Equity curve", "realized P&L ตามเวลาปิดไม้")
    curve = equity_curve(trades, capital)
    plot(ui.equity_chart(curve, capital))

    ui.section("ไม้ล่าสุด", "8 ไม้ที่ปิดล่าสุด")
    show_table(style(trades_table(trades.sort_values("close_time", ascending=False).head(8)),
                     TRADE_FMT, ["Net P&L"]))


TRADE_FMT = {"Closed": fmt_time, "Lots": "{:.2f}", "Entry": fmt_price, "Exit": fmt_price,
             "Net P&L": "{:+,.2f}"}


def trades_table(df: pd.DataFrame, noted: set | None = None) -> pd.DataFrame:
    d = pd.DataFrame({
        "Closed": df["close_time"], "Symbol": df["symbol"], "Side": df["direction"],
        "Lots": df["volume"], "Entry": df["entry_price"], "Exit": df["exit_price"],
        "Net P&L": df["net"], "Duration": df["duration_min"].map(ui.duration),
    })
    if noted is not None:
        d["Note"] = df["trade_id"].map(lambda t: "✓" if t in noted else "")
    return d


def page_performance(trades, capital):
    ui.page_header("Performance", "สถิติจากไม้ที่ปิดแล้ว · เวลาตามเซิร์ฟเวอร์โบรกเกอร์")
    if trades.empty:
        ui.empty_state("📭", "ยังไม่มีไม้ที่ปิดแล้ว", "เมื่อมีประวัติเทรดใน Supabase สถิติจะปรากฏที่นี่")
        return
    f, filtered = filter_bar(trades, "perf")
    if f.empty:
        ui.empty_state("🔍", "ไม่พบไม้ตามตัวกรองที่เลือก")
        return

    cap = 0.0 if filtered else capital
    k = kpis(f, cap)
    ui.kpi_grid([
        dict(label="Net P&L", value=ui.money(k["net"], signed=True), tone=ui.tone(k["net"]),
             sub=f'gross {ui.money(k["gross_profit"])} / {ui.money(k["gross_loss"])}'),
        dict(label="Trades", value=k["trades"], sub=f'{k["wins"]}W · {k["losses"]}L · {k["be"]}BE'),
        dict(label="Win rate", value=ui.pct(k["win_rate"])),
        dict(label="Profit factor", value=ui.num(k["profit_factor"])),
        dict(label="Expectancy", value=ui.money(k["expectancy"], signed=True), tone=ui.tone(k["expectancy"]),
             sub="เฉลี่ยต่อไม้"),
    ])
    ui.kpi_grid([
        dict(label="Avg win", value=ui.money(k["avg_win"], signed=True), tone="pos" if k["avg_win"] else ""),
        dict(label="Avg loss", value=ui.money(k["avg_loss"], signed=True), tone="neg" if k["avg_loss"] else ""),
        dict(label="Payoff ratio", value=ui.num(k["payoff"]), sub="avg win ÷ |avg loss|"),
        dict(label="Max drawdown", value=ui.money(k["max_dd"]), tone="neg" if k["max_dd"] < 0 else "",
             sub=ui.pct(k["max_dd_pct"]) if k["max_dd_pct"] is not None else "จากกำไรสะสม"),
        dict(label="Streak W / L", value=f'{k["max_win_streak"]} / {k["max_loss_streak"]}',
             sub=f'avg hold {ui.duration(k["avg_duration_min"])}'),
    ])

    t_eq, t_bd, t_ds, t_cal = st.tabs(["Equity", "Breakdown", "Distribution", "Calendar"])

    with t_eq:
        curve = equity_curve(f, cap)
        ui.section("Equity", "Balance โดยประมาณ" if cap > 0 else "กำไรสะสม")
        plot(ui.equity_chart(curve, cap))
        ui.section("Drawdown", "ระยะห่างจากจุดสูงสุด")
        plot(ui.drawdown_chart(curve))
        ui.section("P&L รายวัน")
        plot(ui.daily_chart(daily_pnl(f)))

    with t_bd:
        gfmt = {"Win rate %": "{:.1f}", "Net P&L": "{:+,.2f}", "Avg / trade": "{:+,.2f}", "Profit factor": "{:.2f}"}
        c1, c2 = st.columns(2)
        with c1:
            ui.section("ตาม Symbol")
            g = group_stats(f, "symbol")
            plot(ui.pnl_bars(g["symbol"], g["Net P&L"], height=max(160, 46 * len(g) + 40), horizontal=True))
            show_table(style(g.rename(columns={"symbol": "Symbol"}), gfmt, ["Net P&L", "Avg / trade"]))
        with c2:
            ui.section("ตามทิศทาง")
            g = group_stats(f, "direction")
            plot(ui.pnl_bars(g["direction"], g["Net P&L"], height=max(160, 46 * len(g) + 40), horizontal=True))
            show_table(style(g.rename(columns={"direction": "Direction"}), gfmt, ["Net P&L", "Avg / trade"]))
        c1, c2 = st.columns(2)
        with c1:
            ui.section("ตามวันที่เข้าไม้")
            g = group_stats(f, "weekday", order=WEEKDAYS)
            plot(ui.pnl_bars(g["weekday"], g["Net P&L"]))
        with c2:
            ui.section("ตามชั่วโมงที่เข้าไม้", "เวลาเซิร์ฟเวอร์")
            g = group_stats(f, "hour").sort_values("hour")
            plot(ui.pnl_bars([f"{int(h):02d}" for h in g["hour"]], g["Net P&L"]))

    with t_ds:
        c1, c2 = st.columns([3, 2])
        with c1:
            ui.section("การกระจายผลต่อไม้")
            plot(ui.hist_chart(f["net"]))
        with c2:
            ui.section("ค่าสุดขั้ว")
            ui.kpi_grid([
                dict(label="Best trade", value=ui.money(k["best"], signed=True), tone=ui.tone(k["best"])),
                dict(label="Worst trade", value=ui.money(k["worst"], signed=True), tone=ui.tone(k["worst"])),
                dict(label="ค่าธรรมเนียม + swap", value=ui.money(k["costs"], signed=True),
                     tone=ui.tone(k["costs"]), sub="รวมอยู่ใน Net P&L แล้ว"),
            ])
        c1, c2 = st.columns(2)
        with c1:
            ui.section("5 ไม้ที่ดีที่สุด")
            show_table(style(trades_table(f.nlargest(5, "net")), TRADE_FMT, ["Net P&L"]))
        with c2:
            ui.section("5 ไม้ที่แย่ที่สุด")
            show_table(style(trades_table(f.nsmallest(5, "net")), TRADE_FMT, ["Net P&L"]))

    with t_cal:
        daily = daily_pnl(f)
        counts = f.groupby("close_date").size()
        months = sorted({(d.year, d.month) for d in daily.index}, reverse=True)
        pick = st.selectbox("เดือน", months, format_func=lambda ym: pd.Timestamp(ym[0], ym[1], 1).strftime("%B %Y"),
                            label_visibility="collapsed")
        y, m = pick
        total = float(daily[(daily.index.year == y) & (daily.index.month == m)].sum())
        ui.section(pd.Timestamp(y, m, 1).strftime("%B %Y"), f"รวม {total:+,.2f}")
        st.markdown(ui.calendar_html(daily, counts, y, m), unsafe_allow_html=True)


def _idx(options: list, value) -> int:
    return options.index(value) if value in options else 0


def render_editor(tr: pd.Series, note: dict, account_id: str) -> None:
    tid = str(tr["trade_id"])
    ui.section(f'{tr["symbol"]} · {tr["direction"]}',
               f'ปิด {fmt_time(tr["close_time"])} · Net {tr["net"]:+,.2f}')
    with st.form(f"note_{tid}"):
        c1, c2, c3 = st.columns(3)
        setup = c1.selectbox("Setup", [""] + SETUPS, index=_idx([""] + SETUPS, note.get("setup", "")))
        tf = c2.selectbox("Timeframe", [""] + TIMEFRAMES, index=_idx([""] + TIMEFRAMES, note.get("timeframe", "")))
        conf = c3.slider("Confidence (1–5)", 1, 5, int(note.get("confidence") or 3))
        c1, c2, c3 = st.columns(3)
        e_in = c1.selectbox("อารมณ์ตอนเข้า", [""] + EMOTIONS, index=_idx([""] + EMOTIONS, note.get("emotion_in", "")))
        e_out = c2.selectbox("อารมณ์ตอนออก", [""] + EMOTIONS, index=_idx([""] + EMOTIONS, note.get("emotion_out", "")))
        followed = c3.checkbox("ทำตามแผน", value=bool(int(note.get("followed_plan", 1) or 0)))
        mistakes = st.multiselect("Mistakes", MISTAKES,
                                  default=[m for m in notes.parse_mistakes(note.get("mistakes")) if m in MISTAKES])
        thesis = st.text_area("Thesis — ทำไมถึงเข้าไม้นี้", value=note.get("thesis", "") or "", height=90)
        lesson = st.text_area("Lesson — ได้เรียนรู้อะไร", value=note.get("lesson", "") or "", height=90)
        submitted = st.form_submit_button("บันทึกโน้ต", type="primary")
    if submitted:
        ok, msg = notes.save_note(
            tid, account_id, setup=setup, timeframe=tf, confidence=conf, emotion_in=e_in,
            emotion_out=e_out, followed_plan=followed, mistakes=mistakes, thesis=thesis, lesson=lesson,
        )
        if ok:
            st.session_state["flash"] = f"บันทึกโน้ตไม้ {tr['symbol']} แล้ว"
            st.rerun()
        else:
            st.error(msg)


def page_journal(trades, snap):
    ui.page_header("Journal", "เลือกไม้จากตารางเพื่อบันทึก setup อารมณ์ และบทเรียน")
    if st.session_state.get("flash"):
        st.success(st.session_state.pop("flash"))
    if trades.empty:
        ui.empty_state("📭", "ยังไม่มีไม้ที่ปิดแล้ว", "เมื่อมีประวัติเทรดใน Supabase ไม้จะปรากฏที่นี่ให้จดบันทึก")
        return

    account_id = str(snap.get("login", ""))
    saved, nerr = notes.load_notes(account_id)
    f, _ = filter_bar(trades, "jr")
    if f.empty:
        ui.empty_state("🔍", "ไม่พบไม้ตามตัวกรองที่เลือก")
        return

    view = f.sort_values("close_time", ascending=False).reset_index(drop=True)
    noted = {t for t, n in saved.items() if n.get("thesis") or n.get("lesson") or n.get("setup")
             or notes.parse_mistakes(n.get("mistakes"))}
    ui.kpi_grid([
        dict(label="ไม้ในมุมมองนี้", value=len(view)),
        dict(label="จดบันทึกแล้ว", value=int(view["trade_id"].isin(noted).sum()),
             sub=f'{view["trade_id"].isin(noted).mean() * 100:.0f}% ของไม้'),
    ])

    event = show_table(style(trades_table(view, noted), TRADE_FMT, ["Net P&L"]), height=330,
                       on_select="rerun", selection_mode="single-row", key="jr_table")
    rows = list(getattr(getattr(event, "selection", None), "rows", []) or [])

    if nerr == "missing_table":
        ui.note("ยังไม่มีตาราง trade_notes ใน Supabase — รันไฟล์ supabase/trade_notes.sql ใน SQL Editor ก่อน "
                "จึงจะบันทึกโน้ตได้", warn=True)
        return
    if nerr:
        ui.note(f"โหลดโน้ตไม่สำเร็จ: {nerr}", warn=True)
        return

    if rows and rows[0] < len(view):
        render_editor(view.iloc[rows[0]], saved.get(str(view.iloc[rows[0]]["trade_id"]), {}), account_id)
    else:
        ui.note("คลิกแถวในตารางด้านบนเพื่อเปิดแบบฟอร์มบันทึก")

    if noted:
        with st.expander("Insights จากโน้ตที่จดไว้"):
            g = view.copy()
            for col in ("setup", "emotion_in"):
                g[col] = g["trade_id"].map(lambda t, c=col: (saved.get(t) or {}).get(c, "") or "")
            gfmt = {"Win rate %": "{:.1f}", "Net P&L": "{:+,.2f}", "Avg / trade": "{:+,.2f}", "Profit factor": "{:.2f}"}
            c1, c2 = st.columns(2)
            for col, label, holder in (("setup", "Setup", c1), ("emotion_in", "อารมณ์ตอนเข้า", c2)):
                sub = g[g[col] != ""]
                with holder:
                    ui.section(f"ผลตาม {label}")
                    if sub.empty:
                        ui.note("ยังไม่มีข้อมูล")
                    else:
                        show_table(style(group_stats(sub, col).rename(columns={col: label}), gfmt,
                                         ["Net P&L", "Avg / trade"]))
            mrows = [
                {"Mistake": m, "Net P&L": float(r["net"])}
                for _, r in view.iterrows()
                for m in notes.parse_mistakes((saved.get(r["trade_id"]) or {}).get("mistakes"))
            ]
            if mrows:
                ui.section("ข้อผิดพลาดที่ทำให้เสียเงินมากที่สุด")
                mdf = (pd.DataFrame(mrows).groupby("Mistake")["Net P&L"].agg(["count", "sum"])
                       .rename(columns={"count": "Trades", "sum": "Net P&L"}).sort_values("Net P&L").reset_index())
                show_table(style(mdf, {"Net P&L": "{:+,.2f}"}, ["Net P&L"]))


# ====================================================================== main

def main() -> None:
    if not gate():
        st.stop()

    url, key = data.supabase_config()
    if not url or not key:
        ui.empty_state("🔐", "ยังไม่ได้ตั้งค่า Supabase",
                       "ใส่ SUPABASE_URL และ SUPABASE_KEY ใน Streamlit Secrets แล้วรีสตาร์ตแอป")
        st.stop()

    snap, err = data.load_snapshot()

    with st.sidebar:
        st.markdown(f'<div class="brand">📓 {APP_NAME}</div>'
                    f'<div class="brand-sub">Trading journal · v{APP_VERSION}</div>', unsafe_allow_html=True)
        st.write("")
        page = st.radio("เมนู", PAGES, label_visibility="collapsed")
        if snap:
            ui.side_card("Account", f'{snap.get("login", "")} · {snap.get("currency", "")}')
            ui.side_card("Server", str(snap.get("server", "")))
        if stretch(st.button, "↻  รีเฟรชข้อมูล"):
            data.clear_cache()
            notes.load_notes.clear()
            st.rerun()

    if not snap:
        ui.empty_state("📡", "ยังไม่พบข้อมูลบัญชีใน Supabase",
                       err or "ตรวจสอบว่า NobodyCollector EA กำลังทำงานอยู่ใน MT5")
        st.stop()

    pos_raw, e_pos = data.load_positions(snap)
    pend, e_pend = data.load_pending(snap)
    hist, e_hist = data.load_history(snap)
    for e in (e_pos, e_pend, e_hist):
        if e:
            ui.note(e, warn=True)

    pos = positions_view(pos_raw)
    trades = build_trades(hist)
    bal = pd.to_numeric(pd.Series([snap.get("balance")]), errors="coerce").iloc[0]
    balance = 0.0 if pd.isna(bal) else float(bal)
    capital = est_capital(balance, trades)
    cur = str(snap.get("currency") or "")

    if page == "Overview":
        page_overview(snap, pos, pend, trades, capital, cur)
    elif page == "Performance":
        page_performance(trades, capital)
    else:
        page_journal(trades, snap)


main()
