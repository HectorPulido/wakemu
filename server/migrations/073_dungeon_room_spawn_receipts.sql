-- Eight actor IDs are reserved per group, matching common encounter capacity.
CREATE SEQUENCE dungeon_room_group_ids AS bigint
 START WITH 288230376151711744 INCREMENT BY 8 MAXVALUE 9223372036854775792 NO CYCLE;
CREATE TABLE dungeon_room_spawn_receipts (
 instance_id bigint NOT NULL REFERENCES dungeon_room_runs(instance_id),
 room_order integer NOT NULL CHECK(room_order>0),
 asset_map_id integer NOT NULL CHECK(asset_map_id>0),
 group_id bigint NOT NULL DEFAULT nextval('dungeon_room_group_ids'),
 created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
 PRIMARY KEY(instance_id,room_order),
 UNIQUE(asset_map_id,instance_id,group_id),
 FOREIGN KEY(asset_map_id,instance_id,group_id)
 REFERENCES combat_groups(map_id,instance_id,group_id) DEFERRABLE INITIALLY DEFERRED
);
