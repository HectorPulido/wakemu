-- A craft operation is tied to one authenticated character lease and has a
-- monotonic version so completion/cancellation retries cannot apply twice.
CREATE TABLE craft_occupations (
    token uuid PRIMARY KEY,
    account_id bigint NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    generation text NOT NULL CHECK (length(generation)>0),
    character_id bigint NOT NULL,
    table_uid bigint NOT NULL CHECK (table_uid>0),
    map_id integer NOT NULL CHECK (map_id>0),
    instance_id bigint NOT NULL CHECK (instance_id>=0),
    definition_id integer NOT NULL CHECK (definition_id>0),
    profession_id integer NOT NULL CHECK (profession_id>0),
    recipe_id integer NOT NULL CHECK (recipe_id>0),
    request_opcode integer NOT NULL CHECK (request_opcode IN (12231,13382)),
    mode smallint NOT NULL DEFAULT 0,
    batch_count integer NOT NULL CHECK (batch_count BETWEEN 1 AND 32767),
    request_hash bytea NOT NULL CHECK (octet_length(request_hash)=32),
    inventory_snapshot jsonb NOT NULL CHECK (jsonb_typeof(inventory_snapshot)='object'),
    duration_ms integer NOT NULL CHECK (duration_ms BETWEEN 1 AND 2147483647),
    version bigint NOT NULL DEFAULT 1 CHECK (version>0),
    state text NOT NULL DEFAULT 'active'
        CHECK (state IN ('active','completed','canceled')),
    started_at timestamptz NOT NULL,
    due_at timestamptz NOT NULL,
    finished_at timestamptz,
    consumed_items jsonb NOT NULL DEFAULT '[]'::jsonb
        CHECK (jsonb_typeof(consumed_items)='array'),
    products jsonb NOT NULL DEFAULT '[]'::jsonb
        CHECK (jsonb_typeof(products)='array'),
    applied_xp bigint NOT NULL DEFAULT 0 CHECK (applied_xp BETWEEN 0 AND 3000000),
    terminal_reason text CHECK (terminal_reason IS NULL OR length(terminal_reason)<=64),
    FOREIGN KEY (account_id,character_id)
        REFERENCES characters(account_id,id) ON DELETE CASCADE,
    CHECK (due_at>started_at),
    CHECK ((state='active' AND finished_at IS NULL AND terminal_reason IS NULL)
        OR (state='completed' AND finished_at IS NOT NULL AND terminal_reason='completed')
        OR (state='canceled' AND finished_at IS NOT NULL AND terminal_reason IS NOT NULL))
);

CREATE UNIQUE INDEX craft_one_active_occupation_per_character
    ON craft_occupations(character_id) WHERE state='active';
CREATE INDEX craft_occupations_owner_history
    ON craft_occupations(account_id,character_id,started_at DESC);
