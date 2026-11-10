-- Historical source seals need inventories, not duplicate payload/index data.
CREATE TABLE native_catalog_retired_inventories (
 revision text PRIMARY KEY REFERENCES native_catalog_releases(revision),
 inventory jsonb NOT NULL,
 retired_at timestamptz NOT NULL DEFAULT now()
);

-- Cross-release index reuse is safe only for the same indexing implementation.
CREATE TABLE native_catalog_document_index_contracts (
 revision text NOT NULL,
 path text NOT NULL,
 contract_sha256 text NOT NULL CHECK(contract_sha256 ~ '^[0-9a-f]{64}$'),
 PRIMARY KEY(revision,path),
 FOREIGN KEY(revision,path) REFERENCES native_catalog_documents(revision,path)
);
