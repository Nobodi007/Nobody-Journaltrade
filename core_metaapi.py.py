"""
MetaApi + MetaStats REST client
ใช้ requests ล้วน ไม่มี asyncio จึงรันบน Streamlit Cloud ได้ตรง ๆ
"""

from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from typing import Any

import requests

from core.config import (
    CLIENT_HOST_TPL,
    HTTP_TIMEOUT,
    MAX_RETRY,
    METASTATS_HOST_TPL,
    PROVISIONING_HOST,
)


class MetaApiError(RuntimeError):
    def __init__(self, status: int, message: str, payload: Any = None):
        super().__init__(f"[{status}] {message}")
        self.status = status
        self.message = message
        self.payload = payload


class MetaApiClient:
    """ครอบ 3 API: Provisioning, Client (MT terminal), MetaStats"""

    def __init__(self, token: str, region: str = "new-york"):
        if not token:
            raise MetaApiError(0, "ยังไม่ได้ตั้งค่า METAAPI_TOKEN")
        self.token = token.strip()
        self.region = region
        self.client_host = CLIENT_HOST_TPL.format(region=region)
        self.stats_host = METASTATS_HOST_TPL.format(region=region)

        self.s = requests.Session()
        self.s.headers.update({
            "auth-token": self.token,
            "Accept": "application/json",
            "Content-Type": "application/json",
        })

    # ---------- core ----------

    def _req(
        self,
        method: str,
        url: str,
        *,
        params: dict | None = None,
        json_body: dict | None = None,
        retry_202: bool = False,
    ) -> Any:
        """ยิง request พร้อมจัดการ 202 (กำลังคำนวณ) และ 429 (rate limit)"""
        attempt = 0
        while True:
            attempt += 1
            try:
                r = self.s.request(
                    method, url, params=params, json=json_body, timeout=HTTP_TIMEOUT
                )
            except requests.Timeout:
                if attempt >= 3:
                    raise MetaApiError(408, "หมดเวลารอการตอบกลับจาก MetaApi")
                time.sleep(2 * attempt)
                continue
            except requests.RequestException as e:
                raise MetaApiError(0, f"เชื่อมต่อไม่สำเร็จ: {e}")

            # MetaStats ยังคำนวณไม่เสร็จ
            if r.status_code == 202 and retry_202 and attempt <= MAX_RETRY:
                wait = int(r.headers.get("retry-after", 5) or 5)
                time.sleep(min(wait, 20))
                continue

            if r.status_code == 429 and attempt <= MAX_RETRY:
                time.sleep(min(2 ** attempt, 30))
                continue

            if r.status_code == 401:
                raise MetaApiError(401, "Token ไม่ถูกต้องหรือหมดอายุ")
            if r.status_code == 403:
                raise MetaApiError(
                    403,
                    "ไม่มีสิทธิ์ — อาจยังไม่เปิด MetaStats บนบัญชีนี้ "
                    "(ตั้ง metastatsApiEnabled = true)",
                )
            if r.status_code == 404:
                raise MetaApiError(404, "ไม่พบบัญชีหรือ endpoint นี้")

            if not r.ok:
                try:
                    body = r.json()
                    msg = body.get("message") or body.get("error") or r.text[:300]
                except Exception:
                    body, msg = None, r.text[:300]
                raise MetaApiError(r.status_code, msg, body)

            if not r.content:
                return None
            try:
                return r.json()
            except ValueError:
                return r.text

    # ---------- provisioning ----------

    def list_accounts(self) -> list[dict[str, Any]]:
        data = self._req("GET", f"{PROVISIONING_HOST}/users/current/accounts")
        if isinstance(data, dict):
            return data.get("items", []) or data.get("accounts", [])
        return data or []

    def get_account(self, account_id: str) -> dict[str, Any]:
        return self._req(
            "GET", f"{PROVISIONING_HOST}/users/current/accounts/{account_id}"
        )

    def create_account(
        self,
        *,
        name: str,
        login: str,
        password: str,
        server: str,
        platform: str = "mt5",
        region: str | None = None,
    ) -> dict[str, Any]:
        """เพิ่มบัญชี MT เข้า MetaApi — แนะนำใช้ investor password"""
        body = {
            "name": name,
            "type": "cloud-g2",
            "login": str(login),
            "password": password,
            "server": server,
            "platform": platform,
            "magic": 0,
            "application": "MetaApi",
            "region": region or self.region,
            "metastatsApiEnabled": True,
        }
        return self._req(
            "POST", f"{PROVISIONING_HOST}/users/current/accounts", json_body=body
        )

    def deploy(self, account_id: str) -> None:
        self._req(
            "POST", f"{PROVISIONING_HOST}/users/current/accounts/{account_id}/deploy"
        )

    def undeploy(self, account_id: str) -> None:
        self._req(
            "POST", f"{PROVISIONING_HOST}/users/current/accounts/{account_id}/undeploy"
        )

    def enable_metastats(self, account_id: str) -> dict[str, Any]:
        return self._req(
            "PUT",
            f"{PROVISIONING_HOST}/users/current/accounts/{account_id}",
            json_body={"metastatsApiEnabled": True},
        )

    def wait_deployed(self, account_id: str, timeout_sec: int = 300) -> dict[str, Any]:
        """รอจน state = DEPLOYED และ connectionStatus = CONNECTED"""
        deadline = time.time() + timeout_sec
        last: dict[str, Any] = {}
        while time.time() < deadline:
            last = self.get_account(account_id)
            if (
                last.get("state") == "DEPLOYED"
                and last.get("connectionStatus") == "CONNECTED"
            ):
                return last
            time.sleep(5)
        return last

    # ---------- client (terminal) ----------

    def account_information(self, account_id: str) -> dict[str, Any]:
        return self._req(
            "GET",
            f"{self.client_host}/users/current/accounts/{account_id}"
            "/account-information",
        )

    def positions(self, account_id: str) -> list[dict[str, Any]]:
        return self._req(
            "GET", f"{self.client_host}/users/current/accounts/{account_id}/positions"
        ) or []

    def orders(self, account_id: str) -> list[dict[str, Any]]:
        return self._req(
            "GET", f"{self.client_host}/users/current/accounts/{account_id}/orders"
        ) or []

    def deals_by_time(
        self, account_id: str, start: datetime, end: datetime
    ) -> list[dict[str, Any]]:
        s = _iso_z(start)
        e = _iso_z(end)
        data = self._req(
            "GET",
            f"{self.client_host}/users/current/accounts/{account_id}"
            f"/history-deals/time/{s}/{e}",
        )
        if isinstance(data, dict):
            return data.get("deals", [])
        return data or []

    def history_orders_by_time(
        self, account_id: str, start: datetime, end: datetime
    ) -> list[dict[str, Any]]:
        s = _iso_z(start)
        e = _iso_z(end)
        data = self._req(
            "GET",
            f"{self.client_host}/users/current/accounts/{account_id}"
            f"/history-orders/time/{s}/{e}",
        )
        if isinstance(data, dict):
            return data.get("historyOrders", [])
        return data or []

    # ---------- metastats ----------

    def metrics(self, account_id: str, include_open: bool = True) -> dict[str, Any]:
        data = self._req(
            "GET",
            f"{self.stats_host}/users/current/accounts/{account_id}/metrics",
            params={"includeOpenPositions": str(include_open).lower()},
            retry_202=True,
        )
        if isinstance(data, dict):
            return data.get("metrics", data)
        return {}

    def historical_trades(
        self,
        account_id: str,
        start: datetime,
        end: datetime,
        update_history: bool = True,
    ) -> list[dict[str, Any]]:
        s = _ms_time(start)
        e = _ms_time(end)
        data = self._req(
            "GET",
            f"{self.stats_host}/users/current/accounts/{account_id}"
            f"/historical-trades/{s}/{e}",
            params={"updateHistory": str(update_history).lower()},
            retry_202=True,
        )
        if isinstance(data, dict):
            return data.get("trades", [])
        return data or []

    def open_trades(self, account_id: str) -> list[dict[str, Any]]:
        data = self._req(
            "GET",
            f"{self.stats_host}/users/current/accounts/{account_id}/open-trades",
            retry_202=True,
        )
        if isinstance(data, dict):
            return data.get("openTrades", [])
        return data or []


# ---------- helpers ----------


def _iso_z(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")


def _ms_time(dt: datetime) -> str:
    """MetaStats ใช้รูปแบบ 'YYYY-MM-DD HH:MM:SS.mmm'"""
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt.strftime("%Y-%m-%d %H:%M:%S.000")


def default_range(days: int = 365) -> tuple[datetime, datetime]:
    end = datetime.now(timezone.utc) + timedelta(days=1)
    return end - timedelta(days=days + 1), end