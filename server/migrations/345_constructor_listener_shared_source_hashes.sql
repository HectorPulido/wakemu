-- The NPC import projection adds native_active_effect=true; the actual shared
-- state runtime projection does not carry that exporter-only annotation.
-- Pin the exact shared runtime programs. All native effect fields, state data
-- and retained metadata are identical; no callback semantics are changed.
UPDATE native_npc_constructor_table_listeners
SET source_sha256='b7173854d5f6d9d03966bb4a19a10bb6359c3bfaac3c0a89d9621cd739fcb134'
WHERE monster_reference IN (4756,4757,4758)
  AND state_id=5606 AND root_id=265135
  AND source_sha256='87c02e12045b7c9a36114d8e402e8bc30e3c396572d3001bc0f68233401550d8';

UPDATE native_npc_constructor_table_listeners
SET source_sha256='ebe5c357906f1d53643d478124839e83b74c7c9fbd4f5b7d9be7b9e6de9fde35'
WHERE monster_reference=4886
  AND state_id=5770 AND root_id=270723
  AND source_sha256='a4b497076ac4fc364df3732bee25c95c5c51359e07eaec72e4fb61b3ea25ddfb';
