-- Explicit manual bindings, distinct from the unqualified client metadata.
CREATE TABLE quest_interactive_bindings (
    map_id integer NOT NULL CHECK (map_id > 0),
    object_id bigint NOT NULL,
    action_id integer NOT NULL CHECK (action_id BETWEEN 0 AND 65535),
    parameter integer NOT NULL CHECK (parameter BETWEEN 0 AND 65535),
    x integer NOT NULL, y integer NOT NULL, z integer NOT NULL,
    object_type text NOT NULL CHECK (object_type <> ''),
    max_distance integer NOT NULL CHECK (max_distance BETWEEN 1 AND 4),
    required_item integer NOT NULL DEFAULT 0 CHECK (required_item >= 0),
    required_quantity integer NOT NULL DEFAULT 0 CHECK (required_quantity >= 0),
    quest_id integer NOT NULL,
    objective_id integer NOT NULL CHECK (objective_id > 0),
    revision text NOT NULL,
    evidence text NOT NULL CHECK (evidence <> ''),
    CHECK ((required_item = 0) = (required_quantity = 0)),
    PRIMARY KEY (map_id, object_id, action_id, parameter),
    FOREIGN KEY (revision, quest_id) REFERENCES native_quest_metadata_definitions(revision, definition_id)
);
