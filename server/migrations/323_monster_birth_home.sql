-- Whole-group homes follow actual birth provenance, never species allowlists.
CREATE TABLE monster_group_birth_homes (
 map_id integer NOT NULL,
 instance_id bigint NOT NULL,
 group_id bigint NOT NULL,
 region_id integer NOT NULL CHECK(region_id>0),
 source_kind text NOT NULL CHECK(source_kind IN
  ('initial_population','planting','reproduction_parent','reproduction_birth',
   'archmonster_birth','environmental_birth','genesis_scope',
   'legacy_current_fallback')),
 source_key text NOT NULL,
 anchor jsonb CHECK(anchor IS NULL OR jsonb_typeof(anchor)='array'),
 recorded_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 PRIMARY KEY(map_id,instance_id,group_id),
 FOREIGN KEY(map_id,instance_id,group_id)
  REFERENCES combat_groups(map_id,instance_id,group_id) ON DELETE CASCADE
);
CREATE FUNCTION immutable_monster_group_birth_home() RETURNS trigger
 LANGUAGE plpgsql AS $$ BEGIN
 RAISE EXCEPTION 'A recorded monster group home is immutable';
 END $$;
CREATE TRIGGER monster_group_birth_home_immutable BEFORE UPDATE
 ON monster_group_birth_homes FOR EACH ROW
 EXECUTE FUNCTION immutable_monster_group_birth_home();
