-- One frozen distribution per observed empty-map episode. Roster changes and
-- outcome acknowledgement commit together; completed episodes never replan.
CREATE TABLE monster_idle_distribution_runs (
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 world_epoch text NOT NULL CHECK(length(world_epoch)>0),
 map_id integer NOT NULL,
 instance_id bigint NOT NULL CHECK(instance_id>=0),
 empty_generation bigint NOT NULL CHECK(empty_generation>=0),
 status text NOT NULL CHECK(status IN ('pending','completed','cancelled')),
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 finished_at timestamptz,
 UNIQUE(world_epoch,map_id,instance_id,empty_generation)
);
CREATE TABLE monster_idle_distribution_moves (
 run_id bigint NOT NULL REFERENCES monster_idle_distribution_runs(id),
 ordinal integer NOT NULL CHECK(ordinal>=0),
 chunk_index integer NOT NULL CHECK(chunk_index>=0),
 group_id bigint NOT NULL,
 expected_members jsonb NOT NULL CHECK(jsonb_typeof(expected_members)='array'),
 moved_members jsonb NOT NULL CHECK(jsonb_typeof(moved_members)='array'),
 status text NOT NULL DEFAULT 'pending'
  CHECK(status IN ('pending','applied','skipped','cancelled')),
 reason text,
 finished_at timestamptz,
 PRIMARY KEY(run_id,ordinal),
 UNIQUE(run_id,group_id)
);
CREATE INDEX monster_idle_distribution_pending
 ON monster_idle_distribution_moves(run_id,chunk_index) WHERE status='pending';
