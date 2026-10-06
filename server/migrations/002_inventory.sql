-- One allocator for items, bags and client UID reservations; gaps are allowed.
CREATE SEQUENCE inventory_uid AS bigint START WITH 1099511627776 NO CYCLE;

CREATE TABLE inventory_containers (
    character_id bigint NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
    uid bigint NOT NULL DEFAULT nextval('inventory_uid') UNIQUE,
    reference integer NOT NULL CHECK (reference > 0),
    kind smallint NOT NULL CHECK (kind BETWEEN 0 AND 127),
    capacity smallint NOT NULL CHECK (capacity BETWEEN 1 AND 32767),
    flags smallint NOT NULL CHECK (flags BETWEEN 0 AND 255),
    PRIMARY KEY (character_id, kind),
    UNIQUE (character_id, uid)
);

CREATE TABLE inventory_initialized (
    character_id bigint PRIMARY KEY REFERENCES characters(id) ON DELETE CASCADE
);

CREATE TABLE inventory_items (
    uid bigint PRIMARY KEY DEFAULT nextval('inventory_uid'),
    character_id bigint NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
    reference integer NOT NULL CHECK (reference > 0),
    quantity smallint NOT NULL CHECK (quantity BETWEEN 1 AND 32767),
    container bigint NOT NULL,
    slot smallint NOT NULL CHECK (slot >= 0),
    FOREIGN KEY (character_id, container)
        REFERENCES inventory_containers(character_id, uid),
    UNIQUE (container, slot)
);
CREATE INDEX inventory_items_owner ON inventory_items(character_id);

CREATE TABLE inventory_item_elements (
    uid bigint PRIMARY KEY REFERENCES inventory_items(uid) ON DELETE CASCADE,
    damage_elements smallint NOT NULL
        CHECK (damage_elements BETWEEN 0 AND 30 AND damage_elements % 2 = 0),
    resistance_elements smallint NOT NULL
        CHECK (resistance_elements BETWEEN 0 AND 30 AND resistance_elements % 2 = 0)
);

CREATE TABLE inventory_reserved_uids (
    uid bigint PRIMARY KEY DEFAULT nextval('inventory_uid'),
    account_id bigint NOT NULL REFERENCES accounts(id),
    generation text NOT NULL,
    character_id bigint NOT NULL,
    used_request bytea,
    FOREIGN KEY (account_id, character_id) REFERENCES characters(account_id, id)
);
CREATE INDEX inventory_reserved_lease
    ON inventory_reserved_uids(account_id, generation, character_id)
    WHERE used_request IS NULL;
