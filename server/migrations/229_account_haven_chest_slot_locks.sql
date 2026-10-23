-- Explicit native slot locks retain reference memories without item custody.
CREATE TABLE account_haven_chest_locks (
 account_id bigint NOT NULL REFERENCES account_haven_chests(account_id) ON DELETE CASCADE,
 slot integer NOT NULL CHECK (slot >= 0 AND slot < 32767),
 reference integer NOT NULL CHECK (reference > 0),
 remembered_uid bigint NOT NULL CHECK (remembered_uid > 0),
 PRIMARY KEY(account_id,slot)
);
