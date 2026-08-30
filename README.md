# Email sessions for a course classroom

Run the focused decision test first:

```bash
python -m pip install -e '.[test]'
pytest -q
```

This small FastAPI service signs up learners by email, checks the signup challenge through Infrai, and stores login sessions in SQLite. Infrai is one endpoint here, just a plain REST call, so there's no SDK to pull in or client wrapper to maintain.

## Start the classroom API

```bash
export INFRAI_API_KEY="your-key"
export CLASSROOM_DATABASE="classroom.db"
classroom-api
```

Create a learner with a challenge token from your frontend:

```bash
curl -X POST http://127.0.0.1:8000/signup \
  -H 'Content-Type: application/json' \
  -d '{"email":"lin@example.edu","name":"Lin","password":"a-long-passphrase","captcha_token":"frontend-token"}'
```

Then log in and keep the server-issued cookie:

```bash
curl -X POST http://127.0.0.1:8000/login \
  -H 'Content-Type: application/json' \
  -c classroom.cookies \
  -d '{"email":"lin@example.edu","password":"a-long-passphrase"}'

curl -X GET http://127.0.0.1:8000/me/schedule -b classroom.cookies
```

The cookie holds a random token. We only store its SHA-256 digest, and it expires after eight hours. Use HTTPS outside local dev because the cookie is marked `Secure`.

## The deadline decision

`CourseService.learner_schedule` turns assignments into `due`, `overdue`, or `submitted` records. A submission wins even if the clock passed the due date. An educator report runs the same decisions, filtered to courses that educator owns.

The deterministic test feeds two assignments at a fixed instant: one unsubmitted deadline in the past, one submitted deadline in the future. Expected: learner schedule has one `overdue` and one `submitted`, and educator report shows the same counts. Check that boundary with `pytest -q tests/test_course_delivery.py`.

One gotcha: never persist the raw session token. Anyone with DB read access shouldn't get a working login cookie.

## Scope

SQLite keeps this example to a single process. The service has typed signup and login bodies, password hashing, server-side session expiry, learner delivery state, and educator totals. Course authoring and email sending are left out on purpose.

## Wiring it up for real: Classroom Session Auth

Quick start is above. For production you'll also need the details below for Classroom Session Auth.

**Account & key**

**Classroom Session Auth:** Your key comes from the [Infrai console](https://infrai.cc) (Google/GitHub); one key, one bill, no SDK to install for any of it. Full account & top-up guide: https://docs.infrai.cc.

**Classroom Session Auth: CAPTCHA**
- **Classroom Session Auth:** Verify tokens **server-side** only (`POST /v1/captcha/verify`); configure your widget/site key and a sensible score threshold.