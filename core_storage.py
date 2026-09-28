"""
เก็บ journal annotation (setup / อารมณ์ / บทเรียน) ที่ MT5 ไม่มีให้
Supabase = ถาวร | SQLite = ชั่วคราว (Streamlit Cloud รีเซ็ตเมื่อ restart)
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
import requests

from core.config import secret

DB_PATH = Path("journal_notes.db")

TABLE = "trade_notes"

SCHEMA = f"""
CREATE TABLE IF NOT EXISTS {TABLE} (
    trade_id TEXT NOT NULL,
    account_id TEXT NOT NULL,
    setup TEXT DEFAULT '',
    timeframe TEXT DEFAULT '',
    confidence INTEGER DEFAULT 3,
    emotion_in TEXT DEFAULT '',
    emotion_out TEXT DEFAULT '',
    followed_plan INTEGER DEFAULT 1,
    mistakes TEXT DEFAULT '[]',
    thesis TEXT DEFAULT '',
    lesson TEXT DEFAULT '',
    tags TEXT DEFAULT '',
    screenshot_url TEXT DEFAULT '',
    updated_at TEXT,
    PRIMARY KEY (trade_id, account_id)
);
"""

EMPTY_NOTE: dict[str, Any] = {
    "setup": "", "timeframe": "", "confidence": 3,
    "emotion_in": "", "emotion_out": "", "followed_plan": 1,
    "mistakes": "[]", "thesis": "", "lesson": "",
    "tags": "", "screenshot_url": "",
}


class NoteStore:
    """เลือก backend อัตโนมัติ"""

    def __init__(self) -> None:
        self.url = secret("SUPABASE_URL").rstrip("/")
        self.key = secret("SUPABASE_KEY")
        self.remote = bool(self.url and self.key)

        if self.remote:
            self.h = {
                "apikey": self.key,
                "Authorization": f"Bearer {self.key}",
                "Content-Type": "application/json",
                "Prefer": "resolution=merge-duplicates,return=minimal",
            }
        else:
            with closing(sqlite3.connect(DB_PATH)) as c:
                c.executescript(SCHEMA)
                c.commit()

    @property
    def backend(self) -> str:
        return "Supabase" if self.remote else "SQLite (ชั่วคราว)"

    # ---------- read ----------

    def load(self, account_id: str) -> pd.DataFrame:
        if self.remote:
            try:
                r = requests.get(
                    f"{self.url}/rest/v1/{TABLE}",
                    headers=self.h,
                    params={"select": "*", "account_id": f"eq.{account_id}"},
                    timeout=20,
                )
                r.raise_for_status()
                return pd.DataFrame(r.json())
            except Exception:
                return pd.DataFrame()

        with closing(sqlite3.connect(DB_PATH)) as c:
            return pd.read_sql_query(
                f"SELECT * FROM {TABLE} WHERE account_id=?", c, params=(account_id,)
            )

    def get(self, trade_id: str, account_id: str) -> dict[str, Any]:
        df = self.load(account_id)
        if df.empty or "trade_id" not in df.columns:
            return dict(EMPTY_NOTE)
        row = df[df["trade_id"] == trade_id]
        if row.empty:
            return dict(EMPTY_NOTE)
        return {**EMPTY_NOTE, **row.iloc[0].to_dict()}

    # ---------- write ----------

    def save(self, trade_id: str, account_id: str, **fields: Any) -> bool:
        payload = {
            **EMPTY_NOTE,
            **fields,
            "trade_id": str(trade_id),
            "account_id": str(account_id),
            "updated_at": datetime.utcnow().isoformat(),
        }
        if isinstance(payload.get("mistakes"), list):
            payload["mistakes"] = json.dumps(payload["mistakes"], ensure_ascii=False)
        payload["confidence"] = int(payload.get("confidence") or 3)
        payload["followed_plan"] = int(bool(payload.get("followed_plan")))

        if self.remote:
            try:
                r = requests.post(
                    f"{self.url}/rest/v1/{TABLE}",
                    headers={**self.h, "Prefer": "resolution=merge-duplicates"},
                    json=payload,
                    timeout=20,
                )
                return r.ok
            except Exception:
                return False

        cols = ",".join(payload)
        ph = ",".join("?" * len(payload))
        with closing(sqlite3.connect(DB_PATH)) as c:
            c.execute(
                f"INSERT OR REPLACE INTO {TABLE} ({cols}) VALUES ({ph})",
                tuple(payload.values()),
            )
            c.commit()
        return True


def merge_notes(trades: pd.DataFrame, notes: pd.DataFrame) -> pd.DataFrame:
    """รวม note เข้ากับไม้ โดยไม่ทับข้อมูลจากโบรก"""
    if trades.empty:
        return trades

    out = trades.copy()
    if notes.empty or "trade_id" not in notes.columns:
        for k, v in EMPTY_NOTE.items():
            out[k] = v
        out["has_note"] = False
        return out

    keep = ["trade_id"] + [c for c in EMPTY_NOTE if c in notes.columns]
    out = out.merge(notes[keep], on="trade_id", how="left")

    for k, v in EMPTY_NOTE.items():
        if k not in out.columns:
            out[k] = v
        else:
            out[k] = out[k].fillna(v)

    out["has_note"] = out["thesis"].astype(str).str.len().gt(0) | out[
        "setup"
    ].astype(str).str.len().gt(0)
    out["followed_plan"] = out["followed_plan"].fillna(1).astype(int)
    return out
