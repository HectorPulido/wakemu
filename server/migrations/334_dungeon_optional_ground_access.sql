-- Reviewed optional access is independent of the completed mandatory frontier.
CREATE TABLE dungeon_optional_access (
 instance_id bigint PRIMARY KEY REFERENCES dungeon_room_runs(instance_id),
 room_order integer NOT NULL CHECK(room_order>0),
 source_order integer NOT NULL CHECK(source_order>0),
 asset_map_id integer NOT NULL CHECK(asset_map_id>0),
 group_id bigint NOT NULL,
 account_id bigint NOT NULL REFERENCES accounts(id),
 character_id bigint NOT NULL REFERENCES characters(id),
 source_uid bigint NOT NULL CHECK(source_uid>0),
 source_reference integer NOT NULL CHECK(source_reference>0),
 action_id integer NOT NULL CHECK(action_id>0),
 activation_method text NOT NULL CHECK(activation_method IN ('native_inventory_action','step_on_target')),
 target jsonb NOT NULL CHECK(jsonb_typeof(target)='array' AND jsonb_array_length(target)=3),
 catalog_hash text NOT NULL CHECK(length(catalog_hash)=64),
 rule_sha256 text NOT NULL CHECK(length(rule_sha256)=64),
 status text NOT NULL DEFAULT 'available' CHECK(status IN ('available','active','victory')),
 revision bigint NOT NULL DEFAULT 1 CHECK(revision>0),
 created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
 UNIQUE(instance_id,room_order),
 UNIQUE(asset_map_id,instance_id,group_id),
 FOREIGN KEY(asset_map_id,instance_id,group_id) REFERENCES combat_groups(map_id,instance_id,group_id) DEFERRABLE INITIALLY DEFERRED
);
ALTER TABLE dungeon_room_encounters ADD COLUMN encounter_scope text NOT NULL DEFAULT 'main' CHECK(encounter_scope IN ('main','optional'));
ALTER TABLE dungeon_room_encounters ADD COLUMN optional_instance_id bigint REFERENCES dungeon_optional_access(instance_id);
ALTER TABLE dungeon_room_encounters ADD CONSTRAINT dungeon_encounter_scope_receipt CHECK((encounter_scope='optional')=(optional_instance_id IS NOT NULL) AND (optional_instance_id IS NULL OR optional_instance_id=instance_id));
CREATE TABLE dungeon_optional_publication_outbox (
 instance_id bigint PRIMARY KEY REFERENCES dungeon_optional_access(instance_id),
 published boolean NOT NULL DEFAULT false,
 created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP
);
-- No route configuration is activated here. The reviewed Wakemu policy uses
-- one source unit and one optional slot/run; original consumption/repeatability
-- are not asserted. No profession XP or legacy item expiry cleanup is applied.
