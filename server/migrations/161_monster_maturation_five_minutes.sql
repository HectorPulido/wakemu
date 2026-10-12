-- Retune emulator defaults to five active minutes and a lower chance per attempt.
-- Preserve independently customized settings and all unrelated policy fields.
UPDATE settings
SET value=jsonb_set(value,'{interval_ms}','300000'::jsonb)
WHERE name='monster_maturation' AND value->'interval_ms'='900000'::jsonb;

UPDATE settings
SET value=jsonb_set(value,'{base_probability}','0.10'::jsonb)
WHERE name='monster_maturation' AND value->'base_probability'='0.25'::jsonb;

-- Shorten existing waits without restarting active clocks, changing observer
-- generations, or discarding an already-due cycle or committed receipt.
UPDATE monster_maturation_timers
SET remaining_ms=300000
WHERE remaining_ms>300000;
