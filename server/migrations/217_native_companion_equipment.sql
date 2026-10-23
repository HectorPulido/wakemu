ALTER TABLE account_companions ADD COLUMN linked boolean NOT NULL DEFAULT true;
ALTER TABLE account_companions ADD COLUMN link_revision bigint NOT NULL DEFAULT 0;
CREATE TABLE companion_equipment (
 companion_id bigint NOT NULL REFERENCES account_companions(id),
 slot smallint NOT NULL CHECK(slot BETWEEN 0 AND 24),
 uid bigint NOT NULL UNIQUE CHECK(uid>0),
 entry jsonb NOT NULL CHECK(jsonb_typeof(entry)='object'),
 PRIMARY KEY(companion_id,slot)
);
CREATE TABLE inventory_item_companions (
 uid bigint PRIMARY KEY REFERENCES inventory_items(uid) ON DELETE CASCADE,
 xp bigint NOT NULL CHECK(xp>=0)
);
CREATE TABLE companion_unlink_receipts (
 companion_id bigint NOT NULL REFERENCES account_companions(id),
 link_revision bigint NOT NULL,
 account_id bigint NOT NULL REFERENCES accounts(id),
 item_uid bigint NOT NULL,
 PRIMARY KEY(companion_id,link_revision)
);
