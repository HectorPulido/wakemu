-- A native NPC's action list is presentation data, not speaker identity.
-- Keeping action_ids inside the captured-contract key made it impossible to
-- publish the complete native action set observed in the official Celestial
-- Dojo session (Airyna uses 1390, 1389 and 1252), because the published row
-- and its captured evidence could not move together. Identity stays pinned to
-- the actor, map, cell, facing and dialogue root.
-- Written to be replay-safe: the runner may apply it again after a manual run.
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'world_dialogue_npcs_native_capture_fk'
          AND pg_get_constraintdef(oid) LIKE '%action_ids%'
    ) THEN
        ALTER TABLE world_dialogue_npcs
            DROP CONSTRAINT world_dialogue_npcs_native_capture_fk;
    END IF;

    IF EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'native_captured_npc_contracts_actor_id_reference_id_map_id__key'
    ) THEN
        ALTER TABLE native_captured_npc_contracts
            DROP CONSTRAINT native_captured_npc_contracts_actor_id_reference_id_map_id__key;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'native_captured_npc_contracts_identity_key'
    ) THEN
        ALTER TABLE native_captured_npc_contracts
            ADD CONSTRAINT native_captured_npc_contracts_identity_key
            UNIQUE (
                actor_id, reference_id, map_id, x, y, z, direction,
                dialogue_root, publication_authorized
            );
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'world_dialogue_npcs_native_capture_fk'
    ) THEN
        ALTER TABLE world_dialogue_npcs
            ADD CONSTRAINT world_dialogue_npcs_native_capture_fk FOREIGN KEY
            (native_capture_id, reference_id, map_id, x, y, z, direction,
             dialogue_root, native_publication_authorized)
            REFERENCES native_captured_npc_contracts
            (actor_id, reference_id, map_id, x, y, z, direction,
             dialogue_root, publication_authorized);
    END IF;
END
$$;
