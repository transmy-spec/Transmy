#!/bin/sh
set -eu

base_url="${BASE_URL:-https://caddy}"
headers="$(mktemp)"
trap 'rm -f "$headers"' EXIT

curl -ksS -D "$headers" -o /dev/null "$base_url/"
for expected in \
  'content-security-policy:' \
  'strict-transport-security:' \
  'x-content-type-options: nosniff' \
  'x-frame-options: DENY' \
  'cross-origin-opener-policy: same-origin'
do
  grep -qi "$expected" "$headers"
done

status="$(curl -ksS -o /dev/null -w '%{http_code}' "$base_url/api/v1/session")"
test "$status" = "401"
status="$(curl -ksS -o /dev/null -w '%{http_code}' -X POST \
  -H 'Origin: https://attacker.invalid' -H 'Content-Type: application/json' \
  -d '{}' "$base_url/api/v1/exports")"
test "$status" = "401"

printf '%s\n' 'Security smoke successful: headers present and anonymous access denied.'
