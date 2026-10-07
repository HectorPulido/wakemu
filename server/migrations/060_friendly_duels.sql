ALTER TABLE combat_fights
    ADD COLUMN fight_kind text NOT NULL DEFAULT 'pve'
    CHECK (fight_kind IN ('pve','duel'));

CREATE TABLE friendly_duel_invitations (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    challenger_account_id bigint NOT NULL REFERENCES accounts(id),
    challenger_character_id bigint NOT NULL,
    challenger_generation text NOT NULL CHECK (length(challenger_generation) > 0),
    target_account_id bigint NOT NULL REFERENCES accounts(id),
    target_character_id bigint NOT NULL,
    target_generation text NOT NULL CHECK (length(target_generation) > 0),
    map_id integer NOT NULL CHECK (map_id > 0),
    instance_id bigint NOT NULL CHECK (instance_id >= 0),
    challenger_x integer NOT NULL,
    challenger_y integer NOT NULL,
    challenger_z smallint NOT NULL,
    target_x integer NOT NULL,
    target_y integer NOT NULL,
    target_z smallint NOT NULL,
    mode smallint NOT NULL CHECK (mode = 1),
    auto_lock boolean NOT NULL,
    status text NOT NULL CHECK (status IN ('pending','accepted','rejected','cancelled','expired')),
    fight_id integer UNIQUE REFERENCES combat_fights(id),
    created_at timestamptz NOT NULL,
    expires_at timestamptz NOT NULL,
    responded_at timestamptz,
    CHECK (challenger_account_id <> target_account_id),
    CHECK (challenger_character_id <> target_character_id),
    CHECK (expires_at > created_at),
    CHECK ((status = 'accepted') = (fight_id IS NOT NULL)),
    UNIQUE (fight_id,id),
    FOREIGN KEY (challenger_account_id,challenger_character_id)
        REFERENCES characters(account_id,id),
    FOREIGN KEY (target_account_id,target_character_id)
        REFERENCES characters(account_id,id)
);
CREATE UNIQUE INDEX friendly_duel_one_pending_invite_per_target
    ON friendly_duel_invitations(target_account_id,target_character_id)
    WHERE status='pending';
CREATE INDEX friendly_duel_invite_expiry
    ON friendly_duel_invitations(expires_at,id)
    WHERE status='pending';

CREATE TABLE friendly_duel_outcomes (
    fight_id integer PRIMARY KEY REFERENCES combat_fights(id),
    invitation_id bigint NOT NULL UNIQUE,
    winner_character_id bigint NOT NULL,
    loser_character_id bigint NOT NULL,
    reason text NOT NULL CHECK (reason IN ('defeat','disconnect')),
    settled_at timestamptz NOT NULL,
    CHECK (winner_character_id <> loser_character_id),
    FOREIGN KEY (fight_id,winner_character_id)
        REFERENCES combat_fight_participants(fight_id,character_id),
    FOREIGN KEY (fight_id,loser_character_id)
        REFERENCES combat_fight_participants(fight_id,character_id),
    FOREIGN KEY (fight_id,invitation_id)
        REFERENCES friendly_duel_invitations(fight_id,id)
);
