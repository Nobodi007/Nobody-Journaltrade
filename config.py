"""ค่าคงที่และการอ่าน secrets"""

from __future__ import annotations

import os
from typing import Any

import streamlit as st

APP_NAME = "Nobody Trade Journal"
APP_VERSION = "2.0.0-cloud"

REGIONS = ["new-york", "london", "singapore"]

PROVISIONING_HOST = "https://mt-provisioning-api-v1.agiliumtrade.agiliumtrade.ai"
CLIENT_HOST_TPL = "https://mt-client-api-v1.{region}.agiliumtrade.ai"
METASTATS_HOST_TPL = "https://metastats-api-v1.{region}.agiliumtrade.ai"

HTTP_TIMEOUT = 45
MAX_RETRY = 6

SETUPS = [
    "Breakout", "Pullback", "Reversal", "Range", "Trend Follow",
    "News Play", "Scalp", "Swing", "Grid", "Algo", "Other",
]

EMOTIONS = [
    "Calm", "Confident", "FOMO", "Fear", "Greed",
    "Revenge", "Bored", "Impatient", "Tilted",
]

MISTAKES = [
    "No Stop Loss", "Moved Stop", "Oversized", "Entered Early",
    "Entered Late", "Exited Early", "Held Too Long", "Revenge Trade",
    "Overtrading", "Ignored Plan", "No Mistake",
]

TIMEFRAMES = ["M1", "M5", "M15", "M30", "H1", "H4", "D1", "W1"]


def secret(key: str, default: str = "") -> str:
    """อ่านจาก st.secrets ก่อน แล้วค่อย env"""
    try:
        val = st.secrets.get(key)
        if val:
            return str(val)
    except Exception:
        pass
    return os.getenv(key, default)


def get_token() -> str:
    return st.session_state.get("mapi_token") or secret("METAAPI_TOKEN")


def get_region() -> str:
    return st.session_state.get("mapi_region") or secret("METAAPI_REGION", "new-york")


CSS = """
<style>
    .block-container { padding: 1rem 1.2rem 4rem 1.2rem !important; max-width: 1500px !important; }
    [data-testid="stMetricValue"] { font-size: 1.45rem !important; }
    [data-testid="stMetricLabel"] { color: #848e9c !important; }
    .nj-card {
        background: #181a20; border: 1px solid #2b3139;
        border-radius: 12px; padding: 14px 16px; margin-bottom: 10px;
    }
    .nj-win  { border-left: 4px solid #0ecb81 !important; }
    .nj-loss { border-left: 4px solid #f6465d !important; }
    .nj-open { border-left: 4px solid #f0b90b !important; }
    .nj-tag {
        display: inline-block; padding: 2px 9px; margin: 2px 4px 2px 0;
        font-size: .72rem; font-weight: 600;
        background: #2b3139; color: #eaecef; border-radius: 999px;
    }
    .nj-muted { color: #848e9c; font-size: .78rem; }
    .nj-pos { color: #0ecb81; font-weight: 700; }
    .nj-neg { color: #f6465d; font-weight: 700; }
    .nj-pill {
        display:inline-block; padding:3px 12px; border-radius:999px;
        font-size:.74rem; font-weight:700;
    }
    .nj-live { background:#0ecb81; color:#0b0e11; }
    .nj-demo { background:#f0b90b; color:#0b0e11; }
</style>
"""