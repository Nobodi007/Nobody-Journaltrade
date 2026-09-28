"""กราฟ Plotly ธีมมืด"""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

GREEN = "#0ecb81"
RED = "#f6465d"
GOLD = "#f0b90b"
GRID = "#2b3139"
WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def _layout(fig: go.Figure, title: str, height: int = 340) -> go.Figure:
    fig.update_layout(
        title=title,
        template="plotly_dark",
        height=height,
        margin=dict(l=10, r=10, t=45, b=10),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        legend=dict(orientation="h", y=-0.15),
    )
    fig.update_xaxes(gridcolor=GRID)
    fig.update_yaxes(gridcolor=GRID)
    return fig


def equity_chart(eq: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    if not eq.empty:
        fig.add_trace(go.Scatter(
            x=eq["time"], y=eq["equity"], mode="lines",
            line=dict(color=GOLD, width=2), fill="tozeroy",
            fillcolor="rgba(240,185,11,0.08)", name="Equity",
        ))
    return _layout(fig, "Equity Curve (จากไม้ที่ปิด)", 380)


def pnl_bars(df: pd.DataFrame) -> go.Figure:
    d = df.sort_values("close_time")
    fig = go.Figure(go.Bar(
        x=list(range(1, len(d) + 1)),
        y=d["net"],
        marker_color=[GREEN if v > 0 else RED for v in d["net"]],
        customdata=d[["symbol", "close_time"]].astype(str).values,
        hovertemplate="ไม้ #%{x}<br>%{customdata[0]}<br>%{customdata[1]}<br>%{y:+,.2f}<extra></extra>",
    ))
    fig.update_xaxes(title="ลำดับไม้")
    return _layout(fig, "กำไร/ขาดทุนรายไม้")


def symbol_pie(df: pd.DataFrame) -> go.Figure:
    c = df["symbol"].value_counts()
    fig = go.Figure(go.Pie(labels=c.index, values=c.values, hole=0.55))
    return _layout(fig, "สัดส่วนจำนวนไม้ตาม Symbol")


def monthly_chart(tbl: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    if not tbl.empty:
        fig.add_trace(go.Bar(
            x=tbl["เดือน"], y=tbl["Net"],
            marker_color=[GREEN if v >= 0 else RED for v in tbl["Net"]],
            text=tbl["Net"].map(lambda v: f"{v:+,.0f}"), textposition="outside",
        ))
    return _layout(fig, "ผลรายเดือน")


def hour_heat(df: pd.DataFrame) -> go.Figure:
    pv = (
        df.pivot_table(index="weekday", columns="hour", values="net", aggfunc="sum")
        .reindex(index=WEEKDAYS, columns=range(24))
    )
    fig = go.Figure(go.Heatmap(
        z=pv.values, x=list(pv.columns), y=list(pv.index),
        colorscale=[[0, RED], [0.5, "#181a20"], [1, GREEN]], zmid=0,
        hovertemplate="%{y} %{x}:00<br>Net %{z:+,.2f}<extra></extra>",
        colorbar=dict(title="Net"),
    ))
    fig.update_xaxes(title="ชั่วโมงที่ปิดไม้ (เวลาไทย)", dtick=1)
    fig.update_yaxes(autorange="reversed")
    return _layout(fig, "Heatmap: วัน × ชั่วโมง", 320)
