#!/bin/bash
set -e

CONTAINER=$1
BACKUP_FILE=$2

if [ -z "$CONTAINER" ] || [ -z "$BACKUP_FILE" ]; then
  echo "Usage: restore-container.sh <container-name> <backup.tar.gz>"
  exit 1
fi

echo "🎯 Restoring container: $CONTAINER"

TMP_DIR="/tmp/restore_$CONTAINER"
mkdir -p "$TMP_DIR"

echo "Extracting relevant files..."
tar -xvf "$BACKUP_FILE" -C "$TMP_DIR"

echo "Stopping container..."
docker stop "$CONTAINER" || true

# -------------------------
# Restore volumes
# -------------------------
echo "Restoring volumes..."

docker inspect "$CONTAINER" | jq -r '.[0].Mounts[].Source' | while read volume; do
  echo "→ Restoring volume: $volume"

  if [ -d "$TMP_DIR$volume" ]; then
    rm -rf "$volume"/*
    cp -a "$TMP_DIR$volume/." "$volume/"
  fi
done

echo "Starting container..."
docker start "$CONTAINER"

sleep 5

# -------------------------
# Restore DB if needed
# -------------------------
if ls "$TMP_DIR"/*.sql 1> /dev/null 2>&1; then
  echo "Restoring SQL dump..."
  for f in "$TMP_DIR"/*.sql; do
    docker exec -i "$CONTAINER" sh -c "cat > /tmp/restore.sql"
    docker exec -i "$CONTAINER" sh -c "psql -U postgres < /tmp/restore.sql || mysql < /tmp/restore.sql"
  done
fi

if ls "$TMP_DIR"/*dump.rdb 1> /dev/null 2>&1; then
  echo "Restoring Redis..."
  docker cp "$TMP_DIR"/*dump.rdb "$CONTAINER":/data/dump.rdb
  docker restart "$CONTAINER"
fi

echo "✅ Container restore complete!"
