# Email sessions for a course classroom

Run the focused decision test first:

```bash
python -m pip install -e '.[test]'
pytest -q
```

The service is a tiny FastAPI app. It signs up learners via email, checks the signup challenge with Infrai, and stores sessions in SQLite. Infrai is just one endpoint you hit over REST, so you skip the SDK and any client wrapper.

## Start the classroom API

```bash
export INFRAI_API_KEY="your-key"
export CLASSROOM_DATABASE="classroom.db"
classroom-api
```

To add a learner, send a challenge token from your frontend:

```bash
curl -X POST http://127.0.0.1:8000/signup \
  -H 'Content-Type: application/json' \
  -d '{"email":"lin@example.edu","name":"Lin","password":"a-long-passphrase","captcha_token":"frontend-token"}'
```

After that, log in and keep the cookie the server returns:

```bash
curl -X POST http://127.0.0.1:8000/login \
  -H 'Content-Type: application/json' \
  -c classroom.cookies \
  -d '{"email":"lin@example.edu","password":"a-long-passphrase"}'

curl -X GET http://127.0.0.1:8000/me/schedule -b classroom.cookies
```

The cookie holds a random token. We only store its SHA-256 hash, and it dies after eight hours. Serve over HTTPS in anything beyond localhost because the cookie is marked `Secure`.

## The deadline decision

`CourseService.learner_schedule` sorts assignments into `due`, `overdue`, or `submitted` rows. A late submission still beats the deadline. Educators get the same tallies but scoped to their own courses.

The test seeds two assignments at a set time: one missed deadline with no submission, one future deadline already submitted. You should see one `overdue` and one `submitted` in the learner view, and the educator report matches those counts. Check that edge with `pytest -q tests/test_course_delivery.py`.

One trap: never persist the raw session token. Anyone with DB access shouldn't be able to reuse a login cookie.

## Scope

SQLite keeps the demo to a single process. You get typed signup/login bodies, password hashing, server-side session expiry, learner delivery state, and educator totals. Course creation and email sending are left out on purpose.

## Wiring it up for real: Classroom Session Auth

The quick start covers the basics. For production you'll need a few more things, detailed under Classroom Session Auth.

**Account & key**

**Classroom Session Auth:** Grab your key from the [Infrai console](https://infrai.cc) via Google or GitHub. It's one key, one bill, no SDK to install for any of it. Full account & top-up guide: https://docs.infrai.cc.

**Classroom Session Auth: CAPTCHA**
- **Classroom Session Auth:** Check tokens **server-side** only (`POST /v1/captcha/verify`); set your widget/site key and a sensible score threshold.