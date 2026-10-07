-- An occupation must retain the authoritative actor location for completion.
-- In-flight reservations created before this invariant cannot be completed.
DELETE FROM resource_harvest_occupations;
ALTER TABLE resource_harvest_occupations
    ADD COLUMN actor_map_id integer NOT NULL,
    ADD COLUMN actor_instance_id bigint NOT NULL,
    ADD COLUMN actor_x integer NOT NULL,
    ADD COLUMN actor_y integer NOT NULL,
    ADD COLUMN actor_z smallint NOT NULL;
