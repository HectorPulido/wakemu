"""Export only static public shop configuration as replay-safe SQL.

Run with the existing database environment. No player, wallet, order, token or
inventory table is read. The output is an installation input, never a runtime
JSON catalog or permission to overwrite an operator's later edits.
"""
import hashlib
import json
import os
import sys


def literal(value):
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if type(value) is int:
        return str(value)
    if isinstance(value, str):
        return "'" + value.replace("'", "''") + "'"
    raise ValueError("Unexpected public shop configuration value")


def render(categories, articles):
    held = [row for row in articles if row["item_ref"] == 11387]
    if len(held) != 1 or held[0]["enabled"] is not False:
        raise ValueError("Special seed publication hold must remain disabled")
    digest = hashlib.sha256(
        json.dumps(
            dict(categories=categories, articles=articles),
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()
    out = [
        "-- Static public shop configuration; no player or commerce history.",
        "-- Source content SHA256: " + digest,
        "-- 11387 remains disabled: native bIg outcome is not qualified.",
        "BEGIN;",
        "SET LOCAL standard_conforming_strings = on;",
        "CREATE TEMP TABLE _shop_public_categories (LIKE shop_categories INCLUDING DEFAULTS) ON COMMIT DROP;",
        "CREATE TEMP TABLE _shop_public_articles (LIKE shop_articles INCLUDING DEFAULTS) ON COMMIT DROP;",
    ]
    columns = {
        "categories": ("id", "key", "name", "description", "sort_order", "enabled"),
        "articles": (
            "id",
            "key",
            "name",
            "description",
            "item_ref",
            "quantity",
            "price_kamas",
            "category",
            "enabled",
        ),
    }
    for kind, rows in (("categories", categories), ("articles", articles)):
        fields = columns[kind]
        for start in range(0, len(rows), 500):
            out.append(
                "INSERT INTO _shop_public_"
                + kind
                + " ("
                + ",".join(fields)
                + ") VALUES\n"
                + ",\n".join(
                    "(" + ",".join(literal(row[key]) for key in fields) + ")"
                    for row in rows[start : start + 500]
                )
                + ";"
            )
    out.append(
        """
CREATE TEMP TABLE _shop_migration_categories (LIKE shop_categories INCLUDING DEFAULTS) ON COMMIT DROP;
INSERT INTO _shop_migration_categories(id,key,name,description,sort_order,enabled) VALUES
 (1,'sets','Sets','',10,true),(2,'items','Objetos','',20,true),
 (3,'weapons','Armas','',30,true),(4,'appearances','Apariencias','',40,true),
 (5,'pets','Mascotas','',50,true),(6,'mounts','Monturas','',60,true),
 (7,'consumables','Consumibles','',70,true),(8,'resources','Recursos','',80,true),
 (9,'haven-bag','Merkasaco','',90,true);
CREATE TEMP TABLE _shop_migration_articles (LIKE shop_articles INCLUDING DEFAULTS) ON COMMIT DROP;
INSERT INTO _shop_migration_articles(id,key,name,description,item_ref,quantity,price_kamas,category,enabled)
VALUES(1,'gobbhammer','Jalamartillo',
 'Martillo de jalato. 1 OG = 1 kama: this purchase debits the same kama wallet.',2027,1,1000,'weapons',true);
DO $shop_public_seed$
DECLARE kind text; sequence_name text; highest bigint; current_value bigint;
BEGIN
 FOREACH kind IN ARRAY ARRAY['categories','articles'] LOOP
  -- Existing operator configuration must never silently become this export.
  IF kind='categories' THEN
   IF EXISTS(SELECT 1 FROM shop_categories c JOIN _shop_public_categories e USING(key)
      WHERE c IS DISTINCT FROM e AND NOT EXISTS(SELECT 1 FROM _shop_migration_categories b WHERE b=c))
      OR EXISTS(SELECT 1 FROM shop_categories c JOIN _shop_public_categories e USING(id) WHERE c.key<>e.key) THEN
    RAISE EXCEPTION 'Public shop category seed conflicts with existing operator configuration';
   END IF;
   IF EXISTS(SELECT 1 FROM shop_categories c JOIN _shop_public_categories e USING(key) WHERE c IS DISTINCT FROM e) THEN
    UPDATE shop_categories c SET name=e.name,description=e.description,sort_order=e.sort_order,enabled=e.enabled
     FROM _shop_public_categories e WHERE c.key=e.key AND c IS DISTINCT FROM e;
   END IF;
   IF EXISTS(SELECT 1 FROM _shop_public_categories e WHERE NOT EXISTS(SELECT 1 FROM shop_categories c WHERE c.key=e.key)) THEN
    INSERT INTO shop_categories SELECT e.* FROM _shop_public_categories e
     WHERE NOT EXISTS(SELECT 1 FROM shop_categories c WHERE c.key=e.key) ORDER BY e.id;
   END IF;
  ELSE
   IF EXISTS(SELECT 1 FROM shop_articles c JOIN _shop_public_articles e USING(key)
      WHERE c IS DISTINCT FROM e AND NOT EXISTS(SELECT 1 FROM _shop_migration_articles b WHERE b=c))
      OR EXISTS(SELECT 1 FROM shop_articles c JOIN _shop_public_articles e USING(id) WHERE c.key<>e.key) THEN
    RAISE EXCEPTION 'Public shop article seed conflicts with existing operator configuration';
   END IF;
   IF EXISTS(SELECT 1 FROM shop_articles c JOIN _shop_public_articles e USING(key) WHERE c IS DISTINCT FROM e) THEN
    UPDATE shop_articles c SET name=e.name,description=e.description,item_ref=e.item_ref,
      quantity=e.quantity,price_kamas=e.price_kamas,category=e.category,enabled=e.enabled
     FROM _shop_public_articles e WHERE c.key=e.key AND c IS DISTINCT FROM e;
   END IF;
   IF EXISTS(SELECT 1 FROM _shop_public_articles e WHERE NOT EXISTS(SELECT 1 FROM shop_articles c WHERE c.key=e.key)) THEN
    INSERT INTO shop_articles SELECT e.* FROM _shop_public_articles e
     WHERE NOT EXISTS(SELECT 1 FROM shop_articles c WHERE c.key=e.key) ORDER BY e.id;
   END IF;
  END IF;
  sequence_name := pg_get_serial_sequence('shop_'||kind,'id');
  EXECUTE format('SELECT max(id) FROM %I','shop_'||kind) INTO highest;
  current_value := pg_sequence_last_value(sequence_name::regclass);
  IF highest>coalesce(current_value,0) THEN
   PERFORM setval(sequence_name::regclass,highest,true);
  END IF;
 END LOOP;
END;
$shop_public_seed$;
COMMIT;
"""
    )
    return "\n".join(out) + "\n"


def main():
    from wakfu_server.store import Store

    store = Store(os.environ["WAKFU_DATABASE_URL"])
    try:
        with store.connection() as db:
            db.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
            categories = db.execute(
                "SELECT id,key,name,description,sort_order,enabled FROM shop_categories ORDER BY id"
            ).fetchall()
            articles = db.execute(
                "SELECT id,key,name,description,item_ref,quantity,price_kamas,category,enabled FROM shop_articles ORDER BY id"
            ).fetchall()
        sys.stdout.write(render(categories, articles))
    finally:
        store.close()


if __name__ == "__main__":
    main()
