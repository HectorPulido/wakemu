-- Native reward17 uses a declared Wakemu base-XP policy without subscription.
CREATE TABLE achievement_scaled_xp_policies (
 policy_version text PRIMARY KEY,
 formula text NOT NULL CHECK(formula='native-monster-base-real-level-percent-java-round'),
 subscription_factor integer NOT NULL CHECK(subscription_factor=1),
 authority text NOT NULL CHECK(length(authority)>0)
);
CREATE TABLE achievement_scaled_xp_active (
 singleton boolean PRIMARY KEY DEFAULT true CHECK(singleton),
 policy_version text NOT NULL REFERENCES achievement_scaled_xp_policies,
 enabled boolean NOT NULL DEFAULT false
);
CREATE TABLE achievement_scaled_xp_receipts (
 character_id bigint NOT NULL,
 achievement_id integer NOT NULL,
 cycle_key text NOT NULL,
 reward_key text NOT NULL,
 policy_version text NOT NULL REFERENCES achievement_scaled_xp_policies,
 native_parameter integer NOT NULL CHECK(native_parameter>0),
 real_level integer NOT NULL CHECK(real_level BETWEEN 1 AND 32767),
 native_base_xp bigint NOT NULL CHECK(native_base_xp>0),
 final_amount bigint NOT NULL CHECK(final_amount>=0),
 payload jsonb NOT NULL CHECK(jsonb_typeof(payload)='object'),
 earned_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
 PRIMARY KEY(character_id,achievement_id,cycle_key,reward_key),
 FOREIGN KEY(character_id,achievement_id,cycle_key,reward_key)
 REFERENCES character_achievement_reward_outbox(character_id,achievement_id,cycle_key,reward_key)
);
CREATE FUNCTION achievement_scaled_xp_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION 'Scaled achievement XP earned facts are immutable'; END $$;
CREATE TRIGGER achievement_scaled_xp_policy_immutable BEFORE UPDATE OR DELETE ON achievement_scaled_xp_policies
 FOR EACH ROW EXECUTE FUNCTION achievement_scaled_xp_immutable();
CREATE TRIGGER achievement_scaled_xp_receipt_immutable BEFORE UPDATE OR DELETE ON achievement_scaled_xp_receipts
 FOR EACH ROW EXECUTE FUNCTION achievement_scaled_xp_immutable();
INSERT INTO achievement_scaled_xp_policies VALUES(
 'wakemu.achievement-native17-base-no-subscription-v1',
 'native-monster-base-real-level-percent-java-round',1,
 'Explicit Wakemu interpretation: original native reward17 percentage of monster base XP at actual character real level; subscription coefficient fixed to one');
INSERT INTO achievement_scaled_xp_active VALUES(true,'wakemu.achievement-native17-base-no-subscription-v1',false);
