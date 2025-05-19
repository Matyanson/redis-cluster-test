https://www.kaggle.com/datasets/psparks/instacart-market-basket-analysis

# Data explanation
## 📂 Přehled a význam jednotlivých CSV souborů (Instacart)
Toto je datová sada z Instacart Market Basket Analysis, která zachycuje nákupy zákazníků v reálném čase. Níže je popis všech CSV:

### ✅ products.csv
Popis: Obsahuje seznam všech produktů.

    Sloupec	Význam
    product_id	Unikátní ID produktu
    product_name	Název produktu
    aisle_id	Odkaz na aisles
    department_id	Odkaz na departments

### ✅ aisles.csv
Popis: Popisuje uličky v obchodě (např. "mléčné výrobky", "ovoce", ...).

    Sloupec	Význam
    aisle_id	Unikátní ID uličky
    aisle	Název uličky

### ✅ departments.csv
Popis: Širší členění obchodních oddělení (např. "chlazené", "trvanlivé potraviny").

    Sloupec	Význam
    department_id	Unikátní ID oddělení
    department	Název oddělení

### ✅ orders.csv
Popis: Seznam všech objednávek každého zákazníka.

    Sloupec	Význam
    order_id	Unikátní ID objednávky
    user_id	Zákazník
    eval_set	Určuje, do jaké sady patří: "", "train", nebo "test"
    order_number	Kolikátá objednávka daného uživatele to byla
    order_dow	Den v týdnu (0 = neděle)
    order_hour_of_day	Hodina odeslání
    days_since__order	Kolik dní od poslední objednávky

### 🟡 order_products__.csv
Popis: Obsahuje položky z minulých objednávek (historie) – slouží jako vstupní data pro trénink modelu doporučování.

    Sloupec	Význam
    order_id	ID objednávky
    product_id	Produkt
    add_to_cart_order	Pořadí přidání do košíku
    reordered	1 = uživatel už dříve koupil daný produkt, 0 = nový produkt

✅ Vztah: order_id je klíč do orders.csv, kde eval_set == ""

### 🟡 order_products__train.csv
Popis: Obsahuje produkty z objednávek určených pro trénování modelu.

    Sloupec	Význam
    order_id	ID objednávky
    product_id	Produkt
    add_to_cart_order	Pořadí přidání
    reordered	Produkt byl znovu objednán?

✅ Vztah: order_id je klíč do orders.csv, kde eval_set == "train"

🧠 Shrnutí datových vztahů

    graph TD
    A[users] --> B[orders.csv]
    B --> C[order_products__.csv]
    B --> D[order_products__train.csv]
    C --> E[products.csv]
    D --> E
    E --> F[aisles.csv]
    E --> G[departments.csv]

# Original dataset
## Orders
    order_id,user_id,eval_set,order_number,order_dow,order_hour_of_day,days_since__order
    sorted_by: user_id, order_number

## Order products train (poslední objednávka)
    order_id,product_id,add_to_cart_order,reordered
    sorted_by: order_id, add_to_cart_order

## Order products  (všechny ostatní objednávky)
    order_id,product_id,add_to_cart_order,reordered
    sorted_by: order_id, add_to_cart_order

## Products
    product_id,product_name,aisle_id,department_id
    sorted_by: product_id

## Ailes
    aisle_id,aisle
    sorted_by: aisle_id

## Departments
    department_id,department
    sorted_by: department_id



# Redis db

## Products
    HSET product:{<product_id>}:info {
        product_name,
        aisle_id,
        department_id
    }
    # Statistiky (počet prodejů a počty opakovaných objednávek) – ve stejném hashtagu {product_id}
    HSET product:{<product_id>}:stats {
        total_count,
        reordered_count
    }
    # Populárnost produktu (celkové prodeje, používáme ZINCRBY)
    ZINCRBY product:{<product_id>}:popularity 1 <product_id>

## Aisles
    HSET aisle:<aisle_id> {
        aisle
    }

## Departments
    HSET department:<department_id> {
        department
    }

## Orders
    HSET order:{<order_id>}:info {
        user_id,
        order_number,
        order_dow,
        order_hour_of_day,
        days_since_prior_order
    }
    # Seznam všech objednávek pro konkrétního uživatele
    SADD user:{<user_id>}:orders <order_id>
    # Všechny objednávky seskupené podle dne v týdnu
    SADD orders:day:<order_dow> <order_id>
    # Počet objednávek na uživatele (sorted set), uživatel vkládá s +1 při nové objednávce
    ZINCRBY user:order_count 1 <user_id>

## Order-products
    # Pro každý řádek (order_id, product_id, add_to_cart_order, reordered) vložíme:
    #   - ZSET, kde klíč obsahuje hashtag {order_id}, aby veškeré operace nad jedním order_id byly ve stejném slotu
    ZADD order:{<order_id>}:products <add_to_cart_order> <product_id>

    # Produktu navíc navyšujeme statistiky:
    #   • ZINCRBY product:{<product_id>}:popularity (celkové prodeje)
    #   • Pokud reordered == 1, ZINCRBY product:{<product_id>}:reorder_count (opakováné objednávky)
    ZINCRBY product:{<product_id>}:popularity 1 <product_id>
    # pokud reordered == 1:
    ZINCRBY product:{<product_id>}:reorder_count 1 <product_id>

    # A navíc uložíme souhrn do hash:
    HINCRBY product:{<product_id>}:stats total_count 1
    # pokud reordered == 1:
    HINCRBY product:{<product_id>}:stats reordered_count 1
