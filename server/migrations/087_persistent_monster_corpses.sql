-- Presentation-only remains, independent from combat/rewards/respawn ownership.
INSERT INTO settings(name,value) VALUES (
 'monster_corpse_policy', '{"lifetime_seconds":3600}'::jsonb
) ON CONFLICT(name) DO NOTHING;
CREATE TABLE monster_corpses (
 fight_id integer NOT NULL REFERENCES combat_fights(id),
 source_actor_id bigint NOT NULL CHECK(source_actor_id<0),
 actor_id bigint NOT NULL UNIQUE CHECK(actor_id<0 AND actor_id>=-9007199254740992),
 map_id bigint NOT NULL CHECK(map_id>0),
 instance_id bigint NOT NULL CHECK(instance_id>=0),
 monster jsonb NOT NULL CHECK(jsonb_typeof(monster)='object'),
 lifetime_seconds integer NOT NULL CHECK(lifetime_seconds BETWEEN 1 AND 2678400),
 created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
 expires_at timestamptz NOT NULL,
 expiry_published boolean NOT NULL DEFAULT false,
 PRIMARY KEY(fight_id,source_actor_id),
 CHECK(expires_at=created_at + make_interval(secs=>lifetime_seconds))
);
CREATE INDEX monster_corpses_visibility ON monster_corpses(map_id,instance_id,expires_at);
CREATE INDEX monster_corpses_expiry ON monster_corpses(expires_at);
CREATE INDEX monster_corpses_pending_expiry ON monster_corpses(expires_at)
 WHERE NOT expiry_published;
