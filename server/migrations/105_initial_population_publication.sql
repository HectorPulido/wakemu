-- New background seed registrations require retryable world projection.
-- Existing boot-time seeds are intentionally not retroactively republished.
CREATE TABLE monster_initial_population_publication (
 map_id integer NOT NULL,
 instance_id bigint NOT NULL,
 region_id integer NOT NULL,
 group_id bigint NOT NULL CHECK(group_id>0),
 published_at timestamptz,
 PRIMARY KEY(map_id,instance_id,region_id),
 FOREIGN KEY(map_id,instance_id,region_id)
  REFERENCES monster_initial_population(map_id,instance_id,region_id)
);
CREATE INDEX monster_initial_population_publication_pending
 ON monster_initial_population_publication(map_id,instance_id,region_id)
 WHERE published_at IS NULL;
