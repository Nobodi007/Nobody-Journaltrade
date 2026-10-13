"""อ่านข้อมูล MT5 ที่ NobodyCollector ส่งขึ้น Supabase (อ่านอย่างเดียว)"""

from __future__ import annotations

import pandas as pd
import requests
import streamlit as st

from core.config import secret

PAGE = 1000          # PostgREST ส่งได้สูงสุด ~1000 แถวต่อครั้ง
MAX_HISTORY = 20000  # เพดานจำนวน deal ที่ดึงมาคำนวณ


def supabase_config() -> tuple[str, str]:
    return (
        secret("SUPABASE_URL").strip().rstrip("/"),
        secret("SUPABASE_KEY").strip(),
    )


def _headers(key: str) -> dict:
    return {"apikey": key, "Authorization": f"Bearer {key}", "Accept": "application/json"}


@st.cache_data(ttl=15, show_spinner=False)
def _fetch(table: str, params: tuple, max_rows: int) -> tuple[list[dict], str]:
    """ดึงตารางแบบแบ่งหน้า คืน (rows, error) — error เป็น '' ถ้าสำเร็จ"""
    url, key = supabase_config()
    if not url or not key:
        return [], "ยังไม่ได้ตั้งค่า SUPABASE_URL / SUPABASE_KEY"
    rows: list[dict] = []
    offset = 0
    try:
        while offset < max_rows:
            limit = min(PAGE, max_rows - offset)
            r = requests.get(
                f"{url}/rest/v1/{table}",
                headers=_headers(key),
                params=[("select", "*"), *params, ("limit", str(limit)), ("offset", str(offset))],
                timeout=15,
            )
            r.raise_for_status()
            chunk = r.json()
            if not isinstance(chunk, list):
                return rows, f"{table}: รูปแบบข้อมูลไม่ถูกต้อง"
            rows.extend(chunk)
            if len(chunk) < limit:
                break
            offset += limit
    except Exception as exc:  # noqa: BLE001 - แสดงให้ผู้ใช้เห็นแทนที่จะล่ม
        return rows, f"{table}: {exc}"
    return rows, ""


def _account_params(snapshot: dict) -> tuple:
    out = []
    if snapshot.get("login") not in (None, ""):
        out.append(("login", f"eq.{snapshot['login']}"))
    if snapshot.get("server") not in (None, ""):
        out.append(("server", f"eq.{snapshot['server']}"))
    return tuple(out)


def load_snapshot() -> tuple[dict, str]:
    rows, err = _fetch("mt5_account_snapshots", (("order", "collected_at.desc"),), 1)
    return (rows[0] if rows else {}), err


def load_positions(snapshot: dict) -> tuple[pd.DataFrame, str]:
    rows, err = _fetch("mt5_positions", _account_params(snapshot), 500)
    return pd.DataFrame(rows), err


def load_pending(snapshot: dict) -> tuple[pd.DataFrame, str]:
    rows, err = _fetch("mt5_pending_orders", _account_params(snapshot), 500)
    return pd.DataFrame(rows), err


def load_history(snapshot: dict) -> tuple[pd.DataFrame, str]:
    params = _account_params(snapshot) + (("order", "deal_time.asc,deal_ticket.asc"),)
    rows, err = _fetch("mt5_trade_history", params, MAX_HISTORY)
    return pd.DataFrame(rows), err


def clear_cache() -> None:
    _fetch.clear()
