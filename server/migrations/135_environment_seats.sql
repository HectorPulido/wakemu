-- Occupancy for installed native stools; definitions remain in the authoritative catalog.
CREATE TABLE environment_seats (
 map_id INTEGER NOT NULL, object_id BIGINT NOT NULL,
 account_id BIGINT NOT NULL REFERENCES accounts(id), generation TEXT NOT NULL,
 character_id BIGINT NOT NULL REFERENCES characters(id),
 PRIMARY KEY(map_id,object_id), UNIQUE(character_id)
);
