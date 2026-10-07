-- Durable per-player Wakfu-native combat drop decisions. The drop multiplier
-- is versioned and defaults to 1x; this policy does not edit client rates.
CREATE TABLE combat_drop_policy_versions (
    version integer PRIMARY KEY CHECK (version > 0),
    drop_rate_bp integer NOT NULL CHECK (drop_rate_bp BETWEEN 0 AND 1000000),
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP
);
INSERT INTO combat_drop_policy_versions(version,drop_rate_bp) VALUES (1,10000);

CREATE TABLE combat_drop_policy_active (
    singleton boolean PRIMARY KEY DEFAULT true CHECK (singleton),
    version integer NOT NULL REFERENCES combat_drop_policy_versions(version)
);
INSERT INTO combat_drop_policy_active(singleton,version) VALUES (true,1);

CREATE TABLE fight_drop_awards (
    fight_id integer NOT NULL,
    character_id bigint NOT NULL,
    account_id bigint NOT NULL,
    generation text NOT NULL CHECK (length(generation)>0),
    policy_version integer NOT NULL REFERENCES combat_drop_policy_versions(version),
    snapshot jsonb NOT NULL CHECK (jsonb_typeof(snapshot)='object'),
    snapshot_sha256 char(64) NOT NULL CHECK (snapshot_sha256 ~ '^[0-9a-f]{64}$'),
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (fight_id,character_id),
    FOREIGN KEY (fight_id,character_id,account_id)
        REFERENCES combat_fight_participants(fight_id,character_id,account_id)
);

CREATE TABLE fight_drop_attempt_receipts (
    fight_id integer NOT NULL,
    character_id bigint NOT NULL,
    defeated_actor_id bigint NOT NULL CHECK (defeated_actor_id < 0),
    monster_reference integer NOT NULL CHECK (monster_reference > 0),
    drop_row_index smallint NOT NULL CHECK (drop_row_index >= 0),
    attempt_index smallint NOT NULL CHECK (attempt_index >= 0),
    item_reference integer NOT NULL CHECK (item_reference > 0),
    success boolean NOT NULL,
    quantity integer,
    quantity_min integer NOT NULL CHECK (quantity_min BETWEEN 1 AND 32767),
    quantity_max integer NOT NULL CHECK (quantity_max BETWEEN quantity_min AND 32767),
    base_probability numeric NOT NULL CHECK (base_probability BETWEEN 0 AND 1),
    raw_probability numeric NOT NULL CHECK (raw_probability >= 0),
    effective_probability numeric NOT NULL CHECK (effective_probability BETWEEN 0 AND 1),
    draw_numerator bigint NOT NULL CHECK (draw_numerator BETWEEN 0 AND 9007199254740991),
    quantity_draw_numerator integer,
    roll_count smallint NOT NULL CHECK (roll_count BETWEEN -32768 AND 1000),
    native_roll_max smallint NOT NULL,
    native_min_prospection integer NOT NULL CHECK (native_min_prospection >= 0),
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (fight_id,character_id,defeated_actor_id,drop_row_index,attempt_index),
    FOREIGN KEY (fight_id,character_id)
        REFERENCES fight_drop_awards(fight_id,character_id) ON DELETE CASCADE,
    CHECK (
        (success AND quantity BETWEEN quantity_min AND quantity_max AND quantity_draw_numerator >= 0
            AND quantity_draw_numerator < quantity_max-quantity_min+1)
        OR (NOT success AND quantity IS NULL AND quantity_draw_numerator IS NULL)
    )
);
CREATE INDEX fight_drop_successes ON fight_drop_attempt_receipts(fight_id,character_id)
    WHERE success;
