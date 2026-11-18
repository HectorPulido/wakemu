-- Preserve existing item/native-combat origins and admit only explicit
-- instance-owned, source-pinned native marker carriers without invented items.
DO $$
DECLARE original_expression text;
BEGIN
    SELECT pg_get_expr(conbin,conrelid) INTO STRICT original_expression
    FROM pg_constraint WHERE conrelid='character_consumable_buffs'::regclass
        AND conname='consumable_native_origin';
    ALTER TABLE character_consumable_buffs DROP CONSTRAINT consumable_native_origin;
    EXECUTE format($check$
        ALTER TABLE character_consumable_buffs ADD CONSTRAINT consumable_native_origin
        CHECK ((%s) OR COALESCE((
            source_item_ref IS NULL AND source_item_uid IS NULL
            AND clock='event' AND level=1 AND duration_ms=0 AND remaining_ms=0
            AND jsonb_typeof(native_origin)='object'
            AND native_origin->>'kind'='owned-story-native-marker'
            AND native_origin->>'character_id'=character_id::text
            AND native_origin->>'state_id'=state_id::text
            AND (native_origin->>'instance_id')::bigint>0
            AND native_origin->>'profile_sha256' ~ '^[a-f0-9]{64}$'
            AND native_origin->>'source_sha256' ~ '^[a-f0-9]{64}$'
            AND length(native_origin->>'story_id')>0
            AND length(native_origin->>'step_id')>0
        ),false))
    $check$, original_expression);
END $$;
