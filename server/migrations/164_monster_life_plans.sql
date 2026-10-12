-- Decisions survive replanning and restarts; active timers alone charge time.
CREATE TABLE monster_life_plans (
 map_id integer NOT NULL, instance_id bigint NOT NULL, monster_id bigint NOT NULL,
 kind text NOT NULL CHECK(kind IN ('maturation','reproduction')),
 reference integer NOT NULL, seed text NOT NULL CHECK(length(seed)=64),
 incarnation text NOT NULL CHECK(length(incarnation)=32),
 policy jsonb NOT NULL CHECK(jsonb_typeof(policy)='object'),
 version integer NOT NULL CHECK(version=1), block_start bigint NOT NULL CHECK(block_start>0),
 events jsonb NOT NULL CHECK(jsonb_typeof(events)='array' AND jsonb_array_length(events)=32),
 PRIMARY KEY(map_id,instance_id,monster_id,kind),
 FOREIGN KEY(map_id,instance_id,monster_id) REFERENCES combat_group_members(map_id,instance_id,monster_id) ON DELETE CASCADE
);
CREATE FUNCTION delete_defeated_monster_life_plans() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF NEW.status='defeated' AND OLD.status IS DISTINCT FROM NEW.status THEN
  DELETE FROM monster_life_plans p USING combat_group_members m
   WHERE m.map_id=NEW.map_id AND m.instance_id=NEW.instance_id AND m.group_id=NEW.group_id
     AND p.map_id=m.map_id AND p.instance_id=m.instance_id AND p.monster_id=m.monster_id;
  UPDATE monster_maturation_timers t SET due=false,last_active_ms=NULL,observer_generation=NULL,
   remaining_ms=(SELECT (value->>'interval_ms')::bigint FROM settings WHERE name='monster_maturation')
   FROM combat_group_members m WHERE m.map_id=NEW.map_id AND m.instance_id=NEW.instance_id
    AND m.group_id=NEW.group_id AND t.map_id=m.map_id AND t.instance_id=m.instance_id AND t.monster_id=m.monster_id;
  UPDATE monster_reproduction_timers t SET due=false,last_active_ms=NULL,observer_generation=NULL,
   remaining_ms=(SELECT (value->>'interval_ms')::bigint FROM settings WHERE name='monster_reproduction')
   FROM combat_group_members m WHERE m.map_id=NEW.map_id AND m.instance_id=NEW.instance_id
    AND m.group_id=NEW.group_id AND t.map_id=m.map_id AND t.instance_id=m.instance_id AND t.monster_id=m.monster_id;
 END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER combat_groups_delete_life_plans AFTER UPDATE OF status ON combat_groups
 FOR EACH ROW EXECUTE FUNCTION delete_defeated_monster_life_plans();
