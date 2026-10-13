"""
โน้ตประกอบแต่ละไม้ (setup / อารมณ์ / ข้อผิดพลาด / บทเรียน) เก็บใน Supabase ตาราง trade_notes
สร้างตารางด้วย supabase/trade_notes.sql ก่อนใช้งาน
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

import requests
import streamlit as st

from core.config import secret

TABLE = "trade_notes"

EMPTY_NOTE = {
    "setup": "", "timeframe": "", "confidence": 3,
    "emotion_in": "", "emotion_out": "", "followed_plan": 1,
    "mistakes": "[]", "thesis": "", "lesson": "",
    "tags": "", "screenshot_url": "",
}


def _cfg() -> tuple[str, str]:
    return secret("SUPABASE_URL").strip().rstrip("/"), secret("SUPABASE_KEY").strip()


def _headers(key: str, extra: dict | None = None) -> dict:
    h = {"apikey": key, "Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    h.update(extra or {})
    return h


def parse_mistakes(raw) -> list[str]:
    if isinstance(raw, list):
        return [str(x) for x in raw]
    try:
        v = json.loads(raw or "[]")
        return [str(x) for x in v] if isinstance(v, list) else []
    except (TypeError, ValueError):
        return []


@st.cache_data(ttl=10, show_spinner=False)
def load_notes(account_id: str) -> tuple[dict, str]:
    """คืน ({trade_id: note}, error)"""
    url, key = _cfg()
    if not url or not key:
        return {}, "ยังไม่ได้ตั้งค่า SUPABASE_URL / SUPABASE_KEY"
    try:
        r = requests.get(
            f"{url}/rest/v1/{TABLE}",
            headers=_headers(key),
            params={"select": "*", "account_id": f"eq.{account_id}", "limit": "5000"},
            timeout=15,
        )
        if r.status_code == 404:
            return {}, "missing_table"
        r.raise_for_status()
        return {str(n["trade_id"]): n for n in r.json()}, ""
    except Exception as exc:  # noqa: BLE001
        return {}, str(exc)


def save_note(trade_id: str, account_id: str, **fields) -> tuple[bool, str]:
    url, key = _cfg()
    if not url or not key:
        return False, "ยังไม่ได้ตั้งค่า Supabase"
    payload = {**EMPTY_NOTE, **fields}
    if isinstance(payload["mistakes"], list):
        payload["mistakes"] = json.dumps(payload["mistakes"], ensure_ascii=False)
    payload["confidence"] = int(payload.get("confidence") or 3)
    payload["followed_plan"] = int(bool(payload.get("followed_plan")))
    payload["trade_id"] = str(trade_id)
    payload["account_id"] = str(account_id)
    payload["updated_at"] = datetime.now(timezone.utc).isoformat()
    try:
        r = requests.post(
            f"{url}/rest/v1/{TABLE}?on_conflict=trade_id,account_id",
            headers=_headers(key, {"Prefer": "resolution=merge-duplicates,return=minimal"}),
            json=payload,
            timeout=15,
        )
        if r.ok:
            load_notes.clear()
            return True, "บันทึกแล้ว"
        return False, f"บันทึกไม่สำเร็จ [{r.status_code}] {r.text[:200]}"
    except Exception as exc:  # noqa: BLE001
        return False, f"บันทึกไม่สำเร็จ: {exc}"
