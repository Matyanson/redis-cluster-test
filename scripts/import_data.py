import pandas as pd
import redis
import os

from redis.exceptions import ClusterDownError
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
startup_nodes = [
    ClusterNode('redis-node-1', 6379),
    ClusterNode('redis-node-2', 6379),
    ClusterNode('redis-node-3', 6379)
]
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


# Funkce: zkusíme přečíst sentinel klíč, ale pokud je cluster ještě "down", zachytíme chybu
def data_imported():
    try:
        val = r.get('import:complete')
        print(val)
        return val
    except ClusterDownError:
        # Cluster ještě není hotový → vracíme False, abychom šli importovat
        print("⚠️ ClusterDownError při kontrole sentinel klíče, počkám a zkusím import.")
        return False

# Pokud už byl import dokončen, ukončíme se
if data_imported():
    print("✅ Data již byla importována. Skript končí.")
    exit(0)



# Function to import a CSV into Redis hashes
def import_csv_to_hash(csv_path, prefix, mapping_cols):
    df = pd.read_csv(csv_path)
    if df.empty:
        print(f"⚠️  Soubor {csv_path} je prázdný.")
        return
    for _, row in df.iterrows():
        key = f"{prefix}:{row[mapping_cols[0]]}"
        # build mapping dict
        mapping = {col: str(row[col]) for col in mapping_cols[1:]}
        r.hset(key, mapping=mapping)
    print(f"✅ Načteno {len(df)} záznamů z {csv_path} do Redis jako {prefix}:*")

# Import konfigurace
imports = [
    ('./data/products.csv', 'products', ['product_id', 'product_name', 'aisle_id', 'department_id']),
    ('./data/aisles.csv', 'aisles', ['aisle_id', 'aisle']),
    ('./data/departments.csv', 'departments', ['department_id', 'department']),
    ('./data/orders.csv', 'orders', ['order_id', 'user_id', 'eval_set', 'order_number', 'order_dow', 'order_hour_of_day', 'days_since_prior_order']),
    ('./data/order_products__prior.csv', 'order_products_prior', ['order_id', 'product_id', 'add_to_cart_order', 'reordered']),
    ('./data/order_products__train.csv', 'order_products_train', ['order_id', 'product_id', 'add_to_cart_order', 'reordered'])
]

# Spuštění importu
if __name__ == '__main__':
    for csv_path, prefix, cols in imports:
        import_csv_to_hash(csv_path, prefix, cols)
    # Set sentinel key to mark import as complete
    r.set('import:complete', '1')
    print("🎉 Import dat dokončen.")
