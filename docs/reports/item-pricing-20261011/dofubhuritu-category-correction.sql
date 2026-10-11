-- Applied and verified through the live shop API on2026-10-11: Dofus now has6 articles.
-- Move the existing Dofub'huritu article into Dofus (safe to reapply).
-- Native reference29456: type646, RELIC, level230, equipment slot17.
-- Preserve the reviewed7,300,000-kama price, visibility, identity and receipts.
-- The deployed catalog revision trigger invalidates Redis automatically.
BEGIN;
SET LOCAL lock_timeout = '5s';
DO $$
BEGIN
    IF (SELECT count(*) FROM shop_articles WHERE item_ref = 29456 AND enabled) <> 1 THEN
        RAISE EXCEPTION 'Expected one active Dofub''huritu article; review catalog drift';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM shop_categories WHERE key = 'dofus' AND enabled) THEN
        RAISE EXCEPTION 'Dofus category is missing or disabled';
    END IF;
END;
$$;
UPDATE shop_articles SET category = 'dofus'
WHERE item_ref = 29456 AND enabled AND category <> 'dofus';
COMMIT;
SELECT id, name, item_ref, category, price_kamas, enabled
FROM shop_articles WHERE item_ref = 29456;
