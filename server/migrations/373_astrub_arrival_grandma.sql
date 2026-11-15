-- Official Rii departure capture: house bootstrap7162, action7196, root7197.
-- Scope is the original Astrub arrival house; quest criteria remain authoritative.
INSERT INTO native_captured_npc_contracts
(actor_id,reference_id,map_id,x,y,z,direction,dialogue_root,action_ids,publication_authorized,source_sha256,provenance)
VALUES
(-1776810787923716,3257,895,0,-2,0,3,7115,'[587]'::jsonb,true,
'c0626c4e964fe491969fc6f7e679cdc9ece1c4ffb456f7aad813927e83a88b86',
'Official official-incarnam-20261112 inbound7162, action7196 and dialogue7197; exact house-arrival placement, speaker and action. Dialogue graph is an explicit source contract; native running/objective criteria control entry.');
INSERT INTO world_dialogue_npcs
(actor_id,reference_id,map_id,instance_id,x,y,z,direction,dialogue_root,action_ids,enabled,provenance,native_capture_id,native_publication_authorized)
SELECT actor_id,reference_id,map_id,0,x,y,z,direction,dialogue_root,action_ids,true,provenance,actor_id,true
FROM native_captured_npc_contracts WHERE actor_id=-1776810787923716;
