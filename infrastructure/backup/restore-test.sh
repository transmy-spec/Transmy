#!/bin/sh
set -eu

: "${BACKUP_ENCRYPTION_PASSWORD:?BACKUP_ENCRYPTION_PASSWORD is required}"
started="$(date +%s)"
stamp="$(date -u +%Y%m%dT%H%M%SZ)"
suffix="restore_${stamp}_$$"
app_test="app_$suffix"
identity_test="identity_$suffix"
work="$(mktemp -d)"
artifact="$(find /backups -maxdepth 1 -name 'backup-*.tar.gz.enc' -type f | sort | tail -n 1)"
test -n "$artifact"
checksum="${artifact%.tar.gz.enc}.sha256"
test -f "$checksum"
sha256sum -c "$checksum"

cleanup() {
  PGPASSWORD="$APP_DATABASE_PASSWORD" dropdb -h postgres-app -U "$APP_DATABASE_USER" --if-exists "$app_test" >/dev/null 2>&1 || true
  PGPASSWORD="$KEYCLOAK_DATABASE_PASSWORD" dropdb -h postgres-keycloak -U "$KEYCLOAK_DATABASE_USER" --if-exists "$identity_test" >/dev/null 2>&1 || true
  rm -rf "$work"
}
trap cleanup EXIT

openssl enc -d -aes-256-cbc -pbkdf2 -in "$artifact" \
  -out "$work/databases.tar.gz" -pass env:BACKUP_ENCRYPTION_PASSWORD
tar -C "$work" -xzf "$work/databases.tar.gz"
test -s "$work/manifest.json"
grep -q '"schema_version":1' "$work/manifest.json"

PGPASSWORD="$APP_DATABASE_PASSWORD" createdb -h postgres-app -U "$APP_DATABASE_USER" "$app_test"
PGPASSWORD="$APP_DATABASE_PASSWORD" pg_restore -h postgres-app -U "$APP_DATABASE_USER" \
  -d "$app_test" --no-owner --no-acl "$work/application.dump"
PGPASSWORD="$APP_DATABASE_PASSWORD" psql -h postgres-app -U "$APP_DATABASE_USER" \
  -d "$app_test" -v ON_ERROR_STOP=1 -Atc "SELECT 1 FROM app.organization LIMIT 1" >/dev/null

PGPASSWORD="$KEYCLOAK_DATABASE_PASSWORD" createdb -h postgres-keycloak -U "$KEYCLOAK_DATABASE_USER" "$identity_test"
PGPASSWORD="$KEYCLOAK_DATABASE_PASSWORD" pg_restore -h postgres-keycloak -U "$KEYCLOAK_DATABASE_USER" \
  -d "$identity_test" --no-owner --no-acl "$work/identity.dump"
PGPASSWORD="$KEYCLOAK_DATABASE_PASSWORD" psql -h postgres-keycloak -U "$KEYCLOAK_DATABASE_USER" \
  -d "$identity_test" -v ON_ERROR_STOP=1 -Atc "SELECT 1 FROM realm LIMIT 1" >/dev/null

duration="$(( $(date +%s) - started ))"
printf '{"status":"success","tested_at":"%s","duration_seconds":%s,"application_database":"restored_and_checked","identity_database":"restored_and_checked","business_data_in_report":false}\n' \
  "$stamp" "$duration" > "/backups/restore-report-$stamp.json"
printf '%s\n' "Restore exercise successful in ${duration}s; temporary databases removed."
