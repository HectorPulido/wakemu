-- Record which live session joined each durable fight. The participant row is
-- already the ownership authority; this generation binds that membership to
-- the selected session that created/joined it without changing historical rows.
ALTER TABLE combat_fight_participants
    ADD COLUMN session_generation text;

UPDATE combat_fight_participants p
SET session_generation = c.generation
FROM fight_checkpoints c
WHERE c.fight_id = p.fight_id
  AND c.account_id = p.account_id
  AND p.session_generation IS NULL;

UPDATE combat_fight_participants p
SET session_generation = s.generation
FROM sessions s
WHERE s.account_id = p.account_id
  AND s.character_id = p.character_id
  AND s.expires_at > CURRENT_TIMESTAMP
  AND p.session_generation IS NULL;

ALTER TABLE combat_fight_participants
    ADD CONSTRAINT combat_fight_participants_session_generation_nonempty
    CHECK (session_generation IS NULL OR length(session_generation) > 0);

CREATE INDEX combat_fight_participants_owner
    ON combat_fight_participants(account_id, character_id, fight_id);
