"""คำนวณสถิติแบบ Myfxbook"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd


def _safe(v: Any, default: float = 0.0) -> float:
    try:
        f = float(v)
        return default if (np.isnan(f) or np.isinf(f)) else f
    except (TypeError, ValueError):
        return default


def summary(df: pd.DataFrame, metrics: dict[str, Any] | None = None) -> dict[str, Any]:
    """รวมสถิติจากไม้ที่มี + เสริมด้วย metrics ทางการจาก MetaStats"""
    metrics = metrics or {}

    if df.empty:
        base = dict.fromkeys(
            [
                "n", "wins", "losses", "win_rate", "net", "gross_win", "gross_loss",
                "profit_factor", "expectancy", "avg_win", "avg_loss", "payoff",
                "best", "worst", "max_dd", "max_dd_pct", "costs",
                "streak_win", "streak_loss", "avg_duration", "total_volume",
            ],
            0.0,
        )
    else:
        wins = df[df["net"] > 0]
        losses = df[df["net"] < 0]
        gw = _safe(wins["net"].sum())
        gl = abs(_safe(losses["net"].sum()))

        eq = df.sort_values("close_time")["net"].cumsum()
        peak = eq.cummax()
        dd = _safe((eq - peak).min())

        seq = df.sort_values("close_time")["net"].tolist()
        sw = sl = cw = cl = 0
        for v in seq:
            if v > 0:
                cw, cl = cw + 1, 0
            elif v < 0:
                cl, cw = cl + 1, 0
            sw, sl = max(sw, cw), max(sl, cl)

        n = len(df)
        aw = _safe(wins["net"].mean()) if len(wins) else 0.0
        al = _safe(losses["net"].mean()) if len(losses) else 0.0

        base = {
            "n": n,
            "wins": len(wins),
            "losses": len(losses),
            "win_rate": (len(wins) / n * 100) if n else 0.0,
            "net": _safe(df["net"].sum()),
            "gross_win": gw,
            "gross_loss": gl,
            "profit_factor": (gw / gl) if gl > 0 else (float("inf") if gw > 0 else 0.0),
            "expectancy": _safe(df["net"].mean()),
            "avg_win": aw,
            "avg_loss": al,
            "payoff": (abs(aw / al) if al else 0.0),
            "best": _safe(df["net"].max()),
            "worst": _safe(df["net"].min()),
            "max_dd": dd,
            "max_dd_pct": 0.0,
            "costs": _safe(df["costs"].sum()) if "costs" in df else 0.0,
            "streak_win": sw,
            "streak_loss": sl,
            "avg_duration": _safe(df["duration_min"].mean()),
            "total_volume": _safe(df["volume"].sum()),
        }

    # ทับด้วยค่าทางการจาก MetaStats เมื่อมี
    base["balance"] = _safe(metrics.get("balance"))
    base["equity"] = _safe(metrics.get("equity"))
    base["deposits"] = _safe(metrics.get("deposits"))
    base["withdrawals"] = _safe(metrics.get("withdrawals"))
    base["cagr"] = _safe(metrics.get("cagr"))
    base["sharpe"] = _safe(metrics.get("sharpeRatio"))
    base["sortino"] = _safe(metrics.get("sortinoRatio"))
    base["risk_of_ruin"] = _safe(metrics.get("riskOfRuin"))
    base["expectancy_pips"] = _safe(metrics.get("expectancyPips"))
    base["gain_pct"] = _safe(metrics.get("gain"))
    base["absolute_gain"] = _safe(metrics.get("absoluteGain"))
    base["monthly_gain"] = _safe(metrics.get("monthlyGain"))
    base["daily_gain"] = _safe(metrics.get("dailyGain"))
    base["lots"] = _safe(metrics.get("lots"), base.get("total_volume", 0.0))

    if metrics.get("maxDrawdown") is not None:
        base["max_dd_pct"] = _safe(metrics.get("maxDrawdown"))
    if metrics.get("profitFactor"):
        base["profit_factor"] = _safe(metrics.get("profitFactor"), base["profit_factor"])

    return base


def by_group(df: pd.DataFrame, key: str, label: str | None = None) -> pd.DataFrame:
    if df.empty or key not in df.columns:
        return pd.DataFrame()

    g = (
        df.groupby(key)
        .agg(
            Trades=("trade_id", "count"),
            Wins=("is_win", "sum"),
            Net=("net", "sum"),
            AvgNet=("net", "mean"),
            Volume=("volume", "sum"),
        )
        .reset_index()
    )
    g["WinRate"] = (g["Wins"] / g["Trades"] * 100).round(1)
    g["Net"] = g["Net"].round(2)
    g["AvgNet"] = g["AvgNet"].round(2)
    g["Volume"] = g["Volume"].round(2)
    g = g.rename(columns={key: label or key})
    return g.sort_values("Net", ascending=False).reset_index(drop=True)


def plan_discipline(df: pd.DataFrame) -> pd.DataFrame:
    """ตารางชี้ขาด: ไม้ตามแผน vs นอกแผน"""
    if df.empty or "followed_plan" not in df.columns:
        return pd.DataFrame()

    d = df.copy()
    d["ประเภท"] = d["followed_plan"].map({1: "ตามแผน", 0: "นอกแผน"}).fillna("ตามแผน")
    g = (
        d.groupby("ประเภท")
        .agg(Trades=("trade_id", "count"), Wins=("is_win", "sum"), Net=("net", "sum"))
        .reset_index()
    )
    g["WinRate"] = (g["Wins"] / g["Trades"] * 100).round(1)
    g["Net"] = g["Net"].round(2)
    return g


def equity_series(df: pd.DataFrame, start_balance: float = 0.0) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=["time", "equity", "drawdown", "dd_pct"])

    d = df.sort_values("close_time").copy()
    d["equity"] = d["net"].cumsum() + start_balance
    d["peak"] = d["equity"].cummax()
    d["drawdown"] = d["equity"] - d["peak"]
    d["dd_pct"] = np.where(d["peak"] != 0, d["drawdown"] / d["peak"] * 100, 0.0)
    return d[["close_time", "equity", "drawdown", "dd_pct"]].rename(
        columns={"close_time": "time"}
    )


def monthly_table(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty or "month" not in df.columns:
        return pd.DataFrame()
    g = (
        df.groupby("month")
        .agg(Trades=("trade_id", "count"), Wins=("is_win", "sum"), Net=("net", "sum"))
        .reset_index()
    )
    g["WinRate"] = (g["Wins"] / g["Trades"] * 100).round(1)
    g["Net"] = g["Net"].round(2)
    g["Cumulative"] = g["Net"].cumsum().round(2)
    return g.sort_values("month")