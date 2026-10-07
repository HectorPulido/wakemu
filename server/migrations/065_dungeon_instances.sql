-- Durable party-owned dungeon runs. Template and live map instance are
-- separate identifiers; this migration does not enable any teleporter route.
CREATE TABLE dungeon_instances (
    instance_id bigint GENERATED ALWAYS AS IDENTITY
        (START WITH 144115188075855873 MAXVALUE 9223372036854775807) PRIMARY KEY,
    party_id bigint NOT NULL REFERENCES player_parties(id) ON DELETE RESTRICT,
    party_revision bigint NOT NULL CHECK (party_revision > 0),
    created_by_character_id bigint NOT NULL REFERENCES characters(id) ON DELETE RESTRICT,
    template_id integer NOT NULL CHECK (template_id > 0),
    definition_id integer NOT NULL CHECK (definition_id > 0),
    entry_map_id integer NOT NULL CHECK (entry_map_id > 0),
    entry_object_id bigint NOT NULL CHECK (entry_object_id > 0),
    entry_destination_id integer NOT NULL CHECK (entry_destination_id > 0),
    start_map_id integer NOT NULL CHECK (start_map_id > 0),
    status text NOT NULL DEFAULT 'active'
        CHECK (status IN ('active','completed','closed')),
    revision bigint NOT NULL DEFAULT 1 CHECK (revision > 0),
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    ended_at timestamptz,
    UNIQUE (instance_id, party_id),
    CHECK ((status='active') = (ended_at IS NULL))
);

CREATE UNIQUE INDEX dungeon_one_active_run_per_party
    ON dungeon_instances(party_id) WHERE status='active';

CREATE TABLE dungeon_instance_members (
    instance_id bigint NOT NULL,
    party_id bigint NOT NULL,
    character_id bigint NOT NULL REFERENCES characters(id) ON DELETE RESTRICT,
    session_generation text NOT NULL CHECK (length(session_generation)>0),
    party_revision bigint NOT NULL CHECK (party_revision>0),
    role text NOT NULL CHECK (role IN ('leader','member')),
    status text NOT NULL DEFAULT 'active'
        CHECK (status IN ('active','returned','removed')),
    joined_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    ended_at timestamptz,
    PRIMARY KEY(instance_id,character_id),
    FOREIGN KEY(instance_id,party_id)
        REFERENCES dungeon_instances(instance_id,party_id) ON DELETE RESTRICT,
    CHECK ((status='active') = (ended_at IS NULL))
);

CREATE UNIQUE INDEX dungeon_character_one_active_membership
    ON dungeon_instance_members(character_id) WHERE status='active';

ALTER TABLE dungeon_instances
    ADD CONSTRAINT dungeon_creator_is_member
    FOREIGN KEY(instance_id,created_by_character_id)
    REFERENCES dungeon_instance_members(instance_id,character_id)
    DEFERRABLE INITIALLY DEFERRED;

CREATE INDEX dungeon_members_by_party
    ON dungeon_instance_members(party_id,instance_id,status,character_id);
