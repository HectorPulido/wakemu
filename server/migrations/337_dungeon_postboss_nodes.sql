-- Version337: independent source-qualified dungeon postboss encounter receipts.
-- Qualified postboss nodes never mutate primary progression or legacy optional access.
CREATE TABLE dungeon_postboss_nodes (
 instance_id bigint NOT NULL REFERENCES dungeon_room_runs(instance_id),
 source_order integer NOT NULL CHECK(source_order>0),
 room_order integer NOT NULL CHECK(room_order>0),
 asset_map_id integer NOT NULL CHECK(asset_map_id>0),
 group_id bigint NOT NULL,
 catalog_hash text NOT NULL CHECK(length(catalog_hash)=64),
 status text NOT NULL DEFAULT 'available' CHECK(status IN ('available','active','victory')),
 revision bigint NOT NULL DEFAULT 1 CHECK(revision>0),
 active_fight_id integer REFERENCES combat_fights(id),
 created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
 PRIMARY KEY(instance_id,source_order),
 UNIQUE(instance_id,room_order),
 UNIQUE(asset_map_id,instance_id,group_id),
 CHECK((status='active')=(active_fight_id IS NOT NULL)),
 FOREIGN KEY(asset_map_id,instance_id,group_id) REFERENCES combat_groups(map_id,instance_id,group_id) DEFERRABLE INITIALLY DEFERRED
);
ALTER TABLE dungeon_room_encounters DROP CONSTRAINT dungeon_room_encounters_encounter_scope_check;
ALTER TABLE dungeon_room_encounters ADD CONSTRAINT dungeon_room_encounter_scope_kind CHECK(encounter_scope IN ('main','optional','postboss'));
ALTER TABLE dungeon_room_encounters ADD COLUMN postboss_source_order integer;
ALTER TABLE dungeon_room_encounters ADD CONSTRAINT dungeon_encounter_postboss_receipt
 CHECK((encounter_scope='postboss')=(postboss_source_order IS NOT NULL));
ALTER TABLE dungeon_room_encounters ADD CONSTRAINT dungeon_encounter_postboss_node
 FOREIGN KEY(instance_id,postboss_source_order) REFERENCES dungeon_postboss_nodes(instance_id,source_order);
-- Preserve 334 dungeon_encounter_scope_receipt unchanged: optional still requires
-- optional_instance_id=instance_id, while main/postboss require it to be NULL.
DROP INDEX dungeon_room_one_active_encounter;
CREATE UNIQUE INDEX dungeon_room_one_active_primary_optional
 ON dungeon_room_encounters(instance_id) WHERE status='active' AND encounter_scope IN ('main','optional');
CREATE UNIQUE INDEX dungeon_postboss_one_active_node
 ON dungeon_room_encounters(instance_id,postboss_source_order) WHERE status='active' AND encounter_scope='postboss';
CREATE TABLE dungeon_postboss_publication_outbox (
 instance_id bigint NOT NULL,
 source_order integer NOT NULL,
 published boolean NOT NULL DEFAULT false,
 created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
 PRIMARY KEY(instance_id,source_order),
 FOREIGN KEY(instance_id,source_order) REFERENCES dungeon_postboss_nodes(instance_id,source_order)
);
-- No configuration, player, progress, item, currency or existing receipt rewrite.
