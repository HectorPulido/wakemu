-- Preserve normal exit delivery when the exterior is an owner-only cinematic.
-- Reuse the existing introductory scene namespace; no rows or progress change.
ALTER TABLE dungeon_transition_outbox
    DROP CONSTRAINT dungeon_transition_destination_kind;
ALTER TABLE dungeon_transition_outbox
    ADD CONSTRAINT dungeon_transition_destination_kind
    CHECK (
        (transition_kind IN ('enter','door') AND destination_instance_id=instance_id)
        OR (
            transition_kind='exit'
            AND (
                destination_instance_id=0
                OR destination_instance_id=(4611686018427387904 + character_id)
            )
        )
    );
