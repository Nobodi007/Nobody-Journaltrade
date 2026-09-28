"""สถิติและตารางสรุปจาก DataFrame ของไม้ที่ปิดแล้ว"""

from __future__ import annotations

import numpy as np
import pandas as pd

WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def _f(v, default: float = 0.0) -> float:
    try:
        f = float(v)
        return default if np.isnan(f) else f
    except (TypeError, ValueError):
        return default


def equity_series(df: pd.DataFrame, start_balance: float = 0.0) -> pd.DataFrame:
    """เส้น equity จากไม้ที่ปิด เรียงตามเวลาปิด"""
    if df.empty:
        return pd.DataFrame(columns=["time", "equity"])
    d = df.sort_values("close_time")
    eq = start_balance + d["net"].cumsum()
    out = pd.DataFrame({"time": d["close_time"].values, "equity": eq.values})
    first = pd.DataFrame({
        "time": [d["open_time"].min() if d["open_time"].notna().any() else d["close_time"].min()],
        "equity": [start_balance],
    })
    return pd.concat([first, out], ignore_index=True)


def _drawdown(eq: pd.DataFrame) -> tuple[float, float]:
    if eq.empty:
        return 0.0, 0.0
    s = eq["equity"].astype(float)
    peak = s.cummax()
    dd = peak - s
    max_dd = float(dd.max())
    pct = dd / peak.where(peak > 0)
    return max_dd, float(pct.max() * 100) if pct.notna().any() else 0.0


def summary(df: pd.DataFrame, metrics: dict | None = None) -> dict:
    m = metrics or {}
    n = len(df)
    balance = _f(m.get("balance"))
    equity = _f(m.get("equity"))

    if n == 0:
        return {
            "n": 0, "wins": 0, "losses": 0, "win_rate": 0.0, "net": 0.0,
            "profit_factor": 0.0, "expectancy": 0.0, "payoff": 0.0,
            "sharpe": 0.0, "costs": 0.0, "lots": 0.0,
            "max_dd": 0.0, "max_dd_pct": 0.0,
            "balance": balance, "equity": equity,
        }

    net = float(df["net"].sum())
    wins = int(df["is_win"].sum())
    losses = int(df["is_loss"].sum())
    gross_win = float(df.loc[df["net"] > 0, "net"].sum())
    gross_loss = abs(float(df.loc[df["net"] < 0, "net"].sum()))

    if gross_loss > 0:
        pf = gross_win / gross_loss
    else:
        pf = float("inf") if gross_win > 0 else 0.0

    avg_win = gross_win / wins if wins else 0.0
    avg_loss = gross_loss / losses if losses else 0.0
    payoff = avg_win / avg_loss if avg_loss else 0.0

    daily = df.groupby("date")["net"].sum()
    sd = daily.std(ddof=1) if len(daily) > 1 else 0.0
    sharpe = float(daily.mean() / sd * np.sqrt(252)) if sd and sd > 0 else 0.0

    start_bal = balance - net if balance else 0.0
    max_dd, max_dd_pct = _drawdown(equity_series(df, start_bal))

    return {
        "n": n, "wins": wins, "losses": losses,
        "win_rate": wins / n * 100,
        "net": net,
        "profit_factor": pf,
        "expectancy": net / n,
        "payoff": payoff,
        "sharpe": sharpe,
        "costs": float(df["costs"].sum()),
        "lots": float(df["volume"].sum()),
        "max_dd": max_dd, "max_dd_pct": max_dd_pct,
        "balance": balance, "equity": equity,
    }


def by_group(df: pd.DataFrame, col: str, label: str) -> pd.DataFrame:
    cols = [label, "ไม้", "Win %", "Net", "เฉลี่ย/ไม้", "Lots"]
    if df.empty or col not in df.columns:
        return pd.DataFrame(columns=cols)

    g = df.groupby(col).agg(
        n=("net", "size"),
        wins=("is_win", "sum"),
        net=("net", "sum"),
        avg=("net", "mean"),
        lots=("volume", "sum"),
    ).reset_index()
    g["Win %"] = (g["wins"] / g["n"] * 100).round(1)
    g = g.rename(columns={col: label, "n": "ไม้", "net": "Net", "avg": "เฉลี่ย/ไม้", "lots": "Lots"})
    g["Net"] = g["Net"].round(2)
    g["เฉลี่ย/ไม้"] = g["เฉลี่ย/ไม้"].round(2)
    g["Lots"] = g["Lots"].round(2)
    g = g[cols]

    if col == "weekday":
        g["_o"] = g[label].map({d: i for i, d in enumerate(WEEKDAYS)})
        return g.sort_values("_o").drop(columns="_o").reset_index(drop=True)
    return g.sort_values("Net", ascending=False).reset_index(drop=True)


def monthly_table(df: pd.DataFrame) -> pd.DataFrame:
    cols = ["เดือน", "ไม้", "Win %", "Net"]
    if df.empty:
        return pd.DataFrame(columns=cols)
    g = df.groupby("month").agg(
        n=("net", "size"), wins=("is_win", "sum"), net=("net", "sum")
    ).reset_index()
    g["Win %"] = (g["wins"] / g["n"] * 100).round(1)
    g = g.rename(columns={"month": "เดือน", "n": "ไม้", "net": "Net"})
    g["Net"] = g["Net"].round(2)
    return g[cols].sort_values("เดือน").reset_index(drop=True)


def plan_discipline(df: pd.DataFrame) -> pd.DataFrame:
    """เทียบไม้ตามแผน/นอกแผน (ต้องมีคอลัมน์ followed_plan จาก merge_notes)"""
    cols = ["ประเภท", "ไม้", "Win %", "Net", "เฉลี่ย/ไม้"]
    if df.empty or "followed_plan" not in df.columns:
        return pd.DataFrame(columns=cols)
    # นับเฉพาะไม้ที่มีโน้ต ไม่งั้นทุกไม้จะถูกนับเป็น "ตามแผน" โดยดีฟอลต์
    d = df[df.get("has_note", False) == True] if "has_note" in df.columns else df  # noqa: E712
    if d.empty:
        return pd.DataFrame(columns=cols)

    d = d.assign(ประเภท=np.where(d["followed_plan"].astype(int) == 1, "ตามแผน", "นอกแผน"))
    g = d.groupby("ประเภท").agg(
        n=("net", "size"), wins=("is_win", "sum"), net=("net", "sum"), avg=("net", "mean")
    ).reset_index()
    g["Win %"] = (g["wins"] / g["n"] * 100).round(1)
    g = g.rename(columns={"n": "ไม้", "net": "Net", "avg": "เฉลี่ย/ไม้"})
    g["Net"] = g["Net"].round(2)
    g["เฉลี่ย/ไม้"] = g["เฉลี่ย/ไม้"].round(2)
    return g[cols]
