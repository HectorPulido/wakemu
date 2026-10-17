-- Individual withdrawal health continuation is distinct from a finished-fight
-- return. Preserve fight_health_exits abort provenance and ACK-only-return rule.
ALTER TABLE combat_pve_withdrawals ADD COLUMN health_returned_at timestamptz;
ALTER TABLE combat_pve_withdrawals
    ADD CONSTRAINT pve_withdrawal_health_requires_return
    CHECK (health_returned_at IS NULL OR returned_at IS NOT NULL);
-- No backfill: historical returned0HP needs its original owned death baseline
-- and current continuation lease attested by the same runtime recovery path.
