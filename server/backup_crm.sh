#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "$0")"
umask 077
backup_dir="${1:-./backups}"
mkdir -p -- "$backup_dir"
backup_file="$backup_dir/roma-crm-$(date -u +%Y%m%dT%H%M%SZ).dump"
temporary_file="$backup_file.partial"
trap 'rm -f -- "$temporary_file"' EXIT
docker compose --env-file .env.crm -f compose.yaml -f compose.crm.yaml exec -T crm-db \
  sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' > "$temporary_file"
test -s "$temporary_file"
mv -- "$temporary_file" "$backup_file"
printf 'Backup creado: %s\n' "$backup_file"
