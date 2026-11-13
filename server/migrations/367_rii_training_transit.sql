-- A temporary, owner-scoped move to the native floor of Rii's dojo.
-- The original encounter relocation is not present in the client data.
CREATE TABLE rii_training_transits (
    character_id bigint PRIMARY KEY,
    account_id bigint NOT NULL,
    source_map integer NOT NULL CHECK (source_map = 1388),
    source_instance bigint NOT NULL CHECK (source_instance = 0),
    source_x integer NOT NULL,
    source_y integer NOT NULL,
    source_z smallint NOT NULL,
    floor_x integer NOT NULL,
    floor_y integer NOT NULL,
    floor_z smallint NOT NULL CHECK (floor_z = 0),
    -- A crash between moving and encounter creation must recover on login.
    setup_failed boolean NOT NULL DEFAULT true,
    lesson_objective integer NOT NULL CHECK (lesson_objective IN (10608, 10609, 10610, 10611)),
    UNIQUE (source_map, source_instance, source_x, source_y, source_z),
    UNIQUE (source_map, source_instance, floor_x, floor_y, floor_z),
    FOREIGN KEY (account_id, character_id) REFERENCES characters(account_id, id)
);
