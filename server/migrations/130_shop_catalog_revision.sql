-- Public shop caches are invalidated by both operator edits and direct SQL imports.
-- Idempotent so the isolated shop can bootstrap this DDL while World migrations
-- are pending; the normal contiguous migrator subsequently records this version.
CREATE TABLE IF NOT EXISTS shop_catalog_revision (
    id integer PRIMARY KEY CHECK (id = 1),
    revision bigint NOT NULL DEFAULT 1 CHECK (revision > 0)
);
INSERT INTO shop_catalog_revision(id) VALUES (1) ON CONFLICT(id) DO NOTHING;

CREATE OR REPLACE FUNCTION advance_shop_catalog_revision() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    UPDATE shop_catalog_revision SET revision = revision + 1 WHERE id = 1;
    RETURN NULL;
END;
$$;

DROP TRIGGER IF EXISTS shop_articles_catalog_revision ON shop_articles;
CREATE TRIGGER shop_articles_catalog_revision
AFTER INSERT OR UPDATE OR DELETE OR TRUNCATE ON shop_articles
FOR EACH STATEMENT EXECUTE FUNCTION advance_shop_catalog_revision();

DROP TRIGGER IF EXISTS shop_categories_catalog_revision ON shop_categories;
CREATE TRIGGER shop_categories_catalog_revision
AFTER INSERT OR UPDATE OR DELETE OR TRUNCATE ON shop_categories
FOR EACH STATEMENT EXECUTE FUNCTION advance_shop_catalog_revision();
