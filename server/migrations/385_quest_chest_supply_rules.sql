-- Reviewed quest supply associations, independent of ordinary treasure rewards.
-- Attempts and successful character/source receipts use the existing event ledger.
CREATE TABLE quest_chest_supply_rules (
 map_id integer NOT NULL CHECK(map_id>0),
 object_id bigint NOT NULL CHECK(object_id>0),
 rule jsonb NOT NULL CHECK(jsonb_typeof(rule)='object'),
 sha256 text NOT NULL CHECK(sha256 ~ '^[a-f0-9]{64}$'),
 sealed boolean NOT NULL DEFAULT false,
 PRIMARY KEY(map_id,object_id),
 CHECK((rule->>'map_id')::integer=map_id AND (rule->>'object_id')::bigint=object_id)
);
CREATE FUNCTION protect_quest_chest_supply_rule() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF OLD.sealed THEN
  RAISE EXCEPTION 'Published quest chest supply rule is immutable';
 END IF;
 IF TG_OP='DELETE' THEN RETURN OLD; END IF;
 RETURN NEW;
END;
$$;
CREATE TRIGGER immutable_quest_chest_supply_rule BEFORE UPDATE OR DELETE
 ON quest_chest_supply_rules FOR EACH ROW EXECUTE FUNCTION protect_quest_chest_supply_rule();
