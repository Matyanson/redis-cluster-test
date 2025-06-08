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
(3_500_000 řádků)

    order_id,user_id,eval_set,order_number,order_dow,order_hour_of_day,days_since__order
    sorted_by: user_id, order_number

## Order products train (poslední objednávka)
(1_400_000 řádků)

    order_id,product_id,add_to_cart_order,reordered
    sorted_by: order_id, add_to_cart_order

## Order products  (všechny ostatní objednávky)
(32_500_000 řádků)

    order_id,product_id,add_to_cart_order,reordered
    sorted_by: order_id, add_to_cart_order

## Products
(50_000 řádků)

    product_id,product_name,aisle_id,department_id
    sorted_by: product_id

## Ailes
(135 řádků)

    aisle_id,aisle
    sorted_by: aisle_id

## Departments
(22 řádků)

    department_id,department
    sorted_by: department_id



# Redis db

## Products
    # Detail jednoho produktu
    HSET   product:{<product_id>}:hash
           "name"        <product_name>
           "aisle_id"    <aisle_id>
           "department_id"     <department_id>

    # Všechny ID produktů v jedné uličce
    SADD   products:by_aisle:{<aisle_id>}      <product_id>

    # Všechny ID produktů v jednom oddělení
    SADD   products:by_department:{<department_id>}  <product_id>


## Aisles
    # Detail jedné uličky
    HSET   aisle:{<aisle_id>}:hash
           "name"        <aisle>
    # Klíč `aisle:{id}:hash` ve slotu podle `{<aisle_id>}`.

## Departments
    # Detail jednoho oddělení
    HSET   department:{<department_id>}:hash
           "name"        <department>
    # Klíč `department:{id}:hash` ve slotu podle `{<department_id>}`.

## Orders
    # Detail jedné objednávky
    HSET   order:{<order_id>}:hash
           "user_id"                 <user_id>
           "order_number"            <order_number>
           "order_dow"               <order_dow>
           "order_hour_of_day"       <order_hour_of_day>
           "days_since_prior_order"  <days_since_prior_order>

    # Set všech objednávek podle dne v týdnu (0–6)
    SADD   orders:by_day:{<order_dow>}    <order_id>

    # Set všech objednávek, které uživatel kdy udělal
    SADD   user:{<user_id>}:orders        <order_id>

    # Sorted Set celkového počtu objednávek uživatelů 
    ZINCRBY {agg}:users:order_count      1   <user_id>

## Order‑Products
    # Sorted Set všech produktů v konkrétní objednávce
    ZADD order:{<order_id>}:products   <cart_order> <product_id>

    # Set všech unikátních produktů, které uživatel koupil
    SADD user:{<user_id>}:products      <product_id>

    Pokud `reordered=1`:
        # Set přeobjednaných produktů od uživatele
        SADD user:{<user_id>}:reordered_products   <product_id>

    # Globální frekvence (kolikrát se produkt objevil v jakékoli objednávce)
    ZINCRBY {agg}:products:frequency    1   <product_id>
    
    # Globální počet přeobjednání
    ZINCRBY {agg}:products:reorder_count   1   <product_id>

## Globální agregace
    # Top N produktů dle frekvence
    ZREVRANGE {agg}:products:frequency 0 9 WITHSCORES

    # Top N produktů dle počtu přeobjednání
    ZREVRANGE {agg}:products:reorder_count 0 9 WITHSCORES

    # Počet objednávek každého uživatele
    ZREVRANGE {agg}:users:order_count 0 -1 WITHSCORES

    # Počet unikátních přeobjednaných produktů na uživatele
    ZREVRANGE {agg}:users:distinct_reorders 0 -1 WITHSCORES

## Klíčové hashtagy (pro Redis Cluster sloty)
- `{<product_id>}` → všechny klíče `product:{<product_id>}:hash`
- `{<aisle_id>}` → `aisle:{<aisle_id>}:hash` a rejstřík `products:by_aisle:{<aisle_id>}`
- `{<department_id>}` → `department:{<department_id>}:hash` a rejstřík `products:by_department:{<department_id>}`
- `{<user_id>}` → všechny klíče `user:{<user_id>}:*`
- `{<order_id>}` → všechny klíče `order:{<order_id>}:*`
- `{<order_dow>}` → klíč `orders:by_day:{<order_dow>}`
- `{agg}` → všechny globální agregace (`products:frequency`, `products:reorder_count`, `users:order_count`, `users:distinct_reorders`)

---

### 🚀 Vysvětlení a výhody tohoto návrhu

1. **Singular vs. Plural**  
   - Jednotlivé objekty:  
     - `product:{id}:hash` – singular, protože odkazuje na přesně jeden produkt.  
     - `order:{id}:hash` – singular, jeden záznam o objednávce.  
     - `aisle:{id}:hash`, `department:{id}:hash`, `user:{id}:hash` – každý singular.  
   - Kolekce (Sets / ZSets) používají plurál:  
     - `products:by_aisle:{aisle_id}`, `products:by_department:{dept_id}`,  
     - `user:{user_id}:orders`, `user:{user_id}:products`, `order:{order_id}:products`,  
     - Globální ZSets: `{agg}:products:frequency`, `{agg}:users:order_count`, atd.

2. **Sloučení „prior“ a „train“**  
   - Při importu `order_products__prior.csv` i `order_products__train.csv` stavíme stejnou strukturu:  
     - `order:{order_id}:products`,  
     - globální agregace `{agg}:products:frequency`  
   - Odpadá potřeba `orders:by_eval:*` i duplikace ZSetů.

3. **Máme pouze jeden slot pro globální agregace**  
   - Všechny klíče začínající `{agg}:…` leží ve stejném slotu, takže LUA skript nad nimi nikdy nepadne na `CROSSSLOT`.  

4. **Entitní hashtagy (uživatel, objednávka, produkt) umožňují per‑entity operace v jednom Lua/MULTI**  
   - Např. „vlož objednávku #123456 + položky + přidej do `user:{uid}:orders`“ ale protože `orders:{123456}` a `user:{uid}` mají ODLIŠNÉ hashtagy, musíme:  
     1. nejprve spustit Lua nad `order:{123456}:*` (slot `{123456}`) pro vložení detailů a položek,  
     2. pak (ve druhém kroku) spustit Lua nad `user:{uid}:orders` (slot `{uid}`) pro přidání do Setu.  

5. **Indexy pro dotazy**  
   - „Unwind + Group + Sort“ → většina agregací typu „Top N produktů“ aj. čte přímo jediné ZSety `{agg}:*`.  
   - „Které produkty koupil uživatel X?“ → čteme `user:{X}:products` (slot `{X}`), pak můžeme i `HGETALL product:{pid}:hash` pro každý `pid`.  
   - „Kolik produktů bylo v objednávce Y?“ → `SCARD order:{Y}:products`. 

6. **Minimální CROSSSLOT**  
   - Pouze při operacích, kde jednoznačně potřebuji “vložit objednávku i do uživatele” v jednom kroku.  
   - V ostatních případech se transakce rozdělí na dva Lua bloky (per slot).  

Tímto způsobem máme:
- **Čisté, jednoznačné klíče** (singular/plural, jasné hashtagy),
- **Efektivní shardování** nad 3 mastery,
- **Jednoduché globální agregace** (slot `{agg}`),
- **Možnost psát netriviální dotazy** formou Lua (bez CROSSSLOT) nebo per‑shard map/reduce.
