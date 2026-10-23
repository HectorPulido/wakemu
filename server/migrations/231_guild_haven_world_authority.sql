CREATE SEQUENCE haven_world_instance_ids AS bigint START WITH 1152921504606846976 NO CYCLE;
-- Explicit Wakemu assignment of a private world scope; no worlds are assigned here.
CREATE TABLE guild_haven_worlds (
 guild_id bigint PRIMARY KEY REFERENCES guilds(id),
 native_world_id bigint NOT NULL UNIQUE CHECK(native_world_id<0),
 map_id integer NOT NULL CHECK(map_id>0),
 instance_id bigint NOT NULL UNIQUE CHECK(instance_id>0),
 entry_x integer NOT NULL,
 entry_y integer NOT NULL,
 entry_z smallint NOT NULL,
 assigned_by bigint NOT NULL REFERENCES accounts(id),
 assignment_origin text NOT NULL CHECK(assignment_origin='wakemu_explicit_private_assignment_v1'),
 created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
 UNIQUE(map_id,instance_id),
 CHECK(native_world_id=-guild_id)
);
CREATE TABLE haven_world_bomb_uses (
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 guild_id bigint NOT NULL REFERENCES guild_haven_worlds(guild_id),
 account_id bigint NOT NULL REFERENCES accounts(id),
 character_id bigint NOT NULL REFERENCES characters(id),
 source_uid bigint NOT NULL,
 source_reference integer NOT NULL,
 native_world_id bigint NOT NULL,
 map_id integer NOT NULL,
 instance_id bigint NOT NULL CHECK(instance_id>0),
 center_x integer NOT NULL,
 center_y integer NOT NULL,
 radius integer NOT NULL CHECK(radius IN(4,8,16)),
 outcome jsonb NOT NULL CHECK(jsonb_typeof(outcome)='object'),
 created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE haven_world_visits (
 character_id bigint PRIMARY KEY REFERENCES characters(id),
 guild_id bigint NOT NULL REFERENCES guild_haven_worlds(guild_id),
 source jsonb NOT NULL CHECK(jsonb_typeof(source)='object'),
 entered_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
 returned_at timestamptz
);
CREATE TABLE haven_world_transitions (
 token text PRIMARY KEY,
 account_id bigint NOT NULL REFERENCES accounts(id),
 character_id bigint NOT NULL REFERENCES characters(id),
 kind text NOT NULL CHECK(kind IN('entry','return')),
 source jsonb NOT NULL CHECK(jsonb_typeof(source)='object'),
 destination jsonb NOT NULL CHECK(jsonb_typeof(destination)='object'),
 cohort jsonb NOT NULL CHECK(jsonb_typeof(cohort)='array'),
 created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
 delivered_at timestamptz
);
CREATE UNIQUE INDEX haven_world_transition_pending ON haven_world_transitions(character_id)
 WHERE delivered_at IS NULL;
