-- Hourly account matchups use the normal consenting native duel and reward outbox.
CREATE TABLE objectives_pvp_events (
    id bigserial PRIMARY KEY,
    period_key text NOT NULL UNIQUE,
    starts_at timestamptz NOT NULL,
    ends_at timestamptz NOT NULL,
    status text NOT NULL DEFAULT 'open' CHECK(status IN ('open','in_fight','completed','expired')),
    first_account_id bigint NOT NULL REFERENCES accounts(id),
    first_character_id bigint NOT NULL REFERENCES characters(id),
    first_generation text NOT NULL,
    first_level integer NOT NULL CHECK(first_level BETWEEN 1 AND 200),
    second_account_id bigint NOT NULL REFERENCES accounts(id),
    second_character_id bigint NOT NULL REFERENCES characters(id),
    second_generation text NOT NULL,
    second_level integer NOT NULL CHECK(second_level BETWEEN 1 AND 200),
    reward_snapshot jsonb NOT NULL,
    level_policy jsonb NOT NULL,
    fight_id integer UNIQUE REFERENCES combat_fights(id),
    map_id integer,
    instance_id bigint,
    winner_character_id bigint REFERENCES characters(id),
    completed_at timestamptz,
    rewards_reserved boolean NOT NULL DEFAULT false,
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK(first_account_id<>second_account_id),
    CHECK(first_character_id<>second_character_id),
    CHECK(ends_at>starts_at),
    CHECK(winner_character_id IS NULL OR winner_character_id IN(first_character_id,second_character_id)),
    CHECK((status='completed')=(completed_at IS NOT NULL)),
    CHECK(NOT rewards_reserved OR status='completed')
);
CREATE INDEX objectives_pvp_active ON objectives_pvp_events(starts_at DESC) WHERE status IN ('open','in_fight');
CREATE UNIQUE INDEX objectives_pvp_one_active ON objectives_pvp_events((true)) WHERE status IN ('open','in_fight');
INSERT INTO objectives_definitions(key,definition) VALUES
('hourly-pvp-participation','{"key":"hourly-pvp-participation","title":"Hourly PvP participation","description":"Complete the selected hourly duel against the other account.","kind":"pvp","scope":"account","enabled":false,"objectives":[{"key":"complete","event":"hourly_pvp_completed","filters":{},"target":1}],"schedule":{"type":"interval","timezone":"America/Bogota","anchor":"1970-01-01T00:00:00+00:00","seconds":3600},"rewards":[{"kind":"scaled","policy_key":"content-v1.daily"}],"prerequisite_keys":[]}'::jsonb),
('hourly-pvp-winner','{"key":"hourly-pvp-winner","title":"Hourly PvP winner","description":"Win the selected hourly duel against the other account.","kind":"pvp","scope":"account","enabled":false,"objectives":[{"key":"win","event":"hourly_pvp_completed","filters":{},"target":1}],"schedule":{"type":"interval","timezone":"America/Bogota","anchor":"1970-01-01T00:00:00+00:00","seconds":3600},"rewards":[{"kind":"scaled","policy_key":"content-v1.dungeon"}],"prerequisite_keys":[]}'::jsonb)
ON CONFLICT(key) DO NOTHING;

-- Hector-approved local rule: at most 20% of the lower level. This rule was
-- not present in the Starloco reference; each matchup freezes its policy.
INSERT INTO settings(name,value) VALUES
('objectives_pvp_level_policy','{"type":"relative","maximum_percent":20}'::jsonb)
ON CONFLICT(name) DO NOTHING;
CREATE TABLE objectives_pvp_fight_roster (
    event_id bigint NOT NULL REFERENCES objectives_pvp_events(id),
    fight_id integer NOT NULL,
    character_id bigint NOT NULL,
    account_id bigint NOT NULL REFERENCES accounts(id),
    team integer NOT NULL CHECK(team IN(0,1)),
    level integer NOT NULL CHECK(level BETWEEN 1 AND 200),
    PRIMARY KEY(event_id,character_id),
    FOREIGN KEY(fight_id,character_id) REFERENCES combat_fight_participants(fight_id,character_id)
);
