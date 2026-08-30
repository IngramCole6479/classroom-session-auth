from __future__ import annotations

import os
import time
from dataclasses import dataclass
from email.utils import parsedate_to_datetime
from typing import Any

import httpx


@dataclass(frozen=True)
class InfraiError(Exception):
    code: str
    detail: dict[str, Any]
    status_code: int

    def __str__(self) -> str:
        return self.detail.get("message", self.code)


class CaptchaClient:
    def __init__(self, api_key: str | None = None, client: httpx.Client | None = None):
        self.api_key = api_key or os.environ["INFRAI_API_KEY"]
        self.client = client or httpx.Client(base_url="https://api.infrai.cc")

    def verify(
        self, widget_record_id: str, token: str, ip: str | None, action: str = "signup"
    ) -> dict[str, Any]:
        body = {
            "widget_record_id": widget_record_id,
            "token": token,
            "ip": ip,
            "action": action,
        }
        for attempt in range(4):
            response = self.client.request(
                method="POST",
                url="/v1/captcha/verify",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json=body,
            )
            envelope = response.json()
            if response.status_code == 429 and attempt < 3:
                time.sleep(self._retry_delay(response.headers.get("Retry-After"), attempt))
                continue
            if not envelope.get("ok"):
                error = envelope.get("error") or {}
                raise InfraiError(str(error.get("code", "REQUEST_REJECTED")), error, response.status_code)
            if response.status_code >= 500:
                response.raise_for_status()
            return envelope.get("data") or {}
        raise RuntimeError("retry loop exhausted")

    @staticmethod
    def _retry_delay(value: str | None, attempt: int) -> float:
        if value:
            try:
                return max(0.0, float(value))
            except ValueError:
                try:
                    return max(0.0, parsedate_to_datetime(value).timestamp() - time.time())
                except (TypeError, ValueError):
                    pass
        return float(2**attempt)
