-- Move the only active cron callback into World while preserving its cadence.
INSERT INTO settings(name,value)
SELECT 'world_position_checkpoint_policy',
       jsonb_build_object(
           'interval_seconds', LEAST(30, GREATEST(0.1,
               COALESCE((value #>> '{tasks,positions_flush,interval}')::numeric, 2))),
           'max_accounts', 32,
           'max_seconds', 0.1)
FROM settings WHERE name='cron_scheduler_policy'
ON CONFLICT(name) DO NOTHING;

INSERT INTO settings(name,value) VALUES (
    'world_position_checkpoint_policy',
    '{"interval_seconds":2,"max_accounts":32,"max_seconds":0.1}'::jsonb
) ON CONFLICT(name) DO NOTHING;
