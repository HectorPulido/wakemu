-- eWO equipment can leave an actor at zero HP without asserting the separate
-- native dead bit. Keep that state distinct from a combat casualty.
ALTER TABLE characters
    ADD COLUMN hp_zero_valid boolean NOT NULL DEFAULT false;

ALTER TABLE characters
    DROP CONSTRAINT characters_death_health;
ALTER TABLE characters
    ADD CONSTRAINT characters_death_health CHECK (
        health_dead = (hp = 0 AND NOT hp_zero_valid)
        AND (NOT hp_zero_valid OR (hp = 0 AND NOT health_dead))
    );

-- Exact raw HP PA input and live family21 receipts needed to reconcile an
-- equipment build without treating eWO as a flat stat delta.
CREATE TABLE character_equipment_hp_projection (
    character_id bigint PRIMARY KEY REFERENCES characters(id) ON DELETE CASCADE,
    raw_current integer NOT NULL,
    raw_maximum integer NOT NULL,
    raw_minimum integer NOT NULL,
    percentage integer NOT NULL,
    frozen boolean NOT NULL DEFAULT false,
    receipts jsonb NOT NULL DEFAULT '[]'::jsonb
        CHECK (jsonb_typeof(receipts) = 'array'),
    revision bigint NOT NULL DEFAULT 0 CHECK (revision >= 0),
    CHECK (raw_maximum >= raw_minimum),
    CHECK (raw_current BETWEEN -2147483648 AND 2147483647),
    CHECK (raw_maximum BETWEEN -2147483648 AND 2147483647),
    CHECK (raw_minimum BETWEEN -2147483648 AND 2147483647),
    CHECK (percentage BETWEEN -2147483648 AND 2147483647)
);
