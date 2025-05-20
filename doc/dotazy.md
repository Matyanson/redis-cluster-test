# Vytváření a úpravy dat (Insert/Update)

## 1.1 Vložit nový produkt do uličky a vrátit detail hash

    MULTI
    HSET product:{100}:hash name "Organic Milk" aisle_id "102" department_id "7"
    HGETALL product:{100}:hash
    EXEC
    
    SADD products:by_aisle:{102} 100

- **Obecné chování (MULTI/EXEC)**:  
  - `HSET …` vytvoří hash `product:{3007}:hash` s třemi poli.  
  - `SADD …` vloží ID `3007` do setu produktů pro uličku `102`.  
  - `HGETALL …` vrátí všechny pole z právě vytvořeného hash.  

## 1.2 Aktualizovat `order_number` v objednávce a vrátit celý hash

    EVAL "
      redis.call('HSET', KEYS[1], 'order_number', ARGV[1])
      return redis.call('HGETALL', KEYS[1])
      " 1 order:{8382}:hash 8

- **Obecné chování (EVAL/Lua)**:  
  - `HSET order:{1002}:hash order_number 8` – přepíše `order_number` na `8`.  
  - `HGETALL order:{1002}:hash` – vrátí všechny páry `field:value` z hashe.  
  - Lua vrátí pole: `[ "user_id","2345","order_number","8","order_dow","3", … ]`.  
- **Konkrétně**:  
  - Klíč `order:{1002}:hash` leží ve slotu `{1002}`, takže Lua pracuje výhradně v tomto sloku → CROSSSLOT‑free.  
  - Vrátili jsme kompletní hash v jednom volání.
  
## 1.3 Přidat položku do `order:8382:products` a vrátit 2 poslední položky

    EVAL "
      local top = redis.call('ZRANGE', KEYS[1], -1, -1, 'WITHSCORES')
      local max_score = 0
      if #top > 0 then
        max_score = tonumber(top[2])
      end

      local new_score = max_score + 1

      redis.call('ZADD', KEYS[1], new_score, ARGV[1])

      return redis.call('ZREVRANGE', KEYS[1], 0, 1, 'WITHSCORES')
      " 1 order:{8382}:products 23

- Obecné chování (EVAL/Lua):

  1. ZRANGE order:{8382}:products -1 -1 WITHSCORES – vrátí nejvyšší existující skóre ve formě `{ <member>, <score> }`.

  2. Pokud existuje alespoň jeden prvek, top[2] je jeho skóre. Pokud je set prázdný, max_score zůstane 0.

  3. new_score = max_score + 1 zajistí, že nový produkt (ID 23) bude mít o jedno vyšší skóre než dosud nejvyšší.

  4. ZADD order:{8382}:products new_score 23 – vloží produkt 23 s novým skóre.

  5. ZREVRANGE order:{8382}:products 0 1 WITHSCORES – vrátí pole dvou prvků:

    - `[ <member1>, <score1>, <member2>, <score2> ]`,

    - kde `<member1>` je produkt s nejvyšším skóre a `<member2>` je ten se druhým nejvyšším.

## 1.4 Aktualizace dne v objednávce (hash + sety)

    MULTI
    HGET order:{2539329} order_dow
    HSET order:{2539329} order_dow 6
    SREM orders:day:2:{2539329} 2539329
    SADD orders:day:6:{2539329} 2539329
    EXEC
- Obecně:

    1. HGET order:123456 order_dow vrátí původní den (2).

    2. HSET změní order_dow na 5 (pátek).

    3. SREM odebere 123456 z setu orders:day:2.

    4. SADD přidá 123456 do setu orders:day:5.

- Konkrétně: Příklad, kdy jsme u objednávky 123 456 špatně zapsali den ‒ protože se olouplo data od zákazníků, opravíme ho a přesuneme indexy.

- Výsledek: Příkaz vrátí (integer) 2 pro HGET (řekne „2“), (integer) 0/1 pro HSET (0 = pole už existovalo), (integer) 1 pro SREM/SADD.

## 1.5 Aktualizovat aisle_id u produktu a vrátit předchozí i novou hodnotu

    EVAL "
      local prev = redis.call('HGET', KEYS[1], 'aisle_id')
      redis.call('HSET', KEYS[1], 'aisle_id', ARGV[1])
      return {prev, ARGV[1]}
    " 1 product:{160}:hash 37

- Obecné chování:

  1. HGET product:{160}:hash 'aisle_id' → vrátí starou hodnotu (např. "30").

  2. HSET product:{160}:hash 'aisle_id' ARGV[1] → přepíše aisle_id na "37".

  3. Lua vrátí { prev, new } (např. { "101", "37" }).

## 1.6 Změnit days_since_prior_order v objednávce a vrátit předchozí i novou hodnotu

    EVAL "
      local old = redis.call('HGET', KEYS[1], 'days_since_prior_order')
      redis.call('HSET', KEYS[1], 'days_since_prior_order', ARGV[1])
      return { old, ARGV[1] }
      " 1 order:{327827}:hash 14

- Obecné chování (EVAL/Lua):

  1. HGET order:{1002}:hash 'days_since_prior_order' → vrátí původní počet dní (např. "7").
  2. HSET order:{1002}:hash 'days_since_prior_order' ARGV[1] → změní na "14".
  3. Lua vrátí { old, new } např. { "7", "14" }.


# Kategorie 2: Mazání a čištění dat (Delete/Remove)

## 2.1 Odstranit produkt z objednávky a vrátit nový počet položek

    MULTI
    ZREM order:{738281}:products 21150
    ZCARD order:{738281}:products
    EXEC

* Obecné chování:

  1. `ZREM … 3003` → odstraní člena „3003“ ze Sorted Setu

  2. `ZCARD …` → vrátí aktuální počet členů (nově např. 4)

## 2.2 Smazat kompletně všechna data uživatele 44

    EVAL "
      redis.call('DEL', KEYS[1])
      redis.call('DEL', KEYS[2])
      redis.call('DEL', KEYS[3])
      return 1
    " 3 user:{44}:orders user:{44}:products user:{44}:reordered_products

- Obecné chování:

  1. DEL user:{2001}:orders

  2. DEL user:{2001}:products

  3. DEL user:{2001}:reordered_products

  4. vrátí 1 (úspěch)

## 2.3 Smazat uličku a související set produktů v ni

    EVAL "
      local name = redis.call('HGET', KEYS[1], 'name')
      redis.call('DEL', KEYS[1])
      redis.call('DEL', KEYS[2])
      return 'aisle ' .. name .. ' removed successfully'
      " 2 aisle:{10}:hash products:by_aisle:{10}

- Obecné chování:

  1. Smaže aisle:{10}:hash i products:by_aisle:{10}

  2. Vrátí potvrzující zprávu: 'aisle ' .. name .. ' removed successfully'

## 2.4 Smazat department a související set produktů v něm

    EVAL "
      local name = redis.call('HGET', KEYS[1], 'name')
      redis.call('DEL', KEYS[1])
      redis.call('DEL', KEYS[2])
      return 'department ' .. name .. ' removed successfully'
      " 2 department:{5}:hash products:by_department:{5}

- Obecné chování:

  1. Smaže department:{10}:hash i products:by_department:{10}

  2. Vrátí potvrzující zprávu: 'department ' .. name .. ' removed successfully'


## 2.5 Odstranit produkt z `user:64:products` a vrátit počet zbylých produků
    EVAL "
      local removed = redis.call('SREM', KEYS[1], ARGV[1])
      local remaining = redis.call('SCARD', KEYS[1])
      return {removed, remaining}
      " 1 user:{64}:products 401

- **Obecné chování (EVAL)**:  
  1. `SREM user:{2003}:products 3007` – odebere produkt `3007`, vrátí `(integer) 1` pokud existoval.  
  2. `SCARD user:{2003}:products` – vrátí nový počet (např. `15`).  
  3. Lua vrátí `[1, 15]`.  
- **Konkrétně**:  
  - Klíč `user:{2003}:products` má hashtag `{2003}` → CROSSSLOT‑free.


## 2.6 Smazat všechny globální statistiky

    MULTI
    DEL {agg}:products:frequency
    DEL {agg}:products:reorder_count
    DEL {agg}:users:order_count
    DEL {agg}:users:distinct_reorders
    EXEC

- Obecné chování:

  - atomicky odstraní všechny {agg} sety

# Kategotie 3 Získávání a prohlížení dat (Read/Retrieval)

## 3.1 Vypsat všechny produkty v objednávce s jejich „pořadím v košíku“
    ZRANGE order:{444309}:products 0 -1 WITHSCORES

- Obecné chování:

  - Vrátí kompletní seznam párů <product_id>, <score> ze Sorted Setu order:{444309}:products, seřazených podle skóre.

## 3.1.2

    EVAL "
      local detail = redis.call('HGETALL', KEYS[1])
      local products = redis.call('ZRANGE', KEYS[2], 0, -1)
      local count = redis.call('ZCARD', KEYS[2])
      return { detail, products, count }
    " 2 order:{444309}:hash order:{444309}:products

- Obecné chování (EVAL):

  1. HGETALL order:{1001}:hash → vrátí všechny páry klíč/hodnota z hashe objednávky.

  2. ZRANGE order:{1001}:products 0 -1 → vrátí všechny ID produktů (bez skóre) v pořadí v košíku.

  3. ZCARD order:{1001}:products → vrátí počet produktů v objednávce.

  4. Lua zabalí výsledky do seznamu:

      - prvek 1 = pole detailních vlastností objednávky,

      - prvek 2 = pole product_id,

      - prvek 3 = integer s počtem produktů.

## 3.2 Vrátit počet objednávek uživatele + počet unikátních produktů, které kdy koupil

    EVAL "
      local orders_count   = redis.call('SCARD', KEYS[1])
      local products_count = redis.call('SCARD', KEYS[2])
      return {orders_count, products_count}
      " 2 user:{20}:orders user:{20}:products

- Obecné chování:

  - SCARD user:{20}:orders → např. 15

  - SCARD user:{20}:products → např. 42

  - Lua vrací [15, 42]

## 3.3 Vrátit detail oddělení + seznam všech produktů v něm

EVAL "
  local detail = redis.call('HGETALL', KEYS[1])
  local prods  = redis.call('SMEMBERS',  KEYS[2])
  return {detail, prods}
  " 2 department:{4}:hash products:by_department:{4}

- Obecné chování:

  - HGETALL department:{4}:hash → { name, "Produce" }

  - SCARD products:by_department:{4} → např. 32

  - Lua vrací [ detail_map, 32 ]

## 3.4 Zobrazení všech dat uživatele

    EVAL "
      local a = redis.call('SMEMBERS', KEYS[1])
      local b = redis.call('SMEMBERS', KEYS[2])
      local c = redis.call('SMEMBERS', KEYS[3])
      return {
        {'orders', a},
        {'products', b},
        {'reordered_products', c}
      }
      " 3 user:{44}:orders user:{44}:products user:{44}:reordered_products

- SMEMBERS načte všechny prvky (členy) z daných Redis množin:

  - a = všechny objednávky uživatele (user:{44}:orders)

  - b = všechny produkty přidané uživatelem (user:{44}:products)

  - c = všechny produkty, které uživatel znovu objednal (user:{44}:reordered_products)

- Skript vrátí strukturovaný výstup jako seznam trojic (orders, products, reordered_products)

## 3.5 Vrátit intersection mezi všemi produkty uživatele a produkty, které přeobjednal

    EVAL "
      local all      = redis.call('SMEMBERS',   KEYS[1])
      local reordered = redis.call('SMEMBERS',  KEYS[2])
      local set_all   = {}
      for _, pid in ipairs(all) do
        set_all[pid] = true
      end
      local intersection = {}
      for _, pid in ipairs(reordered) do
        if set_all[pid] then
          table.insert(intersection, pid)
        end
      end
      local cnt = #intersection
      return {cnt, intersection}
    " 2 user:{44}:products user:{44}:reordered_products

- Obecné chování (EVAL):

  1. SMEMBERS user:{44}:products → získá seznam všech product_id, které uživatel 44 kdy koupil.

  2. SMEMBERS user:{44}:reordered_products → získá seznam produktů, které uživatel 44 označil jako „reordered“.

  3. V Lua se vytvoří dočasná tabulka (set_all), kde se všechny ID z prvního setu uloží jako klíče (pro rychlé hledání).

  4. Prochází se druhý seznam (reordered); pokud se pid nachází i v set_all, přidá se do výsledné tabulky intersection.

  5. cnt = #intersection spočítá velikost průniku.

  6. Lua vrátí { cnt, intersection }, tj. pole:

      - prvek 1 = integer (např. 3), 

      - prvek 2 = pole <product_id> (např. { "3001","3050","3075" }).

- Konkrétně:

  - Operace probíhají pouze nad klíči:

    - user:{44}:products

    - user:{44}:reordered_products

  - Oba klíče sdílejí stejný hashtag {44}, takže nedojde k CROSSSLOT.

  - Tento dotaz vrátí:

    1. Počet produktů, které uživatel 44 koupil a současně je později přeobjednal.

    2. Přesný seznam těchto product_id.

# 3.5.2 Intersection setů jednoduššeji

    EVAL "
      local inter = redis.call('SINTER', KEYS[1], KEYS[2])
      return { #inter, inter }
      " 2 user:{44}:products user:{44}:reordered_products

1. SINTER user:{44}:products user:{44}:reordered_products – přímo vrátí všechny product_id, které jsou v obou setech.

2. #inter (v Lua) zjistí počet prvků v této průnikové tabulce.

3. Lua vrátí pole, jehož prvek 1 je počet (např. 3) a prvek 2 je samotný seznam product_id (např. { "3001","3050","3075" }).

## 3.6 Vrátit první a poslední produkt v objednávce 

    EVAL "
      local first_pair  = redis.call('ZRANGE',   KEYS[1], 0,   0,   'WITHSCORES')
      local last_pair   = redis.call('ZRANGE',   KEYS[1], -1, -1, 'WITHSCORES')
      return { first_pair, last_pair }
    " 1 order:{327827}:products

- Obecné chování (EVAL):

  1. ZRANGE order:{1001}:products 0 0 WITHSCORES → vrátí pole { <first_product_id>, <first_score> }.

  2. ZRANGE order:{1001}:products -1 -1 WITHSCORES → vrátí pole { <last_product_id>, <last_score> }.

  3. Lua vrátí seznam dvou prvků:

    - prvek 1 = první dvojice [ product_id, score ],

    - prvek 2 = poslední dvojice [ product_id, score ].



# Kategorie 4: Agregační a analytické dotazy (Aggregation & Analytics)

## 4.1 Zjistit, kolik produktů patří do oddělení 4 + vrátit jeho jméno

    EVAL "
      local name = redis.call('HGET', KEYS[1], 'name')
      local cnt  = redis.call('SCARD', KEYS[2])
      return {name, cnt}
      " 2 department:{7}:hash products:by_department:{7}

- Obecné chování:

  - HGET … 'name' → "Beverages"

  - SCARD … → např. 280

  - Lua vrátí [ "Beverages", 280 ]

## 4.2 Vypsat Top 5 produktů dle celkové frekvence objednávek

    ZREVRANGE {agg}:products:frequency 0 4 WITHSCORES

- Obecné chování:

  - Vrátí prvních 5 <product_id> z {agg}:products:frequency (Sorted Set) seřazených sestupně podle skóre a zároveň jejich skóre.

## 4.3 Vypsat Top 5 produktů dle počtu přeobjednání

    ZREVRANGE {agg}:products:reorder_count 0 4 WITHSCORES

- Obecné chování:

  - Vrátí „Top 5“ <product_id> z {agg}:products:reorder_count s jejich hodnotami (počty).

## 4.4 Vypsat Top 5 uživatelů dle počtu objednávek

    ZREVRANGE {agg}:users:order_count 0 4 WITHSCORES

- Obecné chování:

  - Vrátí „Top 5“ <user_id> z {agg}:users:order_count, s jejich skóre.

## 4.5 Spočítat celkový počet objednávek napříč všemi uživateli

    EVAL "
      local members = redis.call('ZRANGE', KEYS[1], 0, -1, 'WITHSCORES')
      local sum = 0
      for i=2,#members,2 do
      sum = sum + tonumber(members[i])
      end
      return sum
      " 1 {agg}:users:order_count

- **Obecné chování (EVAL/Lua)**:  
  1. `ZRANGE {agg}:users:order_count 0 -1 WITHSCORES` vrátí pole `[ user1,orders1, user2,orders2, … ]`.  
  2. Lua prochází skóre (`members[2]`, `members[4]`, …) a sčítá je.  
  3. Vrátí součet, např. `1500` pokud je celkem 1 500 objednávek.  
- **Konkrétně**:  
  - Jediný klíč `{agg}:users:order_count` → ve slotu `{agg}` → CROSSSLOT‑free.

## 4.6 Zjistit počet položek ve všech globálních ZSetech (frequency, reorder_count, order_count, distinct_reorders)

    EVAL "
    local fcnt = redis.call('ZCARD', KEYS[1])
    local rcnt = redis.call('ZCARD', KEYS[2])
    local ocnt = redis.call('ZCARD', KEYS[3])
    local dcnt = redis.call('ZCARD', KEYS[4])
    return {fcnt, rcnt, ocnt, dcnt}
    " 4 {agg}:products:frequency {agg}:products:reorder_count {agg}:users:order_count {agg}:users:distinct_reorders

- **Obecné chování**:  
  1. `ZCARD {agg}:products:frequency` → počet produktů se sledovanou frekvencí.  
  2. `ZCARD {agg}:products:reorder_count` → počet produktů s reorder count.  
  3. `ZCARD {agg}:users:order_count` → počet uživatelů s počtem objednávek.  
  4. `ZCARD {agg}:users:distinct_reorders` → počet uživatelů se záznamem unikátních reorderů.  
  5. Lua vrátí pole `[fcnt, rcnt, ocnt, dcnt]`.  
- **Konkrétně**:  
  - Všechny čtyři klíče leží ve slotu `{agg}` → atomické.

# Kategorie 5: Transakce a hromadné/batch operace

## 5.1 Získat detaily objednávky + počet produktů v objednávce (v jedné atomické operaci)

    EVAL "
      local details = redis.call('HGETALL', KEYS[1])
      local count   = redis.call('ZCARD',   KEYS[2])
      return { details, count }
      " 2 order:{2539329}:hash order:{2539329}:products

**Obecné chování (EVAL)**: Spustí LUA skript, kde se všechny příkazy vykonají atomicky na jednom slotu.
- **Konkrétně**:
  - `HGETALL order:{1001}:hash` vrátí pole `{ 'user_id', '1234', 'order_number', '4', … }`.
  - `ZCARD order:{1001}:products` vrátí počet členů ve Sorted Setu produktů (např. `5`).
  - Skript vrátí list, kde první položka je pole detailů a druhá položka je počet.

## 5.2 Přidat nový produkt do objednávky a vrátit kompletní seznam produktů seřazený dle pořadí v košíku

    MULTI
    ZADD order:{8382}:products 3 3005
    ZRANGE order:{8382}:products 0 -1 WITHSCORES
    EXEC

- **Obecné chování (MULTI/EXEC)**: Všechny příkazy mezi MULTI a EXEC půjdou na stejný slot (hashtag `{1001}`) a provedou se atomicky.
- **Konkrétně**:
  1. `ZADD order:{1001}:products 3 3005` přidá produkt s ID `3005` s pořadím `3`.
  2. `ZRANGE order:{1001}:products 0 -1 WITHSCORES` vrátí např. `{ '3001', '1', '3003', '2', '3005', '3', … }`.

## 5.3 záloha uživatele

    EVAL "
      local total = {}

      for i, key in ipairs(KEYS) do
        local backup_key = 'backup:' .. key
        local cnt = redis.call('SUNIONSTORE', backup_key, key)
        local card = redis.call('SCARD', backup_key)
        table.insert(total, {key, cnt, card})
      end

      return total
      " 3 user:{20}:products user:{20}:orders user:{20}:reordered_products

- Pro každý klíč v KEYS:

  - Vytvoří záložní klíč s prefixem backup:

  - Pomocí SUNIONSTORE nakopíruje obsah

  - Vrátí původní název, počet zkopírovaných členů (cnt), a počet členů v záloze (card)

  - Funguje pro libovolný počet klíčů


## 5.4 Vytvořit novou objednávku i přiřadit položky v rámci jedné (vlastně dvou) atomické transakce

    MULTI
    HSET order:{1004}:hash user_id "50" order_number "1" order_dow "6" order_hour_of_day "18" days_since_prior_order "NULL"
    ZADD order:{1004}:products 1 3011 2 3022 3 3033
    EXEC

    MULTI
    SADD user:{50}:orders 1004
    SMEMBERS user:{50}:orders
    EXEC

    ZINCRBY {agg}:users:order_count 1 50

- **Obecné chování**:  
  1. `HSET order:{1004}:hash …` – vytvoří hash objednávky `1004`.  
  2. `ZADD order:{1004}:products 1 3011 2 3022 3 3033` – vloží tři produkty s pořadím (1, 2, 3).  
  3. `SADD user:{50}:orders 1004` – přidá `1004` do uživatele `50`.  
  4. `ZINCRBY {agg}:users:order_count 1 50` – navyšuje ZSet uživatelských objednávek.  
  5. EXEC zabezpečí, že všechny čtyři příkazy běží atomicky.  


## 5.5 Smazat objednávku včetně jejího seznamu produktů

    EVAL "
      redis.call('DEL', KEYS[1])
      redis.call('DEL', KEYS[2])
      return 1
      " 2 order:{423262}:hash order:{423262}:products

- **Obecné chování**:  
  1. `DEL order:{423262}:hash` – smaže hash objednávky.  
  2. `DEL order:{423262}:products` – smaže sorted set produktů.  
  3. Lua vrátí `1` (úspěch).  
- **Konkrétně**:  
  - Oba klíče spadají do slotu `{423262}` → atomické.

## 5.6 Odebrání produktu z globálních statistik

    EVAL "
      local product_id = ARGV[1]
      local removed1 = redis.call('ZREM', KEYS[1], product_id)
      local removed2 = redis.call('ZREM', KEYS[2], product_id)
      return removed1 + removed2
    " 2 {agg}:products:reorder_count {agg}:products:frequency 6182

- **Obecné chování**
  - ZREM odebere product_id z obou zadaných ZSETů
  - Vrací součet počtů odebraných záznamů (0–2)



