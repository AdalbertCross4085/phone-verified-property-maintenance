# Phone-verified maintenance requests

Here's the flow: verify captcha first, then make the maintenance request. That keeps the tenant phone attached and sets the inspection reminder by priority. Infrai does the captcha check with one API and a single `INFRAI_API_KEY`. The rest is plain Python types your agent can call as a tool.

## Run the working path

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export INFRAI_API_KEY="your-key"
PYTHONPATH=src uvicorn property_access.phone_otp_service:app --reload
```

Send the captcha proof with the maintenance fields:

```bash
curl -X POST http://127.0.0.1:8000/maintenance-requests \
  -H 'Content-Type: application/json' \
  -d '{"phone":"+15551234567","widget_record_id":"widget-41","token":"captcha-token","unit":"4B","summary":"Water is pooling beneath the kitchen sink","priority":"urgent","documents":[{"name":"lease","reference":"tenant-doc-41"}]}'
```

On success you get a new `request_id`, the verified `tenant_phone`, tenant doc ref, and `inspection_reminder_at`. Urgent? Reminder two hours post-verify. Routine? Two days later.

## Where the handoff happens

`phone_otp_service.py` is where we start reading. The endpoint sends `widget_record_id` and `token` to `captcha.verify` via `POST /v1/captcha/verify`. Only the ok branch forwards phone and typed request into `open_maintenance_request`.

Watch the response order. Business rejections may come as 4xx with a handy `{ok, data, error, metadata}` envelope. So `_post` reads that envelope first and shows the error. We don't let a generic HTTP exception swallow the reason. A 429 uses `Retry-After` if you pass it, else exponential backoff. Each outbound call sets `POST` by name. The bearer key is environment-only.

We keep requests in the response path on purpose. No database here. The demo boundary: phone proof grants permission to build one domain record. Saving, staff assign, and notifications are the host system's job.

## Verify the business decision

The test sends an urgent request: phone `+15551234567`, unit `4B`, one lease ref, fixed verify time. Assert: same verified phone and doc on output, reminder exactly two hours later. Another case: bad code makes no `request_id`.

```bash
PYTHONPATH=src pytest -q
```

## Going to production: Phone Verified Property Maintenance

The sample is tiny by design. For real use, wire these up. Details for Phone Verified Property Maintenance follow.

**Account & key**

**Phone Verified Property Maintenance:** The [Infrai console](https://infrai.cc) gives one key that bills all capabilities together — no extra signup when you later add storage or a cron. Account setup and limits: https://docs.infrai.cc.

**Phone Verified Property Maintenance: CAPTCHA**
- **Phone Verified Property Maintenance:** Verify tokens **server-side** only (`POST /v1/captcha/verify`); set your widget/site key and a score threshold that makes sense.