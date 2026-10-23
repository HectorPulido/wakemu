-- Applied territorial HP is canonical character state, separate from icon/UI observations.
-- This migration does not enable the territory health policy or alter existing HP.
CREATE TABLE character_territory_health_projection (
 character_id bigint PRIMARY KEY REFERENCES characters(id) ON DELETE CASCADE,
 applied_flat integer NOT NULL CHECK(applied_flat BETWEEN -1000 AND 1000),
 state_id integer CHECK(state_id IN (1915,1916,1917)),
 map_id integer NOT NULL CHECK(map_id>0),
 instance_id bigint NOT NULL CHECK(instance_id>=0),
 region_id integer,
 revision bigint NOT NULL CHECK(revision>0),
 updated_at_ms bigint NOT NULL CHECK(updated_at_ms>=0),
 CHECK(state_id IS NOT NULL OR applied_flat=0)
);
