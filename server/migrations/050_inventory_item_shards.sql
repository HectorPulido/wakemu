-- Persist the client's complete ProtoShard state by item UID.  The blob is
-- the native lD/ProtoShard protobuf used by opcode 13766 and kX field 52.
-- An absent row means no known socket state; it is never synthesized at load.
CREATE TABLE inventory_item_shards (
    uid bigint PRIMARY KEY REFERENCES inventory_items(uid) ON DELETE CASCADE,
    shard_state bytea NOT NULL CHECK (octet_length(shard_state) BETWEEN 1 AND 65536)
);
