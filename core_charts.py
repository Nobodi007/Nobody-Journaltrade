"""กราฟทั้งหมด"""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

DARK = dict(
    template="plotly_dark",
    paper_bgcolor="#0b0e11",
    plot_bgcolor="#0b0e11",
    margin=dict(l=10, r=10, t=44, b=10),
)

GREEN = "#0ecb81"
RED = "#f6465d"
GREY = "#848e9c"


def equity_chart(eq: pd.DataFrame) -> go.Figure:
    fig = make_subplots(
        rows=2, cols=1, shared_xaxes=True,
        row_heights=[0.7, 0.3], vertical_spacing=0.06,
        subplot_titles=("Equity Curve", "Drawdown"),
    )
    if not eq.empty:
        fig.add_trace(
            go.Scatter(
                x=eq["time"], y=eq["equity"], mode="lines", name="Equity",
                line=dict(color=GREEN, width=2),
                fill="tozeroy", fillcolor="rgba(14,203,129,.10)",
            ),
            row=1, col=1,
        )
        fig.add_trace(
            go.Scatter(
                x=eq["time"], y=eq["drawdown"], mode="lines", name="DD",
                line=dict(color=RED, width=1.4),
                fill="tozeroy", fillcolor="rgba(246,70,93,.16)",
            ),
            row=2, col=1,
        )
    fig.update_layout(height=440, showlegend=False, **DARK)
    return fig


def pnl_bars(df: pd.DataFrame, limit: int = 120) -> go.Figure:
    fig = go.Figure()
    if not df.empty:
        d = df.sort_values("close_time").tail(limit)
        fig.add_trace(
            go.Bar(
                x=list(range(1, len(d) + 1)),
                y=d["net"].round(2),
                marker_color=[GREEN if v > 0 else RED for v in d["net"]],
                hovertext=d["symbol"],
            )
        )
        fig.add_hline(y=0, line_color=GREY, line_width=1)
    fig.update_layout(
        height=300, showlegend=False,
        title=f"กำไร/ขาดทุนรายไม้ (ล่าสุด {limit})",
        xaxis_title="ลำดับไม้", yaxis_title="Net", **DARK,
    )
    return fig


def monthly_chart(m: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    if not m.empty:
        fig.add_trace(
            go.Bar(
                x=m["month"], y=m["Net"],
                marker_color=[GREEN if v > 0 else RED for v in m["Net"]],
                name="Net",
            )
        )
        fig.add_trace(
            go.Scatter(
                x=m["month"], y=m["Cumulative"], mode="lines+markers",
                name="สะสม", line=dict(color="#f0b90b", width=2), yaxis="y2",
            )
        )
        fig.update_layout(
            yaxis2=dict(overlaying="y", side="right", showgrid=False)
        )
    fig.update_layout(height=330, title="ผลรายเดือน", **DARK)
    return fig


def hour_heat(df: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    if not df.empty and "hour" in df.columns:
        g = df.groupby("hour")["net"].sum().reindex(range(24), fill_value=0)
        fig.add_trace(
            go.Bar(
                x=g.index, y=g.values.round(2),
                marker_color=[GREEN if v > 0 else RED for v in g.values],
            )
        )
        fig.add_hline(y=0, line_color=GREY, line_width=1)
    fig.update_layout(
        height=290, showlegend=False, title="กำไรสะสมตามชั่วโมงที่ปิดไม้ (UTC)",
        xaxis_title="ชั่วโมง", **DARK,
    )
    return fig


def symbol_pie(df: pd.DataFrame, top: int = 10) -> go.Figure:
    fig = go.Figure()
    if not df.empty:
        g = df.groupby("symbol")["trade_id"].count().nlargest(top)
        fig.add_trace(go.Pie(labels=g.index, values=g.values, hole=0.55))
    fig.update_layout(height=290, title="สัดส่วนจำนวนไม้ตาม Symbol", **DARK)
    return fig
