-- One durable native route choice shared by every member of a dungeon run.
ALTER TABLE dungeon_room_runs ADD COLUMN branch_key text;
ALTER TABLE dungeon_room_runs ADD CONSTRAINT dungeon_branch_key_nonempty
    CHECK (branch_key IS NULL OR length(branch_key) > 0);
