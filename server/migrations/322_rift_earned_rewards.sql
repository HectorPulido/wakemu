-- Explicit Wakemu earned progression applies to genuine Rift wins and losses.
-- Native common loot keeps its original rolls; only accepted quantities scale.
INSERT INTO settings(name,value) VALUES ('rift_earned_reward_policy', '{
 "policy":"wakemu.rift.reached-wave-times-ten.v1","version":1,
 "wave_basis":"reached_wave","multiplier_per_wave":10,
 "outcomes":["won","lost"],"require_defeated_native_monsters":true,
 "withdrawals":"none"
}'::jsonb) ON CONFLICT(name) DO UPDATE SET value=excluded.value;

UPDATE settings SET value=jsonb_set(value,'{losses}','"earned_native_kills"'::jsonb)
WHERE name='rift_reward_policy' AND value->>'kind'='local_dev_items_v1';

UPDATE settings SET value=jsonb_set(value,'{ULTIMATE_INFINITE_WAVE,losses}',
                                  '"earned_native_kills"'::jsonb)
WHERE name='rift_reward_type_overrides'
  AND value->'ULTIMATE_INFINITE_WAVE'->>'kind'='local_dev_items_v1';
