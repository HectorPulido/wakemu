# Cra final source review — 2026-10-08

## Result

The current inspected source does not establish an outstanding Cra-specific missing core implementation. This is not a statement that every Cra spell or passive is correct. Current published data was verified successfully; remaining work consists of semantic coverage of conditional/event branches, and full client acceptance. Previously identified concrete defects must not be reported as still missing after their shared repairs.

## Exact inventory

| Domain | Count | Native references |
|---|---:|---|
| Active deck spells | 21 | 4769,4774,4805,4806,4808,4809,4810,4811,4812,4813,4814,4815,4816,4817,4818,4819,4820,4821,4822,6842,7753 |
| Passive deck spells | 19 | 6945,6946,6947,6948,6949,6950,6951,6952,6953,6955,6956,6957,6958,6959,6960,6961,6962,6963,7795 |
| Granted/temporary spells | 6 | 4807,6349,7752,7792,7793,7807 |
| Innate state seeds | 2 | 3419,4464 |
| Beacon profiles | 3 | 3798,3799,3800 |

The established dependency graph contains 48 entry roots, 46 distinct spell references, 1,198 effect definitions, 42 states and one effect area. Active-only closure contains 838 definitions, 28 predicate functions and 18 conditional casting rules. These are definition counts, not passed-spell counts. Innate4464 includes shared cosmetic finisher branches.

## Source findings rechecked now

| Previously established issue | Current source evidence | Remaining limitation |
|---|---|---|
| State decurse321 omitted native2288 reactions | `combat_state_decurse.py:_phase` invokes the lifecycle provider with definition-specific `target_masks[6]` and runner metadata. | Verify appropriate event/channel/order for every dependent branch; the absence of a hardcoded2288 literal is not an absent publisher. |
| Direct null400 omitted native produced phases | `combat_stat_handler.py` publishes definition-specific produced masks through the lifecycle provider, including retained-registration sequencing. | Dynamic masks drive phases; every null marker is not expected to deal damage. |
| External1010 lacked an owned producer | `combat_death_events.py` emits1010 through replay and declares policy `wakemu.owned-ko-and-death-v2`. | This is explicit Wakemu server policy, not recovered original-server semantics. |
| Positive equipped finisher lacked presentation boundary | `combat_finisher_events.py` declares owned-finisher policy; `combat_death_events.py` and `combat_death.py` integrate execution and post-death cleanup. | Full equipped-finisher client acceptance remains distinct from core Cra spells. |
| Desbalizaje disabled despite visible beacons | `combat_summon_stats.py` validates true summon authority and serializes native `pW.Uh` from `authority["is_summon"]`. | User acceptance is recorded for r31 in `cra-desbalizaje-ui-criterion-20261008.md`; it is not all-spell acceptance. |
| Granted definitions excluded when general grant flag disabled | `combat_native_spell_casting.py:merged_spell_effects` now merges class summon and class grant dependency closures even when the general grant flag is disabled. | The 2026-10-07 default-flag diagnosis cannot be reused as a current missing-definition claim. |

## Beacons and passive semantics

Three native beacon creation profiles are present in the established source inventory:7793→3798/state7781,7792→3799/state7780 and4807→3800/state7779. Shared creation, actual owner registration, constructor states, stat snapshots and retained grants have source consumers.

Balizas Discretas6947 applies native property54, DONT_BLOCK_LOS, rather than invisibility properties5/18. A visible owner beacon is not by itself a defect. Constructor damage leaves357565/357566/357567 have literalFalse criteria; enabling them would change native behavior. Several passive direct roots are400 markers while their behavior is supplied by real deck conditions in innates and casting tables. Do not count those markers as missing passive implementation.

## Precisely remaining checks

1. **Published catalog authority verified:** read-only inspection inside the existing world confirmed published revision `7071a8d8c8664e9e0d5fe8f44bf2a948d4138060fc1353ea70f65f2dcf00b568`. The actual compiled catalog contains all 1,198 graph effect dependencies and 42 state dependencies; all 46 spell references have casting definitions. Missing effects, states and casting spells: **zero**. Existing graph membership was checked against current published data; no gameplay was simulated.
2. **Current-source routes refreshed:** the route builder's unchanged AST factory/dispatcher analysis was executed against the current checkout and authoritative published characteristic/set-current registries, with outputs under `/tmp/wakemu-cra-current-route/`. All **70 effect families** used by the **48 Cra roots** have a current binding: **zero missing handler families**. Seven families have construction guards (300,302,307,315,421,843,1013); these are provider requirements, not demonstrated failing Cra branches. No historical report was overwritten.
3. **Branch semantics:** normal/critical availability, conditional range/cost/LOS tables, passive event timing, retention/removal, resource limits and temporary7807 grant/cleanup must have expected-result assertions. A route existing or a generic actor change is insufficient. No precise count of missing semantic cases is justified by the present static evidence.
4. **Shared terrain limits:** the previous active audit records27 legacy terrain archives without decodable exports. This is a shared data limitation, not21 broken Cra spells; map527 is not among them. Revalidate that count before claiming current completeness across all maps.
5. **Full client acceptance:** the recorded Desbalizaje confirmation covers its tested sequence only. It does not certify21 actives,19 passives, all three beacon reaction paths, movement/teleport terrain cases, reconnect, critical variants or finisher visuals. Hector has confirmed glyph functionality; do not keep glyph behavior listed as an outstanding user acceptance gap. Other presentation contracts require their own recorded evidence.

## Review method and evidence

Read-only source inspection, existing native definition graph and existing acceptance records were used. No service restart, client launch, gameplay scenario or code/catalog modification occurred. An authorized read-only command inspected the existing world's compiled published catalogs; the normal catalog reader may populate its internal Redis cache. Current source files inspected include `combat_state_decurse.py`, `combat_stat_handler.py`, `combat_death_events.py`, `combat_finisher_events.py`, `combat_death.py`, `combat_summon_stats.py`, `combat_native_spell_casting.py`, `combat_server_spell.py`, `characters/spell_audit.py` and `storage/native_catalog.py`.

Reuse the class parameterized `server/tools/inventory_class_code.py --breed9` after a coordinated current-source route rebuild and with the published native-catalog dependency environment. Preserve historical evidence; distinguish exact missing definitions/handlers from unverified behavior and legal prerequisite rejection. Source guards are defects only when an actual native Cra configuration requires authority production fails to supply.

## Current published-data verification

Command: `docker compose exec -T world python - < /tmp/wakemu-cra-published-readonly.py > /tmp/wakemu-cra-published-readonly.json`. The script imports actual compiled catalogs, resolves the pinned published revision, and checks the48 existing graph roots. Results:1198effects/42states present,46casting definitions present,zero missing. No complete-behavior claim follows from this structural availability check.

## Current route verification

The full global route-builder entry requires deleted protocol import artifacts and is unsuitable for this read-only published-catalog review. Its exact AST factory/dispatcher binding block was reused unchanged with two registry reads supplied from the pinned live catalog. Current source binding details and hashes are recorded in `/tmp/wakemu-cra-current-route/routes.json`. Results across48 roots:70 distinct families,zero absent handlers,seven guarded families. This refresh establishes actual code registration today; it does not bypass guards or simulate gameplay.
