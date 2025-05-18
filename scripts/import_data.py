import pandas as pd
import redis
import os

from redis.exceptions import ClusterDownError
from redis.cluster import RedisCluster
from redis.cluster import ClusterNode

# --- 1) CONNECT TO REDIS CLUSTER ---

# Settings from environment or defaults
USERNAME   = os.getenv('REDIS_USER', 'admin')
PASSWORD   = os.getenv('REDIS_PASS', 'adminpassword')
TLS_CERT = os.getenv('TLS_CERT', 'redis/tls/redis.crt')
TLS_KEY = os.getenv('TLS_KEY', 'redis/tls/redis.key')
TLS_CA = os.getenv('TLS_CA', 'redis/tls/ca.crt')


# Connect to Redis with TLS and ACL authentication
startup_nodes = [
    ClusterNode('redis-node-1', 6379),
    ClusterNode('redis-node-2', 6379),
    ClusterNode('redis-node-3', 6379)
]
r = RedisCluster(
    startup_nodes=startup_nodes,
    username=USERNAME,
    password=PASSWORD,
    ssl=True,
    ssl_certfile=TLS_CERT,
    ssl_keyfile=TLS_KEY,
    ssl_ca_certs=TLS_CA,
    decode_responses=True
)

# Test connection
try:
    assert r.ping()
    print("✅ TLS připojení úspěšné")
except Exception as e:
    print("❌ Připojení selhalo:", e)
    raise

# --- 2) CHECK FOR EXISTING DATA ---

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

# --- 3) CHECK FOR MISSING FILES ---

# Import konfigurace
imports = [
    ('./data/products.csv', 'products', ['product_id', 'product_name', 'aisle_id', 'department_id']),
    ('./data/aisles.csv', 'aisles', ['aisle_id', 'aisle']),
    ('./data/departments.csv', 'departments', ['department_id', 'department']),
    ('./data/orders.csv', 'orders', ['order_id', 'user_id', 'eval_set', 'order_number', 'order_dow', 'order_hour_of_day', 'days_since_prior_order']),
    ('./data/order_products__prior.csv', 'order_products_prior', ['order_id', 'product_id', 'add_to_cart_order', 'reordered']),
    ('./data/order_products__train.csv', 'order_products_train', ['order_id', 'product_id', 'add_to_cart_order', 'reordered'])
]

# Debug: Check that all TLS and CSV files exist
print("🔍 Ověřuji přítomnost souborů:")
paths_to_check = [TLS_CERT, TLS_KEY, TLS_CA] + [imp[0] for imp in imports]
for path in paths_to_check:
    exists = os.path.exists(path)
    print(f"  {path}: {'✅ existuje' if exists else '❌ nenalezeno'}")

# --- 4) IMPORT DATA ---

# Helper function to import a CSV into Redis hashes
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


def import_HSET_datasets():
    hsetDatasets = imports[0:3]
    for csv_path, prefix, cols in hsetDatasets:
        import_csv_to_hash(csv_path, prefix, cols)

def import_orders():
    df_orders = pd.read_csv('./data/orders.csv')
    print(f"ℹ️  Načítání {len(df_orders)} řádků z orders.csv ...")

    for _, row in df_orders.iterrows():
        order_id = str(row['order_id'])
        user_id  = str(row['user_id'])
        eval_set = row['eval_set']       # prior/train/test
        order_dow= row['order_dow']
        order_hour = row['order_hour_of_day']
        days_prior = row['days_since_prior_order']

        # 1) HSET do hashu orders:<order_id>
        r.hset(
            f"order:{order_id}",
            mapping={
                'user_id': user_id,
                'eval_set': eval_set,
                'order_number': row['order_number'],
                'order_dow': order_dow,
                'order_hour_of_day': order_hour,
                'days_since_prior_order': days_prior
            }
        )

        # 2) Set user:orders:<user_id>
        r.sadd(f"user:orders:{user_id}", order_id)

        # 3) Set orders:evalset:<eval_set>
        r.sadd(f"orders:evalset:{eval_set}", order_id)

        # 4) Set orders:day:<order_dow>
        r.sadd(f"orders:day:{order_dow}", order_id)

        # 5) ZINCRBY user:order_count
        r.zincrby("user:order_count", 1, user_id)

    print("✅ Orders naimportovány.")

def import_order_products__prior():
    df_prior = pd.read_csv('./data/order_products__prior.csv')
    print(f"ℹ️  Načítání {len(df_prior)} řádků z order_products__prior.csv ...")

    for _, row in df_prior.iterrows():
        order_id   = str(row['order_id'])
        product_id = str(row['product_id'])
        add_idx    = int(row['add_to_cart_order'])
        reordered  = int(row['reordered'])

        # 1) Sorted Set order:products:prior:<order_id> ← {product_id: score=add_idx}
        #    (zachováme pořadí, ve kterém byl produkt přidán)
        r.zadd(f"order:products:prior:{order_id}", {product_id: add_idx})

        # 2) Celková popularita produktu v prior
        r.zincrby("product:prior:popularity", 1, product_id)

        # 3) Počet „reorders“ na úrovni produktu (jen pokud reordered == 1)
        if reordered == 1:
            r.zincrby("product:prior:reorder_count", 1, product_id)

        # 4) Podrobné stats pro každý produkt
        r.hincrby(f"product:prior:stats:{product_id}", "total_count", 1)
        if reordered == 1:
            r.hincrby(f"product:prior:stats:{product_id}", "reordered_count", 1)

    print("✅ Prior order_products naimportováno.")

def import_order_products__train():
    df_train = pd.read_csv('./data/order_products__train.csv')
    print(f"ℹ️  Načítání {len(df_train)} řádků z order_products__train.csv ...")

    for _, row in df_train.iterrows():
        order_id   = str(row['order_id'])
        product_id = str(row['product_id'])
        add_idx    = int(row['add_to_cart_order'])
        reordered  = int(row['reordered'])

        # 1) Sorted Set order:products:train:<order_id>
        r.zadd(f"order:products:train:{order_id}", {product_id: add_idx})

        # 2) Celková popularita produktu v train
        r.zincrby("product:train:popularity", 1, product_id)

        # 3) Počet „reorders“ na úrovni produktu (train)
        if reordered == 1:
            r.zincrby("product:train:reorder_count", 1, product_id)

        # 4) Stats pro každý produkt (train)
        r.hincrby(f"product:train:stats:{product_id}", "total_count", 1)
        if reordered == 1:
            r.hincrby(f"product:train:stats:{product_id}", "reordered_count", 1)

    print("✅ Train order_products naimportováno.")

# Spuštění importu
if __name__ == '__main__':
    # -- 4.1) products, aisles, departments --
    import_HSET_datasets()
    
    # -- 4.2) orders.csv a základní indexy --
    import_orders()

    # -- 4.3) order_products__prior.csv --
    import_order_products__prior()

    # -- 4.4) order_products__train.csv --
    import_order_products__train()


    # --- 5) END IMPORT ---
    # Set sentinel key to mark import as complete
    r.set('import:complete', '1')
    print("🎉 Import dat dokončen.")
