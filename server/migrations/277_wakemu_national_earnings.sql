-- Explicit Wakemu reconstruction, not recovered original earning formulas.
ALTER TABLE character_national_authority DROP CONSTRAINT character_national_authority_provenance_check;
ALTER TABLE character_national_authority ADD CHECK
 (provenance IN ('native_constructor','native_import','wakemu_policy_epoch'));
CREATE TABLE wakemu_national_earning_policies (
 policy_key text PRIMARY KEY,
 ecology_gain integer NOT NULL CHECK(ecology_gain>0),
 ecology_loss integer NOT NULL CHECK(ecology_loss<0),
 citizenship_min integer NOT NULL,citizenship_max integer NOT NULL,
 merit_win integer NOT NULL CHECK(merit_win>0),merit_loss integer NOT NULL CHECK(merit_loss<0),
 merit_max integer NOT NULL CHECK(merit_max>=18000),
 provenance text NOT NULL CHECK(length(provenance)>0),
 CHECK(citizenship_min<0 AND citizenship_max>0)
);
INSERT INTO wakemu_national_earning_policies VALUES
 ('wakemu-national-v1',10,-10,-2000,2000,100,-50,18000,
  'User-authorized Wakemu reconstruction: managed public ecological improvement/damage; valid hourly PvP defeat only. No original earning formula claimed.');
CREATE TRIGGER wakemu_national_policy_immutable BEFORE UPDATE OR DELETE ON wakemu_national_earning_policies
 FOR EACH ROW EXECUTE FUNCTION native_national_source_immutable();
CREATE TABLE character_national_merit (
 character_id bigint PRIMARY KEY,account_id bigint NOT NULL,
 policy_key text NOT NULL REFERENCES wakemu_national_earning_policies,
 merit integer NOT NULL CHECK(merit>=0),
 baseline_rank smallint NOT NULL CHECK(baseline_rank BETWEEN 0 AND 9),
 FOREIGN KEY(character_id,account_id) REFERENCES character_national_authority(character_id,account_id)
);
CREATE TABLE character_national_earning_receipts (
 character_id bigint NOT NULL,account_id bigint NOT NULL,
 source_kind text NOT NULL CHECK(source_kind IN ('ecology','hourly_pvp')),
 source_key text NOT NULL CHECK(length(source_key) BETWEEN 1 AND 160),
 policy_key text NOT NULL REFERENCES wakemu_national_earning_policies,
 nation_id integer NOT NULL CHECK(nation_id BETWEEN 30 AND 34),
 source_digest text NOT NULL CHECK(length(source_digest)=64),
 before_value integer NOT NULL,after_value integer NOT NULL,
 requested_delta integer NOT NULL,period_key text,
 PRIMARY KEY(character_id,source_kind,source_key),
 FOREIGN KEY(character_id,account_id) REFERENCES character_national_authority(character_id,account_id),
 CHECK((source_kind='hourly_pvp')=(period_key IS NOT NULL))
);
CREATE UNIQUE INDEX national_hourly_account_receipt ON character_national_earning_receipts(account_id,period_key)
 WHERE source_kind='hourly_pvp';
ALTER TABLE objectives_pvp_events ADD COLUMN national_policy_key text NOT NULL
 DEFAULT 'wakemu-national-v1' REFERENCES wakemu_national_earning_policies;
CREATE FUNCTION freeze_hourly_national_policy() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF NEW.national_policy_key IS DISTINCT FROM OLD.national_policy_key THEN
  RAISE EXCEPTION 'Announced national merit policy is frozen';
 END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER objectives_pvp_national_policy_frozen BEFORE UPDATE ON objectives_pvp_events
 FOR EACH ROW EXECUTE FUNCTION freeze_hourly_national_policy();
CREATE TABLE wakemu_national_neutrality_rules (
 item_ref integer PRIMARY KEY,clear_citizenship boolean NOT NULL,
 clear_merit boolean NOT NULL,provenance text NOT NULL
);
INSERT INTO wakemu_national_neutrality_rules VALUES
 (16979,true,false,'Native bVr reset clears score map and preserves rank'),
 (16980,true,false,'Native bVr reset clears score map and preserves rank'),
 (16981,true,false,'Native bVr reset clears score map and preserves rank'),
 (16982,true,false,'Native bVr reset clears score map and preserves rank'),
 (24836,true,true,'Explicit Wakemu modern neutrality reconstruction clears the newly implemented merit balance');
CREATE TRIGGER wakemu_national_neutrality_immutable BEFORE UPDATE OR DELETE ON wakemu_national_neutrality_rules
 FOR EACH ROW EXECUTE FUNCTION native_national_source_immutable();
