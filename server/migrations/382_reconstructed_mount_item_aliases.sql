-- Keep the forty verified native models distinct from explicit server item aliases.
-- Original aMo has no32993 alias. This policy uses the verified ordinary Milubo
-- body116/ref19555;32993 retains its own native item effects and equipment rules.
CREATE TABLE IF NOT EXISTS mount_item_aliases (
    reference integer PRIMARY KEY CHECK (reference > 0),
    model_id integer NOT NULL REFERENCES mount_models(model_id),
    provenance text NOT NULL CHECK (length(provenance) > 0),
    qualification jsonb NOT NULL CHECK (jsonb_typeof(qualification) = 'object')
);

-- A targeted operational application may precede canonical migration382.
-- Reuse only this exact feature table; never accept an incompatible registry.
DO $$
BEGIN
    IF (SELECT jsonb_agg(jsonb_build_array(attname,format_type(atttypid,atttypmod),attnotnull) ORDER BY attnum)
        FROM pg_attribute WHERE attrelid='mount_item_aliases'::regclass
        AND attnum>0 AND NOT attisdropped) IS DISTINCT FROM
        '[["reference","integer",true],["model_id","integer",true],["provenance","text",true],["qualification","jsonb",true]]'::jsonb
        OR NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conrelid='mount_item_aliases'::regclass
                       AND contype='p' AND conkey=ARRAY[1]::smallint[])
        OR NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conrelid='mount_item_aliases'::regclass
                       AND contype='f' AND conkey=ARRAY[2]::smallint[]
                       AND confrelid='mount_models'::regclass AND confkey=ARRAY[1]::smallint[])
    THEN
        RAISE EXCEPTION 'Incompatible mount item alias registry' USING ERRCODE='23514';
    END IF;
END;
$$;

INSERT INTO mount_item_aliases(reference,model_id,provenance,qualification)
VALUES(32993,116,'wakemu.explicit_ordinary_milubo_item_variant.v1',
    '{"original_alias_recovered":false,"verified_base_reference":19555,"verified_model_id":116,"body_gfx":27,"policy":"Use the ordinary Milubo runtime body; preserve variant item reference, effects and eligibility."}'::jsonb)
ON CONFLICT(reference) DO NOTHING;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM mount_item_aliases WHERE reference=32993 AND model_id=116
        AND provenance='wakemu.explicit_ordinary_milubo_item_variant.v1'
        AND qualification='{"original_alias_recovered":false,"verified_base_reference":19555,"verified_model_id":116,"body_gfx":27,"policy":"Use the ordinary Milubo runtime body; preserve variant item reference, effects and eligibility."}'::jsonb)
    THEN
        RAISE EXCEPTION 'Existing Milubo item alias differs from qualified policy' USING ERRCODE='23514';
    END IF;
END;
$$;

CREATE OR REPLACE VIEW mount_item_models AS
SELECT * FROM mount_models
UNION ALL
SELECT model.model_id,alias.reference,model.maximum_health,model.xp_per_level,
       model.maximum_level,model.speed_id,model.milliseconds_per_cell,model.gfx,
       model.meal_item_refs,model.xp_per_meal,model.meal_min_interval_seconds,
       model.meal_max_interval_seconds
FROM mount_item_aliases alias JOIN mount_models model USING(model_id)
WHERE NOT EXISTS (SELECT 1 FROM mount_models native WHERE native.reference=alias.reference);

CREATE OR REPLACE FUNCTION validate_mount_unit() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    unit_record inventory_items%ROWTYPE;
    model_record mount_item_models%ROWTYPE;
BEGIN
    SELECT * INTO unit_record FROM inventory_items WHERE uid=NEW.uid FOR UPDATE;
    SELECT * INTO model_record FROM mount_item_models
        WHERE reference=unit_record.reference AND model_id=NEW.model_id;
    IF unit_record.uid IS NULL OR model_record.model_id IS NULL
        OR unit_record.quantity <> 1 OR NEW.health > model_record.maximum_health THEN
        RAISE EXCEPTION 'Invalid authoritative mount unit' USING ERRCODE='23514';
    END IF;
    RETURN NEW;
END;
$$;
