-- Local guild authority is opt-in; native identity and rules require explicit policy.
INSERT INTO settings(name,value) VALUES ('guild_policy', '{"enabled":false,"identity_changes":{"name":{"enabled":false,"authority":null,"item":25101,"kamas":null},"blazon":{"enabled":false,"authority":null,"item":25100,"kamas":null}},"native_sync_enabled":false,"moderation_bonus_learning_factor":null,"owner_id_semantics":null,"creation_kamas":10000,"creation_item":16942,"max_members":200,"max_ranks":15,"name_pattern":null,"name_normalization":null,"allowed_blazons":[],"description_max_bytes":null,"message_max_bytes":null,"leader_permissions":null,"member_permissions":null,"permissions":{},"invitation_seconds":86400,"catalog":{},"economy":{"treasury_enabled":false,"progression_enabled":false,"bonuses_enabled":false,"permission_bits":{},"point_sources":{},"weekly_point_cap":null,"bonus_catalog":{}}}');
CREATE TABLE guilds (
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 name text NOT NULL, name_key text NOT NULL UNIQUE,
 blazon bigint NOT NULL, leader_id bigint NOT NULL REFERENCES characters(id),
 revision bigint NOT NULL DEFAULT 0 CHECK(revision>=0),
 level integer NOT NULL DEFAULT 1 CHECK(level BETWEEN 1 AND 32767), description text NOT NULL DEFAULT '', message text NOT NULL DEFAULT '',
 current_points bigint NOT NULL DEFAULT 0 CHECK(current_points BETWEEN 0 AND 2147483647), total_points bigint NOT NULL DEFAULT 0 CHECK(total_points BETWEEN 0 AND 2147483647), weekly_points bigint NOT NULL DEFAULT 0 CHECK(weekly_points BETWEEN 0 AND 2147483647),
 created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
 dissolved_at timestamptz
);
CREATE TABLE guild_ranks (
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 guild_id bigint NOT NULL REFERENCES guilds(id), name text NOT NULL,
 position integer NOT NULL CHECK(position>=0), permissions bigint NOT NULL CHECK(permissions BETWEEN 0 AND 9223372036854775807),
 UNIQUE(guild_id,id), UNIQUE(guild_id,position) DEFERRABLE INITIALLY DEFERRED
);
CREATE TABLE guild_members (
 character_id bigint PRIMARY KEY REFERENCES characters(id),
 guild_id bigint NOT NULL REFERENCES guilds(id), rank_id bigint NOT NULL,
 joined_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
 last_seen timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
 points bigint NOT NULL DEFAULT 0 CHECK(points BETWEEN 0 AND 2147483647),
 FOREIGN KEY(guild_id,rank_id) REFERENCES guild_ranks(guild_id,id)
);
CREATE INDEX guild_members_guild ON guild_members(guild_id);
CREATE TABLE guild_invitations (
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 guild_id bigint NOT NULL REFERENCES guilds(id), inviter_id bigint NOT NULL REFERENCES characters(id),
 target_id bigint NOT NULL REFERENCES characters(id), target_generation text, expires_at timestamptz NOT NULL,
 status text NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','accepted','rejected','cancelled'))
);
CREATE UNIQUE INDEX guild_pending_invite ON guild_invitations(target_id) WHERE status='pending';
CREATE TABLE guild_operation_receipts (
 character_id bigint NOT NULL REFERENCES characters(id), operation_key text NOT NULL,
 request jsonb NOT NULL, result jsonb NOT NULL, PRIMARY KEY(character_id,operation_key)
);
CREATE TABLE guild_events (
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY, guild_id bigint NOT NULL REFERENCES guilds(id),
 revision bigint NOT NULL, kind text NOT NULL, payload jsonb NOT NULL,
 created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP, published_at timestamptz,
 UNIQUE(guild_id,revision)
);
CREATE INDEX guild_events_pending ON guild_events(id) WHERE published_at IS NULL;
CREATE TABLE guild_service_state (
 guild_id bigint NOT NULL REFERENCES guilds(id), service text NOT NULL,
 record jsonb NOT NULL DEFAULT '{}', PRIMARY KEY(guild_id,service)
);
CREATE FUNCTION prevent_guild_member_deletion() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF NEW.deleted_at IS NOT NULL AND OLD.deleted_at IS NULL AND EXISTS(SELECT 1 FROM guild_members WHERE character_id=NEW.id) THEN
  RAISE EXCEPTION 'Leave or dissolve guild before deleting character';
 END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER characters_guild_deletion_guard BEFORE UPDATE OF deleted_at ON characters FOR EACH ROW EXECUTE FUNCTION prevent_guild_member_deletion();
-- Trusted progression events are idempotent independently of actor requests.
CREATE TABLE guild_progression_receipts (
 guild_id bigint NOT NULL REFERENCES guilds(id), event_key text NOT NULL,
 request jsonb NOT NULL, result jsonb NOT NULL,
 PRIMARY KEY(guild_id,event_key)
);

ALTER TABLE guilds ADD COLUMN member_capacity_bonus integer NOT NULL DEFAULT 0 CHECK(member_capacity_bonus>=0), ADD COLUMN weekly_capacity_bonus integer NOT NULL DEFAULT 0 CHECK(weekly_capacity_bonus>=0), ADD COLUMN unlocked_compartments jsonb NOT NULL DEFAULT '[]';
