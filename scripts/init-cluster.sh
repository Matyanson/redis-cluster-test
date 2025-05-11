#!/bin/sh

# exit on error
set -e

# admin credentials
USER=admin
PASS=adminpassword

# Paths to TLS certs
CERT=/usr/local/etc/redis/tls/redis.crt
KEY=/usr/local/etc/redis/tls/redis.key
CA=/usr/local/etc/redis/tls/ca.crt

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