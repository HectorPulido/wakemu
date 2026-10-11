-- Explicit local adaptations. Never replace operator-configured profiles.
-- Neoogrest shares Ogrest's native initial state5022/minimumHP and abilities.
-- Love Gobball uses the documented three-round boss window as a local
-- standalone challenge, without claiming original Shoot'Aime wave parity.
UPDATE settings SET value=jsonb_set(value,'{profiles}',
    value->'profiles' ||
    CASE WHEN value->'profiles' ? '5806' THEN '{}'::jsonb ELSE
      '{"5806":{"round_limit":20}}'::jsonb END ||
    CASE WHEN value->'profiles' ? '5608' THEN '{}'::jsonb ELSE
      '{"5608":{"round_limit":3,"allow_early_boss_defeat":true}}'::jsonb END)
WHERE name='boss_score_policy'
  AND value->>'policy'='wakemu-boss-validated-damage-v1'
  AND jsonb_typeof(value->'profiles')='object';
