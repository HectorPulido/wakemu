-- Official house-departure bootstrap7235 supplies this exact Gultard actor.
-- Action969 comes from the installed4688 speaker. Root7119 and narrative
-- continuation graphs are reviewed reconstruction from native text/criteria,
-- not a claim that the player's capture contains a Gultard conversation.
INSERT INTO native_captured_npc_contracts
(actor_id,reference_id,map_id,x,y,z,direction,dialogue_root,action_ids,publication_authorized,source_sha256,provenance)
VALUES
(-1776810790485981,4688,527,11,155,0,3,7119,'[969]'::jsonb,true,
'c0626c4e964fe491969fc6f7e679cdc9ece1c4ffb456f7aad813927e83a88b86',
'Official official-incarnam-20261112 inbound7235 exact Gultard placement. Installed4688 action969; root7119 and follow-up roots7128/7129 are local reviewed reconstruction from quest5568 criteria and native text, not captured server dialogue edges.');
INSERT INTO world_dialogue_npcs
(actor_id,reference_id,map_id,instance_id,x,y,z,direction,dialogue_root,action_ids,enabled,provenance,native_capture_id,native_publication_authorized)
SELECT actor_id,reference_id,map_id,0,x,y,z,direction,dialogue_root,action_ids,true,provenance,actor_id,true
FROM native_captured_npc_contracts WHERE actor_id=-1776810790485981;

-- The apprentice is part of the same captured exterior scene. Preserve his
-- native appearance; standalone dialogue remains disabled until qualified.
INSERT INTO world_native_npc_placements
(actor_id,reference_id,map_id,instance_id,x,y,z,direction,name_es,visual_id,level,native_action_ids,source_sha256,source_frame,provenance)
VALUES
(-1776810790485982,4687,527,0,10,158,0,7,'Tristepin',192404687,1,'[968]'::jsonb,
'c0626c4e964fe491969fc6f7e679cdc9ece1c4ffb456f7aad813927e83a88b86',7235,
'Official official-incarnam-20261112 inbound7235 exact apprentice position beside Gultard; native4687 appearance/action catalog. Dialogue is presented through the reviewed Gultard conversation; standalone action968 remains disabled.');
