-- A native abandonment ACK is distinct from a normal finished-fight return.
ALTER TABLE fight_health_exits
    ADD COLUMN abandon_return_acknowledged_at timestamptz;

ALTER TABLE fight_health_exits
    ADD CONSTRAINT fight_health_exits_abandon_ack_only_abort
    CHECK (abandon_return_acknowledged_at IS NULL OR reason = 'abort');
