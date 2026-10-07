INSERT INTO settings(name,value) VALUES
 ('monster_initial_population','{"version":1,"enabled":true,"members_per_zone":2}');
-- A tombstone-independent marker: extermination must never cause a refill.
CREATE TABLE monster_initial_population (
 map_id integer NOT NULL CHECK(map_id>0),
 instance_id bigint NOT NULL CHECK(instance_id>=0),
 region_id integer NOT NULL CHECK(region_id>0),
 policy_version integer NOT NULL CHECK(policy_version>0),
 group_id bigint NOT NULL CHECK(group_id>0),
 initial_members jsonb NOT NULL CHECK(jsonb_typeof(initial_members)='array'),
 PRIMARY KEY(map_id,instance_id,region_id)
);
