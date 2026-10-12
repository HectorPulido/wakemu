-- Original protocol bootstrap records are imported explicitly, never file-backed at runtime.
CREATE TABLE bootstrap_capture_manifests (
    capture_key text PRIMARY KEY CHECK (length(capture_key) BETWEEN 1 AND 128),
    source_sha256 text NOT NULL CHECK (source_sha256 ~ '^[0-9a-f]{64}$'),
    content_sha256 text NOT NULL CHECK (content_sha256 ~ '^[0-9a-f]{64}$'),
    frame_count integer NOT NULL CHECK (frame_count >= 45),
    imported_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE bootstrap_capture_records (
    capture_key text NOT NULL REFERENCES bootstrap_capture_manifests(capture_key) ON DELETE CASCADE,
    ordinal integer NOT NULL CHECK (ordinal >= 0),
    payload jsonb NOT NULL CHECK (jsonb_typeof(payload) = 'object'),
    payload_sha256 text NOT NULL CHECK (payload_sha256 ~ '^[0-9a-f]{64}$'),
    PRIMARY KEY (capture_key, ordinal)
);
