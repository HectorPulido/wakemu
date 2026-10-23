-- Explicit Wakemu populations using positive native scenario breed parameters.
-- No original type74 roster is inferred; no profile is activated here.
CREATE TABLE environmental_profile_group_population (
 profile_key text NOT NULL,version integer NOT NULL,source_key text NOT NULL,
 native_scenario_id integer NOT NULL,
 policy_contract text NOT NULL CHECK(policy_contract='wakemu.explicit-native-breed-roster.v1'),
 source_authority text NOT NULL CHECK(length(source_authority)>0),
 PRIMARY KEY(profile_key,version),
 FOREIGN KEY(profile_key,version) REFERENCES environmental_runtime_profiles(profile_key,version),
 FOREIGN KEY(source_key,native_scenario_id) REFERENCES environmental_native_scenarios(source_key,scenario_id)
);
CREATE TABLE environmental_profile_group_cells (
 profile_key text NOT NULL,version integer NOT NULL,group_ordinal integer NOT NULL CHECK(group_ordinal>=0),
 member_ordinal integer NOT NULL CHECK(member_ordinal BETWEEN 0 AND 7),
 group_reference integer NOT NULL CHECK(group_reference>0),monster_reference integer NOT NULL CHECK(monster_reference>0),
 native_level integer NOT NULL CHECK(native_level BETWEEN 1 AND 32767),
 x integer NOT NULL,y integer NOT NULL,z smallint NOT NULL,
 PRIMARY KEY(profile_key,version,group_ordinal,member_ordinal),UNIQUE(profile_key,version,x,y,z),
 FOREIGN KEY(profile_key,version) REFERENCES environmental_profile_group_population(profile_key,version),
 FOREIGN KEY(profile_key,version,group_reference,monster_reference)
 REFERENCES environmental_profile_group_composition(profile_key,version,group_reference,monster_reference)
);
CREATE TABLE environmental_owned_groups (
 instance_id bigint NOT NULL REFERENCES environmental_event_instances(instance_id),
 group_ordinal integer NOT NULL,group_id bigint NOT NULL CHECK(group_id>0),
 map_id integer NOT NULL,world_instance_id bigint NOT NULL,group_reference integer NOT NULL,
 source_key text NOT NULL,roster_sha256 text NOT NULL CHECK(length(roster_sha256)=64),
 spawned_at_ms bigint NOT NULL,retired_at_ms bigint,
 PRIMARY KEY(instance_id,group_ordinal),UNIQUE(map_id,world_instance_id,group_id)
);
CREATE TABLE environmental_owned_group_members (
 instance_id bigint NOT NULL,group_ordinal integer NOT NULL,monster_id bigint NOT NULL CHECK(monster_id<0),
 monster_reference integer NOT NULL,native_level integer NOT NULL,
 PRIMARY KEY(instance_id,monster_id),
 FOREIGN KEY(instance_id,group_ordinal) REFERENCES environmental_owned_groups(instance_id,group_ordinal)
);
CREATE TABLE environmental_group_publications (
 instance_id bigint NOT NULL,group_ordinal integer NOT NULL,
 kind text NOT NULL CHECK(kind IN ('spawn','despawn')),created_at_ms bigint NOT NULL,
 published_at_ms bigint,superseded_at_ms bigint,
 PRIMARY KEY(instance_id,group_ordinal,kind),
 FOREIGN KEY(instance_id,group_ordinal) REFERENCES environmental_owned_groups(instance_id,group_ordinal)
);
CREATE FUNCTION guard_environmental_group_population_policy() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE sealed_profile boolean;
BEGIN
 SELECT COALESCE(bool_or(sealed),FALSE) INTO sealed_profile FROM environmental_runtime_profiles
 WHERE (profile_key,version)=(NEW.profile_key,NEW.version)
    OR (profile_key,version)=(OLD.profile_key,OLD.version);
 IF sealed_profile THEN RAISE EXCEPTION 'Sealed environmental group population policy'; END IF;
 RETURN COALESCE(NEW,OLD);
END $$;
CREATE TRIGGER immutable_sealed_group_population BEFORE INSERT OR UPDATE OR DELETE
 ON environmental_profile_group_population FOR EACH ROW EXECUTE FUNCTION guard_environmental_group_population_policy();
CREATE TRIGGER immutable_sealed_group_cells BEFORE INSERT OR UPDATE OR DELETE
 ON environmental_profile_group_cells FOR EACH ROW EXECUTE FUNCTION guard_environmental_group_population_policy();
