# Native NPC execution validation lessons

## Scope and evidence status

The investigation used in-process candidate catalog overlays and PostgreSQL read-only connections. It did not activate a catalog, change database content, restart a service, or grant spells. The candidate population contains 69 monster references whose entire native level range is below 10 and whose exported effect families are covered. Whole-range selection avoids activating a low-level variant of a monster that also has higher native levels.

Historical complete batches exercised 169 native level/spell combinations. Of those, 129 produced an effectful native transaction in the finite target search. Thirty references passed every tested combination without unresolved initial states; 39 remained pending. These are historical execution observations, not a certificate for the current checkout: subsequent concurrent runtime changes and the preservation gate require fresh final receipts.

Twenty-one selected references have native initial-state triples. The runtime-facing monster catalog omits those triples, so the validator reads the original extraction artifact and records its checksum. Those references remain pending even if all individual spells execute. Initial effects can establish state, conditions, properties, or behavior required by later attacks; successful execution from an empty initial state cannot prove the complete monster works.

## Dependencies and boundaries

Effect-family coverage is necessary but insufficient. Native casting also requires exact casting roots, native ownership and spell levels, actor statistics and targeting metadata, resource-cost tables, state authority, spatial registration, and lifecycle producers.

The active catalog initially lacked the shared resource-cost document required by current runtime code. The extracted dependency contains 4,143 spells, SHA256 `fb10cfe102215efac81153552aa112a3a92d95d91dff76e53fb036d754f827b0`. Missing mandatory cost authority caused all attempted casts to reject; treating that as individual monster incompatibility would be misleading. The dependency was first included in the isolated candidate and later appeared in the active base. Rebuilding the candidate against the new pinned revision preserved the revision fence rather than bypassing it.

The candidate overlays only NPC effects and native casting roots, plus the missing resource-cost document when required. Existing class documents remain byte-identical. Huppermage regressions read a staged resource-cost document; the harness explicitly verifies that its checksum equals the baseline/candidate authority, preventing a false comparison between different datasets.

## Preserve existing behavior before enabling imports

Filtering native ownership to the new activation allowlist would remove existing eligible attacks from unrelated NPCs that reuse shared class definitions. Player-controlled summons inherit a different casting route, so this finding does not establish a regression for all summons. Ownership therefore remains the original native abilities plus valid temporary grants. The activation decision controls which compiled effect catalog a cast can use.

The baseline compiled catalog combines the existing class effects with the exact pre-import NPC effects saved as `baseline_effects`. Selected reference/level/spell tuples can use the expanded NPC effects; other casts retain the original compiled catalog. Temporary grants and shared class roots remain available through the original route. A scoped document without preserved baseline effects fails closed. Regression tests verify both catalogs retain class roots, baseline NPC roots survive unchanged, imported roots remain isolated, and unknown high-level actors retain native ownership and grants.

## Native previews and actual delivery

Each case uses fresh native actor snapshots on map 1134, actual QI terrain/registration, and an explicitly serialized empty QL obstacle collection. The terrain's empty obstacle source is checked before using that fixture. This proves execution within that scope; it does not certify every map or obstacle layout.

The search tries self, enemy, and empty-cell targets within the native range envelope. It does not mock line of sight. Rejection from a finite sample is recorded as pending conditions/metadata/search scope, not automatically labeled an engine bug. Source snapshots must remain unchanged after both successful and failed previews.

Historical AI checks covered one effectful representative spell for each of the 30 fully preview-validated references. They used actual `NativeProvider.preview` and `commit`, real packet serializers, observable resource/HP/state/position changes, and an injected serialization failure that must restore the complete checkpoint. The engine deliberately preserves Fight and Actor identities during adoption; an early harness assertion expecting replacement was incorrect and that receipt was discarded. Packet emission alone is insufficient evidence of an attack.

## Fixture authority and regressions

Broad baseline runs exposed stale fixtures rather than immediately proving candidate regressions. Corrections used native actor heights, explicit player/NPC control facts, QI setup before `fight.ready()`, actual global-PV producers, and registered movement instead of direct position mutation. Directly changing MP without updating native raw/effective snapshots likewise violates authority. Assertions were retained while producers were repaired.

An earlier preserved-candidate diagnostic baseline ran 167 tests: 164 passed, one tactical Jalató assertion failed, and two setup errors remained. Its runtime changed during execution, so it is not final evidence. Earlier baseline failures and discarded harness receipts remain private diagnostic artifacts. Final approval requires an absolute passing class suite, not merely matching baseline failures.

## Immutable inputs and receipt fences

Concurrent changes to cost selection, effect recursion/payment dispatch, and NPC casting invalidated otherwise completed batches. Runtime hashes now begin before native imports, and the receipt compares all combat source files afterward, including added or removed files. It also hashes test fixtures, the validator, and the native monster extraction before and after execution. `sources_stable` requires every authority to remain stable.

Resume and extension require matching candidate manifest, changed documents, pinned base revision and audited original document hashes, runtime sources, native extraction, validator, and test sources. Old receipts missing these fences cannot be reused. AI delivery evidence cannot be reused after runtime changes. Completed rows can be resumed only under identical authority; a candidate from another base is rebuilt rather than silently retargeted.

Repeated full garbage collections originally traversed the large immutable native catalogs and caused severe memory pressure. Collecting and freezing the catalog graph after completed cases reduced a fresh 69-reference batch to approximately 85 seconds and 30 AI delivery checks to approximately 30 seconds. This optimization changes collection behavior only; it does not weaken validation or alter native authority.

## Offline receipt regressions

`validate_receipt_context` is a pure comparison boundary shared by resume, extension, and baseline comparison. Unit cases accept an unchanged context and reject both a changed value and a missing field for each of its eight authorities. Thus legacy receipts without the newer validator, fixture, extraction, or base-document fences cannot be silently reused. Additional cases reject added or removed fixture files. The pure `changed_hashes` comparison detects added, deleted, and modified runtime files while retaining unchanged entries and leaving both input maps intact.

The latest offline command passed 48 tests without a PostgreSQL connection:

```sh
PYTHONPATH=server:server/tests .runtime/local/verification-venv/bin/python -m unittest \
  test_monster_spell_activation test_npc_casting_root_import \
  test_monster_combat_extraction \
  test_combat_active_spell.ActiveSpellTests.test_current_scope_restores_even_on_failure_and_nested_cast
```

This includes 29 activation, catalog-preservation, overlay, and receipt tests. It is local regression evidence; it does not replace the pending native execution and class certification under a stable checkout.


## Expanded class diagnostic follow-up

After the tactical fixtures were corrected, `diagnostic-baseline-classes.json` completed 173 tests with zero failures, errors, or skips in 160.38 seconds. The selected suite contains 27 class/combat/extraction modules, including native Feca, Sram, Sacrier, Cra, Huppermage, Iop, Xelor, shared costs, NPC transactions, and tactical planning. Runtime source hashes remained unchanged. The broader fixture hash changed for `server/tests/test_combat_event_costs.py`, which is outside those 27 modules; the conservative receipt therefore reports `tests_stable=false` and `sources_stable=false`.

This result is a successful local diagnostic, not a final activation certificate or a valid differential comparison. The candidate class diagnostic is run separately so its own evidence is retained even if the complete comparison context differs. No additional 169-case NPC batch or 30-monster AI delivery batch is implied by these class results.

The separate candidate diagnostic then passed the same 173 tests with zero failures, errors, or skips in 134.12 seconds. Its runtime, fixtures, validator, and extraction hashes remained stable (`sources_stable=true`). Both results are retained individually beneath `.runtime/monster-activation-under10-preserved-20261010/`:

- `diagnostic-baseline-classes.json`
- `diagnostic-candidate-classes.json`
- `diagnostic-class-comparison.json`

The comparison correctly rejected the differing `test_code_sha256` context and records `available=false`. The two independent successful runs are useful local class/combat diagnostics; they are not presented as an identical-authority differential. The passing candidate class run contains no NPC case or AI delivery rows and therefore cannot alone authorize activation. No additional native NPC batch was run during this follow-up.

## Latest full activation validation attempt

The expanded baseline class suite includes 29 modules, adding the complete Feca grant pipeline and Sram trap audit configuration to the existing Huppermage, Sram, Feca, Iop, Xelor, Sacrier, Cra and shared combat coverage. The current attempt ran 178 tests in 150.5 seconds with zero failures, errors or skips. Runtime and validator hashes remained unchanged. The strict receipt fence correctly rejected certification because an unrelated test file, `server/tests/test_hybrid_native_candidates_postgres.py`, changed concurrently during the run. This individual green baseline is diagnostic evidence, not a reusable certified baseline. Receipt: `.runtime/monster-activation-under10-preserved-20261010/final-baseline-classes.json`. No original assertions were changed for this run.

## Final current-source execution receipt

The final fence covers all 988 production Python files beneath `server`, including NativeOracle and activation tools, plus the static AST import closure of the 29 selected class regression modules (50 test/tool files). The receipt records its explicit `test_scope`. A tempfile regression verifies transitive test fixtures, relative imports, imported tools, missing modules, and exclusion of unrelated test changes. All 30 activation helper tests passed before the full sequence. No existing expectation was rewritten.

Fresh baseline and candidate runs each passed 179 tests with zero failures, errors or skips. The candidate comparison reports no added failures. Both runs cover Huppermage, Sram and Feca, including the Feca grant pipeline. The fresh NPC preview evaluated all 69 selected references and 169 native level/spell cases: 129 effectful cases, 30 fully validated references and 39 pending references. All 30 eligible references then passed real AI preview/serialized commit, source immutability, observable-state change and late-serialization rollback checks. Every final runtime, fixture, validator, native-extraction and preview-reuse fence is true.

Read-only validation artifacts are under `.runtime/monster-activation-under10-preserved-20261010`: `final-baseline-classes-v2.json` (139.77 seconds), `final-native-preview-v2.json` (81.41 seconds), and `final-validation-v2.json` (152.84 seconds including AI and candidate classes). The offline finalizer succeeded and produced `.runtime/monster-activation-under10-final-20261010`: 30 validated references, 39 pending selected references, and the complete 2,874-monster inventory. Pending initialization and finite-target outcomes remain in each monster's execution receipt. The finalizer narrows imported-spell eligibility to the validated 30, preserves baseline NPC/class effects, and leaves higher-level references inventory-only. Finalization itself neither writes PostgreSQL nor activates/restarts services.

This certification concerns the selected activation/class suite. The separately documented original resolver assertion about fresh explicit zero-mask PV remains a visible contradictory expectation, loaded twice in its focused run; it was not silently changed or included as a passing test. The unchanged original Aniripsa integration now passes after the independently evidenced singleton-target fix. See `ANIRIPSA_5459_TRIAGE.md` for that exact limitation and evidence.
