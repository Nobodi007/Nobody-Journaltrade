"""ค่าคงที่ + การอ่าน secrets"""

from __future__ import annotations

import os

import streamlit as st

APP_NAME = "Nobody Trade Journal"
APP_VERSION = "3.0.0"

SETUPS = [
    "Breakout", "Pullback", "Reversal", "Range", "Trend Follow",
    "News Play", "Scalp", "Swing", "Other",
]
TIMEFRAMES = ["M1", "M5", "M15", "M30", "H1", "H4", "D1", "W1"]
EMOTIONS = [
    "Calm", "Confident", "FOMO", "Fear", "Greed",
    "Revenge", "Bored", "Impatient", "Tilted",
]
MISTAKES = [
    "No Stop Loss", "Moved Stop", "Oversized", "Entered Early",
    "Entered Late", "Exited Early", "Held Too Long", "Revenge Trade",
    "Overtrading", "Ignored Plan",
]


def secret(key: str, default: str = "") -> str:
    """อ่านจาก st.secrets ก่อน แล้วค่อย env"""
    try:
        val = st.secrets.get(key)
        if val:
            return str(val)
    except Exception:
        pass
    return os.getenv(key, default)
