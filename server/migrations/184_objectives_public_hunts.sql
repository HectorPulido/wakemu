-- Public, finite, native-stat encounters. Spawn and terminal outboxes are durable.
CREATE TABLE objectives_public_hunts (
 id bigserial PRIMARY KEY,
 monster_ref integer NOT NULL,
 monster_name text NOT NULL,
 level integer NOT NULL CHECK(level BETWEEN 1 AND 200),
 map_id integer NOT NULL,
 map_name text NOT NULL,
 region_id integer NOT NULL,
 anchor jsonb NOT NULL,
 group_id bigint UNIQUE,
 monster_id bigint UNIQUE,
 status text NOT NULL DEFAULT 'pending' CHECK(status IN('pending','alive','in_fight','defeated','expired')),
 reward_snapshot jsonb NOT NULL,
 points integer NOT NULL DEFAULT 100 CHECK(points>=0),
 created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
 expires_at timestamptz NOT NULL,
 fight_id integer REFERENCES combat_fights(id),
 completed_at timestamptz,
 published_at timestamptz,
 removed_at timestamptz
);
CREATE UNIQUE INDEX objectives_public_hunt_one_active ON objectives_public_hunts ((1)) WHERE status IN('pending','alive','in_fight');
CREATE TABLE objectives_public_hunt_winners (
 hunt_id bigint NOT NULL REFERENCES objectives_public_hunts(id),
 account_id bigint NOT NULL REFERENCES accounts(id),
 character_id bigint NOT NULL REFERENCES characters(id),
 PRIMARY KEY(hunt_id,account_id)
);
INSERT INTO objectives_definitions(key,definition) VALUES
('public-world-hunt','{"key":"public-world-hunt","title":"World hunt","description":"Find and defeat the announced public-world monster.","kind":"mission","scope":"account","enabled":false,"objectives":[{"key":"kill","event":"public_hunt_completed","filters":{},"target":1}],"schedule":{"type":"once"},"rewards":[{"kind":"scaled","policy_key":"content-v1.dungeon"}],"prerequisite_keys":[]}'::jsonb)
ON CONFLICT(key) DO NOTHING;
INSERT INTO settings(name,value) VALUES('objectives_public_hunts','{"enabled":true,"lifetime_seconds":3600,"points":100}') ON CONFLICT(name) DO NOTHING;
