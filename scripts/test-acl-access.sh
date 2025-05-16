#!/bin/bash

echo "Spouštím ACL testovací skript..."

DOCKER_CONTAINER="redis-node-1"
REDIS_PORT="6379"

USERS=(
  "admin adminpassword test"
  "ingestor ingestorpassword orders"
  "catalog_reader catalogpass products"
  "analyst analystpass analytics"
)

echo "=== Redis ACL Access Test ==="

for entry in "${USERS[@]}"; do
  read -r USERNAME PASSWORD PREFIX <<< "$entry"
  URI="redis://${USERNAME}:${PASSWORD}@localhost:${REDIS_PORT}"

  echo -e "\n Testing user: $USERNAME"

  echo "-> SET $PREFIX:key by $USERNAME"
  OUTPUT_SET=$(docker exec "$DOCKER_CONTAINER" redis-cli -u "$URI" -c \
    SET "$PREFIX:key" "value" 2>&1)
  echo "$OUTPUT_SET"

  echo "-> GET $PREFIX:key by $USERNAME"
  OUTPUT_GET=$(docker exec "$DOCKER_CONTAINER" redis-cli -u "$URI" -c \
    GET "$PREFIX:key" 2>&1)
  echo "$OUTPUT_GET"

  echo "-> DEL $PREFIX:key by $USERNAME"
  OUTPUT_DEL=$(docker exec "$DOCKER_CONTAINER" redis-cli -u "$URI" -c \
    DEL "$PREFIX:key" 2>&1)
  echo "$OUTPUT_DEL"
done
