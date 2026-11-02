-- Explicit reviewed vote activation, separate from native seed provenance.
-- No configuration is activated; existing ground rows retain their contract.
CREATE TABLE dungeon_optional_gate_choices (
 instance_id bigint PRIMARY KEY REFERENCES dungeon_room_runs(instance_id),
 contract_key text NOT NULL,
 asset_map_id integer NOT NULL CHECK(asset_map_id>0),
 source_object_id bigint NOT NULL CHECK(source_object_id>0),
 required_checkpoint integer NOT NULL CHECK(required_checkpoint>0),
 catalog_hash text NOT NULL CHECK(length(catalog_hash)=64),
 rule_sha256 text NOT NULL CHECK(length(rule_sha256)=64),
 threshold integer NOT NULL CHECK(threshold>0),
 archimonster_votes integer NOT NULL DEFAULT 0 CHECK(archimonster_votes>=0),
 treasure_votes integer NOT NULL DEFAULT 0 CHECK(treasure_votes>=0),
 winner text CHECK(winner IN ('archimonster','treasure')),
 winner_account_id bigint REFERENCES accounts(id),
 winner_character_id bigint REFERENCES characters(id),
 revision bigint NOT NULL DEFAULT 0 CHECK(revision>=0),
 publication_pending boolean NOT NULL DEFAULT false,
 created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
 CHECK((winner IS NULL)=(winner_account_id IS NULL)),
 CHECK((winner IS NULL)=(winner_character_id IS NULL)),
 CHECK(winner IS NULL OR CASE winner WHEN 'archimonster' THEN archimonster_votes ELSE treasure_votes END>=threshold)
);
CREATE TABLE dungeon_optional_ballot_entitlements (
 instance_id bigint NOT NULL REFERENCES dungeon_room_runs(instance_id),
 character_id bigint NOT NULL REFERENCES characters(id),
 room_order integer NOT NULL CHECK(room_order>0),
 fight_id bigint NOT NULL REFERENCES dungeon_room_encounters(fight_id),
 chest_id bigint NOT NULL CHECK(chest_id>0),
 rule_sha256 text NOT NULL CHECK(length(rule_sha256)=64),
 observation jsonb NOT NULL CHECK(jsonb_typeof(observation)='object'),
 granted_units integer NOT NULL DEFAULT 0 CHECK(granted_units IN (0,1)),
 spent_units integer NOT NULL DEFAULT 0 CHECK(spent_units>=0 AND spent_units<=granted_units),
 claim_attempt uuid REFERENCES native_generic_reward_attempts(token) DEFERRABLE INITIALLY DEFERRED,
 PRIMARY KEY(instance_id,character_id,room_order),
 UNIQUE(fight_id,character_id),
 CHECK((granted_units=0)=(claim_attempt IS NULL))
);
CREATE TABLE dungeon_optional_vote_receipts (
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 instance_id bigint NOT NULL REFERENCES dungeon_optional_gate_choices(instance_id),
 character_id bigint NOT NULL REFERENCES characters(id),
 account_id bigint NOT NULL REFERENCES accounts(id),
 entitlement_room_order integer NOT NULL,
 source_uid bigint NOT NULL CHECK(source_uid>0),
 source_reference integer NOT NULL CHECK(source_reference>0),
 wire_action smallint NOT NULL CHECK(wire_action>=0),
 choice text NOT NULL CHECK(choice IN ('archimonster','treasure')),
 gate_revision bigint NOT NULL CHECK(gate_revision>0),
 consumed_units integer NOT NULL CHECK(consumed_units=1),
 created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
 UNIQUE(instance_id,gate_revision),
 UNIQUE(instance_id,character_id,entitlement_room_order),
 FOREIGN KEY(instance_id,character_id,entitlement_room_order) REFERENCES dungeon_optional_ballot_entitlements(instance_id,character_id,room_order)
);
ALTER TABLE dungeon_optional_access DROP CONSTRAINT dungeon_optional_access_activation_method_check;
ALTER TABLE dungeon_optional_access ADD CONSTRAINT dungeon_optional_activation_kind
 CHECK(activation_method IN ('native_inventory_action','step_on_target','native_vote'));
ALTER TABLE dungeon_optional_access ALTER COLUMN source_uid DROP NOT NULL;
ALTER TABLE dungeon_optional_access ALTER COLUMN source_reference DROP NOT NULL;
ALTER TABLE dungeon_optional_access ADD COLUMN vote_gate_instance_id bigint REFERENCES dungeon_optional_gate_choices(instance_id);
ALTER TABLE dungeon_optional_access ADD CONSTRAINT dungeon_optional_source_provenance
 CHECK(CASE WHEN activation_method='native_vote' THEN source_uid IS NULL AND source_reference IS NULL AND vote_gate_instance_id IS NOT NULL AND vote_gate_instance_id=instance_id
 ELSE source_uid IS NOT NULL AND source_reference IS NOT NULL AND vote_gate_instance_id IS NULL END);
