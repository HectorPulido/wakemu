-- Explicit opt-in Wakemu cadence; no profile activation or original cadence claim.
CREATE TABLE environmental_regional_schedule_policies (
 policy_key text NOT NULL CHECK(length(policy_key) BETWEEN 1 AND 128),
 version integer NOT NULL CHECK(version>0),
 map_id integer NOT NULL CHECK(map_id>0),region_id integer NOT NULL CHECK(region_id>0),
 selection_policy text NOT NULL CHECK(selection_policy='wakemu_round_robin'),
 cadence_policy text NOT NULL CHECK(cadence_policy='occupied_sequential_windows'),
 intermission_ms bigint NOT NULL CHECK(intermission_ms>=0),
 authority text NOT NULL CHECK(length(authority)>0),
 source_sha256 text NOT NULL CHECK(length(source_sha256)=64),
 sealed boolean NOT NULL DEFAULT false,enabled boolean NOT NULL DEFAULT false,
 PRIMARY KEY(policy_key,version),CHECK(NOT enabled OR sealed)
);
CREATE UNIQUE INDEX environmental_one_regional_schedule
 ON environmental_regional_schedule_policies(map_id,region_id) WHERE enabled;
CREATE TABLE environmental_regional_schedule_candidates (
 policy_key text NOT NULL,version integer NOT NULL,ordinal integer NOT NULL CHECK(ordinal>=0),
 profile_key text NOT NULL,profile_version integer NOT NULL,
 PRIMARY KEY(policy_key,version,ordinal),
 UNIQUE(policy_key,version,profile_key,profile_version),
 FOREIGN KEY(policy_key,version) REFERENCES environmental_regional_schedule_policies,
 FOREIGN KEY(profile_key,profile_version) REFERENCES environmental_runtime_profiles(profile_key,version)
);
CREATE TABLE environmental_regional_schedule_slots (
 map_id integer NOT NULL CHECK(map_id>0),world_instance_id bigint NOT NULL CHECK(world_instance_id>=0),
 region_id integer NOT NULL CHECK(region_id>0),
 policy_key text NOT NULL,version integer NOT NULL,candidate_ordinal integer NOT NULL,
 event_instance_id bigint NOT NULL UNIQUE REFERENCES environmental_event_instances(instance_id),
 next_selection_at_ms bigint NOT NULL CHECK(next_selection_at_ms>=0),
 PRIMARY KEY(map_id,world_instance_id,region_id),
 FOREIGN KEY(policy_key,version,candidate_ordinal)
 REFERENCES environmental_regional_schedule_candidates(policy_key,version,ordinal)
);
CREATE FUNCTION environmental_regional_schedule_policy_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF OLD.sealed THEN
  IF TG_OP='DELETE' OR (to_jsonb(OLD)-'enabled')<>(to_jsonb(NEW)-'enabled') THEN
   RAISE EXCEPTION 'Sealed environmental regional schedule is immutable';
  END IF;
 END IF;
 IF TG_OP='DELETE' THEN RETURN OLD; END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER environmental_regional_schedule_policy_guard BEFORE UPDATE OR DELETE
 ON environmental_regional_schedule_policies FOR EACH ROW
 EXECUTE FUNCTION environmental_regional_schedule_policy_immutable();
CREATE FUNCTION environmental_regional_schedule_candidates_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE p text;v integer;
BEGIN
 IF TG_OP='DELETE' THEN p=OLD.policy_key;v=OLD.version;
 ELSE p=NEW.policy_key;v=NEW.version; END IF;
 IF EXISTS(SELECT 1 FROM environmental_regional_schedule_policies
           WHERE policy_key=p AND version=v AND sealed) THEN
  RAISE EXCEPTION 'Sealed environmental regional candidates are immutable';
 END IF;
 IF TG_OP='UPDATE' AND EXISTS(SELECT 1 FROM environmental_regional_schedule_policies
           WHERE policy_key=OLD.policy_key AND version=OLD.version AND sealed) THEN
  RAISE EXCEPTION 'Sealed environmental regional candidates are immutable';
 END IF;
 IF TG_OP='DELETE' THEN RETURN OLD; END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER environmental_regional_schedule_candidates_guard BEFORE INSERT OR UPDATE OR DELETE
 ON environmental_regional_schedule_candidates FOR EACH ROW
 EXECUTE FUNCTION environmental_regional_schedule_candidates_immutable();
