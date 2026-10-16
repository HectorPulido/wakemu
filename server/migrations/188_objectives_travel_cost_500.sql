-- Correct the requested transport price: 500 kamas, not 500,000.
INSERT INTO settings(name,value) VALUES('objectives_travel_cost_kamas','500')
ON CONFLICT(name) DO UPDATE SET value=EXCLUDED.value;
SELECT pg_notify('wakemu_objectives_updates','all');
