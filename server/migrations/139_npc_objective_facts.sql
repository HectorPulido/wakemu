-- NPC criteria facts only. This table does not grant or advance any quest.
-- Known native objectives default to incomplete in the definition-backed
-- evaluator; unknown objective IDs fail closed and are never inferred false.
CREATE TABLE npc_objective_facts (
    account_id bigint NOT NULL,
    character_id bigint NOT NULL,
    objective_id integer NOT NULL CHECK(objective_id > 0),
    completed boolean NOT NULL,
    provenance text NOT NULL CHECK(length(provenance) > 0),
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY(character_id,objective_id),
    FOREIGN KEY(account_id,character_id) REFERENCES characters(account_id,id) ON DELETE CASCADE
);

INSERT INTO native_captured_npc_contracts(actor_id,reference_id,map_id,x,y,z,direction,dialogue_root,action_ids,publication_authorized,source_sha256,provenance)
VALUES(-1706442046308322,5461,1385,-17,-4,17,3,5765,'[1243]'::jsonb,true,'eedbfd7561e0ae53398bab0eddd26bfac674fb77953d537cea4dbbecd9c4cd69','Original creation capture spawn1154; request13222 frame1291 action1243; response12969 frame1294 same actor. Local initial-scene adaptation only; original story visibility not reconstructed. Native objective criteria checked against definition-backed owned facts; no quest grants or later tree progression.');

INSERT INTO native_captured_npc_contracts(actor_id,reference_id,map_id,x,y,z,direction,dialogue_root,action_ids,publication_authorized,source_sha256,provenance)
VALUES(-1706442046308328,5467,1385,12,32,1,1,5782,'[1255]'::jsonb,true,'eedbfd7561e0ae53398bab0eddd26bfac674fb77953d537cea4dbbecd9c4cd69','Original creation capture spawn1584; request13222 frame1667 action1255; response12969 frame1670 same actor. Local initial-scene adaptation only; original story visibility not reconstructed. Native objective criteria checked against definition-backed owned facts; no quest grants or later tree progression.');

INSERT INTO native_captured_npc_contracts(actor_id,reference_id,map_id,x,y,z,direction,dialogue_root,action_ids,publication_authorized,source_sha256,provenance)
VALUES(-1706442046308339,5460,1388,0,-19,3,3,5755,'[1390]'::jsonb,true,'eedbfd7561e0ae53398bab0eddd26bfac674fb77953d537cea4dbbecd9c4cd69','Original creation capture spawn3785; request13222 frame3788 action1390; response12969 frame3791 same actor. Local initial-scene adaptation only; original story visibility not reconstructed. Native objective criteria checked against definition-backed owned facts; no quest grants or later tree progression.');
INSERT INTO world_dialogue_npcs(actor_id,reference_id,map_id,instance_id,x,y,z,direction,dialogue_root,action_ids,enabled,provenance,native_capture_id,native_publication_authorized)
SELECT actor_id,reference_id,map_id,0,x,y,z,direction,dialogue_root,action_ids,true,provenance,actor_id,true
FROM native_captured_npc_contracts WHERE actor_id IN(-1706442046308322,-1706442046308328,-1706442046308339);
