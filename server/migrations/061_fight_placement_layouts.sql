-- Local formation policy, independent of native terrain and group capacity.
INSERT INTO settings(name,value) VALUES
 ('fight_placement_policy','{"version":1,"slots_per_team":12,"variation_enabled":true}'::jsonb)
 ON CONFLICT(name) DO NOTHING;
CREATE TABLE fight_placement_layouts (
 fight_id integer PRIMARY KEY REFERENCES combat_fights(id),
 map_id integer NOT NULL,
 instance_id bigint NOT NULL,
 policy jsonb NOT NULL,
 layout jsonb NOT NULL,
 created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
