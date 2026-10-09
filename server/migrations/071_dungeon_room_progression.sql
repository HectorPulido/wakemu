-- Frozen compiled rosters and idempotent fight-to-room progression.
CREATE TABLE dungeon_room_runs (
 instance_id bigint PRIMARY KEY REFERENCES dungeon_instances(instance_id),
 party_id bigint NOT NULL,
 catalog_hash text NOT NULL CHECK(length(catalog_hash)=64),
 rooms jsonb NOT NULL CHECK(jsonb_typeof(rooms)='array' AND jsonb_array_length(rooms)>0),
 current_room integer NOT NULL DEFAULT 1 CHECK(current_room>0),
 status text NOT NULL DEFAULT 'active' CHECK(status IN ('active','completed')),
 revision bigint NOT NULL DEFAULT 1 CHECK(revision>0),
 FOREIGN KEY(instance_id,party_id) REFERENCES dungeon_instances(instance_id,party_id)
);
CREATE TABLE dungeon_room_encounters (
 fight_id integer PRIMARY KEY REFERENCES combat_fights(id),
 instance_id bigint NOT NULL REFERENCES dungeon_room_runs(instance_id),
 room_order integer NOT NULL CHECK(room_order>0),
 player_team smallint NOT NULL CHECK(player_team IN (0,1)),
 status text NOT NULL DEFAULT 'active' CHECK(status IN ('active','victory','defeat')),
 result_revision bigint,
 result jsonb,
 CHECK((status='active')=(result_revision IS NULL)),
 CHECK((status='active')=(result IS NULL))
);
CREATE UNIQUE INDEX dungeon_room_one_active_encounter
 ON dungeon_room_encounters(instance_id) WHERE status='active';
