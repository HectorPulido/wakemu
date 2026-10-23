-- Explicit reconstruction of the missing successful Nox helper cleanup population.
-- Native kill selector, POINT delivery and self-controlled birth ownership stay intact.
CREATE TABLE encounter_terminal_cleanup_versions (
    policy TEXT PRIMARY KEY CHECK(length(policy)>0),
    authority TEXT NOT NULL CHECK(length(authority)>0),
    catalog_revision TEXT NOT NULL CHECK(length(catalog_revision)=64),
    map_id INTEGER NOT NULL CHECK(map_id>0),
    monster_references INTEGER[] NOT NULL CHECK(cardinality(monster_references)>0),
    boss_reference INTEGER NOT NULL CHECK(boss_reference>0 AND boss_reference=ANY(monster_references)),
    boss_constructor_state INTEGER NOT NULL CHECK(boss_constructor_state>0),
    boss_phase_state INTEGER NOT NULL CHECK(boss_phase_state>0),
    success_state INTEGER NOT NULL CHECK(success_state>0),
    terminal_listener INTEGER NOT NULL CHECK(terminal_listener>0),
    terminal_event INTEGER NOT NULL CHECK(terminal_event=1002),
    terminal_channel INTEGER NOT NULL CHECK(terminal_channel=60),
    terminal_table INTEGER NOT NULL CHECK(terminal_table>0),
    extension_state INTEGER NOT NULL CHECK(extension_state>0),
    boss_kill_effect_reference INTEGER NOT NULL CHECK(boss_kill_effect_reference>0),
    cleanup_effect_reference INTEGER NOT NULL CHECK(cleanup_effect_reference>0),
    helper_references INTEGER[] NOT NULL CHECK(cardinality(helper_references)>0),
    effect_family INTEGER NOT NULL CHECK(effect_family=28),
    selector_mask BIGINT NOT NULL CHECK(selector_mask=8),
    area_class TEXT NOT NULL CHECK(area_class='anD'),
    criterion TEXT NOT NULL CHECK(length(criterion)>0),
    parameter_count INTEGER NOT NULL CHECK(parameter_count>=0),
    native_parameters DOUBLE PRECISION[] NOT NULL,
    CHECK(cardinality(native_parameters)=2*parameter_count),
    native_execution_mode INTEGER NOT NULL,
    native_effect_flags INTEGER[] NOT NULL,
    UNIQUE(policy,map_id,monster_references)
);
CREATE TABLE encounter_terminal_cleanup_helpers (
    policy TEXT NOT NULL REFERENCES encounter_terminal_cleanup_versions(policy),
    helper_reference INTEGER NOT NULL CHECK(helper_reference>0),
    creator_effect_reference INTEGER NOT NULL CHECK(creator_effect_reference>0),
    constructor_state INTEGER NOT NULL CHECK(constructor_state>0),
    PRIMARY KEY(policy,helper_reference)
);
CREATE TABLE encounter_terminal_cleanup_active (
    map_id INTEGER NOT NULL,
    monster_references INTEGER[] NOT NULL,
    policy TEXT NOT NULL,
    PRIMARY KEY(map_id,monster_references),
    FOREIGN KEY(policy,map_id,monster_references)
        REFERENCES encounter_terminal_cleanup_versions(policy,map_id,monster_references)
);
CREATE TRIGGER encounter_terminal_cleanup_versions_immutable
    BEFORE UPDATE OR DELETE ON encounter_terminal_cleanup_versions
    FOR EACH ROW EXECUTE FUNCTION forbid_encounter_role_version_mutation();
CREATE TRIGGER encounter_terminal_cleanup_versions_no_truncate
    BEFORE TRUNCATE ON encounter_terminal_cleanup_versions
    FOR EACH STATEMENT EXECUTE FUNCTION forbid_encounter_role_version_mutation();
CREATE TRIGGER encounter_terminal_cleanup_helpers_immutable
    BEFORE UPDATE OR DELETE ON encounter_terminal_cleanup_helpers
    FOR EACH ROW EXECUTE FUNCTION forbid_encounter_role_version_mutation();
CREATE TRIGGER encounter_terminal_cleanup_helpers_no_truncate
    BEFORE TRUNCATE ON encounter_terminal_cleanup_helpers
    FOR EACH STATEMENT EXECUTE FUNCTION forbid_encounter_role_version_mutation();
CREATE FUNCTION check_encounter_terminal_helper_insert() RETURNS TRIGGER
LANGUAGE plpgsql AS $$
DECLARE declared INTEGER[];
BEGIN
    SELECT helper_references INTO declared FROM encounter_terminal_cleanup_versions WHERE policy=NEW.policy;
    IF declared IS NULL OR NOT NEW.helper_reference=ANY(declared) THEN
        RAISE EXCEPTION 'Terminal helper is outside immutable version inventory';
    END IF;
    RETURN NEW;
END;
$$;
CREATE TRIGGER encounter_terminal_cleanup_helper_inventory
    BEFORE INSERT ON encounter_terminal_cleanup_helpers
    FOR EACH ROW EXECUTE FUNCTION check_encounter_terminal_helper_insert();
CREATE FUNCTION check_encounter_terminal_cleanup_inventory() RETURNS TRIGGER
LANGUAGE plpgsql AS $$
DECLARE declared INTEGER[]; canonical INTEGER[]; actual INTEGER[];
        monsters INTEGER[]; canonical_monsters INTEGER[];
BEGIN
    SELECT helper_references, monster_references INTO declared, monsters
      FROM encounter_terminal_cleanup_versions WHERE policy=NEW.policy;
    SELECT COALESCE(array_agg(DISTINCT item ORDER BY item), '{}'::INTEGER[])
      INTO canonical FROM unnest(declared) AS items(item) WHERE item>0;
    SELECT COALESCE(array_agg(helper_reference ORDER BY helper_reference), '{}'::INTEGER[])
      INTO actual FROM encounter_terminal_cleanup_helpers WHERE policy=NEW.policy;
    SELECT COALESCE(array_agg(DISTINCT item ORDER BY item), '{}'::INTEGER[])
      INTO canonical_monsters FROM unnest(monsters) AS items(item) WHERE item>0;
    IF declared IS NULL OR cardinality(declared)=0 OR declared IS DISTINCT FROM canonical
       OR declared IS DISTINCT FROM actual OR monsters IS DISTINCT FROM canonical_monsters THEN
        RAISE EXCEPTION 'Incomplete or noncanonical encounter terminal cleanup inventory';
    END IF;
    RETURN NULL;
END;
$$;
CREATE CONSTRAINT TRIGGER encounter_terminal_cleanup_version_complete
    AFTER INSERT ON encounter_terminal_cleanup_versions
    DEFERRABLE INITIALLY DEFERRED FOR EACH ROW
    EXECUTE FUNCTION check_encounter_terminal_cleanup_inventory();
CREATE CONSTRAINT TRIGGER encounter_terminal_cleanup_helpers_complete
    AFTER INSERT ON encounter_terminal_cleanup_helpers
    DEFERRABLE INITIALLY DEFERRED FOR EACH ROW
    EXECUTE FUNCTION check_encounter_terminal_cleanup_inventory();

INSERT INTO encounter_terminal_cleanup_versions VALUES (
    'wakemu-nox-native-terminal-helper-cleanup-v1',
    'wakemu-reconstructed-successful-terminal-helper-population;guide-native-terminal-and-original-birth-kill-consumers;not-recovered-server-publisher',
    'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450',
    1435,ARRAY[5664],5664,8969,8979,9031,401563,1002,60,11,8988,402298,401564,
    ARRAY[5783,5786],28,8,'anD','not IsBreedId("target", 5664)',0,
    '{}'::DOUBLE PRECISION[],2,'{}'::INTEGER[]
);
INSERT INTO encounter_terminal_cleanup_helpers VALUES
('wakemu-nox-native-terminal-helper-cleanup-v1',5783,401566,8971),
('wakemu-nox-native-terminal-helper-cleanup-v1',5786,401568,8974);
INSERT INTO encounter_terminal_cleanup_active VALUES
(1435,ARRAY[5664],'wakemu-nox-native-terminal-helper-cleanup-v1');
