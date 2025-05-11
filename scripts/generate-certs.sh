#!/bin/bash

set -e

# go to the tls directory
mkdir -p redis/tls
cd redis/tls
# Determine tls directory
SCRIPT_DIR="$(pwd)"

# Paths
CA_KEY="ca.key"
CA_CERT="ca.crt"
REDIS_KEY="redis.key"
REDIS_CSR="redis.csr"
REDIS_CERT="redis.crt"
REDIS_EXT="redis.ext"

# Clean old certificates
rm -f $CA_KEY $CA_CERT $REDIS_KEY $REDIS_CSR $REDIS_CERT $REDIS_EXT ca.srl



# Detect Windows environment for OpenSSL -subj hack (escape drive letter)
# double slash to fix MINGW behaviour: https://github.com/moby/moby/issues/24029#issuecomment-250412919
OS_NAME=$(uname -s)
if [[ "$OS_NAME" == MINGW* || "$OS_NAME" == CYGWIN* ]]; then
  SUBJ_PREFIX="//"
else
  SUBJ_PREFIX="/"
fi

echo "✅ Generating CA..."
openssl genrsa -out $CA_KEY 4096
openssl req -x509 -new -nodes -key $CA_KEY -sha256 -days 3650 -out $CA_CERT \
  -subj "${SUBJ_PREFIX}CN=Redis-CA"

echo "✅ Generating Redis server key & CSR..."
openssl genrsa -out $REDIS_KEY 2048
openssl req -new -key $REDIS_KEY -out $REDIS_CSR \
  -subj "${SUBJ_PREFIX}CN=redis"

echo "✅ Creating extension config..."
# The extension configuration below ensures that the issued Redis server certificate:
# 1. Is explicitly marked as NOT a Certificate Authority (basicConstraints = CA:FALSE),
#    preventing it from being used to sign other certificates and reducing risk if compromised.
# 2. Specifies keyUsage flags (digitalSignature, keyEncipherment) so the certificate is
#    only valid for performing TLS handshakes and encrypting data, not for unintended purposes.
# 3. Defines subjectAltName entries (DNS.1 = redis, DNS.2 = localhost) because modern TLS clients
#    validate the server’s hostname against SAN, not just the Common Name (CN), ensuring hostname
#    verification succeeds and preventing man-in-the-middle attacks.
cat > $REDIS_EXT <<EOF
basicConstraints = CA:FALSE
keyUsage = digitalSignature, keyEncipherment
subjectAltName = @alt_names

[alt_names]
DNS.1 = redis
DNS.2 = localhost
EOF

echo "✅ Signing Redis certificate with our CA..."
openssl x509 -req -in $REDIS_CSR -CA $CA_CERT -CAkey $CA_KEY -CAcreateserial \
  -out $REDIS_CERT -days 3650 -sha256 -extfile $REDIS_EXT

echo "✅ Cleaning up intermediate files..."
rm -f $REDIS_CSR $REDIS_EXT

echo "🎉 TLS certificates generated in: $SCRIPT_DIR"