-- Explicit reconstructed Nox calendar; original effects and criteria remain authoritative.
-- Guide calendar: Method Wakfu, Coeur de l'Horloge de Nox (1.92 guide).
-- The original server publisher is not recovered; this policy is not native parity.
ALTER TABLE encounter_table_listener_versions
    ADD COLUMN additional_effect_references INTEGER[] NOT NULL DEFAULT '{}';

CREATE TABLE encounter_table_listener_callbacks (
    policy TEXT NOT NULL REFERENCES encounter_table_listener_versions(policy),
    effect_reference INTEGER NOT NULL CHECK(effect_reference>0),
    owner_reference INTEGER NOT NULL CHECK(owner_reference>0),
    owner_state INTEGER NOT NULL CHECK(owner_state>0),
    forbidden_state INTEGER NOT NULL CHECK(forbidden_state>0),
    event_id INTEGER NOT NULL CHECK(event_id>0),
    channel INTEGER NOT NULL CHECK(channel=60),
    timing TEXT NOT NULL CHECK(timing='owned_boss_post_start'),
    effect_family INTEGER NOT NULL CHECK(effect_family=330),
    selector_class TEXT NOT NULL CHECK(selector_class='fcE'),
    selector_mask BIGINT NOT NULL CHECK(selector_mask>=0),
    parameter_count INTEGER NOT NULL CHECK(parameter_count>=0),
    native_parameters JSONB NOT NULL CHECK(
        jsonb_typeof(native_parameters)='array'
        AND jsonb_array_length(native_parameters)=parameter_count*2
        AND NOT jsonb_path_exists(native_parameters, '$[*] ? (@.type() != "number")')
    ),
    criterion TEXT NOT NULL,
    area_class TEXT NOT NULL CHECK(area_class='anD'),
    children INTEGER[] NOT NULL CHECK(cardinality(children)>0),
    execution_count INTEGER NOT NULL CHECK(execution_count>0),
    reverse_subscription BOOLEAN NOT NULL CHECK(reverse_subscription),
    global_subscription BOOLEAN NOT NULL CHECK(NOT global_subscription),
    event_caster_code INTEGER NOT NULL,
    event_target_code INTEGER NOT NULL,
    owner_on_caster BOOLEAN NOT NULL CHECK(NOT owner_on_caster),
    definition_type INTEGER NOT NULL,
    effect_flags INTEGER[] NOT NULL,
    PRIMARY KEY(policy,effect_reference)
);

CREATE FUNCTION check_encounter_table_callback_insert() RETURNS TRIGGER
LANGUAGE plpgsql AS $$
DECLARE declared INTEGER[];
BEGIN
    SELECT additional_effect_references INTO declared
      FROM encounter_table_listener_versions WHERE policy=NEW.policy;
    IF declared IS NULL OR NOT NEW.effect_reference=ANY(declared) THEN
        RAISE EXCEPTION 'Callback is outside its immutable version inventory';
    END IF;
    RETURN NEW;
END;
$$;
CREATE TRIGGER encounter_table_callback_insert_inventory
    BEFORE INSERT ON encounter_table_listener_callbacks
    FOR EACH ROW EXECUTE FUNCTION check_encounter_table_callback_insert();
CREATE TRIGGER encounter_table_callbacks_immutable
    BEFORE UPDATE OR DELETE ON encounter_table_listener_callbacks
    FOR EACH ROW EXECUTE FUNCTION forbid_encounter_role_version_mutation();
CREATE TRIGGER encounter_table_callbacks_no_truncate
    BEFORE TRUNCATE ON encounter_table_listener_callbacks
    FOR EACH STATEMENT EXECUTE FUNCTION forbid_encounter_role_version_mutation();

CREATE FUNCTION check_encounter_table_callback_inventory() RETURNS TRIGGER
LANGUAGE plpgsql AS $$
DECLARE version_policy TEXT; declared INTEGER[]; actual INTEGER[]; canonical INTEGER[];
BEGIN
    version_policy := NEW.policy;
    SELECT additional_effect_references INTO declared
      FROM encounter_table_listener_versions WHERE policy=version_policy;
    SELECT COALESCE(array_agg(DISTINCT item ORDER BY item), '{}'::INTEGER[])
      INTO canonical FROM unnest(declared) AS items(item) WHERE item>0;
    SELECT COALESCE(array_agg(effect_reference ORDER BY effect_reference), '{}'::INTEGER[])
      INTO actual FROM encounter_table_listener_callbacks WHERE policy=version_policy;
    IF declared IS NULL OR declared IS DISTINCT FROM canonical
       OR declared IS DISTINCT FROM actual THEN
        RAISE EXCEPTION 'Incomplete or noncanonical encounter callback inventory';
    END IF;
    RETURN NULL;
END;
$$;
CREATE CONSTRAINT TRIGGER encounter_table_version_callbacks_complete
    AFTER INSERT ON encounter_table_listener_versions
    DEFERRABLE INITIALLY DEFERRED FOR EACH ROW
    EXECUTE FUNCTION check_encounter_table_callback_inventory();
CREATE CONSTRAINT TRIGGER encounter_table_callback_inventory_complete
    AFTER INSERT ON encounter_table_listener_callbacks
    DEFERRABLE INITIALLY DEFERRED FOR EACH ROW
    EXECUTE FUNCTION check_encounter_table_callback_inventory();

INSERT INTO encounter_table_listener_versions (
    policy,authority,map_id,monster_references,catalog_revision,boss_reference,
    boss_constructor_state,owner_reference,owner_constructor_state,effect_reference,
    event_id,channel,timing,additional_effect_references
)
SELECT 'wakemu-nox-owned-boundaries-v3',
       'wakemu-reconstructed-guide-calendar-post-owned-start;native401544-consumer;original-publisher-unrecovered',
       map_id,monster_references,catalog_revision,boss_reference,boss_constructor_state,
       owner_reference,owner_constructor_state,effect_reference,event_id,channel,timing,
       ARRAY[401544]
  FROM encounter_table_listener_versions WHERE policy='wakemu-nox-cube-table-listener-v1';

INSERT INTO encounter_table_listener_callbacks (
    policy,effect_reference,owner_reference,owner_state,forbidden_state,event_id,
    channel,timing,effect_family,selector_class,selector_mask,parameter_count,
    native_parameters,criterion,area_class,children,execution_count,
    reverse_subscription,global_subscription,event_caster_code,event_target_code,
    owner_on_caster,definition_type,effect_flags
) VALUES (
    'wakemu-nox-owned-boundaries-v3',401544,5664,8978,8979,1005,60,
    'owned_boss_post_start',330,'fcE',1,0,'[]'::JSONB,
    E'extraTurn = if (HasState(8988)) then (GetStateLevel(8988)) else (0);\r\nGetFightCurrentTableTurn() == (8 + extraTurn) or HasState(9049)',
    'anD',ARRAY[401545,407663,401546,401744,402218,401771,407660],
    1,TRUE,FALSE,2,2,FALSE,2,'{}'::INTEGER[]
);
UPDATE encounter_table_listener_active
   SET policy='wakemu-nox-owned-boundaries-v3'
 WHERE map_id=1435 AND monster_references=ARRAY[5664]
   AND policy='wakemu-nox-cube-table-listener-v1';
