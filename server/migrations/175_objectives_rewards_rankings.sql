-- Freeze source level and reward policy revisions independently of source payload.
ALTER TABLE objectives_events ADD COLUMN character_level integer;
UPDATE objectives_events e SET character_level=c.level FROM characters c WHERE c.id=e.character_id;
ALTER TABLE objectives_events ALTER COLUMN character_level SET NOT NULL;
ALTER TABLE objectives_events ADD CONSTRAINT objectives_source_level CHECK(character_level BETWEEN 1 AND 200);
ALTER TABLE objectives_events ADD COLUMN reward_policies jsonb NOT NULL DEFAULT '{}';
ALTER TABLE objectives_rewards ADD COLUMN policy_snapshot jsonb NOT NULL DEFAULT '[]';
ALTER TABLE objectives_progress ADD COLUMN rewards_reserved boolean NOT NULL DEFAULT false;
UPDATE objectives_progress p SET rewards_reserved=true WHERE EXISTS(
 SELECT 1 FROM objectives_rewards r WHERE r.character_id=p.character_id AND r.definition_key=p.definition_key AND r.period_key=p.period_key
) OR EXISTS(SELECT 1 FROM objectives_definitions d WHERE d.key=p.definition_key AND d.definition->'rewards'='[]'::jsonb);
CREATE TABLE objectives_reward_policies (
 key text PRIMARY KEY,policy jsonb NOT NULL,revision integer NOT NULL DEFAULT 1,
 updated_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE objectives_reward_policy_audit (
 id bigserial PRIMARY KEY,policy_key text NOT NULL,revision integer NOT NULL,
 operator text NOT NULL,policy jsonb NOT NULL,created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE objectives_weekly_scores (
 week_key text NOT NULL,profile_key text NOT NULL,bracket text NOT NULL,
 account_id bigint NOT NULL REFERENCES accounts(id),character_id bigint NOT NULL REFERENCES characters(id),
 attempt_id text NOT NULL,points integer NOT NULL,turns integer NOT NULL,
 level integer NOT NULL,completed_at timestamptz NOT NULL,
 PRIMARY KEY(week_key,profile_key,bracket,account_id)
);
CREATE TABLE objectives_weekly_finalizations (
 week_key text NOT NULL,bracket text NOT NULL,status text NOT NULL,
 snapshot jsonb NOT NULL,finalized_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
 PRIMARY KEY(week_key,bracket)
);

CREATE TABLE objectives_definition_versions (
 key text NOT NULL,revision integer NOT NULL,definition jsonb NOT NULL,
 PRIMARY KEY(key,revision)
);
INSERT INTO objectives_definition_versions SELECT key,revision,definition FROM objectives_definitions;
CREATE FUNCTION freeze_objective_definition_version() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 INSERT INTO objectives_definition_versions(key,revision,definition) VALUES(NEW.key,NEW.revision,NEW.definition);
 RETURN NEW;
END;
$$;
CREATE TRIGGER objectives_definition_version AFTER INSERT OR UPDATE ON objectives_definitions
FOR EACH ROW EXECUTE FUNCTION freeze_objective_definition_version();
CREATE TABLE objectives_ranked_attempts (
 attempt_id text PRIMARY KEY,event_id bigint NOT NULL REFERENCES objectives_events(id),
 recorded_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE objectives_service_state (
 key text PRIMARY KEY,value jsonb NOT NULL,updated_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE objectives_reward_policy_versions (
 key text NOT NULL,revision integer NOT NULL,policy jsonb NOT NULL,
 PRIMARY KEY(key,revision)
);
CREATE FUNCTION freeze_objective_reward_policy_version() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 INSERT INTO objectives_reward_policy_versions(key,revision,policy) VALUES(NEW.key,NEW.revision,NEW.policy);
 RETURN NEW;
END;
$$;
CREATE TRIGGER objectives_reward_policy_version AFTER INSERT OR UPDATE ON objectives_reward_policies
FOR EACH ROW EXECUTE FUNCTION freeze_objective_reward_policy_version();
