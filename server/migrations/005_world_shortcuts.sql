CREATE TABLE character_world_shortcuts (
    character_id bigint NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
    bar_number smallint NOT NULL CHECK (bar_number BETWEEN 0 AND 3),
    slot smallint NOT NULL CHECK (slot BETWEEN 0 AND 7),
    shortcut_type smallint NOT NULL CHECK (shortcut_type IN (1,2)),
    long_value bigint NOT NULL CHECK (long_value > 0),
    int_value integer NOT NULL CHECK (int_value > 0),
    extra_int integer NOT NULL,
    PRIMARY KEY (character_id,bar_number,slot),
    CHECK (shortcut_type <> 1 OR long_value = int_value)
);
