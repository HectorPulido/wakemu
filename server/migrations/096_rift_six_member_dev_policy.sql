-- User-authorized local DEV party-size override; native rift UI describes four.
-- Existing runs retain their frozen policy. Ordinary parties/combat are unchanged.
UPDATE settings SET value=jsonb_set(value,'{max_members}','6'::jsonb)
WHERE name='rift_policy' AND value->>'policy_kind'='local_dev_not_official';
