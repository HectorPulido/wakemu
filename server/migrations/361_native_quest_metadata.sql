-- Native client evidence only: importing a row does not activate gameplay.
CREATE TABLE native_quest_metadata_releases (
    revision text PRIMARY KEY CHECK (revision ~ '^[0-9a-f]{64}$'),
    source_sha256 jsonb NOT NULL CHECK (jsonb_typeof(source_sha256) = 'object'),
    source_export bytea NOT NULL,
    definition_count integer NOT NULL CHECK (definition_count > 0),
    imported_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE native_quest_metadata_definitions (
    revision text NOT NULL REFERENCES native_quest_metadata_releases(revision),
    definition_id integer NOT NULL CHECK (definition_id > 0),
    data jsonb NOT NULL CHECK (jsonb_typeof(data) = 'object'),
    PRIMARY KEY (revision, definition_id)
);
