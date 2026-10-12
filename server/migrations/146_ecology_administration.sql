-- Administrative removal survives combat release and world recovery.
ALTER TABLE combat_groups ADD COLUMN ecology_admin_removed_ids jsonb NOT NULL DEFAULT '[]'::jsonb
 CHECK (jsonb_typeof(ecology_admin_removed_ids)='array');
CREATE FUNCTION ecology_admin_group_release() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE remaining jsonb;
BEGIN
 IF NEW.status='available' AND jsonb_array_length(NEW.ecology_admin_removed_ids)>0 THEN
  SELECT coalesce(jsonb_agg(member),'[]'::jsonb) INTO remaining
  FROM jsonb_array_elements(NEW.members) member
  WHERE NOT NEW.ecology_admin_removed_ids @> jsonb_build_array(member->'id');
  IF jsonb_array_length(remaining)=0 THEN
   NEW.status := 'defeated';
   NEW.defeated_at := CURRENT_TIMESTAMP;
  ELSE NEW.members := remaining;
  END IF;
 END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER ecology_admin_group_release BEFORE UPDATE ON combat_groups
 FOR EACH ROW EXECUTE FUNCTION ecology_admin_group_release();

-- Administrative mutations and their exact scope commit with population state.
CREATE TABLE ecology_admin_operations (
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 account_id bigint NOT NULL REFERENCES accounts(id),
 character_id bigint NOT NULL REFERENCES characters(id),
 command text NOT NULL CHECK(command IN ('!nuke','!nuke-all','!genesis','!genesis-all')),
 outcome jsonb NOT NULL CHECK(jsonb_typeof(outcome)='object'),
 created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX ecology_admin_operations_created ON ecology_admin_operations(created_at,id);
