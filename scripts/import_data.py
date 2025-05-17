import pandas as pd
import redis
import os

from redis.cluster import RedisCluster
from redis.cluster import ClusterNode

# Settings from environment or defaults
REDIS_URI = os.getenv('REDIS_URI', 'rediss://admin:adminpassword@localhost:6379')
TLS_CERT = os.getenv('TLS_CERT', 'redis/tls/redis.crt')
TLS_KEY = os.getenv('TLS_KEY', 'redis/tls/redis.key')
TLS_CA = os.getenv('TLS_CA', 'redis/tls/ca.crt')

data_dir = 'data'
imports = [
    (f'{data_dir}/products.csv', 'products', ['product_id', 'product_name', 'aisle_id', 'department_id']),
    (f'{data_dir}/aisles.csv', 'aisles', ['aisle_id', 'aisle']),
    (f'{data_dir}/departments.csv', 'departments', ['department_id', 'department'])
]

# Debug: Check that all TLS and CSV files exist
print("🔍 Ověřuji přítomnost souborů:")
paths_to_check = [TLS_CERT, TLS_KEY, TLS_CA] + [imp[0] for imp in imports]
for path in paths_to_check:
    exists = os.path.exists(path)
    print(f"  {path}: {'✅ existuje' if exists else '❌ nenalezeno'}")


# Connect to Redis with TLS and ACL authentication
startup_nodes = [ClusterNode('redis-node-1', 6379)]
r = RedisCluster(
    startup_nodes=startup_nodes,
    host="localhost", port=6379,
    username="admin",
    password="adminpassword",
    ssl=True,
    ssl_certfile=TLS_CERT,
    ssl_keyfile=TLS_KEY,
    ssl_ca_certs=TLS_CA,
    decode_responses=True
)

# Test spojení
try:
    assert r.ping()
    print("✅ TLS připojení úspěšné")
except Exception as e:
    print("❌ Připojení selhalo:", e)
    raise





# # Function to import a CSV into Redis hashes
# def import_csv_to_hash(csv_path, prefix, mapping_cols):
#     df = pd.read_csv(csv_path)
#     if df.empty:
#         print(f"⚠️  Soubor {csv_path} je prázdný.")
#         return
#     for _, row in df.iterrows():
#         key = f"{prefix}:{row[mapping_cols[0]]}"
#         # build mapping dict
#         mapping = {col: row[col] for col in mapping_cols[1:]}
#         r.hset(key, mapping=mapping)
#     print(f"✅ Načteno {len(df)} záznamů z {csv_path} do Redis jako {prefix}:*")

# # Import konfigurace
# imports = [
#     ('./data/products.csv', 'products', ['product_id', 'product_name', 'aisle_id', 'department_id']),
#     ('./data/aisles.csv', 'aisles', ['aisle_id', 'aisle']),
#     ('./data/departments.csv', 'departments', ['department_id', 'department'])
# ]

# # Spuštění importu
# if __name__ == '__main__':
#     for csv_path, prefix, cols in imports:
#         import_csv_to_hash(csv_path, prefix, cols)
#     print("🎉 Import dat dokončen.")
