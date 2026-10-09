-- Owned Osamodas captured identities only; no imported official character roster.
CREATE TABLE character_captured_rosters (
    character_id bigint PRIMARY KEY REFERENCES characters(id) ON DELETE CASCADE,
    record jsonb NOT NULL CHECK (jsonb_typeof(record) = 'object'),
    revision bigint NOT NULL DEFAULT 0 CHECK (revision >= 0),
    CHECK (record ?& ARRAY['schema','owner_id','selected_slot','slots','available']),
    CHECK (record->>'schema' = 'wakemu-captured-roster-v1'),
    CHECK ((record->>'owner_id')::bigint = character_id),
    CHECK (jsonb_typeof(record->'slots') = 'array' AND jsonb_array_length(record->'slots') = 10),
    CHECK (jsonb_typeof(record->'available') = 'array' AND jsonb_array_length(record->'available') = 10)
);
