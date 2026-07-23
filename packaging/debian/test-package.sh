#!/bin/sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
REPOSITORY_ROOT=$(CDPATH= cd -- "$SCRIPT_DIR/../.." && pwd)
PACKAGE=${1:-"$REPOSITORY_ROOT/dist/transmy_0.24.0_all.deb"}

test -f "$PACKAGE"
dpkg-deb --info "$PACKAGE"
dpkg-deb --contents "$PACKAGE" | grep -q './usr/bin/transmy'
dpkg-deb --contents "$PACKAGE" | grep -q './usr/lib/systemd/system/transmy.service'
dpkg-deb --contents "$PACKAGE" | grep -q './usr/lib/transmy/compose.production.yaml'

EXTRACTED=$(mktemp -d)
cleanup() { rm -rf "$EXTRACTED"; }
trap cleanup EXIT INT TERM
dpkg-deb --extract "$PACKAGE" "$EXTRACTED"

TRANSMY_APP_DIR="$EXTRACTED/usr/lib/transmy" \
TRANSMY_CONFIG_DIR="$EXTRACTED/etc/transmy" \
TRANSMY_STATE_DIR="$EXTRACTED/var/lib/transmy" \
  "$EXTRACTED/usr/bin/transmy" help | grep -q 'transmy setup'

python3 "$EXTRACTED/usr/lib/transmy/packaging/debian/configure-realm.py" \
  "$EXTRACTED/usr/lib/transmy/infrastructure/keycloak/transmissions-realm.json" \
  "$EXTRACTED/realm.json" "care.example.org" "oidc-secret" \
  "admin-secret" "manager-secret" "professional-secret"

python3 - "$EXTRACTED/realm.json" <<'PY'
import json
import sys

realm = json.load(open(sys.argv[1], encoding="utf-8"))
client = next(item for item in realm["clients"] if item["clientId"] == "transmissions-web")
assert client["secret"] == "oidc-secret"
assert client["redirectUris"] == ["https://care.example.org/auth/callback"]
assert all(user["credentials"][0]["temporary"] for user in realm["users"])
PY

printf '%s\n' "Package structure and realm generation are valid."
