-- Reviewed mission declarations are immutable publications. Activation is a
-- separate administrative pointer; producer lookups use the event index.
CREATE TABLE mission_toolkit_profiles (
    profile_id text NOT NULL CHECK (length(profile_id) BETWEEN 1 AND 1024),
    version integer NOT NULL CHECK (version > 0),
    native_revision text NOT NULL,
    sha256 text NOT NULL CHECK (sha256 ~ '^[0-9a-f]{64}$'),
    document jsonb NOT NULL CHECK (jsonb_typeof(document) = 'object'),
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (profile_id, version),
    UNIQUE (profile_id, native_revision, sha256)
);
CREATE TABLE mission_toolkit_active (
    profile_id text PRIMARY KEY,
    version integer NOT NULL,
    FOREIGN KEY (profile_id, version) REFERENCES mission_toolkit_profiles(profile_id, version)
);
CREATE TABLE mission_toolkit_event_index (
    profile_id text NOT NULL,
    version integer NOT NULL,
    kind text NOT NULL,
    reference integer,
    FOREIGN KEY (profile_id, version) REFERENCES mission_toolkit_profiles(profile_id, version),
    UNIQUE NULLS NOT DISTINCT (profile_id, version, kind, reference)
);
CREATE INDEX mission_toolkit_event_lookup ON mission_toolkit_event_index (kind, reference);
CREATE FUNCTION immutable_mission_toolkit_publication() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'A published mission toolkit version is immutable';
END;
$$;
CREATE TRIGGER mission_toolkit_profile_immutable BEFORE UPDATE OR DELETE ON mission_toolkit_profiles
    FOR EACH ROW EXECUTE FUNCTION immutable_mission_toolkit_publication();
CREATE TRIGGER mission_toolkit_event_index_immutable BEFORE UPDATE OR DELETE ON mission_toolkit_event_index
    FOR EACH ROW EXECUTE FUNCTION immutable_mission_toolkit_publication();
