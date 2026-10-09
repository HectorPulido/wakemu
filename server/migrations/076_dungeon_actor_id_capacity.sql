-- Existing groups reserve eight contiguous IDs. Future groups reserve 128,
-- enough for all supported placement NPCs, leaving existing identities intact.
-- The next allocation advances by 128 from the old last_value, so it cannot
-- overlap the old last group (at most eight actors) or any earlier allocation.
ALTER SEQUENCE dungeon_room_group_ids INCREMENT BY 128;
