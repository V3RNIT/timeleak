# demo-app -- Vulnerable Login Service

A small Flask + SQLite app that intentionally exposes side-channel
information-leakage flaws in authentication endpoints, used as the scan
target for the TimeLeak detector. **Runs on `localhost:5000` only.** Do not
deploy this anywhere reachable from outside your own machine, and do not
put real credentials in it.

## Setup

From the repo root, with the shared virtualenv active:

```bash
pip install -r requirements.txt
python demo-app/seed.py
python demo-app/app.py
```

The server listens on `http://127.0.0.1:5000`.

## Endpoints

### `POST /login/v1` -- Timing leak (CWE-203: Observable Discrepancy)

Request: `{"username": "...", "password": "..."}`

If the username does not exist, the server returns `401` immediately. If it
does exist, the server runs `bcrypt.checkpw()` -- deliberately slow -- before
returning `401` or `200`. This creates a measurable wall-clock gap between
"username exists" and "username does not exist", letting an attacker
enumerate valid usernames purely from response latency, without ever
guessing a password.

Supports an optional `?inject_delay_ms=<float>` query parameter that pads
the "user not found" path with an artificial sleep, used by the detector's
sensitivity experiment (Phase 5) to shrink the leak on demand and find the
smallest gap the detector can still catch.

### `POST /login/v2` -- Response-size leak (CWE-203: Observable Discrepancy)

Request: `{"username": "...", "password": "..."}`

Both failure cases return `401`, but "wrong password" (username exists)
includes an extra `hint` field with a much longer message than "user not
found". The response byte count alone reveals whether the username exists,
independent of timing.

### `POST /login/v3` -- Patched / control (no leak)

Request: `{"username": "...", "password": "..."}`

For non-existent usernames, the server still performs a `bcrypt.checkpw()`
call against a fixed dummy hash before responding, so the "user not found"
and "wrong password" paths cost the same amount of time. Both cases return
byte-for-byte identical JSON (`{"error": "Invalid username or password"}`,
`401`). This is the baseline the detector should report as clean.

### `POST /signup` -- Classic enumeration leak (CWE-203: Observable Discrepancy)

Request: `{"email": "...", "password": "..."}`

Returns `409 {"error": "Email already registered"}` for an email that's
already in the database, versus `201` with a generic "check your inbox"
message for a new one. The message content directly confirms which emails
are registered, regardless of timing or response size.

## How v3 fixes the leak

`v1` and `v2` differ from `v3` only in what happens on the "user not found"
path:

- **Timing**: `v3` always pays the bcrypt cost (real hash if the user
  exists, a dummy hash if not), so both paths take the same amount of time.
- **Size/content**: `v3` always returns the exact same JSON body and status
  code for both failure modes, so there is no structural difference to
  observe.

`/signup` has no patched counterpart in this project -- it exists purely to
demonstrate the message-based variant of the same CWE-203 class of flaw for
completeness.

## Reseeding

`python seed.py` drops and recreates the `users` table, then inserts 20
fake users (usernames `alice`..`victor`, emails `<username>@example.com`),
all sharing the password `Password123!`, hashed with `bcrypt`. Run it any
time you want a clean database.
