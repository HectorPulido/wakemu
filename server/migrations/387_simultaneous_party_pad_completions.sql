-- Completion receipts persist; current action occupancy remains live World state.
CREATE TABLE simultaneous_party_pad_completions (
 instance_id bigint NOT NULL REFERENCES dungeon_instances(instance_id),
 profile_id text NOT NULL CHECK(length(profile_id) BETWEEN 1 AND 128),
 profile_sha256 text NOT NULL CHECK(length(profile_sha256)=64),
 fight_id integer NOT NULL REFERENCES combat_fights(id),
 participants jsonb NOT NULL CHECK(jsonb_typeof(participants)='array'),
 completed_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
 PRIMARY KEY(instance_id,profile_id)
);
