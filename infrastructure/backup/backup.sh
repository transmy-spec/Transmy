#!/bin/sh
set -eu

: "${BACKUP_ENCRYPTION_PASSWORD:?BACKUP_ENCRYPTION_PASSWORD is required}"
: "${BACKUP_RETENTION_COUNT:=14}"
stamp="$(date -u +%Y%m%dT%H%M%SZ)"
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT

PGPASSWORD="$APP_DATABASE_PASSWORD" pg_dump \
  -h postgres-app -U "$APP_DATABASE_USER" -d "$APP_DATABASE_NAME" \
  --format=custom --no-owner --no-acl --file="$work/application.dump"
PGPASSWORD="$KEYCLOAK_DATABASE_PASSWORD" pg_dump \
  -h postgres-keycloak -U "$KEYCLOAK_DATABASE_USER" -d "$KEYCLOAK_DATABASE_NAME" \
  --format=custom --no-owner --no-acl --file="$work/identity.dump"

migration="$(PGPASSWORD="$APP_DATABASE_PASSWORD" psql -h postgres-app \
  -U "$APP_DATABASE_USER" -d "$APP_DATABASE_NAME" -Atc \
  'SELECT version_num FROM alembic_version')"
printf '{"schema_version":1,"created_at":"%s","alembic_revision":"%s","postgres_version":"17","contains":"application_and_identity_databases"}\n' \
  "$stamp" "$migration" > "$work/manifest.json"

tar -C "$work" -czf "$work/databases.tar.gz" application.dump identity.dump manifest.json
openssl enc -aes-256-cbc -pbkdf2 -salt \
  -in "$work/databases.tar.gz" -out "/backups/backup-$stamp.tar.gz.enc" \
  -pass env:BACKUP_ENCRYPTION_PASSWORD
sha256sum "/backups/backup-$stamp.tar.gz.enc" > "/backups/backup-$stamp.sha256"
printf '{"status":"success","created_at":"%s","artifact":"backup-%s.tar.gz.enc","encryption":"AES-256-CBC/PBKDF2"}\n' \
  "$stamp" "$stamp" > "/backups/backup-$stamp.json"

count=0
find /backups -maxdepth 1 -name 'backup-*.tar.gz.enc' -type f | sort -r | while read -r old
do
  count="$((count + 1))"
  if [ "$count" -gt "$BACKUP_RETENTION_COUNT" ]; then
    base="${old%.tar.gz.enc}"
    rm -f "$old" "$base.sha256" "$base.json"
  fi
done
printf '%s\n' "Backup encrypted successfully: backup-$stamp.tar.gz.enc"
