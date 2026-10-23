-- Explicit reconstruction for the published initial Crow roster only.
-- Native307 births332481/335718 fix corbac1802 to team0;1989 inherits
-- its caster and5356 also fixes team0. No standalone phase roster is admitted.
INSERT INTO encounter_role_versions VALUES
('wakemu-black-crow-player1-npc0-v1','wakemu-reconstructed-black-crow-native-summon-role-contract',363,ARRAY[1988],1,0);
INSERT INTO encounter_role_active(map_id,monster_references,policy) VALUES
(363,ARRAY[1988],'wakemu-black-crow-player1-npc0-v1');
