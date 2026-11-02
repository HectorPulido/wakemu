-- Durable ownership for pinned dungeon resource obstacles.
CREATE TABLE dungeon_resource_obstacles (
 instance_id bigint NOT NULL REFERENCES dungeon_instances(instance_id),
 obstacle_key text NOT NULL CHECK(length(obstacle_key) BETWEEN 1 AND 128),
 resource_uid bigint NOT NULL UNIQUE CHECK(resource_uid>0),
 policy_sha256 text NOT NULL CHECK(length(policy_sha256)=64),
 map_id integer NOT NULL,
 x integer NOT NULL,y integer NOT NULL,z smallint NOT NULL,
 resource_reference integer NOT NULL CHECK(resource_reference>0),
 current_stage smallint NOT NULL CHECK(current_stage BETWEEN 0 AND 127),
 creation_time bigint NOT NULL CHECK(creation_time>=0),
 last_token text,
 PRIMARY KEY(instance_id,obstacle_key),
 UNIQUE(map_id,instance_id,x,y)
);
