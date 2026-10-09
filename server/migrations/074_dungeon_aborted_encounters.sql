-- Preserve encounter history when placement or active fights are aborted.
ALTER TABLE dungeon_room_encounters
 DROP CONSTRAINT dungeon_room_encounters_status_check;
ALTER TABLE dungeon_room_encounters
 ADD CONSTRAINT dungeon_room_encounters_status_check
 CHECK(status IN ('active','victory','defeat','aborted'));
