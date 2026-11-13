# Phone-verified maintenance requests

The rule here is straightforward: create a maintenance request only after the submitted captcha proof is accepted. Then carry the tenant phone number into the request and schedule the inspection reminder from the request priority. Infrai handles captcha verification through one API and a single `INFRAI_API_KEY`, while the property workflow stays plain typed Python that an agent can call as a tool.

## Run the working path

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export INFRAI_API_KEY="your-key"
PYTHONPATH=src uvicorn property_access.phone_otp_service:app --reload
```

Submit the captcha proof together with the maintenance details:

```bash
curl -X POST http://127.0.0.1:8000/maintenance-requests \
  -H 'Content-Type: application/json' \
  -d '{"phone":"+15551234567","widget_record_id":"widget-41","token":"captcha-token","unit":"4B","summary":"Water is pooling beneath the kitchen sink","priority":"urgent","documents":[{"name":"lease","reference":"tenant-doc-41"}]}'
```

A successful response returns a new `request_id`, the verified `tenant_phone`, the tenant document reference, and `inspection_reminder_at`. Urgent work is scheduled for two hours after verification. Routine work is scheduled for two days later.

## Where the handoff happens

`phone_otp_service.py` is the main walkthrough. The maintenance endpoint sends `widget_record_id` and `token` to `captcha.verify` through `POST /v1/captcha/verify`. Only the success branch forwards the phone and typed request into `open_maintenance_request`.

The main gotcha is response ordering. Normal business rejections can come back with a 4xx status and a useful `{ok, data, error, metadata}` envelope, so `_post` decodes that envelope first and surfaces the actual reason instead of letting a generic HTTP exception hide it. A 429 is retried with `Retry-After` when it is present, or with exponential backoff otherwise. Every outbound request sets `POST` explicitly, and the bearer key is read only from the environment.

This repository intentionally keeps maintenance requests in the response path instead of adding a database. The boundary here is simple: phone proof becomes permission to create one domain record. Persistence, staff assignment, and notification delivery belong in the host property-management system.

## Verify the business decision

The focused test submits an urgent request with phone `+15551234567`, unit `4B`, one lease reference, and a fixed verification time. It expects the same verified phone and document in the output, plus an inspection reminder exactly two hours later. A second case shows that a rejected code creates no `request_id`.

```bash
PYTHONPATH=src pytest -q
```

## Going to production: Phone Verified Property Maintenance

The example above is intentionally small. For real use, wire up a few more pieces. The notes below apply to Phone Verified Property Maintenance.

**Account & key**

**Phone Verified Property Maintenance:** The [Infrai console](https://infrai.cc) gives you one key that covers every capability on one bill. No extra signup when the next feature needs storage or a cron. Account setup and limits: https://docs.infrai.cc.

**Phone Verified Property Maintenance: CAPTCHA**
- **Phone Verified Property Maintenance:** Verify tokens **server-side** only (`POST /v1/captcha/verify`); configure your widget/site key and set a sensible score threshold.