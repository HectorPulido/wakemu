-- Explicit reconstruction: original1845 entry378853 grants8242 only to
-- IsCharacter targets on team1. The original encounter publisher is unrecovered.
INSERT INTO encounter_role_versions VALUES
('wakemu-tal-kasha-player1-npc0-v1','wakemu-reconstructed-tal-kasha-clair-role-contract',1400,ARRAY[5500],1,0);
INSERT INTO encounter_role_active(map_id,monster_references,policy) VALUES
(1400,ARRAY[5500],'wakemu-tal-kasha-player1-npc0-v1');
