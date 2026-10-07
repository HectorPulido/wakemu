-- A successful native drop is either placed in ordinary inventory or retained
-- in a durable temporary-inventory row. The natural key is the exact 042 roll.
CREATE TABLE fight_drop_delivery_receipts (
    fight_id integer NOT NULL,
    character_id bigint NOT NULL,
    defeated_actor_id bigint NOT NULL,
    drop_row_index smallint NOT NULL,
    attempt_index smallint NOT NULL,
    item_reference integer NOT NULL CHECK (item_reference > 0),
    awarded_quantity integer NOT NULL CHECK (awarded_quantity BETWEEN 1 AND 32767),
    inventory_quantity integer NOT NULL CHECK (inventory_quantity >= 0),
    temporary_quantity integer NOT NULL CHECK (temporary_quantity >= 0),
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (fight_id,character_id,defeated_actor_id,drop_row_index,attempt_index),
    FOREIGN KEY (fight_id,character_id,defeated_actor_id,drop_row_index,attempt_index)
        REFERENCES fight_drop_attempt_receipts
        (fight_id,character_id,defeated_actor_id,drop_row_index,attempt_index),
    CHECK (inventory_quantity + temporary_quantity = awarded_quantity)
);

CREATE TABLE temporary_combat_items (
    uid bigint PRIMARY KEY DEFAULT nextval('inventory_uid'),
    character_id bigint NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
    reference integer NOT NULL CHECK (reference > 0),
    quantity integer NOT NULL CHECK (quantity BETWEEN 1 AND 32767),
    damage_elements smallint,
    resistance_elements smallint,
    fight_id integer NOT NULL,
    defeated_actor_id bigint NOT NULL,
    drop_row_index smallint NOT NULL,
    attempt_index smallint NOT NULL,
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (fight_id,character_id,defeated_actor_id,drop_row_index,attempt_index),
    FOREIGN KEY (fight_id,character_id,defeated_actor_id,drop_row_index,attempt_index)
        REFERENCES fight_drop_delivery_receipts
        (fight_id,character_id,defeated_actor_id,drop_row_index,attempt_index)
        ON DELETE CASCADE,
    CHECK (
        (damage_elements IS NULL AND resistance_elements IS NULL)
        OR (
            damage_elements BETWEEN 0 AND 30 AND damage_elements % 2 = 0
            AND resistance_elements BETWEEN 0 AND 30 AND resistance_elements % 2 = 0
        )
    )
);
CREATE INDEX temporary_combat_items_owner ON temporary_combat_items(character_id,uid);

-- The native claim/list requests have no request token. Bind their exact body
-- to the source character so a retry after a lost response cannot move twice.
CREATE TABLE temporary_inventory_transfer_receipts (
    source_character_id bigint NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
    operation smallint NOT NULL CHECK (operation IN (1,2)),
    request_sha256 char(64) NOT NULL CHECK (request_sha256 ~ '^[0-9a-f]{64}$'),
    request_body bytea NOT NULL,
    destination_character_id bigint NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (source_character_id,operation,request_sha256),
    CHECK (octet_length(request_body) > 0)
);
