-- The native 12487 request sets elemental masks for one owned UID. The row is
-- the latest committed choice; repeating that choice is a safe no-op.
CREATE TABLE inventory_element_selection_receipts (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    account_id bigint NOT NULL REFERENCES accounts(id),
    character_id bigint NOT NULL,
    uid bigint NOT NULL CHECK (uid > 0),
    damage_elements smallint NOT NULL
        CHECK (damage_elements BETWEEN 0 AND 30 AND damage_elements % 2 = 0),
    resistance_elements smallint NOT NULL
        CHECK (resistance_elements BETWEEN 0 AND 30 AND resistance_elements % 2 = 0),
    applied_at timestamptz NOT NULL,
    FOREIGN KEY (account_id, character_id) REFERENCES characters(account_id, id),
    UNIQUE (character_id, uid)
);
