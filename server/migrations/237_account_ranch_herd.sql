-- Explicit Wakemu acquisition policy; native constructor baseline, no invented genetics.
CREATE TABLE account_ranch_creatures (
 uid bigint PRIMARY KEY CHECK(uid>0),
 account_id bigint NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
 definition integer NOT NULL CHECK(definition>0),
 birth_ms bigint NOT NULL CHECK(birth_ms>=0),
 attributes jsonb NOT NULL CHECK(jsonb_typeof(attributes)='object'),
 name text NOT NULL CHECK(octet_length(name)<=127),
 scale real NOT NULL CHECK(scale>0 AND scale<'Infinity'::real),
 inventory boolean NOT NULL,
 biome_id integer NOT NULL DEFAULT -1,
 sector_id bigint NOT NULL DEFAULT -1,
 paddock_uid bigint,
 x integer NOT NULL DEFAULT 0,
 y integer NOT NULL DEFAULT 0,
 z smallint NOT NULL DEFAULT 0,
 native_tjr bigint NOT NULL DEFAULT 0,
 native_tjv boolean NOT NULL DEFAULT TRUE,
 revision bigint NOT NULL DEFAULT 0 CHECK(revision>=0),
 CHECK(inventory OR (biome_id>0 AND sector_id>=0 AND paddock_uid>0))
);
CREATE INDEX account_ranch_creatures_owner ON account_ranch_creatures(account_id,uid);
CREATE INDEX account_ranch_creatures_scene ON account_ranch_creatures(account_id,biome_id,sector_id)
 WHERE inventory=FALSE;
CREATE TABLE ranch_creature_acquisitions (
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 account_id bigint NOT NULL REFERENCES accounts(id),
 character_id bigint NOT NULL REFERENCES characters(id),
 source_uid bigint NOT NULL,
 source_reference integer NOT NULL,
 action_id integer NOT NULL,
 creature_uid bigint NOT NULL UNIQUE REFERENCES account_ranch_creatures(uid),
 seed text NOT NULL CHECK(seed ~ '^[0-9a-f]{32}$'),
 candidate_slot integer NOT NULL CHECK(candidate_slot>=0),
 policy text NOT NULL CHECK(policy='wakemu_native_seeded_herd_v1'),
 source_binding jsonb CHECK(source_binding IS NULL OR jsonb_typeof(source_binding)='object'),
 created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE account_ranch_paddocks (
 uid bigint PRIMARY KEY CHECK(uid>0),
 account_id bigint NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
 biome_id integer NOT NULL CHECK(biome_id>0),
 sector_id integer NOT NULL CHECK(sector_id>=0),
 native_group integer NOT NULL,
 region_key text NOT NULL CHECK(region_key ~ '^[0-9a-f]{64}$'),
 interior jsonb NOT NULL CHECK(jsonb_typeof(interior)='array'),
 boundary jsonb NOT NULL CHECK(jsonb_typeof(boundary)='array'),
 active boolean NOT NULL DEFAULT TRUE,
 UNIQUE(account_id,biome_id,sector_id,region_key),
 FOREIGN KEY(account_id,biome_id,sector_id)
  REFERENCES account_ranch_sectors(account_id,biome_id,sector_id)
);

ALTER TABLE account_ranch_creatures ADD CONSTRAINT account_ranch_creatures_paddock_fk
 FOREIGN KEY(paddock_uid) REFERENCES account_ranch_paddocks(uid);
