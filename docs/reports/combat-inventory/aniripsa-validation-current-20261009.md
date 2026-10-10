# Aniripsa baseline inventory and validation — 2026-10-09

Scope: inventory-only, offline verification against the active published native catalog. No production implementation changes, service operations, or database writes were made. Native catalog name metadata identifies Aniripsa as breed ID7.

## Ready and ordinary casts

[Normal cast audit](aniripsa-normal-casts-current-20261009.json) covered all available direct class spells at levels20 and200. The active inventory is complete:14 references at level20 and21 at level200. Four legal deck chunks reached Ready (two per level), and the audit source/tool hashes are stable.

Of35 expected spell-level pairs,32 were prepared and committed in isolated in-memory fight branches. All60 prepared attempts committed successfully; there were no effect-transaction rejections, mixed outcomes, or prepared pairs left uncommitted. The remaining three pairs were classified as unavailable native contexts, rather than failed effect transactions:

- **Anisurrección1535**, levels20 and200: native eligibility needs an off-play non-enemy target without fight property66, or a target of breed5162. The baseline contains only an enemy NPC, so neither pair reached gameplay.
- **Vínculo de Amistad781**, level200: native eligibility requires a non-enemy occupied target without state3864. The baseline has no eligible ally, so this pair did not reach gameplay.

The audit separately found three grant references, with six distinct grant spell-level pairs across the two builds. Grant pairs are not included in the35 ordinary-spell denominator. Conditional gameplay is not fully verified; this baseline does not simulate the ally, knockout, or breed-specific situations required by the three unavailable pairs. The generic deployment gate remains false.

## Passive cycles and healing regressions

[Passive cycle audit](aniripsa-passive-cycles-current-20261009.json) exercised20/20 passives through native Ready, NPC damage, turns, acknowledgements and expiry. All20 cycles completed with stable sources and no incomplete traces; three passives activated under the baseline conditions. Other passive-specific conditions were not fabricated.

Existing healing regressions passed **34 tests**, with **one optional test skipped**, across damage healing, handler, parameters, effects, area guard and aptitude healing. These unit regressions do not replace an actual ally-healing or resurrection scenario.

## Exact commands

```sh
PYTHONPATH=server:server/tests:server/tools WAKFU_DATABASE_URL='host=127.0.0.1 port=15432 dbname=wakemu_runtime user=wakemu' WAKFU_DATABASE_PASSWORD_FILE="$PWD/.runtime/local/secrets/postgres-password" /tmp/wakemu-combat-review-venv/bin/python3 server/tools/audit_class_normal_casts.py docs/reports/combat-inventory/aniripsa-normal-casts-current-20261009.json --breeds 7 --levels 20 200 --candidate-limit 32 --maximum-eligible 2 --commit-each-prepared
PYTHONPATH=server:server/tests:server/tools WAKFU_DATABASE_URL='host=127.0.0.1 port=15432 dbname=wakemu_runtime user=wakemu' WAKFU_DATABASE_PASSWORD_FILE="$PWD/.runtime/local/secrets/postgres-password" /tmp/wakemu-combat-review-venv/bin/python3 server/tools/audit_passive_activation.py --breed 7 --output docs/reports/combat-inventory/aniripsa-passive-cycles-current-20261009.json
PYTHONPATH=server:server/tests:server/tools WAKFU_DATABASE_URL='host=127.0.0.1 port=15432 dbname=wakemu_runtime user=wakemu' WAKFU_DATABASE_PASSWORD_FILE="$PWD/.runtime/local/secrets/postgres-password" /tmp/wakemu-combat-review-venv/bin/python3 -m unittest test_combat_damage_healing test_combat_healing_handler test_combat_healing_parameters test_combat_healing_effect test_combat_healing_area_guard test_combat_aptitude_healing_runtime
```
