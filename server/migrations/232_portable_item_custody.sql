-- Mutable metadata follows a physical UID while its inventory row is absent.
CREATE TABLE portable_item_custody (
 uid bigint PRIMARY KEY CHECK(uid>0),
 account_id bigint NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
 source_character_id bigint NOT NULL CHECK(source_character_id>0),
 reference integer NOT NULL CHECK(reference>0),
 kind text NOT NULL CHECK(kind IN ('bag','furniture')),
 metadata jsonb NOT NULL CHECK(jsonb_typeof(metadata)='object')
);
