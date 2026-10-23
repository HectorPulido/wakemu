-- Explicit reconstruction: native border1085 distinguishes player4211/team1
-- from boss4212/team0. Its original encounter publisher remains unrecovered.
INSERT INTO encounter_role_versions VALUES
('wakemu-ful-moon-player1-npc0-v1','wakemu-reconstructed-ful-moon-border-role-contract',1056,ARRAY[3870],1,0);
INSERT INTO encounter_role_active(map_id,monster_references,policy) VALUES
(1056,ARRAY[3870],'wakemu-ful-moon-player1-npc0-v1');
