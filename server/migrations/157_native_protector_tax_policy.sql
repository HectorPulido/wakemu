-- Native MARKET_ADD_ITEM_CONTEXT default; no NPC actors or nation ownership seeded.
INSERT INTO settings(name,value) VALUES
('native_protector_tax_policy','{"schema_version":1,"contexts":{"1":0.05}}'::jsonb)
ON CONFLICT (name) DO NOTHING;
