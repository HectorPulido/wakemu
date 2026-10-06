CREATE TABLE settings (
    name text PRIMARY KEY,
    value jsonb NOT NULL
);
INSERT INTO settings(name,value) VALUES
    ('non_permanent_build_limit','24'),
    ('player_allowed_commands','["!ayuda","!pos"]');

CREATE TABLE character_builds (
    character_id bigint NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
    build_index smallint NOT NULL CHECK (build_index BETWEEN 0 AND 127),
    sheet bytea NOT NULL,
    equipment bytea NOT NULL,
    deck bytea NOT NULL,
    aptitudes bytea NOT NULL,
    PRIMARY KEY (character_id, build_index)
);
-- Native default0 may be virtual. All other selected indices must exist;
-- selection/deletion validate this invariant under the character aggregate lock.
CREATE TABLE character_build_selection (
    character_id bigint PRIMARY KEY REFERENCES characters(id) ON DELETE CASCADE,
    active_index smallint NOT NULL DEFAULT 0 CHECK (active_index BETWEEN 0 AND 127),
    revision bigint NOT NULL DEFAULT 0 CHECK (revision >= 0)
);

CREATE TABLE character_progression (
    character_id bigint PRIMARY KEY REFERENCES characters(id) ON DELETE CASCADE,
    xp bigint NOT NULL DEFAULT 0 CHECK (xp >= 0)
);
-- Currency has one authoritative account balance; no duplicate character saldo.
CREATE TABLE account_wallets (
    account_id bigint PRIMARY KEY REFERENCES accounts(id) ON DELETE CASCADE,
    kamas bigint NOT NULL DEFAULT 0 CHECK (kamas >= 0)
);

CREATE TABLE character_regeneration (
    character_id bigint PRIMARY KEY REFERENCES characters(id) ON DELETE CASCADE,
    initial_hp integer NOT NULL CHECK (initial_hp >= 0),
    started_at timestamptz NOT NULL,
    coefficient integer NOT NULL CHECK (coefficient >= 0),
    last_at timestamptz NOT NULL CHECK (last_at >= started_at)
);

CREATE TABLE character_professions (
    character_id bigint NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
    profession_id integer NOT NULL CHECK (profession_id > 0),
    level smallint NOT NULL CHECK (level BETWEEN 0 AND 200),
    PRIMARY KEY (character_id, profession_id)
);

CREATE TABLE account_tutorials (
    account_id bigint NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    tutorial_id integer NOT NULL CHECK (tutorial_id >= 0),
    pending boolean NOT NULL,
    PRIMARY KEY (account_id, tutorial_id)
);

CREATE TABLE transport_discoveries (
    account_id bigint NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    kind smallint NOT NULL CHECK (kind IN (1,2)),
    transport_id integer NOT NULL CHECK (transport_id > 0),
    PRIMARY KEY (account_id, kind, transport_id)
);

CREATE TABLE haven_bags (
    character_id bigint PRIMARY KEY REFERENCES characters(id) ON DELETE CASCADE,
    appearance_id integer NOT NULL DEFAULT 408,
    layout jsonb NOT NULL CHECK (jsonb_typeof(layout) = 'array'),
    locked boolean NOT NULL DEFAULT false,
    furniture jsonb NOT NULL DEFAULT '[]' CHECK (jsonb_typeof(furniture) = 'array'),
    access jsonb NOT NULL DEFAULT '{"groups":[{"group":0,"rights":1}],"characters":[]}'
        CHECK (jsonb_typeof(access) = 'object')
);
