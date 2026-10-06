-- Mount state belongs to the owned unit; actor PET and item ProtoPet derive
-- from this record. Model rows are loaded from the verified native catalog.
CREATE TABLE mount_models (
    model_id integer PRIMARY KEY CHECK (model_id > 0),
    reference integer NOT NULL UNIQUE CHECK (reference > 0),
    maximum_health integer NOT NULL CHECK (maximum_health > 0),
    xp_per_level integer NOT NULL CHECK (xp_per_level > 0),
    maximum_level integer NOT NULL CHECK (maximum_level > 0),
    speed_id integer NOT NULL CHECK (speed_id >= 0),
    milliseconds_per_cell integer NOT NULL CHECK (milliseconds_per_cell > 0),
    gfx integer NOT NULL CHECK (gfx >= 0),
    meal_item_refs integer[] NOT NULL,
    xp_per_meal integer NOT NULL CHECK (xp_per_meal >= 0),
    meal_min_interval_seconds integer NOT NULL CHECK (meal_min_interval_seconds >= 0),
    meal_max_interval_seconds integer NOT NULL
        CHECK (meal_max_interval_seconds >= meal_min_interval_seconds)
);

CREATE TABLE inventory_mounts (
    uid bigint PRIMARY KEY REFERENCES inventory_items(uid) ON DELETE CASCADE,
    model_id integer NOT NULL REFERENCES mount_models(model_id),
    name text NOT NULL DEFAULT '',
    xp integer NOT NULL DEFAULT 0 CHECK (xp >= 0),
    health integer NOT NULL CHECK (health >= 0),
    color_item_ref integer NOT NULL DEFAULT 0 CHECK (color_item_ref >= 0),
    equipped_item_ref integer NOT NULL DEFAULT 0 CHECK (equipped_item_ref >= 0),
    sleep_item_ref integer NOT NULL DEFAULT 0 CHECK (sleep_item_ref >= 0),
    reskin_item_ref integer NOT NULL DEFAULT 0 CHECK (reskin_item_ref >= 0),
    -- Native TP dates are epoch milliseconds with second precision; zero
    -- denotes no date. Creation explicitly supplies server time for meals.
    last_meal_date bigint NOT NULL CHECK (last_meal_date >= 0 AND last_meal_date % 1000 = 0),
    last_hungry_date bigint NOT NULL CHECK (last_hungry_date >= 0 AND last_hungry_date % 1000 = 0),
    sleep_date bigint NOT NULL DEFAULT 0 CHECK (sleep_date >= 0 AND sleep_date % 1000 = 0),
    revision bigint NOT NULL DEFAULT 0 CHECK (revision >= 0),
    CHECK ((sleep_item_ref = 0 AND sleep_date = 0)
        OR (sleep_item_ref > 0 AND sleep_date > 0))
);

CREATE TABLE character_mount_state (
    character_id bigint PRIMARY KEY REFERENCES characters(id) ON DELETE CASCADE,
    mounted boolean NOT NULL DEFAULT false,
    last_mount_at timestamptz,
    revision bigint NOT NULL DEFAULT 0 CHECK (revision >= 0)
);

CREATE FUNCTION validate_mount_unit() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    unit_record inventory_items%ROWTYPE;
    model_record mount_models%ROWTYPE;
BEGIN
    SELECT * INTO unit_record FROM inventory_items WHERE uid=NEW.uid FOR UPDATE;
    SELECT * INTO model_record FROM mount_models WHERE model_id=NEW.model_id;
    IF unit_record.uid IS NULL OR model_record.model_id IS NULL
        OR unit_record.quantity <> 1 OR unit_record.reference <> model_record.reference
        OR NEW.health > model_record.maximum_health THEN
        RAISE EXCEPTION 'Invalid authoritative mount unit' USING ERRCODE='23514';
    END IF;
    RETURN NEW;
END;
$$;
CREATE TRIGGER inventory_mount_unit_valid
    BEFORE INSERT OR UPDATE ON inventory_mounts
    FOR EACH ROW EXECUTE FUNCTION validate_mount_unit();

CREATE FUNCTION preserve_mount_unit() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF EXISTS (SELECT 1 FROM inventory_mounts WHERE uid=OLD.uid)
        AND (NEW.quantity <> 1 OR NEW.reference <> OLD.reference OR NEW.uid <> OLD.uid) THEN
        RAISE EXCEPTION 'Mount unit cannot be stacked or redefined' USING ERRCODE='23514';
    END IF;
    RETURN NEW;
END;
$$;
CREATE TRIGGER inventory_mount_unit_preserved
    BEFORE UPDATE OF quantity,reference,uid ON inventory_items
    FOR EACH ROW EXECUTE FUNCTION preserve_mount_unit();

INSERT INTO settings(name,value) VALUES
    ('mounts_enabled','true'::jsonb),
    ('mounts_require_unlock_quest','false'::jsonb),
    ('mount_toggle_cooldown_ms','1000'::jsonb);

-- Seed: protocol/mount-models.json, native catalog; policy remains editable in DB.
INSERT INTO mount_models(model_id,reference,maximum_health,xp_per_level,maximum_level,
    speed_id,milliseconds_per_cell,gfx,meal_item_refs,xp_per_meal,
    meal_min_interval_seconds,meal_max_interval_seconds) VALUES
    (76,18682,20,50,50,6,200,24,ARRAY[12284,13358,18377]::integer[],50,72000,259200),
    (81,18704,20,50,50,6,200,24,ARRAY[12284,13358,18377]::integer[],50,72000,259200),
    (82,18705,20,50,50,6,200,24,ARRAY[12284,13358,18377]::integer[],50,72000,259200),
    (83,18706,20,50,50,6,200,24,ARRAY[12284,13358,18377]::integer[],50,72000,259200),
    (84,18709,20,50,50,6,200,25,ARRAY[12284,13358,18377]::integer[],50,72000,259200),
    (85,18710,20,50,50,6,200,25,ARRAY[12284,13358,18377]::integer[],50,72000,259200),
    (86,18711,20,50,50,6,200,25,ARRAY[12284,13358,18377]::integer[],50,72000,259200),
    (87,18712,20,50,50,6,200,25,ARRAY[12284,13358,18377]::integer[],50,72000,259200),
    (88,14422,20,50,50,6,200,28,ARRAY[12284,13358,18377]::integer[],50,72000,259200),
    (104,19274,20,50,50,6,200,26,ARRAY[12284,13358,18377]::integer[],50,86400,259200),
    (105,19275,20,50,50,6,200,26,ARRAY[12284,13358,18377]::integer[],50,86400,259200),
    (106,19276,20,50,50,6,200,26,ARRAY[12284,13358,18377]::integer[],50,86400,259200),
    (107,19277,20,50,50,6,200,26,ARRAY[12284,13358,18377]::integer[],50,86400,259200),
    (116,19555,20,50,50,6,200,27,ARRAY[12284,13358,18377]::integer[],50,72000,259200),
    (117,19556,20,50,50,6,200,27,ARRAY[12284,13358,18377]::integer[],50,72000,259200),
    (118,19557,20,50,50,6,200,27,ARRAY[12284,13358,18377]::integer[],50,72000,259200),
    (119,19558,20,50,50,6,200,27,ARRAY[12284,13358,18377]::integer[],50,72000,259200),
    (123,19724,20,50,50,6,200,28,ARRAY[12284,13358,18377]::integer[],50,72000,259200),
    (124,19725,20,50,50,6,200,28,ARRAY[12284,13358,18377]::integer[],50,72000,259200),
    (125,19726,20,50,50,6,200,28,ARRAY[12284,13358,18377]::integer[],50,72000,259200),
    (135,20624,20,50,50,6,200,24,ARRAY[]::integer[],50,72000,259200),
    (136,20638,20,50,50,6,200,24,ARRAY[]::integer[],50,72000,259200),
    (137,20622,20,50,50,6,200,24,ARRAY[]::integer[],50,72000,259200),
    (138,20741,20,50,50,6,200,29,ARRAY[12284,13358,18377]::integer[],50,72000,259200),
    (139,20742,20,50,50,6,200,29,ARRAY[12284,13358,18377]::integer[],50,72000,259200),
    (140,20743,20,50,50,6,200,29,ARRAY[12284,13358,18377]::integer[],50,72000,259200),
    (141,20744,20,50,50,6,200,29,ARRAY[12284,13358,18377]::integer[],50,72000,259200),
    (146,20760,20,50,50,6,200,30,ARRAY[12284,13358,18377]::integer[],50,72000,259200),
    (148,20811,20,50,50,6,200,30,ARRAY[12284,13358,18377]::integer[],50,72000,259200),
    (149,20812,20,50,50,6,200,30,ARRAY[12284,13358,18377]::integer[],50,72000,259200),
    (150,20813,20,50,50,6,200,30,ARRAY[12284,13358,18377]::integer[],50,72000,259200),
    (152,20916,20,50,50,6,200,31,ARRAY[12284,13358,18377]::integer[],50,72000,259200),
    (153,20917,20,50,50,6,200,31,ARRAY[12284,13358,18377]::integer[],50,72000,259200),
    (154,20918,20,50,50,6,200,31,ARRAY[12284,13358,18377]::integer[],50,72000,259200),
    (155,20919,20,50,50,6,200,31,ARRAY[12284,13358,18377]::integer[],50,72000,259200),
    (182,24161,20,50,50,6,200,32,ARRAY[12284,13358,18377]::integer[],50,72000,259200),
    (183,24162,20,50,50,6,200,33,ARRAY[12284,13358,18377]::integer[],50,72000,259200),
    (184,24163,20,50,50,6,200,34,ARRAY[12284,13358,18377]::integer[],50,72000,259200),
    (197,24860,20,50,50,6,200,35,ARRAY[12284,13358,18377]::integer[],50,72000,259200),
    (209,26884,20,50,50,6,200,36,ARRAY[12284,13358,18377]::integer[],50,72000,259200);
