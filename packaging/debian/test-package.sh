#!/bin/sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
REPOSITORY_ROOT=$(CDPATH= cd -- "$SCRIPT_DIR/../.." && pwd)
PACKAGE=${1:-"$REPOSITORY_ROOT/dist/transmy_0.27.0~rc1_all.deb"}

test -f "$PACKAGE"
dpkg-deb --info "$PACKAGE"

EXTRACTED=$(mktemp -d)
cleanup() { rm -rf "$EXTRACTED"; }
trap cleanup EXIT INT TERM
CONTENTS=$EXTRACTED/package-contents.txt
dpkg-deb --contents "$PACKAGE" >"$CONTENTS"
grep -q './usr/bin/transmy' "$CONTENTS"
grep -q './usr/lib/systemd/system/transmy.service' "$CONTENTS"
grep -q './usr/lib/transmy/compose.production.yaml' "$CONTENTS"
dpkg-deb --extract "$PACKAGE" "$EXTRACTED"
grep -q 'reconcile_keycloak_provisioning' "$EXTRACTED/usr/bin/transmy"
grep -q 'handle /oidc/admin/' \
  "$EXTRACTED/usr/lib/transmy/infrastructure/caddy/Caddyfile.local"

TRANSMY_APP_DIR="$EXTRACTED/usr/lib/transmy" \
TRANSMY_CONFIG_DIR="$EXTRACTED/etc/transmy" \
TRANSMY_STATE_DIR="$EXTRACTED/var/lib/transmy" \
  "$EXTRACTED/usr/bin/transmy" help | grep -q 'Usage: transmy COMMAND'

python3 "$EXTRACTED/usr/lib/transmy/packaging/debian/configure-realm.py" \
  "$EXTRACTED/usr/lib/transmy/infrastructure/keycloak/transmissions-realm.json" \
  "$EXTRACTED/realm.json" "care.example.org" "oidc-secret" \
  "provisioning-secret" "evaluation" \
  "admin-secret" "manager-secret" "professional-secret"

python3 - "$EXTRACTED/realm.json" <<'PY'
import json
import sys

realm = json.load(open(sys.argv[1], encoding="utf-8"))
client = next(item for item in realm["clients"] if item["clientId"] == "transmissions-web")
assert client["secret"] == "oidc-secret"
assert client["redirectUris"] == ["https://care.example.org/auth/callback"]
provisioning = next(
    item for item in realm["clients"] if item["clientId"] == "transmissions-provisioning"
)
assert provisioning["secret"] == "provisioning-secret"
assert all(
    user["credentials"][0]["temporary"]
    for user in realm["users"]
    if not user.get("serviceAccountClientId")
)
PY

python3 "$EXTRACTED/usr/lib/transmy/packaging/debian/configure-realm.py" \
  "$EXTRACTED/usr/lib/transmy/infrastructure/keycloak/transmissions-realm.json" \
  "$EXTRACTED/production-realm.json" "care.example.org" "oidc-secret" \
  "provisioning-secret" "production" \
  "admin-secret" "manager-secret" "professional-secret"

python3 - "$EXTRACTED/production-realm.json" <<'PY'
import json
import sys

realm = json.load(open(sys.argv[1], encoding="utf-8"))
assert {
    user["username"] for user in realm["users"] if not user.get("serviceAccountClientId")
} == {"admin"}
PY

printf '%s\n' "Package structure and realm generation are valid."
