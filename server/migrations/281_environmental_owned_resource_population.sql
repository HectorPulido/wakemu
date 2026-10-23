-- Explicit server placement policy; original resource/action metadata stays separate.
CREATE TABLE environmental_profile_resource_population (
 profile_key text NOT NULL,version integer NOT NULL,
 source_key text NOT NULL REFERENCES environmental_resource_action_source_versions,
 placement_policy text NOT NULL CHECK(placement_policy='declared_native_cells'),
 transition_policy text NOT NULL CHECK(transition_policy='catalog_cvF'),
 source_authority text NOT NULL CHECK(length(source_authority)>0),
 PRIMARY KEY(profile_key,version),
 FOREIGN KEY(profile_key,version) REFERENCES environmental_runtime_profiles
);
CREATE TABLE environmental_profile_resource_cells (
 profile_key text NOT NULL,version integer NOT NULL,ordinal integer NOT NULL CHECK(ordinal>=0),
 x integer NOT NULL,y integer NOT NULL,z smallint NOT NULL,
 PRIMARY KEY(profile_key,version,ordinal),UNIQUE(profile_key,version,x,y),
 FOREIGN KEY(profile_key,version) REFERENCES environmental_profile_resource_population
);
CREATE TRIGGER environmental_resource_population_immutable BEFORE INSERT OR UPDATE OR DELETE
 ON environmental_profile_resource_population FOR EACH ROW EXECUTE FUNCTION environmental_profile_child_immutable();
CREATE TRIGGER environmental_resource_cells_immutable BEFORE INSERT OR UPDATE OR DELETE
 ON environmental_profile_resource_cells FOR EACH ROW EXECUTE FUNCTION environmental_profile_child_immutable();
CREATE TABLE environmental_owned_resources (
 instance_id bigint NOT NULL,resource_uid bigint PRIMARY KEY CHECK(resource_uid>0),
 entity_kind text NOT NULL DEFAULT 'resource' CHECK(entity_kind='resource'),
 map_id integer NOT NULL,world_instance_id bigint NOT NULL,
 x integer NOT NULL,y integer NOT NULL,z smallint NOT NULL,
 reference integer NOT NULL,native_step smallint NOT NULL,
 creation_time bigint NOT NULL,spawned_at_ms bigint NOT NULL,
 retired_at_ms bigint,retirement_reason text,
 CHECK((retired_at_ms IS NULL)=(retirement_reason IS NULL)),
 FOREIGN KEY(instance_id,entity_kind,resource_uid)
 REFERENCES environmental_event_memberships(instance_id,entity_kind,entity_id)
);
CREATE INDEX environmental_owned_resources_event ON environmental_owned_resources(instance_id,resource_uid);
CREATE TABLE environmental_resource_publications (
 publication_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 resource_uid bigint NOT NULL REFERENCES environmental_owned_resources,
 stage smallint NOT NULL CHECK(stage>=0),created_at_ms bigint NOT NULL,
 published_at_ms bigint,superseded_at_ms bigint
);
CREATE INDEX environmental_resource_publications_pending ON environmental_resource_publications(resource_uid,publication_id)
 WHERE published_at_ms IS NULL AND superseded_at_ms IS NULL;
