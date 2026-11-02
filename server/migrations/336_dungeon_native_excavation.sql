-- Reviewed native excavation lifecycle; migration336 assigned by root.
CREATE TABLE dungeon_excavation_runs (
    instance_id bigint PRIMARY KEY REFERENCES dungeon_room_runs(instance_id),
    catalog_hash text NOT NULL,
    rule_sha256 text NOT NULL,
    key_character_id bigint REFERENCES characters(id),
    key_state_uid bigint,
    selected_source_id bigint,
    selected_rooms_sha256 text,
    CHECK ((key_character_id IS NULL) = (key_state_uid IS NULL)),
    CHECK ((selected_source_id IS NULL) = (selected_rooms_sha256 IS NULL))
);
CREATE TABLE dungeon_excavation_actors (
    instance_id bigint NOT NULL REFERENCES dungeon_excavation_runs(instance_id),
    character_id bigint NOT NULL REFERENCES characters(id),
    last_attempt bigint NOT NULL DEFAULT 0,
    next_attempt_ms bigint NOT NULL DEFAULT 0,
    PRIMARY KEY(instance_id, character_id)
);
CREATE TABLE dungeon_excavation_attempts (
    instance_id bigint NOT NULL,
    character_id bigint NOT NULL,
    attempt bigint NOT NULL CHECK(attempt > 0),
    source_uid bigint NOT NULL,
    target jsonb NOT NULL,
    found_key boolean NOT NULL,
    PRIMARY KEY(instance_id, character_id, attempt),
    FOREIGN KEY(instance_id, character_id) REFERENCES dungeon_excavation_actors(instance_id, character_id)
);
CREATE TABLE dungeon_excavation_tools (
    instance_id bigint NOT NULL REFERENCES dungeon_room_runs(instance_id),
    character_id bigint NOT NULL REFERENCES characters(id),
    tool_uid bigint NOT NULL,
    tool_reference integer NOT NULL,
    granted_by_instance boolean NOT NULL,
    rule_sha256 text NOT NULL,
    active boolean NOT NULL DEFAULT true,
    PRIMARY KEY(instance_id, character_id)
);
-- Ordinary inventory rows keep NULL: their updates do not invoke custody
-- logic or perform additional lookups, including ordinary combat ammo/items.
ALTER TABLE inventory_items ADD COLUMN instance_custody_id bigint
    CHECK(instance_custody_id IS NULL OR instance_custody_id>0);
CREATE UNIQUE INDEX dungeon_excavation_owned_tool
    ON dungeon_excavation_tools(tool_uid) WHERE active AND granted_by_instance;

CREATE FUNCTION protect_instance_tool_custody() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP='UPDATE' AND NEW.uid=OLD.uid AND NEW.character_id=OLD.character_id
       AND NEW.reference=OLD.reference AND NEW.quantity=OLD.quantity
       AND NEW.instance_custody_id=OLD.instance_custody_id THEN
      IF NEW.container=OLD.container THEN RETURN NEW; END IF;
      IF EXISTS(SELECT 1 FROM inventory_containers c WHERE c.uid=NEW.container
                AND c.character_id=OLD.character_id AND c.kind IN (0,1,2,3)) THEN
        RETURN NEW;
      END IF;
    END IF;
    IF EXISTS(SELECT 1 FROM dungeon_excavation_tools t
              WHERE t.tool_uid=OLD.uid AND t.instance_id=OLD.instance_custody_id
                AND t.active AND t.granted_by_instance) THEN
      RAISE EXCEPTION 'Temporary instance tool must remain in its source custody';
    END IF;
    IF TG_OP='DELETE' THEN RETURN OLD; END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER inventory_instance_tool_custody
  BEFORE UPDATE OR DELETE ON inventory_items FOR EACH ROW
  WHEN (OLD.instance_custody_id IS NOT NULL)
  EXECUTE FUNCTION protect_instance_tool_custody();

-- Every authoritative exit path already changes durable membership. This
-- cleanup therefore covers portals, console relocation, hero removal and
-- recovery atomically without map-specific exit handlers or inventory resets.
CREATE FUNCTION retire_excavation_member() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE tool dungeon_excavation_tools%ROWTYPE;
DECLARE excavation dungeon_excavation_runs%ROWTYPE;
BEGIN
    IF OLD.status <> 'active' OR NEW.status = 'active' THEN RETURN NEW; END IF;
    SELECT * INTO tool FROM dungeon_excavation_tools
      WHERE instance_id=OLD.instance_id AND character_id=OLD.character_id AND active FOR UPDATE;
    IF NOT FOUND THEN RETURN NEW; END IF;
    PERFORM 1 FROM dungeon_room_runs WHERE instance_id=OLD.instance_id FOR UPDATE;
    -- Retire custody first in this same transaction; rollback restores both.
    UPDATE dungeon_excavation_tools SET active=false
      WHERE instance_id=OLD.instance_id AND character_id=OLD.character_id;
    IF tool.granted_by_instance THEN
      UPDATE inventory_items SET quantity=quantity-1,instance_custody_id=NULL
        WHERE uid=tool.tool_uid AND character_id=OLD.character_id
          AND reference=tool.tool_reference AND quantity>1;
      IF NOT FOUND THEN
        DELETE FROM inventory_items WHERE uid=tool.tool_uid AND character_id=OLD.character_id
          AND reference=tool.tool_reference AND quantity=1;
      END IF;
    END IF;
    SELECT * INTO excavation FROM dungeon_excavation_runs WHERE instance_id=OLD.instance_id FOR UPDATE;
    IF FOUND AND excavation.key_character_id=OLD.character_id AND excavation.selected_source_id IS NULL THEN
      DELETE FROM character_consumable_buffs WHERE uid=excavation.key_state_uid
        AND character_id=OLD.character_id
        AND metadata#>>'{metadata,scenario_lifecycle,instance_id}'=OLD.instance_id::text
        AND metadata#>>'{metadata,scenario_lifecycle,rule_sha256}'=excavation.rule_sha256;
      -- A departed carrier cannot permanently trap remaining members. No key
      -- transfer is invented: a later legitimate dig must win another draw.
      UPDATE dungeon_excavation_runs SET key_character_id=NULL,key_state_uid=NULL WHERE instance_id=OLD.instance_id;
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER dungeon_excavation_member_retirement
  AFTER UPDATE OF status ON dungeon_instance_members FOR EACH ROW
  WHEN (OLD.status IS DISTINCT FROM NEW.status)
  EXECUTE FUNCTION retire_excavation_member();
