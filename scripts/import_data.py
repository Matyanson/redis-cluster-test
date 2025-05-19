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
    ('./data/products.csv', 'product', ['product_id', 'product_name', 'aisle_id', 'department_id']),
    ('./data/aisles.csv', 'aisle', ['aisle_id', 'aisle']),
    ('./data/departments.csv', 'department', ['department_id', 'department']),
    ('./data/orders.csv', 'order', ['order_id', 'user_id', 'eval_set', 'order_number', 'order_dow', 'order_hour_of_day', 'days_since_prior_order']),
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

def import_aisles():
    df_aisles = pd.read_csv('./data/aisles.csv')
    print(f"ℹ️  Načítání {len(df_aisles)} řádků z aisles.csv ...")

    for _, row in df_aisles.iterrows():
        aisle_id = str(row['aisle_id'])
        aisle  = str(row['aisle'])

        # 1) HSET do hashu aisle:{aisle_id}
        r.hset(
            f"aisle:{{{aisle_id}}}:hash",
            mapping={
                'name': aisle,
            }
        )

    print("✅ Aisles naimportovány.")

def import_departments():
    df_departments = pd.read_csv('./data/departments.csv')
    print(f"ℹ️  Načítání {len(df_departments)} řádků z departments.csv ...")

    for _, row in df_departments.iterrows():
        department_id = str(row['department_id'])
        department  = str(row['department'])

        # 1) HSET do hashu department:{department_id}
        r.hset(
            f"department:{{{department_id}}}:hash",
            mapping={
                'name': department,
            }
        )

    print("✅ Departments naimportovány.")

def import_products():
    df_products = pd.read_csv('./data/products.csv')
    print(f"ℹ️  Načítání {len(df_products)} řádků z products.csv ...")

    for _, row in df_products.iterrows():
        product_id = str(row['product_id'])
        product  = str(row['product_name'])
        aisle_id  = str(row['aisle_id'])
        department_id  = str(row['department_id'])

        # HSET do hashu product:{product_id}
        r.hset(
            f"product:{{{product_id}}}:hash",
            mapping={
                'name': product,
                'aisle_id': aisle_id,
                'department_id': department_id
            }
        )
        
        # Všechny ID produktů v jedné uličce
        # SADD   products:by_aisle:{<aisle_id>}      <product_id>
        r.sadd(f"products:by_aisle:{{{aisle_id}}}", product_id)

        # Všechny ID produktů v jednom oddělení
        # SADD   products:by_department:{<department_id>}  <product_id>
        r.sadd(f"products:by_department:{{{department_id}}}", product_id)


    print("✅ Products naimportovány.")

def import_orders():
    df_orders = pd.read_csv('./data/orders.csv')
    print(f"ℹ️  Načítání {len(df_orders)} řádků z orders.csv ...")

    for _, row in df_orders.iterrows():
        order_id = str(row['order_id'])
        user_id  = str(row['user_id'])
        # eval_set = str(row['eval_set'])       # prior/train
        order_number = str(row['order_number'])
        order_dow= str(row['order_dow'])
        order_hour = str(row['order_hour_of_day'])
        days_prior = str(row['days_since_prior_order'])

        # HSET do hashu orders:{order_id}
        r.hset(
            f"order:{{{order_id}}}:hash",
            mapping={
                'user_id': user_id,
                'order_number': order_number,
                'order_dow': order_dow,
                'order_hour_of_day': order_hour,
                'days_since_prior_order': days_prior
            }
        )

        # Set všech objednávek podle dne v týdnu (0–6)
        # SADD   orders:by_day:{<order_dow>}    <order_id>
        r.sadd(f"orders:by_day:{{{order_dow}}}", order_id)

        # Set všech objednávek, které uživatel kdy udělal
        # SADD   user:{<user_id>}:orders        <order_id>
        r.sadd(f"user:{{{user_id}}}:orders", order_id)

        # Sorted Set celkového počtu objednávek uživatelů 
        # ZINCRBY {agg}:users:order_count      1   <user_id>
        r.zincrby("{{agg}}:users:order_count", 1, user_id)

    print("✅ Orders naimportovány.")

def import_order_products():
    df_prior = pd.read_csv('./data/order_products__prior.csv')
    df_train = pd.read_csv('./data/order_products__train.csv')
    print(f"ℹ️  Načítání {len(df_prior)} řádků z order_products__prior.csv ...")
    print(f"ℹ️  Načítání {len(df_train)} řádků z order_products__train.csv ...")
    df_order_products = pd.concat([df_prior, df_train], ignore_index=True)

    for _, row in df_order_products.iterrows():
        order_id   = str(row['order_id'])
        product_id = str(row['product_id'])
        cart_order = int(row['add_to_cart_order'])
        reordered  = int(row['reordered'])

        # Sorted Set všech produktů v konkrétní objednávce
        # ZADD order:{<order_id>}:products   <product_id>
        r.zadd(f"order:{{{order_id}}}:products", {product_id: cart_order})

        user_id = r.hget(f"order:{{{order_id}}}:hash", "user_id")
        if(user_id):
            # Set všech unikátních produktů, které uživatel koupil
            # SADD user:{<user_id>}:products      <product_id>
            r.sadd(f"user:{{{user_id}}}:products", product_id)
        
        if(reordered == 1 and user_id):
            # Set přeobjednaných produktů od uživatele
            # SADD user:{<user_id>}:reordered_products   <product_id>
            r.sadd(f"user:{{{user_id}}}:reordered_products", product_id)

        if(reordered == 1):
            # Globální počet přeobjednání
            # ZINCRBY {agg}:products:reorder_count       1    <product_id> (reordered=1)
            r.zincrby("{{agg}}:products:reorder_count", 1, product_id)

        # Globální frekvence (kolikrát se produkt objevil v jakékoli objednávce)
        # ZINCRBY {agg}:products:frequency    1   <product_id>
        r.zincrby("{{agg}}:products:frequency", 1, product_id)

    print("✅ Prior order_products naimportováno.")


# Spuštění importu
def main():
    # -- 4.1) aisles --
    import_aisles()

    # -- 4.1) departments --
    import_departments()

    # -- 4.1) products --
    import_products()
    
    # -- 4.2) orders.csv a základní indexy --
    import_orders()

    # -- 4.3) order_products__prior.csv a order_products__train.csv --
    import_order_products()


    # --- 5) END IMPORT ---
    # Set sentinel key to mark import as complete
    r.set('import:complete', '1')
    print("🎉 Import dat dokončen.")

if __name__ == '__main__':
    main()