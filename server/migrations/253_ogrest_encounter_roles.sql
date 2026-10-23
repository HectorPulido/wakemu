-- Explicit reconstruction for the published ordinary Ogrest encounter only.
-- Ivory4984 roots237875/237996/237999/238002 require a challenger on team1;
-- their native910 descendants earn elemental resistance on the original boss.
INSERT INTO encounter_role_versions VALUES
('wakemu-ogrest-player1-npc0-v1','wakemu-reconstructed-ogrest-ivory-role-contract',1156,ARRAY[4378],1,0);
INSERT INTO encounter_role_active(map_id,monster_references,policy) VALUES
(1156,ARRAY[4378],'wakemu-ogrest-player1-npc0-v1');
