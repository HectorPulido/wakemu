-- Explicit Wakemu UTC-day rotation; original server selection seed unrecovered.
CREATE TABLE recurring_hunter_daily_pools (
 pool_version text PRIMARY KEY,
 interpretation_policy text NOT NULL CHECK(interpretation_policy='wakemu.daily-hunter-utc-sorted-rotation-v1'),
 source_sha256 text NOT NULL CHECK(source_sha256 ~ '^[0-9a-f]{64}$'),
 sealed boolean NOT NULL DEFAULT false
);
CREATE TABLE recurring_hunter_daily_members (
 pool_version text NOT NULL REFERENCES recurring_hunter_daily_pools,
 category_id integer NOT NULL CHECK(category_id>0),
 definition_id integer NOT NULL,
 version integer NOT NULL,
 PRIMARY KEY(pool_version,category_id,definition_id,version),
 UNIQUE(pool_version,definition_id),
 FOREIGN KEY(definition_id,version) REFERENCES recurring_hunter_contracts(definition_id,version)
);
CREATE TABLE recurring_hunter_daily_active (
 singleton boolean PRIMARY KEY DEFAULT true CHECK(singleton),
 pool_version text NOT NULL REFERENCES recurring_hunter_daily_pools,
 enabled boolean NOT NULL DEFAULT false
);
CREATE TABLE recurring_hunter_daily_choices (
 category_id integer NOT NULL,
 utc_day bigint NOT NULL CHECK(utc_day>=0),
 pool_version text NOT NULL,
 definition_id integer NOT NULL,
 version integer NOT NULL,
 selected_at_ms bigint NOT NULL CHECK(selected_at_ms>=0),
 PRIMARY KEY(category_id,utc_day),
 FOREIGN KEY(pool_version,category_id,definition_id,version)
 REFERENCES recurring_hunter_daily_members(pool_version,category_id,definition_id,version),
 CHECK(selected_at_ms/86400000=utc_day)
);
CREATE FUNCTION recurring_hunter_daily_pool_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF TG_OP='UPDATE' AND NOT OLD.sealed AND NEW.sealed
 AND NEW.pool_version=OLD.pool_version AND NEW.interpretation_policy=OLD.interpretation_policy
 AND NEW.source_sha256=OLD.source_sha256 THEN RETURN NEW; END IF;
 RAISE EXCEPTION 'Daily hunter pool source is immutable';
END $$;
CREATE FUNCTION recurring_hunter_daily_member_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF TG_OP<>'INSERT' THEN RAISE EXCEPTION 'Daily hunter member is immutable'; END IF;
 PERFORM 1 FROM recurring_hunter_daily_pools WHERE pool_version=NEW.pool_version AND NOT sealed FOR UPDATE;
 IF NOT FOUND THEN RAISE EXCEPTION 'Daily hunter pool is sealed'; END IF;
 PERFORM 1 FROM recurring_hunter_target_authority a JOIN recurring_hunter_contracts c
 USING(definition_id,version) WHERE a.definition_id=NEW.definition_id AND a.version=NEW.version
 AND a.category_id=NEW.category_id AND c.period_ms=86400000;
 IF NOT FOUND THEN RAISE EXCEPTION 'Daily hunter member lacks qualified daily authority'; END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER recurring_hunter_daily_pool_immutable BEFORE UPDATE OR DELETE ON recurring_hunter_daily_pools
 FOR EACH ROW EXECUTE FUNCTION recurring_hunter_daily_pool_guard();
CREATE TRIGGER recurring_hunter_daily_member_immutable BEFORE INSERT OR UPDATE OR DELETE ON recurring_hunter_daily_members
 FOR EACH ROW EXECUTE FUNCTION recurring_hunter_daily_member_guard();
CREATE TRIGGER recurring_hunter_daily_choice_immutable BEFORE UPDATE OR DELETE ON recurring_hunter_daily_choices
 FOR EACH ROW EXECUTE FUNCTION recurring_hunter_immutable_source();
INSERT INTO recurring_hunter_daily_pools VALUES('wakemu.daily-hunter-qualified45-v1','wakemu.daily-hunter-utc-sorted-rotation-v1','cb8f18f57c75cba8cfc63d6970dd30b31790b014f74252965d4c49c2bade36a5',false);
INSERT INTO recurring_hunter_daily_members VALUES
('wakemu.daily-hunter-qualified45-v1',701,4140,1),
('wakemu.daily-hunter-qualified45-v1',701,4141,1),
('wakemu.daily-hunter-qualified45-v1',702,4144,1),
('wakemu.daily-hunter-qualified45-v1',702,4145,1),
('wakemu.daily-hunter-qualified45-v1',702,4146,1),
('wakemu.daily-hunter-qualified45-v1',691,4163,1),
('wakemu.daily-hunter-qualified45-v1',691,4164,1),
('wakemu.daily-hunter-qualified45-v1',691,4167,1),
('wakemu.daily-hunter-qualified45-v1',691,4168,1),
('wakemu.daily-hunter-qualified45-v1',692,4174,1),
('wakemu.daily-hunter-qualified45-v1',692,4175,1),
('wakemu.daily-hunter-qualified45-v1',692,4176,1),
('wakemu.daily-hunter-qualified45-v1',692,4178,1),
('wakemu.daily-hunter-qualified45-v1',693,4183,1),
('wakemu.daily-hunter-qualified45-v1',696,4201,1),
('wakemu.daily-hunter-qualified45-v1',698,4210,1),
('wakemu.daily-hunter-qualified45-v1',698,4211,1),
('wakemu.daily-hunter-qualified45-v1',699,4213,1),
('wakemu.daily-hunter-qualified45-v1',699,4214,1),
('wakemu.daily-hunter-qualified45-v1',699,4215,1),
('wakemu.daily-hunter-qualified45-v1',699,4216,1),
('wakemu.daily-hunter-qualified45-v1',700,4218,1),
('wakemu.daily-hunter-qualified45-v1',700,4220,1),
('wakemu.daily-hunter-qualified45-v1',691,4449,1),
('wakemu.daily-hunter-qualified45-v1',691,4450,1),
('wakemu.daily-hunter-qualified45-v1',693,4455,1),
('wakemu.daily-hunter-qualified45-v1',694,4456,1),
('wakemu.daily-hunter-qualified45-v1',695,4457,1),
('wakemu.daily-hunter-qualified45-v1',697,4460,1),
('wakemu.daily-hunter-qualified45-v1',698,4461,1),
('wakemu.daily-hunter-qualified45-v1',698,4463,1),
('wakemu.daily-hunter-qualified45-v1',698,4464,1),
('wakemu.daily-hunter-qualified45-v1',697,4642,1),
('wakemu.daily-hunter-qualified45-v1',699,4645,1),
('wakemu.daily-hunter-qualified45-v1',700,4650,1),
('wakemu.daily-hunter-qualified45-v1',700,4651,1),
('wakemu.daily-hunter-qualified45-v1',699,4725,1),
('wakemu.daily-hunter-qualified45-v1',700,4726,1),
('wakemu.daily-hunter-qualified45-v1',809,4774,1),
('wakemu.daily-hunter-qualified45-v1',809,4776,1),
('wakemu.daily-hunter-qualified45-v1',809,4869,1),
('wakemu.daily-hunter-qualified45-v1',809,4870,1),
('wakemu.daily-hunter-qualified45-v1',853,5116,1),
('wakemu.daily-hunter-qualified45-v1',904,5395,1),
('wakemu.daily-hunter-qualified45-v1',904,5396,1);
UPDATE recurring_hunter_daily_pools SET sealed=true WHERE pool_version='wakemu.daily-hunter-qualified45-v1';
INSERT INTO recurring_hunter_daily_active VALUES(true,'wakemu.daily-hunter-qualified45-v1',false);
