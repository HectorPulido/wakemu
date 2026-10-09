-- Immutable native data releases; activation is independent of import staging.
CREATE TABLE native_catalog_releases (
 revision text PRIMARY KEY CHECK(length(revision)=64),
 document_count integer NOT NULL CHECK(document_count>=0),
 source_bytes bigint NOT NULL CHECK(source_bytes>=0),
 complete boolean NOT NULL DEFAULT false,
 created_at timestamptz NOT NULL DEFAULT now(),
 completed_at timestamptz
);

CREATE TABLE native_catalog_documents (
 revision text NOT NULL REFERENCES native_catalog_releases(revision),
 path text NOT NULL,
 raw bytea NOT NULL,
 sha256 text NOT NULL CHECK(length(sha256)=64),
 source_bytes bigint NOT NULL CHECK(source_bytes=octet_length(raw)),
 record_count integer NOT NULL CHECK(record_count>=0),
 PRIMARY KEY(revision,path)
);

CREATE TABLE native_catalog_records (
 revision text NOT NULL,
 path text NOT NULL,
 collection text NOT NULL,
 record_key text NOT NULL,
 payload jsonb NOT NULL,
 PRIMARY KEY(revision,path,collection,record_key),
 FOREIGN KEY(revision,path) REFERENCES native_catalog_documents(revision,path)
);
CREATE INDEX native_catalog_records_collection_key
 ON native_catalog_records(revision,collection,record_key);

CREATE TABLE native_catalog_active (
 id integer PRIMARY KEY CHECK(id=1),
 revision text NOT NULL REFERENCES native_catalog_releases(revision),
 activated_at timestamptz NOT NULL DEFAULT now()
);
