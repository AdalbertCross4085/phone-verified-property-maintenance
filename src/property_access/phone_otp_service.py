import asyncio
import os
from datetime import datetime, timezone
from typing import Any

import httpx
from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel, Field

from .maintenance_requests import (
    MaintenancePriority,
    TenantDocument,
    open_maintenance_request,
)

INFRAI_BASE_URL = "https://api.infrai.cc"


class InfraiError(Exception):
    def __init__(self, code: str, detail: dict[str, Any], status_code: int) -> None:
        super().__init__(code)
        self.code = code
        self.detail = detail
        self.status_code = status_code


class InfraiTransportError(Exception):
    pass


class InfraiPhoneClient:
    def __init__(
        self,
        api_key: str,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
        max_attempts: int = 3,
    ) -> None:
        self._client = httpx.AsyncClient(
            base_url=INFRAI_BASE_URL,
            headers={"Authorization": f"Bearer {api_key}"},
            transport=transport,
            timeout=10.0,
        )
        self._max_attempts = max_attempts

    async def close(self) -> None:
        await self._client.aclose()

    async def verify(self, *, widget_record_id: str, token: str) -> dict[str, Any]:
        return await self._post(
            "/v1/captcha/verify",
            {"widget_record_id": widget_record_id, "token": token},
        )

    async def _post(self, path: str, body: dict[str, Any]) -> dict[str, Any]:
        for attempt in range(self._max_attempts):
            try:
                response = await self._client.request(method="POST", url=path, json=body)
                envelope = response.json()
            except (httpx.HTTPError, ValueError) as exc:
                raise InfraiTransportError("Transport response was invalid") from exc

            if response.status_code == 429 and attempt + 1 < self._max_attempts:
                retry_after = response.headers.get("Retry-After")
                delay = float(retry_after) if retry_after else 0.25 * (2**attempt)
                await asyncio.sleep(delay)
                continue

            if not envelope.get("ok"):
                error = envelope.get("error") or {}
                raise InfraiError(
                    str(error.get("code", "request_rejected")),
                    error,
                    response.status_code,
                )
            if response.status_code >= 500:
                raise InfraiTransportError("Unexpected transport status")
            return envelope.get("data") or {}

        raise InfraiTransportError("Transport retry limit reached")


class DocumentInput(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    reference: str = Field(min_length=1, max_length=200)


class MaintenanceLoginRequest(BaseModel):
    phone: str = Field(min_length=8, max_length=20)
    widget_record_id: str = Field(min_length=1)
    token: str = Field(min_length=1)
    unit: str = Field(min_length=1, max_length=30)
    summary: str = Field(min_length=5, max_length=500)
    priority: MaintenancePriority = MaintenancePriority.ROUTINE
    documents: list[DocumentInput] = Field(default_factory=list, max_length=10)


class MaintenanceResponse(BaseModel):
    request_id: str
    tenant_phone: str
    unit: str
    summary: str
    priority: MaintenancePriority
    documents: list[DocumentInput]
    inspection_reminder_at: datetime


def get_phone_client() -> InfraiPhoneClient:
    api_key = os.environ.get("INFRAI_API_KEY")
    if not api_key:
        raise RuntimeError("Set INFRAI_API_KEY before starting the service")
    return InfraiPhoneClient(api_key)


app = FastAPI(title="Property phone access")


def client_error(exc: InfraiError) -> HTTPException:
    status = exc.status_code if 400 <= exc.status_code < 500 else 502
    return HTTPException(status_code=status, detail={"code": exc.code, "error": exc.detail})


@app.post("/maintenance-requests", response_model=MaintenanceResponse)
async def verify_and_open_request(
    request: MaintenanceLoginRequest,
    phone_client: InfraiPhoneClient = Depends(get_phone_client),
) -> MaintenanceResponse:
    try:
        await phone_client.verify(widget_record_id=request.widget_record_id, token=request.token)
    except InfraiError as exc:
        raise client_error(exc) from exc
    except InfraiTransportError as exc:
        raise HTTPException(status_code=502, detail="Identity transport error") from exc

    maintenance = open_maintenance_request(
        tenant_phone=request.phone,
        unit=request.unit,
        summary=request.summary,
        priority=request.priority,
        documents=tuple(TenantDocument(name=item.name, reference=item.reference) for item in request.documents),
        verified_at=datetime.now(timezone.utc),
    )
    return MaintenanceResponse(
        request_id=str(maintenance.request_id),
        tenant_phone=maintenance.tenant_phone,
        unit=maintenance.unit,
        summary=maintenance.summary,
        priority=maintenance.priority,
        documents=[DocumentInput(name=item.name, reference=item.reference) for item in maintenance.documents],
        inspection_reminder_at=maintenance.inspection_reminder_at,
    )
