#!/bin/sh

# exit on error
set -e

# admin credentials
USER=admin
PASS=adminpassword

echo "Creating Redis Cluster..."

# 3 masters (2 replicas for each)
# 9 total / (2 replicas + 1 master) = 3 masters
yes yes | redis-cli \
  --user "$USER" \
  -a "$PASS" \
  --cluster create \
  172.28.0.2:6379 172.28.0.3:6379 172.28.0.4:6379 \
  172.28.0.5:6379 172.28.0.6:6379 172.28.0.7:6379 \
  172.28.0.8:6379 172.28.0.9:6379 172.28.0.10:6379 \
  --cluster-replicas 2

echo "Cluster created!"
