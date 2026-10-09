-- Distinguish durable private-map transitions from exterior returns.
ALTER TABLE dungeon_transition_outbox
    ADD COLUMN transition_kind text NOT NULL DEFAULT 'enter'
        CHECK (transition_kind IN ('enter','door','exit'));
DO $$
DECLARE constraint_row record;
BEGIN
    FOR constraint_row IN
        SELECT conname FROM pg_constraint
        WHERE conrelid = 'dungeon_transition_outbox'::regclass
          AND contype = 'c'
          AND (pg_get_constraintdef(oid) = 'CHECK ((destination_instance_id > 0))'
               OR pg_get_constraintdef(oid) = 'CHECK ((destination_instance_id = instance_id))')
    LOOP
        EXECUTE format('ALTER TABLE dungeon_transition_outbox DROP CONSTRAINT %I', constraint_row.conname);
    END LOOP;
END $$;
ALTER TABLE dungeon_transition_outbox ADD CONSTRAINT dungeon_transition_destination_kind
    CHECK ((transition_kind IN ('enter','door') AND destination_instance_id=instance_id)
        OR (transition_kind='exit' AND destination_instance_id=0));
