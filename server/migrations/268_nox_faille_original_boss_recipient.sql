-- Reconstructed recipient binding for native Faille descendants, not native Qe behavior.
CREATE TABLE encounter_effect_recipient_versions (
    policy TEXT PRIMARY KEY CHECK(length(policy)>0),
    authority TEXT NOT NULL CHECK(length(authority)>0),
    mode TEXT NOT NULL CHECK(mode='ORIGINAL_BOSS_RECIPIENT'),
    catalog_revision TEXT NOT NULL CHECK(length(catalog_revision)=64),
    map_id INTEGER NOT NULL,
    monster_references INTEGER[] NOT NULL CHECK(cardinality(monster_references)>0),
    boss_reference INTEGER NOT NULL CHECK(boss_reference=ANY(monster_references)),
    boss_constructor_state INTEGER NOT NULL CHECK(boss_constructor_state>0),
    carrier_state INTEGER NOT NULL CHECK(carrier_state>0),
    source_start_listener INTEGER NOT NULL CHECK(source_start_listener>0),
    start_binding_policy TEXT NOT NULL REFERENCES encounter_owned_start_binding_versions(policy),
    effect_references INTEGER[] NOT NULL CHECK(cardinality(effect_references)>0),
    UNIQUE(policy,map_id,monster_references)
);
CREATE TABLE encounter_effect_recipient_rules (
    policy TEXT NOT NULL REFERENCES encounter_effect_recipient_versions(policy),
    effect_reference INTEGER NOT NULL CHECK(effect_reference>0),
    parent_reference INTEGER NOT NULL CHECK(parent_reference>0),
    event_id INTEGER NOT NULL,
    phase TEXT NOT NULL,
    channel INTEGER NOT NULL CHECK(channel=60),
    CHECK((event_id=1002 AND phase='end') OR (event_id=1037 AND phase='regeneration')),
    effect_family INTEGER NOT NULL CHECK(effect_family IN (304,321)),
    selector_mask BIGINT NOT NULL CHECK(selector_mask=8200),
    area_class TEXT NOT NULL CHECK(area_class='anD'),
    criterion TEXT NOT NULL,
    parameter_count INTEGER NOT NULL CHECK(parameter_count>=0),
    native_parameters DOUBLE PRECISION[] NOT NULL,
    CHECK(cardinality(native_parameters)=2*parameter_count),
    native_children INTEGER[] NOT NULL,
    native_execution_mode INTEGER NOT NULL,
    native_effect_flags INTEGER[] NOT NULL,
    PRIMARY KEY(policy,effect_reference)
);
CREATE TABLE encounter_effect_recipient_active (
    map_id INTEGER NOT NULL,
    monster_references INTEGER[] NOT NULL,
    policy TEXT NOT NULL,
    PRIMARY KEY(map_id,monster_references),
    FOREIGN KEY(policy,map_id,monster_references)
        REFERENCES encounter_effect_recipient_versions(policy,map_id,monster_references)
);
CREATE TRIGGER encounter_effect_recipient_versions_immutable
    BEFORE UPDATE OR DELETE ON encounter_effect_recipient_versions
    FOR EACH ROW EXECUTE FUNCTION forbid_encounter_role_version_mutation();
CREATE TRIGGER encounter_effect_recipient_versions_no_truncate
    BEFORE TRUNCATE ON encounter_effect_recipient_versions
    FOR EACH STATEMENT EXECUTE FUNCTION forbid_encounter_role_version_mutation();
CREATE TRIGGER encounter_effect_recipient_rules_immutable
    BEFORE UPDATE OR DELETE ON encounter_effect_recipient_rules
    FOR EACH ROW EXECUTE FUNCTION forbid_encounter_role_version_mutation();
CREATE TRIGGER encounter_effect_recipient_rules_no_truncate
    BEFORE TRUNCATE ON encounter_effect_recipient_rules
    FOR EACH STATEMENT EXECUTE FUNCTION forbid_encounter_role_version_mutation();
CREATE FUNCTION check_encounter_effect_recipient_rule_insert() RETURNS TRIGGER
LANGUAGE plpgsql AS $$
DECLARE declared INTEGER[];
BEGIN
    SELECT effect_references INTO declared FROM encounter_effect_recipient_versions WHERE policy=NEW.policy;
    IF declared IS NULL OR NOT NEW.effect_reference=ANY(declared) THEN
        RAISE EXCEPTION 'Recipient rule is outside immutable version inventory';
    END IF;
    RETURN NEW;
END;
$$;
CREATE TRIGGER encounter_effect_recipient_rule_inventory
    BEFORE INSERT ON encounter_effect_recipient_rules
    FOR EACH ROW EXECUTE FUNCTION check_encounter_effect_recipient_rule_insert();
CREATE FUNCTION check_encounter_effect_recipient_inventory() RETURNS TRIGGER
LANGUAGE plpgsql AS $$
DECLARE declared INTEGER[]; canonical INTEGER[]; actual INTEGER[];
BEGIN
    SELECT effect_references INTO declared FROM encounter_effect_recipient_versions WHERE policy=NEW.policy;
    SELECT COALESCE(array_agg(DISTINCT item ORDER BY item), '{}'::INTEGER[])
      INTO canonical FROM unnest(declared) AS items(item) WHERE item>0;
    SELECT COALESCE(array_agg(effect_reference ORDER BY effect_reference), '{}'::INTEGER[])
      INTO actual FROM encounter_effect_recipient_rules WHERE policy=NEW.policy;
    IF declared IS NULL OR declared IS DISTINCT FROM canonical OR declared IS DISTINCT FROM actual THEN
        RAISE EXCEPTION 'Incomplete or noncanonical encounter recipient inventory';
    END IF;
    RETURN NULL;
END;
$$;
CREATE CONSTRAINT TRIGGER encounter_effect_recipient_version_complete
    AFTER INSERT ON encounter_effect_recipient_versions
    DEFERRABLE INITIALLY DEFERRED FOR EACH ROW
    EXECUTE FUNCTION check_encounter_effect_recipient_inventory();
CREATE CONSTRAINT TRIGGER encounter_effect_recipient_rules_complete
    AFTER INSERT ON encounter_effect_recipient_rules
    DEFERRABLE INITIALLY DEFERRED FOR EACH ROW
    EXECUTE FUNCTION check_encounter_effect_recipient_inventory();

INSERT INTO encounter_effect_recipient_versions VALUES (
    'wakemu-nox-faille-original-boss-recipient-v1',
    'wakemu-reconstructed-owned-faille-descendant-recipient;native-Qe-chosen-PV-preserved',
    'ORIGINAL_BOSS_RECIPIENT',
    'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450',
    1435,ARRAY[5664],5664,8969,9028,402183,
    'wakemu-nox-faille-owned-start-caster-v1',ARRAY[402195,402212]
);
INSERT INTO encounter_effect_recipient_rules VALUES
('wakemu-nox-faille-original-boss-recipient-v1',402195,402194,1002,'end',60,
 321,8200,'anD','HasState(9027, "target")',2,ARRAY[9027,0,1,0]::DOUBLE PRECISION[],
 '{}'::INTEGER[],2,'{}'::INTEGER[]),
('wakemu-nox-faille-original-boss-recipient-v1',402212,402211,1037,'regeneration',60,
 304,8200,'anD','HasState(8969, "target")',3,ARRAY[9027,0,2,0,-1,0]::DOUBLE PRECISION[],
 '{}'::INTEGER[],2,ARRAY[17]);
INSERT INTO encounter_effect_recipient_active VALUES
(1435,ARRAY[5664],'wakemu-nox-faille-original-boss-recipient-v1');
