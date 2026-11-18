-- Profile-pinned public story resources use normal native harvest occupations.
CREATE TABLE quest_resource_slots (
 resource_uid bigint PRIMARY KEY CHECK(resource_uid>0),
 profile_id text NOT NULL,
 profile_sha256 text NOT NULL CHECK(length(profile_sha256)=64),
 policy jsonb NOT NULL CHECK(jsonb_typeof(policy)='object'),
 map_id integer NOT NULL CHECK(map_id>0),
 instance_id bigint NOT NULL DEFAULT 0 CHECK(instance_id=0),
 x integer NOT NULL,y integer NOT NULL,z smallint NOT NULL,
 resource_reference integer NOT NULL CHECK(resource_reference>0),
 stage smallint NOT NULL CHECK(stage>0 AND stage<>16),
 enabled boolean NOT NULL DEFAULT TRUE,
 UNIQUE(map_id,instance_id,x,y)
);
