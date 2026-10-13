"""ธีม, การ์ด KPI, กราฟ และปฏิทิน — ส่วนหน้าตาทั้งหมดอยู่ที่นี่"""

from __future__ import annotations

import calendar
import html
import math

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

# ------------------------------------------------------------------ tokens
BG = "#0b0e13"
SURFACE = "#12161d"
SURFACE2 = "#171c25"
BORDER = "#222a36"
GRID = "#1a2029"
TEXT = "#e6eaf0"
MUTED = "#8792a2"
FAINT = "#5d6877"
POS = "#3ecf8e"
NEG = "#f0616d"
ACCENT = "#7aa2f7"
WARN = "#f2b84b"
FONT = "Inter, 'Noto Sans Thai', system-ui, sans-serif"

CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Noto+Sans+Thai:wght@400;500;600;700&display=swap');
html, body, [class*="css"], .stApp {{ font-family:{FONT}; }}
.stApp {{ background:{BG}; }}
#MainMenu, footer {{ visibility:hidden; }}
[data-testid="stHeader"] {{ background:transparent; }}
.block-container {{ max-width:1320px; padding:2.2rem 2rem 4rem; }}
[data-testid="stVerticalBlock"] {{ gap:.7rem; }}

section[data-testid="stSidebar"] {{ background:{SURFACE}; border-right:1px solid {BORDER}; }}
section[data-testid="stSidebar"] .block-container {{ padding:1.4rem 1rem; }}
section[data-testid="stSidebar"] [data-testid="stRadio"] > div {{ gap:2px; }}
section[data-testid="stSidebar"] [data-testid="stRadio"] label {{
  padding:9px 12px; border-radius:8px; width:100%; cursor:pointer;
}}
section[data-testid="stSidebar"] [data-testid="stRadio"] label:hover {{ background:{SURFACE2}; }}
section[data-testid="stSidebar"] [data-testid="stRadio"] label p {{ font-size:.9rem; font-weight:500; }}
section[data-testid="stSidebar"] [data-testid="stRadio"] label > div:first-child {{ display:none; }}
section[data-testid="stSidebar"] [data-testid="stRadio"] label:has(input:checked) {{
  background:{SURFACE2}; box-shadow:inset 2px 0 0 {ACCENT};
}}

.brand {{ font-size:1.05rem; font-weight:700; letter-spacing:-.01em; color:{TEXT}; }}
.brand-sub {{ font-size:.72rem; color:{FAINT}; margin-top:2px; }}
.side-card {{ background:{BG}; border:1px solid {BORDER}; border-radius:10px; padding:11px 13px; margin:10px 0; }}
.side-k {{ font-size:.66rem; letter-spacing:.09em; color:{FAINT}; text-transform:uppercase; font-weight:600; }}
.side-v {{ font-size:.86rem; color:{TEXT}; font-weight:500; margin-top:3px; font-variant-numeric:tabular-nums; }}

.ph {{ display:flex; justify-content:space-between; align-items:flex-end; gap:16px; margin:0 0 .6rem; flex-wrap:wrap; }}
.ph h1 {{ font-size:1.65rem; font-weight:700; letter-spacing:-.02em; margin:0; color:{TEXT}; padding:0; }}
.ph p {{ margin:4px 0 0; color:{MUTED}; font-size:.86rem; }}
.pill {{ display:inline-flex; align-items:center; gap:7px; padding:5px 11px; border-radius:999px;
  font-size:.74rem; font-weight:600; border:1px solid {BORDER}; background:{SURFACE}; color:{MUTED}; }}
.pill i {{ width:7px; height:7px; border-radius:50%; background:{FAINT}; display:inline-block; }}
.pill.live {{ color:{POS}; border-color:rgba(62,207,142,.3); }} .pill.live i {{ background:{POS}; box-shadow:0 0 8px {POS}; }}
.pill.stale {{ color:{WARN}; border-color:rgba(242,184,75,.3); }} .pill.stale i {{ background:{WARN}; }}
.pill.off {{ color:{NEG}; border-color:rgba(240,97,109,.3); }} .pill.off i {{ background:{NEG}; }}

.sec {{ display:flex; align-items:baseline; gap:10px; margin:1.5rem 0 .2rem; }}
.sec h3 {{ font-size:1rem; font-weight:600; margin:0; padding:0; color:{TEXT}; letter-spacing:-.005em; }}
.sec span {{ color:{FAINT}; font-size:.78rem; }}

.kpi-grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(176px,1fr)); gap:12px; margin:.35rem 0 .5rem; }}
.kpi {{ background:{SURFACE}; border:1px solid {BORDER}; border-radius:12px; padding:14px 16px 13px; }}
.kpi-l {{ font-size:.72rem; color:{MUTED}; font-weight:500; letter-spacing:.01em; }}
.kpi-v {{ font-size:1.5rem; font-weight:650; letter-spacing:-.02em; margin-top:5px; color:{TEXT};
  font-variant-numeric:tabular-nums; line-height:1.15; }}
.kpi-s {{ font-size:.72rem; color:{FAINT}; margin-top:5px; font-variant-numeric:tabular-nums; min-height:1em; }}
.kpi-v.pos {{ color:{POS}; }} .kpi-v.neg {{ color:{NEG}; }}

.empty {{ text-align:center; padding:56px 20px; border:1px dashed {BORDER}; border-radius:14px; background:{SURFACE}; margin:1rem 0; }}
.empty b {{ display:block; font-size:1.05rem; color:{TEXT}; margin:6px 0 4px; }}
.empty span {{ color:{MUTED}; font-size:.86rem; }}
.empty .ic {{ font-size:1.8rem; }}

.note {{ background:{SURFACE}; border:1px solid {BORDER}; border-left:3px solid {ACCENT}; border-radius:8px;
  padding:10px 14px; color:{MUTED}; font-size:.82rem; margin:.4rem 0; }}
.note.warn {{ border-left-color:{WARN}; }}

[data-testid="stDataFrame"] {{ border:1px solid {BORDER}; border-radius:10px; overflow:hidden; }}
.stTabs [data-baseweb="tab-list"] {{ gap:4px; border-bottom:1px solid {BORDER}; }}
.stTabs [data-baseweb="tab"] {{ height:42px; padding:0 14px; color:{MUTED}; font-weight:500; }}
.stTabs [aria-selected="true"] {{ color:{TEXT}; }}
.stButton > button, .stFormSubmitButton > button {{ border-radius:8px; font-weight:600; }}

.cal {{ display:grid; grid-template-columns:repeat(7,minmax(0,1fr)) 1.15fr; gap:6px; margin-top:.4rem; }}
.cal-h {{ font-size:.7rem; color:{FAINT}; text-align:center; padding:2px 0 4px; font-weight:600; letter-spacing:.05em; }}
.cal-c {{ background:{SURFACE}; border:1px solid {BORDER}; border-radius:8px; min-height:74px; padding:7px 9px;
  display:flex; flex-direction:column; justify-content:space-between; }}
.cal-c.x {{ background:transparent; border-color:transparent; }}
.cal-d {{ font-size:.7rem; color:{FAINT}; }}
.cal-v {{ font-size:.86rem; font-weight:600; text-align:right; font-variant-numeric:tabular-nums; }}
.cal-n {{ font-size:.64rem; color:{MUTED}; text-align:right; }}
.cal-w {{ background:{BG}; }}

@media (max-width: 800px) {{
  .block-container {{ padding:1rem .8rem 3rem; }}
  .ph h1 {{ font-size:1.3rem; }}
  .kpi-grid {{ grid-template-columns:repeat(2,minmax(0,1fr)); gap:8px; }}
  .kpi-v {{ font-size:1.2rem; }}
  .cal {{ gap:3px; }} .cal-c {{ min-height:54px; padding:4px 5px; }} .cal-v {{ font-size:.7rem; }} .cal-n {{ display:none; }}
}}
</style>
"""


def inject_css() -> None:
    st.markdown(CSS, unsafe_allow_html=True)


# ------------------------------------------------------------------ formatting
def _bad(v) -> bool:
    return v is None or (isinstance(v, float) and (math.isnan(v) or math.isinf(v)))


def money(v, signed: bool = False, dp: int = 2) -> str:
    if _bad(v):
        return "—"
    return f"{v:+,.{dp}f}" if signed else f"{v:,.{dp}f}"


def pct(v, dp: int = 1, signed: bool = False) -> str:
    if _bad(v):
        return "—"
    return f"{v:+.{dp}f}%" if signed else f"{v:.{dp}f}%"


def num(v, dp: int = 2) -> str:
    return "—" if _bad(v) else f"{v:,.{dp}f}"


def duration(minutes) -> str:
    if _bad(minutes):
        return "—"
    m = int(round(minutes))
    if m < 60:
        return f"{m}m"
    if m < 60 * 24:
        return f"{m // 60}h {m % 60:02d}m"
    return f"{m // 1440}d {(m % 1440) // 60}h"


def tone(v) -> str:
    if _bad(v) or abs(v) < 0.005:
        return ""
    return "pos" if v > 0 else "neg"


# ------------------------------------------------------------------ components
def page_header(title: str, sub: str = "", right: str = "") -> None:
    st.markdown(
        f'<div class="ph"><div><h1>{html.escape(title)}</h1>'
        + (f"<p>{html.escape(sub)}</p>" if sub else "")
        + f"</div><div>{right}</div></div>",
        unsafe_allow_html=True,
    )


def section(title: str, note: str = "") -> None:
    st.markdown(
        f'<div class="sec"><h3>{html.escape(title)}</h3>'
        + (f"<span>{html.escape(note)}</span>" if note else "")
        + "</div>",
        unsafe_allow_html=True,
    )


def kpi_grid(items: list[dict]) -> None:
    """items: [{label, value, sub, tone}]"""
    cards = "".join(
        f'<div class="kpi"><div class="kpi-l">{html.escape(i["label"])}</div>'
        f'<div class="kpi-v {i.get("tone", "")}">{html.escape(str(i["value"]))}</div>'
        f'<div class="kpi-s">{html.escape(str(i.get("sub", "")))}</div></div>'
        for i in items
    )
    st.markdown(f'<div class="kpi-grid">{cards}</div>', unsafe_allow_html=True)


def empty_state(icon: str, title: str, text: str = "") -> None:
    st.markdown(
        f'<div class="empty"><div class="ic">{icon}</div><b>{html.escape(title)}</b>'
        f"<span>{html.escape(text)}</span></div>",
        unsafe_allow_html=True,
    )


def note(text: str, warn: bool = False) -> None:
    st.markdown(f'<div class="note{" warn" if warn else ""}">{html.escape(text)}</div>', unsafe_allow_html=True)


def status_pill(age_seconds: float | None) -> str:
    if age_seconds is None:
        return '<span class="pill"><i></i>ไม่ทราบสถานะ</span>'
    if age_seconds < 90:
        return '<span class="pill live"><i></i>Live</span>'
    if age_seconds < 900:
        return f'<span class="pill stale"><i></i>อัปเดตเมื่อ {int(age_seconds // 60)} นาทีก่อน</span>'
    return '<span class="pill off"><i></i>Collector ไม่ส่งข้อมูล</span>'


def side_card(label: str, value: str) -> None:
    st.markdown(
        f'<div class="side-card"><div class="side-k">{html.escape(label)}</div>'
        f'<div class="side-v">{html.escape(value)}</div></div>',
        unsafe_allow_html=True,
    )


# ------------------------------------------------------------------ charts
def _base(fig: go.Figure, height: int = 300, hover: str = "x unified") -> go.Figure:
    fig.update_layout(
        height=height,
        margin=dict(l=4, r=4, t=8, b=4),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family=FONT, size=12, color=MUTED),
        showlegend=False,
        hovermode=hover,
        hoverlabel=dict(bgcolor=SURFACE2, bordercolor=BORDER, font=dict(color=TEXT, family=FONT)),
        bargap=0.35,
    )
    fig.update_xaxes(showgrid=False, zeroline=False, linecolor=BORDER, ticks="", tickfont=dict(color=FAINT))
    fig.update_yaxes(gridcolor=GRID, zeroline=False, ticks="", tickfont=dict(color=FAINT), automargin=True)
    return fig


def equity_chart(curve: pd.DataFrame, start_capital: float = 0.0) -> go.Figure:
    use_balance = start_capital > 0
    y = curve["equity"] if use_balance else curve["cum"]
    label = "Balance (est.)" if use_balance else "Cumulative P&L"
    x = curve["time"]
    fig = go.Figure(
        go.Scatter(
            x=x, y=y, mode="lines+markers" if len(curve) <= 40 else "lines",
            line=dict(color=ACCENT, width=2, shape="hv"),
            marker=dict(size=7, color=ACCENT, line=dict(color=BG, width=2)),
            customdata=curve["pnl"],
            hovertemplate=label + ": %{y:,.2f}<br>Trade: %{customdata:+,.2f}<extra></extra>",
        )
    )
    if use_balance:
        fig.add_hline(y=start_capital, line=dict(color=BORDER, width=1, dash="dot"))
    return _base(fig, 300)


def drawdown_chart(curve: pd.DataFrame) -> go.Figure:
    fig = go.Figure(
        go.Scatter(
            x=curve["time"], y=curve["dd"], mode="lines",
            line=dict(color=NEG, width=1.5, shape="hv"),
            fill="tozeroy", fillcolor="rgba(240,97,109,.14)",
            hovertemplate="Drawdown: %{y:,.2f}<extra></extra>",
        )
    )
    return _base(fig, 170)


def pnl_bars(labels, values, height: int = 260, horizontal: bool = False) -> go.Figure:
    """แท่ง P&L: เขียว = กำไร / แดง = ขาดทุน (ทิศทางแท่งบอกเครื่องหมายอยู่แล้ว ไม่ได้พึ่งสีอย่างเดียว)"""
    vals = [0.0 if _bad(v) else float(v) for v in values]
    colors = [POS if v >= 0 else NEG for v in vals]
    labels = [str(x) for x in labels]
    if horizontal:
        fig = go.Figure(go.Bar(
            x=vals, y=labels, orientation="h", marker=dict(color=colors),
            hovertemplate="%{y}: %{x:+,.2f}<extra></extra>",
        ))
        fig = _base(fig, height, hover="closest")
        fig.update_yaxes(autorange="reversed", showgrid=False)
        fig.update_xaxes(showgrid=True, gridcolor=GRID)
        return fig
    fig = go.Figure(go.Bar(
        x=labels, y=vals, marker=dict(color=colors),
        hovertemplate="%{x}: %{y:+,.2f}<extra></extra>",
    ))
    fig = _base(fig, height, hover="closest")
    fig.update_xaxes(type="category")
    return fig


def daily_chart(daily: pd.Series) -> go.Figure:
    fig = go.Figure(go.Bar(
        x=daily.index, y=daily.values,
        marker=dict(color=[POS if v >= 0 else NEG for v in daily.values]),
        hovertemplate="%{x|%d %b %Y}: %{y:+,.2f}<extra></extra>",
    ))
    return _base(fig, 240, hover="closest")


def hist_chart(values: pd.Series) -> go.Figure:
    v = values.dropna()
    fig = go.Figure(go.Histogram(
        x=v, nbinsx=min(24, max(6, len(v) // 2)),
        marker=dict(color=ACCENT, line=dict(color=BG, width=1)),
        hovertemplate="%{x}: %{y} trades<extra></extra>",
    ))
    fig = _base(fig, 240, hover="closest")
    fig.add_vline(x=0, line=dict(color=BORDER, width=1))
    return fig


# ------------------------------------------------------------------ calendar
def calendar_html(daily: pd.Series, counts: pd.Series, year: int, month: int) -> str:
    m = daily[(daily.index.year == year) & (daily.index.month == month)]
    by_day = {ts.day: float(v) for ts, v in m.items()}
    cnt = {ts.day: int(c) for ts, c in counts.items() if ts.year == year and ts.month == month}
    mx = max([abs(v) for v in by_day.values()] + [1e-9])

    head = "".join(f'<div class="cal-h">{d}</div>' for d in
                   ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN", "WEEK"])
    cells = []
    for week in calendar.Calendar(firstweekday=0).monthdayscalendar(year, month):
        wsum, wn = 0.0, 0
        for d in week:
            if d == 0:
                cells.append('<div class="cal-c x"></div>')
                continue
            if d in by_day:
                v = by_day[d]
                wsum += v
                wn += 1
                a = 0.10 + 0.40 * abs(v) / mx
                rgb = "62,207,142" if v >= 0 else "240,97,109"
                color = POS if v >= 0 else NEG
                cells.append(
                    f'<div class="cal-c" style="background:rgba({rgb},{a:.2f});border-color:rgba({rgb},.35)">'
                    f'<div class="cal-d">{d}</div><div><div class="cal-v" style="color:{color}">{v:+,.2f}</div>'
                    f'<div class="cal-n">{cnt.get(d, 0)} trades</div></div></div>'
                )
            else:
                cells.append(f'<div class="cal-c"><div class="cal-d">{d}</div></div>')
        if wn:
            color = POS if wsum >= 0 else NEG
            cells.append(f'<div class="cal-c cal-w"><div class="cal-d">{wn}d</div>'
                         f'<div class="cal-v" style="color:{color}">{wsum:+,.2f}</div></div>')
        else:
            cells.append('<div class="cal-c cal-w"></div>')
    return f'<div class="cal">{head}{"".join(cells)}</div>'
