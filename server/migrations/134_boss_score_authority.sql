CREATE TABLE boss_score_encounters (
    fight_id integer PRIMARY KEY REFERENCES combat_fights(id),
    snapshot jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE boss_score_damage_receipts (
    fight_id integer NOT NULL REFERENCES boss_score_encounters(fight_id),
    event_id text NOT NULL,
    snapshot jsonb NOT NULL,
    amount bigint NOT NULL CHECK (amount >= 0),
    PRIMARY KEY (fight_id,event_id)
);
CREATE TABLE boss_score_terminal_receipts (
    fight_id integer PRIMARY KEY REFERENCES boss_score_encounters(fight_id),
    snapshot jsonb NOT NULL,
    score bigint NOT NULL CHECK (score >= 0)
);
INSERT INTO settings(name,value) VALUES ('boss_score_policy',
'{"schema_version":1,"policy":"wakemu-boss-validated-damage-v1","profiles":{"4378":{"round_limit":20},"5306":{"round_limit":20}}}'::jsonb)
ON CONFLICT(name) DO NOTHING;
CREATE FUNCTION reject_boss_score_receipt_change() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'Boss score authority receipts are immutable';
END;
$$;
CREATE TRIGGER boss_score_encounters_immutable BEFORE UPDATE OR DELETE ON boss_score_encounters
FOR EACH ROW EXECUTE FUNCTION reject_boss_score_receipt_change();
CREATE TRIGGER boss_score_damage_immutable BEFORE UPDATE OR DELETE ON boss_score_damage_receipts
FOR EACH ROW EXECUTE FUNCTION reject_boss_score_receipt_change();
CREATE TRIGGER boss_score_terminal_immutable BEFORE UPDATE OR DELETE ON boss_score_terminal_receipts
FOR EACH ROW EXECUTE FUNCTION reject_boss_score_receipt_change();
