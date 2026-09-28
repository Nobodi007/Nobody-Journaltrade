"""กราฟสำหรับ Nobody Trade Journal"""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go


def _base(fig, height=360, title=None):
    fig.update_layout(
        template="plotly_dark",
        height=height,
        title=title,
        margin=dict(l=10, r=10, t=45 if title else 20, b=20),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        hovermode="x unified",
    )
    return fig


def equity_chart(eq):
    fig = go.Figure()
    if eq.empty:
        fig.add_annotation(text="ยังไม่มีข้อมูล Equity", x=0.5, y=0.5, showarrow=False)
        return _base(fig, 380, "Equity Curve")
    fig.add_trace(go.Scatter(
        x=eq["time"], y=eq["equity"], mode="lines",
        name="Equity", line=dict(width=2)
    ))
    return _base(fig, 380, "Equity Curve")


def pnl_bars(df):
    fig = go.Figure()
    if df.empty:
        fig.add_annotation(text="ยังไม่มี P&L", x=0.5, y=0.5, showarrow=False)
        return _base(fig, 330, "P&L ต่อไม้")
    d = df.sort_values("close_time")
    fig.add_trace(go.Bar(
        x=d["close_time"], y=d["net"], name="Net P&L",
        hovertemplate="%{x}<br>Net: %{y:,.2f}<extra></extra>"
    ))
    fig.add_hline(y=0, line_dash="dot")
    return _base(fig, 330, "P&L ต่อไม้")


def symbol_pie(df):
    fig = go.Figure()
    if df.empty or "symbol" not in df.columns:
        fig.add_annotation(text="ยังไม่มีข้อมูล Symbol", x=0.5, y=0.5, showarrow=False)
        return _base(fig, 330, "จำนวนไม้แยกตาม Symbol")
    counts = df["symbol"].astype(str).value_counts()
    fig.add_trace(go.Pie(labels=counts.index, values=counts.values, hole=0.45))
    return _base(fig, 330, "จำนวนไม้แยกตาม Symbol")


def monthly_chart(monthly):
    fig = go.Figure()
    if monthly.empty:
        fig.add_annotation(text="ยังไม่มีข้อมูลรายเดือน", x=0.5, y=0.5, showarrow=False)
        return _base(fig, 330, "P&L รายเดือน")
    x = monthly["เดือน"] if "เดือน" in monthly.columns else monthly["month"]
    fig.add_trace(go.Bar(x=x, y=monthly["Net"], name="Net"))
    fig.add_hline(y=0, line_dash="dot")
    return _base(fig, 330, "P&L รายเดือน")


def hour_heat(df):
    fig = go.Figure()
    if df.empty or "hour" not in df.columns:
        fig.add_annotation(text="ยังไม่มีข้อมูลช่วงเวลา", x=0.5, y=0.5, showarrow=False)
        return _base(fig, 360, "P&L ตามชั่วโมง")

    d = df.copy()
    d["hour"] = pd.to_numeric(d["hour"], errors="coerce")
    d = d.dropna(subset=["hour"])
    if d.empty:
        fig.add_annotation(text="ยังไม่มีข้อมูลช่วงเวลา", x=0.5, y=0.5, showarrow=False)
        return _base(fig, 360, "P&L ตามชั่วโมง")

    pivot = d.groupby("hour")["net"].agg(["sum", "size"]).reindex(range(24), fill_value=0)
    fig.add_trace(go.Heatmap(
        x=list(range(24)),
        y=["Net P&L", "จำนวนไม้"],
        z=[pivot["sum"].tolist(), pivot["size"].tolist()],
        text=[
            [f"{v:,.2f}" for v in pivot["sum"]],
            [str(int(v)) for v in pivot["size"]],
        ],
        texttemplate="%{text}",
        hovertemplate="Hour %{x}<br>%{y}: %{z}<extra></extra>",
    ))
    return _base(fig, 360, "P&L ตามชั่วโมง")


__all__ = ["equity_chart", "hour_heat", "monthly_chart", "pnl_bars", "symbol_pie"]
