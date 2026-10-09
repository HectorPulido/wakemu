-- Immutable, explicitly configured ProtoDungeon context policies. No policy
-- rows are seeded: the native field layout is known, but Jalató policy values
-- (especially allowed_ids) are not established by the available sources.
CREATE TABLE dungeon_context_policy_versions (
    route_key text NOT NULL CHECK (length(route_key) > 0),
    policy_version integer NOT NULL CHECK (policy_version > 0),
    template_id integer NOT NULL CHECK (template_id > 0),
    definition_id integer NOT NULL CHECK (definition_id > 0),
    max_level integer NOT NULL CHECK (max_level BETWEEN 0 AND 2147483647),
    min_level integer NOT NULL CHECK (min_level BETWEEN 0 AND 2147483647),
    difficulty_level integer NOT NULL CHECK (difficulty_level BETWEEN 1 AND 10),
    is_difficulty_available boolean NOT NULL,
    can_increase_difficulty boolean NOT NULL,
    is_competitive_cancelled boolean NOT NULL,
    allowed_ids bigint[] NOT NULL,
    provenance text NOT NULL CHECK (length(btrim(provenance)) > 0),
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (route_key, policy_version),
    CHECK (max_level = 0 OR min_level <= max_level)
);

-- Changing policy means inserting a new immutable version, then moving this
-- pointer. Existing runs retain their exact version through a foreign key.
CREATE TABLE dungeon_context_active_policies (
    route_key text PRIMARY KEY,
    policy_version integer NOT NULL,
    FOREIGN KEY (route_key, policy_version)
        REFERENCES dungeon_context_policy_versions(route_key, policy_version)
        ON DELETE RESTRICT
);

CREATE FUNCTION reject_dungeon_context_policy_mutation()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'dungeon context policy versions are immutable';
END;
$$;

CREATE TRIGGER dungeon_context_policy_immutable
BEFORE UPDATE OR DELETE ON dungeon_context_policy_versions
FOR EACH ROW EXECUTE FUNCTION reject_dungeon_context_policy_mutation();

ALTER TABLE dungeon_instances
    ADD COLUMN context_route_key text,
    ADD COLUMN context_policy_version integer,
    ADD CONSTRAINT dungeon_context_policy_pair
        CHECK ((context_route_key IS NULL) = (context_policy_version IS NULL)),
    ADD CONSTRAINT dungeon_instance_context_policy_fk
        FOREIGN KEY (context_route_key, context_policy_version)
        REFERENCES dungeon_context_policy_versions(route_key, policy_version)
        ON DELETE RESTRICT;

CREATE INDEX dungeon_instances_by_context_policy
    ON dungeon_instances(context_route_key, context_policy_version)
    WHERE context_route_key IS NOT NULL;
