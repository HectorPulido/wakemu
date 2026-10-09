-- Durable per-session delivery for atomic party-wide dungeon transitions.
-- This records intent only; it does not wire a dispatcher or open a route.
CREATE TABLE dungeon_transition_outbox (
    event_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    instance_id bigint NOT NULL,
    party_id bigint NOT NULL,
    transition_revision bigint NOT NULL CHECK (transition_revision > 0),
    character_id bigint NOT NULL,
    session_generation text NOT NULL CHECK (length(session_generation) > 0),
    source_map_id integer NOT NULL CHECK (source_map_id > 0),
    source_instance_id bigint NOT NULL CHECK (source_instance_id >= 0),
    source_x integer NOT NULL,
    source_y integer NOT NULL,
    source_z smallint NOT NULL,
    destination_map_id integer NOT NULL CHECK (destination_map_id > 0),
    destination_instance_id bigint NOT NULL CHECK (destination_instance_id > 0),
    destination_x integer NOT NULL,
    destination_y integer NOT NULL,
    destination_z smallint NOT NULL,
    status text NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending','acknowledged','superseded')),
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    acknowledged_at timestamptz,
    acknowledged_generation text,
    superseded_at timestamptz,
    FOREIGN KEY (instance_id, party_id)
        REFERENCES dungeon_instances(instance_id, party_id) ON DELETE RESTRICT,
    FOREIGN KEY (instance_id, character_id)
        REFERENCES dungeon_instance_members(instance_id, character_id) ON DELETE RESTRICT,
    UNIQUE (instance_id, transition_revision, character_id),
    CHECK ((status = 'acknowledged') = (acknowledged_at IS NOT NULL)),
    CHECK ((status = 'acknowledged') = (acknowledged_generation IS NOT NULL)),
    CHECK ((acknowledged_generation IS NULL)
        OR acknowledged_generation = session_generation),
    CHECK ((status = 'superseded') = (superseded_at IS NOT NULL)),
    CHECK (destination_instance_id = instance_id)
);

CREATE INDEX dungeon_transition_pending_by_member
    ON dungeon_transition_outbox(character_id, session_generation, transition_revision)
    WHERE status = 'pending';
