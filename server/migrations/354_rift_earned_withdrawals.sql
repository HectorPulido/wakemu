-- Explicit surrender retains only the native kills earned before departure.
-- Existing fight/character reward keys remain the exactly-once authority.
UPDATE settings SET value=jsonb_set(value,'{withdrawals}','"earned_native_kills"'::jsonb)
WHERE name='rift_earned_reward_policy'
  AND value->>'policy'='wakemu.rift.reached-wave-times-ten.v1';
