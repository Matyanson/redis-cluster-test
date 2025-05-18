#!/bin/sh

# admin credentials
USER=admin
PASS=adminpassword

# Paths to TLS certs
CERT=/usr/local/etc/redis/tls/redis.crt
KEY=/usr/local/etc/redis/tls/redis.key
CA=/usr/local/etc/redis/tls/ca.crt

# master node to check the state
CHECK_HOST=redis-node-1
CHECK_PORT=6379

# don NOT exit on error
set +e
echo "🔍 Kontroluji, zda cluster už neexistuje..."

# Zkusíme zavolat CLUSTER INFO; pokud v odpovědi najdeme "cluster_state:ok", víme, že cluster běží.
CLUSTER_INFO=$(redis-cli \
  --tls \
  --cert "$CERT" \
  --key "$KEY" \
  --cacert "$CA" \
  --user "$USER" \
  -a "$PASS" \
  -h "$CHECK_HOST" \
  -p "$CHECK_PORT" \
  CLUSTER INFO 2>/dev/null)

# Zkusíme najít v odpovědi řádek cluster_state:ok
CLUSTER_SLOTS_ASSIGNED=$(echo "$CLUSTER_INFO" | grep "^cluster_slots_assigned:" | cut -d: -f2)

if [ -n "$CLUSTER_SLOTS_ASSIGNED" ] && [ "$CLUSTER_SLOTS_ASSIGNED" -gt 0 ]; then
  echo "✅ Sloty jsou přiděleny (cluster_slots_assigned=$CLUSTER_SLOTS_ASSIGNED). Cluster je tedy hotový. Přeskakuji vytváření."
  exit 0
fi

echo "⚙️  Cluster neexistuje, pokračuji v jeho vytváření..."
echo "$CLUSTER_INFO"


# exit on error
set -e
echo "Creating Redis Cluster over TLS..."

yes yes | redis-cli \
  --tls \
  --cert "$CERT" \
  --key "$KEY" \
  --cacert "$CA" \
  --user "$USER" \
  -a "$PASS" \
  --cluster create \
  172.28.0.2:6379 172.28.0.3:6379 172.28.0.4:6379 \
  172.28.0.5:6379 172.28.0.6:6379 172.28.0.7:6379 \
  172.28.0.8:6379 172.28.0.9:6379 172.28.0.10:6379 \
  --cluster-replicas 2
# 3 masters (2 replicas for each)
# 9 total / (2 replicas + 1 master) = 3 masters

echo "✅ Cluster created with TLS!"