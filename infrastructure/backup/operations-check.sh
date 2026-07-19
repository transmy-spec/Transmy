#!/bin/sh
set -eu

: "${APP_DOMAIN:?APP_DOMAIN is required}"
base_url="https://$APP_DOMAIN"
backup_max_age="${BACKUP_MAX_AGE_HOURS:-26}"
restore_max_age="${RESTORE_MAX_AGE_HOURS:-744}"
now="$(date +%s)"

for path in / /api/v1/health/live /oidc/realms/transmissions/.well-known/openid-configuration
do
  curl --fail --silent --show-error --resolve "$APP_DOMAIN:443:caddy" "$base_url$path" >/dev/null
done

latest_backup="$(find /backups -maxdepth 1 -name 'backup-*.json' -type f | sort | tail -n 1)"
latest_restore="$(find /backups -maxdepth 1 -name 'restore-report-*.json' -type f | sort | tail -n 1)"
test -n "$latest_backup"
test -n "$latest_restore"
grep -q '"status":"success"' "$latest_backup"
grep -q '"status":"success"' "$latest_restore"

backup_age="$(( (now - $(stat -c %Y "$latest_backup")) / 3600 ))"
restore_age="$(( (now - $(stat -c %Y "$latest_restore")) / 3600 ))"
test "$backup_age" -le "$backup_max_age"
test "$restore_age" -le "$restore_max_age"

printf '{"status":"success","backup_age_hours":%s,"restore_age_hours":%s}\n' \
  "$backup_age" "$restore_age"
