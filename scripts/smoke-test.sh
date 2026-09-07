#!/usr/bin/env bash
#
# Post-deploy smoke test — run this against a staging (or fresh production)
# deployment to catch the class of bug that only shows up when the real
# network/DB/Redis topology exists, not in unit tests.
#
#   STAGING_API_URL=https://api-staging.example.com \
#   STAGING_WEB_URL=https://staging.example.com \
#   SMOKE_TEST_EMAIL=admin@school.dev \
#   SMOKE_TEST_PASSWORD='...' \
#     scripts/smoke-test.sh
#
# Required:
#   STAGING_API_URL   backend base URL, no trailing slash (e.g. https://api.example.com)
#   STAGING_WEB_URL   frontend base URL, no trailing slash
#
# Optional (login + authenticated-endpoint checks are skipped without these):
#   SMOKE_TEST_EMAIL, SMOKE_TEST_PASSWORD   a real user's credentials.
#     Use a dedicated low-privilege account, not your own — this script logs
#     in for real against the live backend on every run.
#
# Exit code is non-zero if anything failed. Safe to wire into a deploy
# pipeline as a post-deploy gate.
#
set -uo pipefail

API_URL="${STAGING_API_URL:-}"
WEB_URL="${STAGING_WEB_URL:-}"
EMAIL="${SMOKE_TEST_EMAIL:-}"
PASSWORD="${SMOKE_TEST_PASSWORD:-}"

if [[ -z "$API_URL" || -z "$WEB_URL" ]]; then
  echo "usage: STAGING_API_URL=... STAGING_WEB_URL=... scripts/smoke-test.sh" >&2
  exit 2
fi
API_URL="${API_URL%/}"
WEB_URL="${WEB_URL%/}"

PASS=0
FAIL=0
FAILURES=()

note() { printf '\n\033[1m==> %s\033[0m\n' "$*"; }
ok()   { printf '  \033[32m✓\033[0m %s\n' "$*"; PASS=$((PASS+1)); }
bad()  { printf '  \033[31m✗\033[0m %s\n' "$*"; FAIL=$((FAIL+1)); FAILURES+=("$*"); }

# curl wrapper: prints "<code>|<body>" so callers can split on the first '|'.
req() {
  local method="$1" url="$2"; shift 2
  local out
  out="$(curl -sS -o /tmp/smoke_body.$$ -w '%{http_code}' --max-time 15 -X "$method" "$url" "$@" 2>/tmp/smoke_err.$$)"
  local code="$out"
  local body
  body="$(cat /tmp/smoke_body.$$ 2>/dev/null)"
  rm -f /tmp/smoke_body.$$ /tmp/smoke_err.$$
  printf '%s|%s' "$code" "$body"
}

json_field() {
  # json_field <json> <dotted.path> — tiny, no jq dependency required.
  python3 -c '
import json, sys
data = json.loads(sys.argv[1])
for part in sys.argv[2].split("."):
    data = data[part]
print(data)
' "$1" "$2" 2>/dev/null
}

# ── 1. Backend reachability ─────────────────────────────────────────────────
note "Backend reachable"
resp="$(req GET "$API_URL/docs")"
code="${resp%%|*}"
if [[ "$code" == "200" ]]; then
  ok "GET /docs -> 200"
else
  bad "GET /docs -> $code (expected 200)"
fi

# ── 2. Frontend reachability ─────────────────────────────────────────────────
note "Frontend reachable"
resp="$(req GET "$WEB_URL/")"
code="${resp%%|*}"
if [[ "$code" == "200" ]]; then
  ok "GET / -> 200"
else
  bad "GET / -> $code (expected 200)"
fi

resp="$(req GET "$WEB_URL/login")"
code="${resp%%|*}"
if [[ "$code" == "200" ]]; then
  ok "GET /login -> 200"
else
  bad "GET /login -> $code (expected 200)"
fi

# ── 3. Login round trip (the check that would have caught the Redis outage) ─
ACCESS_TOKEN=""
if [[ -n "$EMAIL" && -n "$PASSWORD" ]]; then
  note "Login round trip"
  resp="$(req POST "$API_URL/api/v1/auth/login" \
    -H "Content-Type: application/x-www-form-urlencoded" \
    --data-urlencode "username=$EMAIL" \
    --data-urlencode "password=$PASSWORD")"
  code="${resp%%|*}"
  body="${resp#*|}"
  if [[ "$code" == "200" ]]; then
    ACCESS_TOKEN="$(json_field "$body" tokens.access_token)"
    if [[ -n "$ACCESS_TOKEN" && "$ACCESS_TOKEN" != "None" ]]; then
      ok "POST /auth/login -> 200 with an access token"
    else
      bad "POST /auth/login -> 200 but no access_token in the response body"
    fi
  elif [[ "$code" == "401" ]]; then
    bad "POST /auth/login -> 401 (wrong credentials — check SMOKE_TEST_EMAIL/PASSWORD, not necessarily a deploy bug)"
  else
    bad "POST /auth/login -> $code (expected 200). A 500 here is exactly the class of bug" \
        "this script exists to catch — e.g. a dependency (Redis, DB) being unreachable" \
        "in this environment. Body: ${body:0:300}"
  fi
else
  note "Login round trip (skipped — set SMOKE_TEST_EMAIL/SMOKE_TEST_PASSWORD to enable)"
fi

# ── 4. An authenticated endpoint, proving the token actually works ──────────
if [[ -n "$ACCESS_TOKEN" ]]; then
  note "Authenticated request"
  resp="$(req GET "$API_URL/api/v1/users/session" -H "Authorization: Bearer $ACCESS_TOKEN")"
  code="${resp%%|*}"
  if [[ "$code" == "200" ]]; then
    ok "GET /users/session with bearer token -> 200"
  else
    bad "GET /users/session with bearer token -> $code (expected 200)"
  fi
fi

# ── 5. Repeated login attempts don't 500 (Redis-outage / rate-limit path) ───
note "Rate-limit path stays healthy under repeat requests"
transient_failure=0
for i in 1 2 3; do
  resp="$(req POST "$API_URL/api/v1/auth/login" \
    -H "Content-Type: application/x-www-form-urlencoded" \
    --data-urlencode "username=smoke-test-nonexistent-user@example.invalid" \
    --data-urlencode "password=wrong")"
  code="${resp%%|*}"
  # 401 (bad creds) or 429 (rate limited) are both healthy responses here.
  # 500 means the rate-limit check itself is crashing the request — the exact
  # failure mode a Redis outage caused before it was fixed to fail open.
  if [[ "$code" != "401" && "$code" != "429" ]]; then
    transient_failure=1
    bad "login attempt $i/3 -> $code (expected 401 or 429 — a 500 means the" \
        "rate-limit check is crashing the endpoint, e.g. Redis unreachable)"
  fi
done
if [[ "$transient_failure" -eq 0 ]]; then
  ok "3 rapid login attempts all returned 401/429, none 500'd"
fi

# ── Summary ──────────────────────────────────────────────────────────────────
echo
echo "────────────────────────────────────────"
echo "Passed: $PASS   Failed: $FAIL"
if [[ "$FAIL" -gt 0 ]]; then
  echo
  echo "Failures:"
  printf '  - %s\n' "${FAILURES[@]}"
  exit 1
fi
echo "All checks passed."
