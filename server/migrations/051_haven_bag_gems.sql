-- Preserve physical gem items while they are installed in an owned haven bag.
-- The UID moves between inventory_items and this table; it is never present in both.
CREATE TABLE haven_bag_gems (
    uid bigint PRIMARY KEY CHECK (uid > 0),
    account_id bigint NOT NULL,
    character_id bigint NOT NULL,
    room_index smallint NOT NULL CHECK (room_index BETWEEN 0 AND 8),
    primary_slot boolean NOT NULL,
    reference integer NOT NULL CHECK (reference > 0),
    source_uid bigint NOT NULL CHECK (source_uid > 0),
    damage_elements smallint,
    resistance_elements smallint,
    shard_state bytea,
    CHECK ((damage_elements IS NULL) = (resistance_elements IS NULL)),
    CHECK (damage_elements IS NULL OR damage_elements BETWEEN 0 AND 30),
    CHECK (resistance_elements IS NULL OR resistance_elements BETWEEN 0 AND 30),
    CHECK (shard_state IS NULL OR octet_length(shard_state) BETWEEN 1 AND 65536),
    FOREIGN KEY (account_id, character_id) REFERENCES characters(account_id, id),
    UNIQUE (character_id, room_index, primary_slot),
    UNIQUE (character_id, uid)
);
CREATE INDEX haven_bag_gems_owner ON haven_bag_gems(account_id, character_id);
