-- Durable exploration visits: reconnecting in the same scene is not a new visit.
CREATE TABLE objectives_world_visits (
 character_id bigint PRIMARY KEY REFERENCES characters(id) ON DELETE CASCADE,
 map_id integer NOT NULL, instance_id bigint NOT NULL, region_id integer,
 visit_id text NOT NULL, updated_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP
);
UPDATE settings SET value=(
 SELECT jsonb_agg(command ORDER BY command)
 FROM (SELECT DISTINCT command FROM jsonb_array_elements_text(value || '["!tasks","!challenge"]'::jsonb) AS existing(command)) commands
) WHERE name='player_allowed_commands';
