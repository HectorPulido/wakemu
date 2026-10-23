-- Native consumable states; gameplay descriptors own their clock and stacking rules.
CREATE TABLE character_consumable_buffs (
    uid bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    character_id bigint NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
    state_id integer NOT NULL CHECK (state_id > 0),
    level integer NOT NULL CHECK (level > 0 AND level <= 32767),
    source_item_ref integer NOT NULL CHECK (source_item_ref > 0),
    source_item_uid bigint NOT NULL CHECK (source_item_uid > 0),
    clock text NOT NULL CHECK (clock IN ('wall','online','event')),
    duration_ms bigint NOT NULL CHECK (duration_ms >= 0),
    remaining_ms bigint NOT NULL CHECK (remaining_ms >= 0),
    expires_ms bigint,
    online_generation text,
    online_anchor_ms bigint,
    combat_id bigint CHECK (combat_id > 0),
    metadata jsonb NOT NULL CHECK (jsonb_typeof(metadata) = 'object'),
    UNIQUE(character_id,state_id),
    CHECK ((clock='wall' AND expires_ms IS NOT NULL AND online_generation IS NULL AND online_anchor_ms IS NULL)
        OR (clock='online' AND expires_ms IS NULL AND
            ((online_generation IS NULL AND online_anchor_ms IS NULL)
                OR (online_generation IS NOT NULL AND online_anchor_ms IS NOT NULL)))
        OR (clock='event' AND duration_ms=0 AND remaining_ms=0 AND expires_ms IS NULL
            AND online_generation IS NULL AND online_anchor_ms IS NULL)),
    CHECK (clock='event' OR duration_ms > 0)
);
CREATE INDEX character_consumable_buffs_owner ON character_consumable_buffs(character_id);
