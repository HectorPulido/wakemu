# Automatic boss ability coverage

All eight identity-validated offline configuration candidates have incomplete native owned boss spell coverage. Exact spell IDs, effective native levels and missing root IDs are recorded in [structured evidence](AUTOMATIC-BOSS-ABILITY-COVERAGE.json) and the [activation readiness report](AUTOMATIC-ACTIVATION-READINESS.md).

The audit checks native `csd` ownership at the configured minimum actor level, exact casting-level availability and required roots against `npc_runtime_catalog().effects`. Presence would still not prove effect branches, AI, invulnerability, summons or special phases. No combat behavior was changed.

Reproduce using `PYTHONPATH=server python server/tools/audit_dungeon_boss_abilities.py` with catalog access. Four pure regression tests cover exact levels, absent roots, unavailable casting levels and empty ability lists.

Earlier placement-only auditing included three additional dungeons with unresolved guide species. They were subsequently withheld; the current reproducible boss audit follows the eight identity-validated candidates.
