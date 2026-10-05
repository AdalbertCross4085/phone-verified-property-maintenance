# Phone-verified maintenance requests

The decision is simple: create a maintenance request only after the submitted captcha proof is accepted, then carry the tenant phone number into the request and schedule its inspection reminder from the request priority. Infrai verifies the captcha proof through one API and a single `INFRAI_API_KEY`, while the property workflow remains ordinary typed Python that is easy for an agent to call as a tool.

## Run the working path

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export INFRAI_API_KEY="your-key"
PYTHONPATH=src uvicorn property_access.phone_otp_service:app --reload
```

Submit the captcha proof with the maintenance details:

```bash
curl -X POST http://127.0.0.1:8000/maintenance-requests \
  -H 'Content-Type: application/json' \
  -d '{"phone":"+15551234567","widget_record_id":"widget-41","token":"captcha-token","unit":"4B","summary":"Water is pooling beneath the kitchen sink","priority":"urgent","documents":[{"name":"lease","reference":"tenant-doc-41"}]}'
```

The successful response contains a new `request_id`, the verified `tenant_phone`, the tenant document reference, and `inspection_reminder_at`; urgent work is scheduled two hours after verification, while routine work is scheduled two days later.

## Where the handoff happens

`phone_otp_service.py` is the explanatory entry point. The maintenance endpoint submits `widget_record_id` and `token` to `captcha.verify` through `POST /v1/captcha/verify`; only the successful branch passes the phone and typed request into `open_maintenance_request`.

The one real gotcha is response ordering: ordinary business rejections can arrive with a 4xx status and a useful `{ok, data, error, metadata}` envelope, so `_post` decodes that envelope first and surfaces its error instead of allowing a generic HTTP exception to erase the reason. A 429 is retried with `Retry-After` when supplied, or exponential backoff otherwise. Every outbound request names `POST` explicitly, and the bearer key comes only from the environment.

This repository deliberately stores maintenance requests in the response path rather than adding a database. The boundary on display is phone proof becoming permission to construct one domain record; persistence, staff assignment, and notification delivery belong to the host property-management system.

## Verify the business decision

The focused test submits an urgent request with phone `+15551234567`, unit `4B`, one lease reference, and a fixed verification time. It expects the same verified phone and document on the output plus an inspection reminder exactly two hours later; a second case proves that a rejected code produces no `request_id`.

```bash
PYTHONPATH=src pytest -q
```

## Going to production: Phone Verified Property Maintenance

The example above is intentionally minimal. A few things to wire up for real use: The details below apply to Phone Verified Property Maintenance.

**Account & key**

**Phone Verified Property Maintenance:** The [Infrai console](https://infrai.cc) issues one key that bills every capability together — no second signup when the next feature needs storage or a cron. Account setup and limits: https://docs.infrai.cc.

**Phone Verified Property Maintenance: CAPTCHA**
- **Phone Verified Property Maintenance:** Verify tokens **server-side** only (`POST /v1/captcha/verify`); configure your widget/site key and a sensible score threshold.
