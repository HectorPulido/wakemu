-- Preserve the original PROTECTOR speaker kind and its exact captured actor join.
ALTER TABLE native_captured_npc_contracts
    ADD COLUMN speaker_type smallint NOT NULL DEFAULT 2,
    ADD COLUMN speaker_id bigint;
ALTER TABLE native_captured_npc_contracts ADD CONSTRAINT captured_npc_speaker_identity_check
    CHECK ((speaker_type=2 AND speaker_id IS NULL)
        OR (speaker_type=1 AND speaker_id IS NOT NULL AND speaker_id BETWEEN 1 AND 2147483647));
CREATE TABLE native_captured_npc_protectors (
    actor_id bigint PRIMARY KEY REFERENCES native_captured_npc_contracts(actor_id),
    protector_id integer NOT NULL UNIQUE CHECK(protector_id>0),
    map_id integer NOT NULL CHECK(map_id>0),
    territory_id integer NOT NULL CHECK(territory_id>0),
    appearance_id integer NOT NULL CHECK(appearance_id>0),
    original_nation integer NOT NULL CHECK(original_nation>=0),
    current_nation integer NOT NULL CHECK(current_nation>=0),
    provenance text NOT NULL CHECK(length(provenance)>0)
);
INSERT INTO native_captured_npc_contracts(actor_id,reference_id,map_id,x,y,z,direction,dialogue_root,action_ids,publication_authorized,source_sha256,provenance,speaker_type,speaker_id)
VALUES(-1706442046308330,5459,1385,20,17,1,3,5772,'[1244]'::jsonb,true,
'eedbfd7561e0ae53398bab0eddd26bfac674fb77953d537cea4dbbecd9c4cd69',
'Original creation capture: preceding spawn1397 map1385(20,17,1); request13222 frame1603 action1244; echo12421 frame1605 same actor/action; response12969 frame1606 root5772 PROTECTOR424. Original13974 protector records bind424 to this exact actor. Local initial-scene adaptation only; objective10596 evaluated against owned facts; no quest grant or later tree progression.',1,424);
INSERT INTO native_captured_npc_protectors(actor_id,protector_id,map_id,territory_id,appearance_id,original_nation,current_nation,provenance)
VALUES(-1706442046308330,424,1385,93601,22193,0,0,
'Original13974 wW.aiQ424; aiR nations0/0 territory93601; aiS appearance22193 actor-1706442046308330. Native bje.dso exact actor join; minimal41-byte wW plus csW/bMd/bLU installed consumers verified. No ecology/economy state fabricated.');
INSERT INTO world_dialogue_npcs(actor_id,reference_id,map_id,instance_id,x,y,z,direction,dialogue_root,action_ids,enabled,provenance,native_capture_id,native_publication_authorized)
SELECT actor_id,reference_id,map_id,0,x,y,z,direction,dialogue_root,action_ids,true,provenance,actor_id,true
FROM native_captured_npc_contracts WHERE actor_id=-1706442046308330;
