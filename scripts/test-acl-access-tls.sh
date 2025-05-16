#!/bin/bash

echo "Spouštím ACL testovací skript (TLS přes URI)..."

DOCKER_CONTAINER="redis-node-1"
REDIS_PORT="6379"

# Paths to TLS certs
# double slash to fix MINGW behaviour: https://github.com/moby/moby/issues/24029#issuecomment-250412919
CERT='//usr/local/etc/redis/tls/redis.crt'
KEY='//usr/local/etc/redis/tls/redis.key'
CA='//usr/local/etc/redis/tls/ca.crt'


USERS=(
  "admin adminpassword test"
  "ingestor ingestorpassword orders"
  "catalog_reader catalogpass products"
  "analyst analystpass analytics"
)

for entry in "${USERS[@]}"; do
  read -r USERNAME PASSWORD PREFIX <<< "$entry"
  URI="rediss://${USERNAME}:${PASSWORD}@localhost:${REDIS_PORT}"

  echo -e "\n🔐 Testing user: $USERNAME"

  echo "-> SET $PREFIX:key by $USERNAME"
  OUTPUT_SET=$(docker exec "$DOCKER_CONTAINER" redis-cli --tls \
    --cert "$CERT" --key "$KEY" --cacert "$CA" -u "$URI" -c \
    SET "$PREFIX:key" "value" 2>&1)
  echo "$OUTPUT_SET"

  echo "-> GET $PREFIX:key by $USERNAME"
  OUTPUT_GET=$(docker exec "$DOCKER_CONTAINER" redis-cli --tls \
    --cert "$CERT" --key "$KEY" --cacert "$CA" -u "$URI" -c \
    GET "$PREFIX:key" 2>&1)
  echo "$OUTPUT_GET"

  echo "-> DEL $PREFIX:key by $USERNAME"
  OUTPUT_DEL=$(docker exec "$DOCKER_CONTAINER" redis-cli --tls \
    --cert "$CERT" --key "$KEY" --cacert "$CA" -u "$URI" -c \
    DEL "$PREFIX:key" 2>&1)
  echo "$OUTPUT_DEL"
done