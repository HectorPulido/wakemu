-- Explicit reconstruction for the published Steel Beak initial roster.
-- Native cliff909 death effects179863/152472 target team1; boss must stay0.
INSERT INTO encounter_role_versions VALUES
('wakemu-steel-beak-player1-npc0-v1','wakemu-reconstructed-steel-beak-border-role-contract',959,ARRAY[3582],1,0);
INSERT INTO encounter_role_active(map_id,monster_references,policy) VALUES
(959,ARRAY[3582],'wakemu-steel-beak-player1-npc0-v1');
