"""แปลงข้อมูลดิบจาก MetaApi/MetaStats เป็น DataFrame ที่ใช้งานได้"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

# เวลาที่ใช้แสดงผล (hour / weekday / date / month) — เปลี่ยนได้
DISPLAY_TZ = "Asia/Bangkok"

# ถ้า profit จาก MetaStats ยังไม่รวม commission/swap ให้ตั้งเป็น False
# (เทียบไม้จริง 1-2 ไม้กับ MT5 เพื่อยืนยัน)
METASTATS_PROFIT_INCLUDES_COSTS = True

TRADE_COLS = [
    "trade_id", "symbol", "direction", "volume",
    "open_time", "close_time", "open_price", "close_price",
    "profit", "gain", "pips", "commission", "swap", "net",
    "duration_min", "success", "magic", "risk_pct", "type_raw",
]
DERIVED_COLS = ["is_win", "is_loss", "costs", "date", "hour", "weekday", "month"]


def _empty() -> pd.DataFrame:
    return pd.DataFrame(columns=TRADE_COLS + DERIVED_COLS)


def _num(v: Any, default: float = 0.0) -> float:
    try:
        if v is None:
            return default
        f = float(v)
        return default if np.isnan(f) else f
    except (TypeError, ValueError):
        return default


def _direction(t: str) -> str:
    t = (t or "").upper()
    if "SELL" in t:
        return "Short"
    if "BUY" in t:
        return "Long"
    return "—"


def _col_sum(g: pd.DataFrame, col: str) -> float:
    if col not in g.columns:
        return 0.0
    return float(pd.to_numeric(g[col], errors="coerce").fillna(0).sum())


def _finish(df: pd.DataFrame) -> pd.DataFrame:
    """เติมคอลัมน์อนุพันธ์ให้เหมือนกันทั้งสองเส้นทาง"""
    df = df.dropna(subset=["close_time"]).copy()
    if df.empty:
        return _empty()

    df["is_win"] = df["net"] > 0
    df["is_loss"] = df["net"] < 0
    df["costs"] = df["commission"].abs() + df["swap"].abs()

    local = df["close_time"].dt.tz_convert(DISPLAY_TZ)
    df["date"] = local.dt.date
    df["hour"] = local.dt.hour
    df["weekday"] = local.dt.day_name()
    df["month"] = local.dt.strftime("%Y-%m")

    return df.sort_values("close_time", ascending=False).reset_index(drop=True)


def metastats_trades_to_df(trades: list[dict[str, Any]]) -> pd.DataFrame:
    """แปลงผลจาก MetaStats historical-trades"""
    if not trades:
        return _empty()

    rows = []
    for t in trades:
        profit = _num(t.get("profit"))
        comm = _num(t.get("commissions"))
        swap = _num(t.get("swap"))
        net = profit if METASTATS_PROFIT_INCLUDES_COSTS else profit + comm + swap

        rows.append({
            "trade_id": str(t.get("_id") or t.get("id") or ""),
            "symbol": t.get("symbol") or "—",
            "direction": _direction(t.get("type")),
            "type_raw": t.get("type") or "",
            "volume": _num(t.get("volume")),
            "open_time": t.get("openTime"),
            "close_time": t.get("closeTime"),
            "open_price": _num(t.get("openPrice")),
            "close_price": _num(t.get("closePrice")),
            "profit": profit,
            "gain": _num(t.get("gain")),
            "pips": _num(t.get("pips")),
            "commission": comm,
            "swap": swap,
            "net": net,
            "duration_min": _num(t.get("durationInMinutes")),
            "success": (t.get("success") or "").lower(),
            "magic": int(_num(t.get("magic"))),
            "risk_pct": _num(t.get("riskInBalancePercent")),
        })

    df = pd.DataFrame(rows)
    for c in ("open_time", "close_time"):
        df[c] = pd.to_datetime(df[c], errors="coerce", utc=True)
    return _finish(df)


def positions_to_df(positions: list[dict[str, Any]]) -> pd.DataFrame:
    """ไม้ที่ยังเปิดอยู่จาก Client API"""
    if not positions:
        return pd.DataFrame()

    rows = []
    for p in positions:
        rows.append({
            "trade_id": str(p.get("id") or ""),
            "symbol": p.get("symbol"),
            "direction": _direction(p.get("type")),
            "volume": _num(p.get("volume")),
            "open_price": _num(p.get("openPrice")),
            "current_price": _num(p.get("currentPrice")),
            "stop_loss": _num(p.get("stopLoss")),
            "take_profit": _num(p.get("takeProfit")),
            "profit": _num(p.get("profit")),
            "unrealized": _num(p.get("unrealizedProfit"), _num(p.get("profit"))),
            "swap": _num(p.get("swap")),
            "commission": _num(p.get("commission")),
            "open_time": p.get("time"),
            "magic": int(_num(p.get("magic"))),
            "comment": p.get("comment") or "",
        })

    df = pd.DataFrame(rows)
    df["open_time"] = pd.to_datetime(df["open_time"], errors="coerce", utc=True)
    return df.sort_values("open_time", ascending=False).reset_index(drop=True)


def deals_to_trades(deals: list[dict[str, Any]]) -> pd.DataFrame:
    """
    สำรอง: ประกอบไม้จาก deals ดิบเอง เผื่อ MetaStats ยังไม่พร้อม
    MT5 เก็บเป็น deal แยกเข้า/ออก ต้องจับกลุ่มด้วย positionId
    """
    if not deals:
        return _empty()

    df = pd.DataFrame(deals)
    if "positionId" not in df.columns or "entryType" not in df.columns:
        return _empty()

    df["time"] = pd.to_datetime(df.get("time"), errors="coerce", utc=True)
    for c in ("price", "volume"):
        df[c] = pd.to_numeric(df.get(c), errors="coerce").fillna(0.0)
    df = df[df["positionId"].notna() & (df["positionId"].astype(str) != "")]

    rows = []
    for pid, g in df.groupby("positionId"):
        g = g.sort_values("time")
        ins = g[g["entryType"].isin(["DEAL_ENTRY_IN", "DEAL_ENTRY_INOUT"])]
        outs = g[g["entryType"].isin(
            ["DEAL_ENTRY_OUT", "DEAL_ENTRY_OUT_BY", "DEAL_ENTRY_INOUT"]
        )]
        # ข้ามไม้ที่ยังไม่ปิด
        if ins.empty or outs.empty:
            continue

        first = ins.iloc[0]
        vin = float(ins["volume"].sum())
        open_px = (
            float((ins["price"] * ins["volume"]).sum() / vin) if vin else _num(first["price"])
        )

        vout = float(outs["volume"].sum())
        close_px = float((outs["price"] * outs["volume"]).sum() / vout) if vout else np.nan
        close_t = outs.iloc[-1]["time"]

        profit = _col_sum(g, "profit")
        comm = _col_sum(g, "commission")
        swap = _col_sum(g, "swap")
        net = profit + comm + swap

        dur = np.nan
        if pd.notna(close_t) and pd.notna(first["time"]):
            dur = (close_t - first["time"]).total_seconds() / 60

        rows.append({
            "trade_id": str(pid),
            "symbol": first.get("symbol") or "—",
            "direction": _direction(first.get("type")),
            "type_raw": first.get("type") or "",
            "volume": vin,
            "open_time": first["time"],
            "close_time": close_t,
            "open_price": open_px,
            "close_price": close_px,
            "profit": profit,
            "gain": 0.0,
            "pips": 0.0,
            "commission": comm,
            "swap": swap,
            "net": net,
            "duration_min": dur,
            "success": "won" if net > 0 else "lost",
            "magic": int(_num(first.get("magic"))),
            "risk_pct": 0.0,
        })

    if not rows:
        return _empty()
    return _finish(pd.DataFrame(rows))
