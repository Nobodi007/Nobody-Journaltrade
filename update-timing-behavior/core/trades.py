"""
ตัวคำนวณสถิติเทรด (pandas ล้วน ไม่พึ่ง Streamlit)

ข้อมูลเข้า: ตาราง mt5_trade_history (1 แถว = 1 deal) ที่ NobodyCollector ส่งขึ้น Supabase
ข้อมูลออก: 1 แถว = 1 position ที่ปิดแล้ว (รวมทุก deal ของ position เดียวกัน)

เวลาทั้งหมดเป็น "เวลาเซิร์ฟเวอร์โบรกเกอร์" ตามที่ MT5 แสดง (EA ส่งมาแบบไม่มี timezone)
"""

from __future__ import annotations

import numpy as np
import pandas as pd

WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
_NUM_DEAL = ("volume", "price", "profit", "commission", "swap", "fee")
_OUT = {"OUT", "OUT_BY", "INOUT"}
_SIDES = {
    "BUY": "BUY", "DEAL_TYPE_BUY": "BUY",
    "SELL": "SELL", "DEAL_TYPE_SELL": "SELL",
}

TRADE_COLUMNS = [
    "trade_id", "position_id", "symbol", "direction", "volume",
    "open_time", "close_time", "entry_price", "exit_price",
    "gross", "costs", "net", "result", "duration_min", "deals",
    "entry_time", "weekday", "hour", "close_date",
]


def empty_trades() -> pd.DataFrame:
    return pd.DataFrame({c: pd.Series(dtype="object") for c in TRADE_COLUMNS})


# ---------------------------------------------------------------- deals -> trades

def normalize_history(history: pd.DataFrame | None) -> pd.DataFrame:
    """แปลงชนิดข้อมูล + กรองเหลือเฉพาะ deal ซื้อ/ขายจริง (ตัด balance/credit/charge)"""
    if history is None or history.empty:
        return pd.DataFrame()
    w = history.copy()
    for c in _NUM_DEAL:
        w[c] = pd.to_numeric(w[c], errors="coerce").fillna(0.0) if c in w else 0.0
    for c in ("position_id", "deal_ticket"):
        w[c] = pd.to_numeric(w[c], errors="coerce").fillna(0).astype("int64") if c in w else 0
    w["deal_time"] = (
        pd.to_datetime(w["deal_time"], errors="coerce", utc=True).dt.tz_localize(None)
        if "deal_time" in w else pd.NaT
    )
    w["symbol"] = w["symbol"].fillna("").astype(str).str.upper() if "symbol" in w else ""
    w["entry_type"] = w["entry_type"].fillna("").astype(str).str.upper() if "entry_type" in w else ""
    dt = w["deal_type"].fillna("").astype(str).str.upper() if "deal_type" in w else ""
    w["side"] = dt.map(_SIDES) if hasattr(dt, "map") else None
    w = w[w["side"].notna() & w["deal_time"].notna()].copy()
    return w.sort_values(["deal_time", "deal_ticket"]).reset_index(drop=True)


def _vwap(g: pd.DataFrame) -> float:
    vol = g["volume"].sum()
    if g.empty or vol <= 0:
        return float("nan")
    return float((g["price"] * g["volume"]).sum() / vol)


def build_trades(history: pd.DataFrame | None) -> pd.DataFrame:
    """รวม deal -> trade (1 position = 1 แถว) เฉพาะ position ที่ปิดครบแล้ว"""
    w = normalize_history(history)
    if w.empty:
        return empty_trades()

    w["_pid"] = w["position_id"].where(w["position_id"] != 0, w["deal_ticket"])
    rows = []
    for pid, g in w.groupby("_pid", sort=False):
        ins = g[g["entry_type"] == "IN"]
        outs = g[g["entry_type"].isin(_OUT)]
        if outs.empty:
            continue  # ยังเปิดอยู่
        in_vol, out_vol = ins["volume"].sum(), outs["volume"].sum()
        if in_vol > 0 and out_vol < in_vol - 1e-9:
            continue  # ปิดบางส่วน ยังไม่ครบ

        if not ins.empty:
            direction = "LONG" if ins.iloc[0]["side"] == "BUY" else "SHORT"
        else:  # entry อยู่นอกช่วงข้อมูล -> เดาจากฝั่งที่ปิด
            direction = "LONG" if outs.iloc[0]["side"] == "SELL" else "SHORT"

        gross = float(g["profit"].sum())
        costs = float(g["commission"].sum() + g["swap"].sum() + g["fee"].sum())
        open_time = ins["deal_time"].min() if not ins.empty else pd.NaT
        close_time = outs["deal_time"].max()
        rows.append({
            "trade_id": str(int(pid)),
            "position_id": int(pid),
            "symbol": outs.iloc[-1]["symbol"] or g.iloc[0]["symbol"],
            "direction": direction,
            "volume": float(in_vol if in_vol > 0 else out_vol),
            "open_time": open_time,
            "close_time": close_time,
            "entry_price": _vwap(ins),
            "exit_price": _vwap(outs),
            "gross": gross,
            "costs": costs,
            "net": gross + costs,
            "deals": int(len(g)),
        })

    if not rows:
        return empty_trades()

    t = pd.DataFrame(rows)
    t["open_time"] = pd.to_datetime(t["open_time"])
    t["close_time"] = pd.to_datetime(t["close_time"])
    net2 = t["net"].round(2)
    t["result"] = np.where(net2 > 0, "Win", np.where(net2 < 0, "Loss", "BE"))
    t["duration_min"] = (t["close_time"] - t["open_time"]).dt.total_seconds() / 60.0
    t["entry_time"] = t["open_time"].fillna(t["close_time"])
    t["weekday"] = t["entry_time"].dt.dayofweek.map(lambda i: WEEKDAYS[int(i)])
    t["hour"] = t["entry_time"].dt.hour
    t["close_date"] = t["close_time"].dt.normalize()
    return t.sort_values("close_time").reset_index(drop=True)[TRADE_COLUMNS]


# ---------------------------------------------------------------- statistics

def _streaks(results: list[str]) -> tuple[int, int]:
    best_w = best_l = cur_w = cur_l = 0
    for r in results:
        if r == "Win":
            cur_w, cur_l = cur_w + 1, 0
        elif r == "Loss":
            cur_l, cur_w = cur_l + 1, 0
        else:
            cur_w = cur_l = 0
        best_w, best_l = max(best_w, cur_w), max(best_l, cur_l)
    return best_w, best_l


def equity_curve(trades: pd.DataFrame, start_capital: float = 0.0) -> pd.DataFrame:
    """เส้น equity ตามลำดับเวลาปิดไม้ (realized only)"""
    if trades.empty:
        return pd.DataFrame(columns=["time", "pnl", "cum", "equity", "peak", "dd", "dd_pct"])
    t = trades.sort_values("close_time")
    cum = t["net"].cumsum().to_numpy()
    equity = start_capital + cum
    peak = np.maximum.accumulate(np.maximum(equity, start_capital))
    dd = equity - peak
    base = np.where(peak > 0, peak, np.nan)
    return pd.DataFrame({
        "time": t["close_time"].to_numpy(),
        "pnl": t["net"].to_numpy(),
        "cum": cum,
        "equity": equity,
        "peak": peak,
        "dd": dd,
        "dd_pct": dd / base * 100.0,
    })


def kpis(trades: pd.DataFrame, start_capital: float = 0.0) -> dict:
    """ตัวเลขสรุปทั้งหมดที่หน้า Performance/Overview ใช้"""
    n = len(trades)
    out = {
        "trades": n, "wins": 0, "losses": 0, "be": 0,
        "win_rate": None, "net": 0.0, "gross_profit": 0.0, "gross_loss": 0.0,
        "profit_factor": None, "avg_win": None, "avg_loss": None, "payoff": None,
        "expectancy": None, "best": None, "worst": None,
        "max_win_streak": 0, "max_loss_streak": 0,
        "max_dd": 0.0, "max_dd_pct": None, "avg_duration_min": None, "costs": 0.0,
    }
    if n == 0:
        return out

    net = t_net = trades["net"].astype(float)
    wins = net[trades["result"] == "Win"]
    losses = net[trades["result"] == "Loss"]
    out.update(
        wins=int(len(wins)), losses=int(len(losses)), be=int((trades["result"] == "BE").sum()),
        net=float(t_net.sum()), gross_profit=float(wins.sum()), gross_loss=float(losses.sum()),
        expectancy=float(net.mean()), best=float(net.max()), worst=float(net.min()),
        costs=float(trades["costs"].sum()),
    )
    decisive = len(wins) + len(losses)
    if decisive:
        out["win_rate"] = len(wins) / decisive * 100.0
    if len(losses) and losses.sum() != 0:
        out["profit_factor"] = float(wins.sum() / abs(losses.sum()))
    if len(wins):
        out["avg_win"] = float(wins.mean())
    if len(losses):
        out["avg_loss"] = float(losses.mean())
    if len(wins) and len(losses) and losses.mean() != 0:
        out["payoff"] = float(wins.mean() / abs(losses.mean()))
    out["max_win_streak"], out["max_loss_streak"] = _streaks(
        trades.sort_values("close_time")["result"].tolist()
    )
    curve = equity_curve(trades, start_capital)
    out["max_dd"] = float(curve["dd"].min())
    if start_capital > 0 and curve["dd_pct"].notna().any():
        out["max_dd_pct"] = float(curve["dd_pct"].min())
    dur = trades["duration_min"].dropna()
    if len(dur):
        out["avg_duration_min"] = float(dur.mean())
    return out


def daily_pnl(trades: pd.DataFrame) -> pd.Series:
    if trades.empty:
        return pd.Series(dtype=float)
    return trades.groupby("close_date")["net"].sum().sort_index()


def group_stats(trades: pd.DataFrame, col: str, order: list | None = None) -> pd.DataFrame:
    """ตารางสถิติแยกตามคอลัมน์ (symbol / direction / weekday / hour / setup ...)"""
    cols = [col, "Trades", "Win rate %", "Net P&L", "Avg / trade", "Profit factor"]
    if trades.empty or col not in trades:
        return pd.DataFrame(columns=cols)
    rows = []
    for key, g in trades.groupby(col, dropna=True):
        k = kpis(g)
        rows.append({
            col: key, "Trades": k["trades"], "Win rate %": k["win_rate"],
            "Net P&L": k["net"], "Avg / trade": k["expectancy"],
            "Profit factor": k["profit_factor"],
        })
    df = pd.DataFrame(rows, columns=cols)
    if order is not None:
        df[col] = pd.Categorical(df[col], categories=order, ordered=True)
        return df.sort_values(col).reset_index(drop=True)
    return df.sort_values("Net P&L", ascending=False).reset_index(drop=True)


# ---------------------------------------------------------------- timing / behavior

HOLD_LABELS = ["<5m", "5–15m", "15–60m", "1–4h", "4–24h", ">1d"]
BLOCK_LABELS = ["00–06", "06–12", "12–18", "18–24"]
AFTER_LABELS = ["หลังไม้ชนะ", "หลังไม้แพ้"]
DAY_LABELS = ["1 ไม้/วัน", "2 ไม้/วัน", "3+ ไม้/วัน"]


def add_features(trades: pd.DataFrame) -> pd.DataFrame:
    """เพิ่มคอลัมน์สำหรับวิเคราะห์พฤติกรรม: ระยะถือ, ช่วงเวลา, ขนาดล็อต, ไม้ถัดจากชนะ/แพ้, จำนวนไม้ต่อวัน"""
    if trades.empty:
        return trades.copy()
    d = trades.sort_values("close_time").reset_index(drop=True).copy()
    d["hold"] = pd.cut(
        d["duration_min"], bins=[-0.001, 5, 15, 60, 240, 1440, np.inf], labels=HOLD_LABELS
    ).astype(object)
    d["block"] = pd.cut(
        d["hour"].astype(float), bins=[-1, 5, 11, 17, 23], labels=BLOCK_LABELS
    ).astype(object)
    d["lots"] = d["volume"].round(2).map(lambda v: f"{v:g} lot")
    d["after"] = d["result"].shift(1).map({"Win": AFTER_LABELS[0], "Loss": AFTER_LABELS[1]})
    n_day = d.groupby("close_date")["net"].transform("size")
    d["day_bucket"] = n_day.map(lambda n: DAY_LABELS[0] if n == 1 else (DAY_LABELS[1] if n == 2 else DAY_LABELS[2]))
    d["sym_dir"] = d["symbol"] + " " + d["direction"]
    return d


def heat_pivot(trades: pd.DataFrame, metric: str) -> pd.DataFrame:
    """ตาราง วัน × ชั่วโมง (metric = Trades / Win rate % / Net P&L)"""
    if trades.empty:
        return pd.DataFrame()
    keys = ["weekday", "hour"]
    if metric == "Net P&L":
        s = trades.groupby(keys)["net"].sum()
    elif metric == "Trades":
        s = trades.groupby(keys).size()
    else:
        dec = trades[trades["result"].isin(["Win", "Loss"])].groupby(keys).size()
        wins = trades[trades["result"] == "Win"].groupby(keys).size().reindex(dec.index, fill_value=0)
        s = wins / dec * 100.0
    days = [d for d in WEEKDAYS if d in set(s.index.get_level_values(0))]
    return s.unstack("hour").reindex(index=days, columns=range(24))


# ---------------------------------------------------------------- open positions

def positions_view(pos: pd.DataFrame | None) -> pd.DataFrame:
    if pos is None or pos.empty:
        return pd.DataFrame()
    w = pos.copy()
    for c in ("volume", "open_price", "current_price", "stop_loss", "take_profit",
              "profit", "swap", "commission"):
        w[c] = pd.to_numeric(w[c], errors="coerce").fillna(0.0) if c in w else 0.0
    w["symbol"] = w["symbol"].fillna("").astype(str).str.upper() if "symbol" in w else ""
    w["side"] = w["side"].fillna("").astype(str).str.upper() if "side" in w else ""
    w["open_time"] = (
        pd.to_datetime(w["open_time"], errors="coerce", utc=True).dt.tz_localize(None)
        if "open_time" in w else pd.NaT
    )
    w["floating"] = w["profit"] + w["swap"] + w["commission"]
    return w.sort_values("open_time").reset_index(drop=True)


def exposure_table(pos: pd.DataFrame) -> pd.DataFrame:
    """Lots ฝั่ง buy/sell + floating ต่อ symbol"""
    cols = ["symbol", "positions", "buy_lots", "sell_lots", "net_lots", "floating"]
    if pos.empty:
        return pd.DataFrame(columns=cols)
    w = pos.copy()
    w["buy_lots"] = w["volume"].where(w["side"] == "BUY", 0.0)
    w["sell_lots"] = w["volume"].where(w["side"] == "SELL", 0.0)
    g = w.groupby("symbol").agg(
        positions=("symbol", "size"), buy_lots=("buy_lots", "sum"),
        sell_lots=("sell_lots", "sum"), floating=("floating", "sum"),
    ).reset_index()
    g["net_lots"] = g["buy_lots"] - g["sell_lots"]
    return g[cols].sort_values("floating").reset_index(drop=True)
