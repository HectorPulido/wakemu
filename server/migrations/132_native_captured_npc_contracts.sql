-- Exact observed original NPC bindings. Captured visibility is not a permanent
-- story-visibility predicate; publication uses an explicit local initial-scene policy, without quest grants.
CREATE TABLE native_captured_npc_contracts (
    actor_id bigint PRIMARY KEY CHECK(actor_id BETWEEN -9007199254740991 AND -1),
    reference_id smallint NOT NULL,
    map_id integer NOT NULL,
    x integer NOT NULL,
    y integer NOT NULL,
    z smallint NOT NULL,
    direction smallint NOT NULL CHECK(direction BETWEEN 0 AND 7),
    dialogue_root integer NOT NULL,
    action_ids jsonb NOT NULL CHECK(jsonb_typeof(action_ids)='array'),
    publication_authorized boolean NOT NULL DEFAULT false,
    source_sha256 text NOT NULL CHECK(source_sha256 ~ '^[a-f0-9]{64}$'),
    provenance text NOT NULL,
    UNIQUE(actor_id,reference_id,map_id,x,y,z,direction,dialogue_root,action_ids,publication_authorized)
);
ALTER TABLE world_dialogue_npcs ADD COLUMN native_capture_id bigint;
ALTER TABLE world_dialogue_npcs ADD COLUMN native_publication_authorized boolean NOT NULL DEFAULT false;
ALTER TABLE world_dialogue_npcs DROP CONSTRAINT world_dialogue_npcs_actor_id_check;
ALTER TABLE world_dialogue_npcs ADD CONSTRAINT world_dialogue_npcs_actor_contract_check CHECK (
    (native_capture_id IS NULL AND actor_id BETWEEN -4503599627370495 AND -2251799813685248)
    OR (native_capture_id IS NOT NULL AND native_capture_id=actor_id AND actor_id BETWEEN -9007199254740991 AND -1
        AND instance_id=0 AND (NOT enabled OR native_publication_authorized))
);
ALTER TABLE world_dialogue_npcs ADD CONSTRAINT world_dialogue_npcs_native_capture_fk
    FOREIGN KEY(native_capture_id,reference_id,map_id,x,y,z,direction,dialogue_root,action_ids,native_publication_authorized)
    REFERENCES native_captured_npc_contracts(actor_id,reference_id,map_id,x,y,z,direction,dialogue_root,action_ids,publication_authorized);
INSERT INTO native_captured_npc_contracts(actor_id,reference_id,map_id,x,y,z,direction,dialogue_root,action_ids,publication_authorized,source_sha256,provenance)
VALUES(-1706442035962340,5458,1387,-12,0,2,1,5764,'[1238]'::jsonb,true,
'eedbfd7561e0ae53398bab0eddd26bfac674fb77953d537cea4dbbecd9c4cd69',
'Original creation capture: spawn9303; request13222 frame9314 action1238; response12969 frame9317 root5764 speaker2 same actor. Observed tutorial context only; later movement9342 is a different position. Local initial-scene adaptation authorized: map1387 instance0 initial conversation only; original story visibility predicate not recovered.');
INSERT INTO world_dialogue_npcs(actor_id,reference_id,map_id,instance_id,x,y,z,direction,dialogue_root,action_ids,enabled,provenance,native_capture_id,native_publication_authorized)
SELECT actor_id,reference_id,map_id,0,x,y,z,direction,dialogue_root,action_ids,true,provenance,actor_id,true
FROM native_captured_npc_contracts WHERE actor_id=-1706442035962340;
