import asyncio
from datetime import datetime, timezone

import httpx
from fastapi.testclient import TestClient

from property_access.phone_otp_service import InfraiError, InfraiPhoneClient, app, get_phone_client


class AcceptingPhoneClient:
    def __init__(self) -> None:
        self.verifications: list[dict[str, object]] = []

    async def verify(self, *, widget_record_id: str, token: str) -> dict[str, object]:
        self.verifications.append({"widget_record_id": widget_record_id, "token": token})
        return {"verified": True}


class RejectingPhoneClient:
    async def verify(self, *, widget_record_id: str, token: str) -> dict[str, object]:
        raise InfraiError("rejected_code", {"message": "Code was rejected"}, 400)


def test_verify_sends_required_captcha_fields() -> None:
    def respond(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/captcha/verify"
        assert request.content == b'{"widget_record_id":"widget-41","token":"test-token"}'
        return httpx.Response(200, json={"ok": True, "data": {"verified": True}})

    async def run() -> None:
        client = InfraiPhoneClient("test-key", transport=httpx.MockTransport(respond))
        try:
            assert await client.verify(widget_record_id="widget-41", token="test-token") == {"verified": True}
        finally:
            await client.close()

    asyncio.run(run())


def test_verified_urgent_request_gets_two_hour_inspection_reminder(monkeypatch) -> None:
    fixed_now = datetime(2026, 9, 11, 8, 0, tzinfo=timezone.utc)

    class FixedDateTime:
        @classmethod
        def now(cls, tz=None):
            return fixed_now

    accepting = AcceptingPhoneClient()
    app.dependency_overrides[get_phone_client] = lambda: accepting
    monkeypatch.setattr("property_access.phone_otp_service.datetime", FixedDateTime)
    try:
        response = TestClient(app).post(
            "/maintenance-requests",
            json={
                "phone": "+15551234567",
                "widget_record_id": "widget-41",
                "token": "test-token",
                "unit": "4B",
                "summary": "Water is pooling beneath the kitchen sink",
                "priority": "urgent",
                "documents": [{"name": "lease", "reference": "tenant-doc-41"}],
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["tenant_phone"] == "+15551234567"
    assert body["documents"] == [{"name": "lease", "reference": "tenant-doc-41"}]
    assert body["inspection_reminder_at"] == "2026-09-11T10:00:00Z"
    assert accepting.verifications == [{"widget_record_id": "widget-41", "token": "test-token"}]


def test_rejected_code_stops_before_request_creation() -> None:
    app.dependency_overrides[get_phone_client] = lambda: RejectingPhoneClient()
    try:
        response = TestClient(app).post(
            "/maintenance-requests",
            json={
                "phone": "+15551234567",
                "widget_record_id": "widget-41",
                "token": "invalid-token",
                "unit": "4B",
                "summary": "Water is pooling beneath the kitchen sink",
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 400
    assert "request_id" not in response.json()
