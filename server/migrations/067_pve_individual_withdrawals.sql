-- Individual surrender is terminal for this participant, not for the fight.
-- Historical participation remains intact for checkpoint roster validation.
CREATE TABLE combat_pve_withdrawals (
    fight_id BIGINT NOT NULL,
    character_id BIGINT NOT NULL,
    account_id BIGINT NOT NULL,
    session_generation TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    returned_at TIMESTAMPTZ,
    PRIMARY KEY (fight_id, character_id),
    FOREIGN KEY (fight_id, character_id)
        REFERENCES combat_fight_participants (fight_id, character_id),
    FOREIGN KEY (account_id) REFERENCES accounts (id)
);
