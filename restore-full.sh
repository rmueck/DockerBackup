#!/bin/bash
set -e

BACKUP_FILE=$1

if [ -z "$BACKUP_FILE" ]; then
  echo "Usage: restore-full.sh <backup.tar.gz>"
  exit 1
fi

echo "🔥 FULL RESTORE from $BACKUP_FILE"

echo "Stopping all containers..."
docker ps -q | xargs -r docker stop

echo "Extracting backup..."
tar -xvf "$BACKUP_FILE" -C /

echo "Starting containers..."
docker compose up -d

sleep 10

echo "Restoring databases..."

for f in /tmp/*.sql; do
  echo "→ Restoring $f"
  docker exec -i $(docker ps --filter ancestor=postgres -q | head -n1) psql -U postgres < "$f" || true
  docker exec -i $(docker ps --filter ancestor=mariadb -q | head -n1) mysql -u root < "$f" || true
done

for f in /tmp/*dump.rdb; do
  echo "→ Restoring Redis $f"
  docker cp "$f" $(docker ps --filter ancestor=redis -q | head -n1):/data/dump.rdb
done

echo "✅ Full restore complete!"
