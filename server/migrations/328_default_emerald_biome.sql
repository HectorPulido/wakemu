-- Every account owns the real native Emerald Biome entitlement by default.
-- Keep existing quantities, including legitimately acquired duplicates.
INSERT INTO account_quest_items(account_id,reference,quantity)
SELECT id,32864,1 FROM accounts
ON CONFLICT(account_id,reference) DO NOTHING;

CREATE FUNCTION grant_default_emerald_biome() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    INSERT INTO account_quest_items(account_id,reference,quantity)
    VALUES(NEW.id,32864,1)
    ON CONFLICT(account_id,reference) DO NOTHING;
    RETURN NEW;
END;
$$;

CREATE TRIGGER account_default_emerald_biome
AFTER INSERT ON accounts
FOR EACH ROW EXECUTE FUNCTION grant_default_emerald_biome();
