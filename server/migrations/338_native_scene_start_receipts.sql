-- Source-qualified paid scene starts, shared by every participant of a run.
-- Completion/exit remains owned by durable dungeon instance/room progression.
CREATE TABLE native_scene_start_receipts (
    instance_id bigint NOT NULL REFERENCES dungeon_instances(instance_id),
    source_id bigint NOT NULL CHECK (source_id>0),
    map_id integer NOT NULL CHECK (map_id>0),
    policy_id text NOT NULL CHECK (length(policy_id)>0),
    policy_sha256 text NOT NULL CHECK (length(policy_sha256)=64),
    policy jsonb NOT NULL CHECK (jsonb_typeof(policy)='object'),
    account_id bigint NOT NULL REFERENCES accounts(id),
    character_id bigint NOT NULL REFERENCES characters(id),
    session_generation text NOT NULL CHECK (length(session_generation)>0),
    payment jsonb NOT NULL CHECK (jsonb_typeof(payment)='array'),
    profile jsonb NOT NULL CHECK (jsonb_typeof(profile)='object'),
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (instance_id,source_id)
);
CREATE INDEX native_scene_start_owner ON native_scene_start_receipts(character_id,instance_id);
