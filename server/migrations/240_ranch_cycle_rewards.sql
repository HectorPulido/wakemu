-- Explicit Wakemu deployed-clock policy; preserve native raw attributes.
CREATE TABLE account_ranch_cycle_progress (
 monster_uid bigint PRIMARY KEY REFERENCES account_ranch_creatures(uid) ON DELETE CASCADE,
 last_observed_ms bigint NOT NULL CHECK(last_observed_ms>=0),
 earned_intervals jsonb NOT NULL DEFAULT '[]'::jsonb CHECK(jsonb_typeof(earned_intervals)='array'),
 cycle_number bigint NOT NULL DEFAULT 0 CHECK(cycle_number>=0),
 should_cycle boolean NOT NULL DEFAULT TRUE
);

-- Empty draws also retain their immutable cycle identity.
CREATE TABLE account_ranch_reward_batches (
 monster_uid bigint NOT NULL REFERENCES account_ranch_creatures(uid),
 cycle_number bigint NOT NULL CHECK(cycle_number>=0),
 account_id bigint NOT NULL REFERENCES accounts(id),
 drop_date_ms bigint NOT NULL CHECK(drop_date_ms>=0),
 items jsonb NOT NULL CHECK(jsonb_typeof(items)='array'),
 PRIMARY KEY(monster_uid,cycle_number)
);
-- Reward UIDs are native fBU ledger identities, not physical inventory UIDs.
CREATE TABLE account_ranch_rewards (
 uid bigint PRIMARY KEY CHECK(uid>0),
 account_id bigint NOT NULL REFERENCES accounts(id),
 monster_uid bigint NOT NULL REFERENCES account_ranch_creatures(uid),
 cycle_number bigint NOT NULL CHECK(cycle_number>=0),
 entry_index integer NOT NULL CHECK(entry_index>=0),
 item_ref integer NOT NULL CHECK(item_ref>0),
 quantity smallint NOT NULL CHECK(quantity>0),
 drop_date_ms bigint NOT NULL CHECK(drop_date_ms>=0),
 retrieved_at timestamptz,
 recipient_character_id bigint REFERENCES characters(id),
 UNIQUE(monster_uid,cycle_number,entry_index),
 FOREIGN KEY(monster_uid,cycle_number) REFERENCES account_ranch_reward_batches(monster_uid,cycle_number),
 CHECK((retrieved_at IS NULL)=(recipient_character_id IS NULL))
);
CREATE INDEX account_ranch_rewards_pending ON account_ranch_rewards(account_id,uid)
 WHERE retrieved_at IS NULL;
