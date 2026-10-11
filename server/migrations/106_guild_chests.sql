-- Guild custody reuses account chest item planning; native access is opt-in.
UPDATE settings SET value=jsonb_set(value,'{chest}',
 '{"enabled":false,"compartments":{},"access_points":[]}'::jsonb)
WHERE name='guild_policy' AND NOT (value ? 'chest');
CREATE TABLE guild_chests (
 guild_id bigint NOT NULL REFERENCES guilds(id),
 compartment_id integer NOT NULL CHECK(compartment_id>=0),
 capacity integer NOT NULL CHECK(capacity BETWEEN 1 AND 128),
 revision bigint NOT NULL DEFAULT 0 CHECK(revision>=0),
 items jsonb NOT NULL DEFAULT '[]' CHECK(jsonb_typeof(items)='array'),
 PRIMARY KEY(guild_id,compartment_id)
);
CREATE TABLE guild_chest_receipts (
 character_id bigint NOT NULL REFERENCES characters(id),
 operation_key text NOT NULL CHECK(length(operation_key) BETWEEN 1 AND 200),
 guild_id bigint NOT NULL REFERENCES guilds(id),
 request jsonb NOT NULL,
 created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
 PRIMARY KEY(character_id,operation_key)
);
