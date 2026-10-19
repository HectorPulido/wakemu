-- Native ACCOUNT_QUEST quantities belong to the account, never a hero's bag.
CREATE TABLE account_quest_items (
    account_id bigint NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    reference integer NOT NULL CHECK (reference > 0),
    quantity smallint NOT NULL CHECK (quantity BETWEEN 1 AND 32767),
    PRIMARY KEY (account_id, reference)
);
