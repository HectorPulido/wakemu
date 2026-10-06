-- IDs survive process/session replacement and fit the native signed32 fight ID.
CREATE TABLE combat_fights (
    id integer GENERATED ALWAYS AS IDENTITY (MAXVALUE 2147483647 NO CYCLE) PRIMARY KEY,
    status text NOT NULL CHECK (status IN ('placement','active','finished','aborted')),
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE combat_fight_participants (
    fight_id integer NOT NULL REFERENCES combat_fights(id),
    character_id bigint NOT NULL,
    account_id bigint NOT NULL,
    team smallint NOT NULL CHECK (team IN (0,1)),
    FOREIGN KEY (account_id,character_id) REFERENCES characters(account_id,id),
    PRIMARY KEY (fight_id,character_id),
    UNIQUE (fight_id,character_id,account_id)
);
CREATE TABLE fight_rewards (
    fight_id integer NOT NULL,
    character_id bigint NOT NULL,
    account_id bigint NOT NULL,
    generation text NOT NULL,
    xp bigint NOT NULL CHECK (xp >= 0),
    kamas integer NOT NULL CHECK (kamas >= 0),
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    start_xp bigint NOT NULL CHECK (start_xp >= 0),
    end_xp bigint NOT NULL CHECK (end_xp >= start_xp),
    start_level smallint NOT NULL CHECK (start_level BETWEEN 1 AND 200),
    end_level smallint NOT NULL CHECK (end_level BETWEEN start_level AND 200),
    CHECK (end_xp - start_xp = xp),
    PRIMARY KEY (fight_id,character_id),
    FOREIGN KEY (fight_id,character_id,account_id)
        REFERENCES combat_fight_participants(fight_id,character_id,account_id)
);
CREATE TABLE fight_health_exits (
    fight_id integer NOT NULL,
    character_id bigint NOT NULL,
    generation text NOT NULL,
    reason text NOT NULL CHECK (reason IN ('return','abort')),
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (fight_id,character_id),
    FOREIGN KEY (fight_id,character_id)
        REFERENCES combat_fight_participants(fight_id,character_id)
);
CREATE TABLE fight_checkpoints (
    fight_id integer PRIMARY KEY REFERENCES combat_fights(id),
    account_id bigint NOT NULL REFERENCES accounts(id),
    generation text NOT NULL,
    revision bigint NOT NULL CHECK (revision >= 0),
    status text NOT NULL CHECK (status IN ('active','ended','aborted')),
    snapshot jsonb NOT NULL CHECK (jsonb_typeof(snapshot) = 'object'),
    updated_at timestamptz NOT NULL
);

CREATE TABLE combat_groups (
    map_id integer NOT NULL,
    instance_id bigint NOT NULL,
    group_id bigint NOT NULL,
    members jsonb NOT NULL CHECK (jsonb_typeof(members) = 'array'),
    status text NOT NULL CHECK (status IN ('available','fighting','defeated')),
    generation text,
    fight_id integer REFERENCES combat_fights(id),
    revision bigint NOT NULL DEFAULT 0 CHECK (revision >= 0),
    defeated_at timestamptz,
    CHECK (status <> 'fighting' OR (generation IS NOT NULL AND fight_id IS NOT NULL)),
    PRIMARY KEY (map_id,instance_id,group_id)
);
CREATE INDEX combat_groups_availability ON combat_groups(map_id,instance_id,status);
CREATE INDEX combat_groups_respawn ON combat_groups(defeated_at) WHERE status='defeated';
-- Database-wide identity claims, beyond a Python process-local lock.
CREATE TABLE combat_group_members (
    map_id integer NOT NULL,
    instance_id bigint NOT NULL,
    group_id bigint NOT NULL,
    monster_id bigint NOT NULL CHECK (monster_id < 0),
    PRIMARY KEY (map_id,instance_id,monster_id),
    FOREIGN KEY (map_id,instance_id,group_id)
        REFERENCES combat_groups(map_id,instance_id,group_id) ON DELETE CASCADE
);

CREATE TABLE planted_resources (
    resource_uid bigint PRIMARY KEY CHECK (resource_uid > 0),
    map_id integer NOT NULL,
    instance_id bigint NOT NULL,
    x integer NOT NULL,
    y integer NOT NULL,
    z smallint NOT NULL,
    resource_reference integer NOT NULL CHECK (resource_reference > 0),
    stage smallint NOT NULL CHECK (stage BETWEEN 0 AND 127),
    creation_time bigint NOT NULL CHECK (creation_time >= 0),
    -- Native occupation is XY-scoped; do not silently introduce overlapping Z.
    UNIQUE (map_id,instance_id,x,y)
);
CREATE TABLE planting_receipts (
    operation_id text PRIMARY KEY,
    character_id bigint NOT NULL REFERENCES characters(id),
    item_uid bigint NOT NULL,
    request jsonb NOT NULL CHECK (jsonb_typeof(request) = 'object'),
    resource jsonb NOT NULL CHECK (jsonb_typeof(resource) = 'object'),
    group_payload jsonb,
    published boolean NOT NULL DEFAULT false
);
CREATE INDEX planting_receipts_pending ON planting_receipts(operation_id) WHERE NOT published;
CREATE TABLE planting_growth_outbox (
    resource_uid bigint PRIMARY KEY,
    resource jsonb NOT NULL CHECK (jsonb_typeof(resource) = 'object'),
    group_payload jsonb,
    published boolean NOT NULL DEFAULT false
);
CREATE INDEX planting_growth_pending ON planting_growth_outbox(resource_uid) WHERE NOT published;
CREATE TABLE monster_harvest_receipts (
    token text PRIMARY KEY,
    character_id bigint NOT NULL REFERENCES characters(id),
    map_id integer NOT NULL,
    instance_id bigint NOT NULL,
    monster_id bigint NOT NULL CHECK (monster_id < 0),
    action_id integer NOT NULL CHECK (action_id > 0),
    completed_at timestamptz NOT NULL,
    item_uid bigint NOT NULL
);
CREATE INDEX monster_harvest_cooldown
    ON monster_harvest_receipts(map_id,instance_id,monster_id,action_id,completed_at DESC);
