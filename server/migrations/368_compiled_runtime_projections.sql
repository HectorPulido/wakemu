-- Optional attestations for narrowly reviewed runtime-only function bodies.
-- The source digest must be checked against the immutable publication manifest
-- by the producer and consumer; absence always falls back to full compilation.
CREATE TABLE native_compiled_runtime_projections (
 generation text NOT NULL REFERENCES native_compiled_catalog_releases(generation) ON DELETE CASCADE,
 source_path text NOT NULL,
 source_sha256 text NOT NULL CHECK(source_sha256 ~ '^[0-9a-f]{64}$'),
 policy_sha256 text NOT NULL CHECK(policy_sha256 ~ '^[0-9a-f]{64}$'),
 projection_sha256 text NOT NULL CHECK(projection_sha256 ~ '^[0-9a-f]{64}$'),
 PRIMARY KEY (generation, source_path, policy_sha256)
);
