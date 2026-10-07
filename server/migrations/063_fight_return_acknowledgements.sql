ALTER TABLE fight_health_exits
    ADD COLUMN return_acknowledged_at timestamptz;

-- Before this migration, a health-exit row was written only by an already
-- completed PvE return. Duel settlement now writes it before the client sends
-- native 12925, so keep old PvE rows closed while allowing offline duel results
-- to replay until that callback arrives.
UPDATE fight_health_exits e
SET return_acknowledged_at = e.created_at
FROM combat_fights f
WHERE f.id = e.fight_id
  AND f.fight_kind = 'pve'
  AND e.reason = 'return';

ALTER TABLE fight_health_exits
    ADD CONSTRAINT fight_health_exits_ack_only_return
    CHECK (return_acknowledged_at IS NULL OR reason = 'return');
