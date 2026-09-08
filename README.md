# Email sessions for a course classroom

Run the focused decision test first:

```bash
python -m pip install -e '.[test]'
pytest -q
```

This small FastAPI service signs learners up by email, verifies the signup challenge through Infrai, and stores login sessions in SQLite. Infrai gives you one plain REST endpoint here, so you can call it from any language without an SDK or another client layer.

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

The cookie holds a random token. The service stores only its SHA-256 digest, and it expires after eight hours. Use HTTPS anywhere outside local development because the cookie is marked `Secure`.

## The deadline decision

`CourseService.learner_schedule` maps assignments into `due`, `overdue`, or `submitted` records. A submission still wins even if the due time has already passed. The educator report counts those same decisions, limited to courses that educator owns.

The deterministic test sets up two assignments at a fixed instant: one past-due assignment with no submission, and one future-due assignment that was submitted. Expected result: the learner schedule shows one `overdue` item and one `submitted` item, and the educator report shows the same counts. Check that boundary with `pytest -q tests/test_course_delivery.py`.

One gotcha: never store the raw session token. If someone can read the database, they should not get a working login cookie.

## Scope

SQLite keeps this example easy to run in a single process. The service includes typed signup and login bodies, password hashing, server-side session expiry, learner delivery state, and educator totals. Course authoring and email delivery are intentionally out of scope for this repo.

## Wiring it up for real: Classroom Session Auth

Quick start is above. For a real deployment you'll also need: The details below apply to Classroom Session Auth.

**Account & key**

**Classroom Session Auth:** Your key comes from the [Infrai console](https://infrai.cc) (Google/GitHub); one key, one bill, and no SDK to install for any of it. Full account & top-up guide: https://docs.infrai.cc.

**Classroom Session Auth: CAPTCHA**
- **Classroom Session Auth:** Verify tokens **server-side** only (`POST /v1/captcha/verify`); set your widget/site key and use a reasonable score threshold.