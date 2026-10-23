-- Freeze the existing canonical XP rate per earned character entitlement.
-- Original catalog components remain base values for native reward validation.
CREATE TABLE environmental_entitlement_xp_rates (
 entitlement_id bigint NOT NULL,
 component_ordinal integer NOT NULL,
 account_id bigint NOT NULL,
 character_id bigint NOT NULL,
 earned_at_ms bigint NOT NULL CHECK(earned_at_ms>=0),
 policy_version integer NOT NULL REFERENCES combat_reward_policy_versions(version),
 xp_rate_bp bigint NOT NULL CHECK(xp_rate_bp BETWEEN 0 AND 99999999999),
 base_xp bigint NOT NULL CHECK(base_xp>0 AND base_xp<2147483648),
 awarded_xp bigint NOT NULL CHECK(awarded_xp>=0),
 authority text NOT NULL CHECK(authority='wakemu.environmental-earned-canonical-xp-rate.v1'),
 PRIMARY KEY(entitlement_id,component_ordinal),
 FOREIGN KEY(entitlement_id,component_ordinal)
  REFERENCES environmental_reward_components(entitlement_id,ordinal),
 FOREIGN KEY(entitlement_id,account_id,character_id)
  REFERENCES environmental_reward_entitlements(entitlement_id,account_id,character_id),
 CHECK(awarded_xp::numeric=floor(base_xp::numeric*xp_rate_bp/10000))
);
CREATE FUNCTION validate_environmental_entitlement_xp_rate() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF NOT EXISTS(SELECT 1 FROM environmental_reward_components c
  JOIN environmental_reward_entitlements e USING(entitlement_id)
  JOIN combat_reward_policy_versions p ON p.version=NEW.policy_version
  WHERE c.entitlement_id=NEW.entitlement_id AND c.ordinal=NEW.component_ordinal
   AND c.kind='xp' AND c.reference IS NULL AND c.quantity=NEW.base_xp
   AND e.account_id=NEW.account_id AND e.character_id=NEW.character_id
   AND e.earned_at_ms=NEW.earned_at_ms AND p.xp_rate_bp=NEW.xp_rate_bp) THEN
  RAISE EXCEPTION 'Environmental XP rate differs from its earned source';
 END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER environmental_entitlement_xp_rate_source BEFORE INSERT
 ON environmental_entitlement_xp_rates FOR EACH ROW
 EXECUTE FUNCTION validate_environmental_entitlement_xp_rate();
CREATE FUNCTION immutable_environmental_entitlement_xp_rates() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION 'Earned environmental XP pricing is immutable'; END $$;
CREATE TRIGGER environmental_entitlement_xp_rate_immutable BEFORE UPDATE OR DELETE
 ON environmental_entitlement_xp_rates FOR EACH ROW
 EXECUTE FUNCTION immutable_environmental_entitlement_xp_rates();
CREATE TRIGGER environmental_entitlement_xp_rate_no_truncate BEFORE TRUNCATE
 ON environmental_entitlement_xp_rates FOR EACH STATEMENT
 EXECUTE FUNCTION immutable_environmental_entitlement_xp_rates();

-- User-declared fresh-install default: XP x10. Only the untouched original
-- v1/default policy is upgraded. Existing operator versions/rates are preserved.
WITH untouched AS (
 SELECT v.* FROM combat_reward_policy_active a
 JOIN combat_reward_policy_versions v USING(version)
 WHERE a.singleton AND v.version=1 AND v.xp_rate_bp=10000
  AND v.kamas_rate_bp=10000 AND v.conquest_rate_bp=10000
  AND NOT EXISTS(SELECT 1 FROM combat_reward_policy_versions p WHERE p.version<>1)
), installed AS (
 INSERT INTO combat_reward_policy_versions(version,xp_rate_bp,kamas_rate_bp,conquest_rate_bp)
 SELECT 2,100000,kamas_rate_bp,conquest_rate_bp FROM untouched
 RETURNING version
)
UPDATE combat_reward_policy_active SET version=installed.version FROM installed
WHERE singleton AND combat_reward_policy_active.version=1;
