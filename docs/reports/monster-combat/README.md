# Monster combat source inventory

Date: 2026-10-10. Scope: extract the installed client's monster combat definitions automatically, starting review with Miaumiaus, Tofus and Gobballs (Spanish client names retained in tables).

Current deployment: [automated native ranges 10–49](ACTIVATION_LEVEL_10_49_20261010.md). **190 newly activated references**, preserving the previous 57; **247 active references total**. The new range contains 371 references, including 303 with covered effect families; 113 covered references remain disabled. Validation passed 430 tests, zero failures/errors/skips, and complete native spell/level plus AI-commit checks for every newly activated reference. [Manual acceptance](MANUAL_LEVEL_10_49_20261010.md) and [reusable cohort automation](AUTOMATION_COHORTS.md) describe testing and expansion. The complete 2,874-reference inventory is current in [ACTIVATION_STATUS.json](ACTIVATION_STATUS.json). Earlier reports retain historical counts.

The [382 ignored low-level actors without spellbooks and incomplete actor 3118](IGNORED_LOW_LEVEL_ACTORS_20261010.md), seven encounter exceptions, and five earlier pending cases remain unchanged.

Follow-on work: [scoped activation below level 10](ACTIVATION_UNDER_10.md) tracks execution validation, class regression protection, deployment status and the complete monster status inventory. The extraction findings below remain source evidence rather than activation claims.

The [lessons learned](LESSONS_LEARNED.md) explain the shared-engine design, preservation of existing class-backed NPC abilities, native transaction checks, initial-state limitations and source-revision fences. [Execution details](EXECUTION_LESSONS.md) retain diagnostic results and local test commands.

[Class regression lessons](CLASS_REGRESSION_LESSONS.md) record fixture authority repairs and targeted tactical checks without weakening behavior assertions.

[Local unit validation](LOCAL_UNIT_VALIDATION.md) records the broad server, service and Java diagnostics, reproducible read-only setup, unresolved failure clusters and intentional integration-test skips.

[Failure investigation](FAILURE_FIX_PROGRESS.md) separates production fixes, catalog evidence, fixture repairs and disputed expectations, with the assertion-preservation audit and current unresolved cases.

The extraction is implemented in [`extract_monster_combat_inventory.py`](../../../server/tools/extract_monster_combat_inventory.py). It exports all monsters; the low-level name filter only selects the review report. The initial extraction did not enable spells or change runtime services. Follow-on [deployment](DEPLOYMENT_20261010.md) now enables 30 completely validated low-level references through the existing shared engine; no monster spell was invented. The inventory retains all 2,874 references and distinguishes activated, pending and inventory-only entries.

## Reuse of the class spell system

The orchestrator reuses the existing class spell exporters and converters for casting, limits, effect trees, states, areas, root metadata and level zero. `ExportMonsterCombatData` adds monster ownership and fresh descriptors while delegating raw record preservation to `ExportMonsterEncyclopedia`. `ExportEffectReferenceTrees` inherits the existing full effect exporter; it only supplies explicit zero-level effect references. There is no separate NPC effect parser or combat engine.

For execution, keep the existing NPC ownership entry point and shared `server_runtime`/`NativeEffectRuntimeFactory`, dispatcher, condition evaluation, geometry, resource accounting, state lifecycle and transactional commit. Extend a common missing capability when necessary so player classes and NPCs use the same implementation. Monster-specific inputs are the native repertoire, level rules, initial states, properties and characteristic profiles.

## What the client provides

| Source | Extracted evidence |
|---|---|
| `aMb.csd / aMk.d,tL` | Actual owned spell references and level parameters. `-1` means actor level. `aMb.csr` is loot, not spells. |
| Fresh `bbo.a(aMb,short) / blj` | Initial-state triples and fight properties, independently of class decks. |
| `bbo.b(aMb) / ffC / ffx` | All 92 characteristic definitions, per-monster curves, native values at minimum/maximum levels, collision radius and LOS height. |
| `aNr / bPS / fyP` | Costs, range, target restrictions, categories, raw casting criteria and conditional casting tables at every native positive spell level. |
| `fyP / fyS` | Per-target, per-turn and interval usage gates, including conditional alternatives. |
| `fG(level) / bcA / aKX / aNw` | Spell roots, child effects, raw parameter curves, evaluated parameters/probabilities at levels 1–200, conditions, flags, selectors, target masks, timing, areas and HMI actions. |
| `fG(0)` | Separate native level-zero casting, effects and dependency evidence; positive-level indices remain unchanged. |
| `eVn.fKX / aZF` | Casting collision geometry and target selector. These are kept distinct from effect damage geometry `aZP`. |
| `aNv / bbV / fyW` | State definitions, roots, durations, retention metadata and native level checks. |
| `aKa / bcN` | Effect-area definitions and their effect trees, retained even when the semantic link from a spell requires further work. |
| Original `aMb` public data getters | Complete raw records, including opaque fields, visuals, loot, world interactions and ecosystem actions. Unknown semantics are not assigned guessed meanings. |
| Installed Spanish localization | Monster, spell and state labels; untranslated references stay null. |

The complete extraction found **2,874 monster references**, **3,091 distinct monster-owned spells**, **4,143 installed casting definitions**, **6,129 states** and **1,436 effect-area definitions**. Secondary granted spells are followed to a fixed point. See the [generated low-level inventory](LOW_LEVEL.md) and [validation results](VALIDATION.md) for final dependency counts and sample parameters.

## First ordinary monsters

| Monster | Ref | Native levels | Owned spells |
|---|---:|---|---|
| Miaumiau | 2616 | 4–6 | 1774, 3803 |
| Miaumiau blanco | 2617 | 4–6 | 2794, 3831 |
| Miaumiau angora | 2598 | 6–8 | 3804, 1774 |
| Bebé tofu | 6 | 4–8 | 5790 |
| Tofu | 4 | 8–12 | 549, 7359, 7360, 7361 |
| Jalatín negro | 2 | 4–8 | 5769 |
| Jalatín blanco | 39 | 4–8 | 5768 |
| Jalató | 1 | 8–12 | 5767 |

All these ordinary abilities use the actor's level. Examples from the native casting tables: Miaumiau 1774 costs 3 AP at range 1; its state spell 3803 costs 2 AP at range 1 with interval 3. Tofu 549 costs 3 AP at range 1–2; the other three abilities each cost 1 WP. Jalató 5767 costs 3 AP at range 1. Jalatín 5769/5768 cost 3 AP at range 2–4 and include resource-loss effects. These costs are source values, including zero components; they are not a local balancing proposal.

The effect roots contain flags and branches. Two damage roots must not be summed without the native branch/critical/condition selection. The existing common effect runtime is the appropriate execution foundation, with separate NPC ownership; a copied player deck is not needed.

## Reproduce

Run from the repository root with the installed client and JDK 21 or newer. The destination must be a new directory under `.runtime`:

```sh
python3 server/tools/extract_monster_combat_inventory.py --extract \
  --output .runtime/monster-combat-new-export
```

Rebuild the inventory from an existing pinned evidence bundle without opening a game session:

```sh
python3 server/tools/extract_monster_combat_inventory.py \
  --output .runtime/monster-combat-extraction-20261010
```

Use repeated `--focus-name` arguments to change the initial review names. The report selects matching references with minimum level at most 15; extraction always covers every installed monster.

The bundle retains `monsters`, `actors`, `casting`, `limits`, `trees`, `states`, `roots`, `areas`, `area-effects`, `level-zero`, `zero-effect-definitions`, and `translations` as compressed JSON, together with `inventory.json.gz`, `focus.json`, `README.md`, TSV evidence and `provenance.json`. Source client archives, Java exporters, converters and documents have SHA-256 evidence. Raw dumps stay in `.runtime`; review documents are kept here.

Dependency traversal uses a compact index of original roots and candidate reference parameters, plus semantic fingerprints for overlap checks. Complete definitions stay in the source bundle. This releases large sampled catalogs between phases; file compression also streams bytes instead of parsing another complete graph.

## Reconstruction boundary

The existing `combat_npc_spell.prepare_npc_spell` checks native ownership and level, validates the cast and dispatches common effects transactionally. The extraction supplies the original definitions needed to extend that path. It does not demonstrate that all effects, target contexts, state initialization, triggers, AI choices or client animations execute correctly.

The starting mechanics already map to common runtime families: Jalató uses earth damage (3); Miaumiau adds state application (304); Tofu adds air damage (5), states and displacement groups (330); black and white Jalatíns combine water damage (4) with MP loss (48) or AP loss (55). Runtime families can also introduce implicit dependencies: the shared resource-loss implementation applies state 5227 after positive loss. The complete state source is retained, but such handler-owned links are outside the current parameter-link inventory and must be included in execution validation.

The next integration should merge a complete NPC domain into a new immutable PostgreSQL release, preserving the class catalogs and existing definitions. Validate source-bound legality, NPC initialization, representative family combinations, atomic rejection of unknown mandatory branches and a complete live combat cycle before claiming gameplay coverage. The runtime reads a pinned PostgreSQL release with Redis caching; historical files or fresh evidence bundles are not the active authority.

Effect samples above level 200 still require additional native evaluation; their raw curves and native positive casting tables are retained. Some monster descriptors have special levels as high as 30,000. State/grant links are conservative candidates across sampled levels, not unconditional execution. Missing candidate definitions are reported explicitly and can represent dynamic reference semantics as well as genuinely absent definitions. Other dynamic references, summons, areas, encounter scripts and server-only mechanics need semantic reconstruction. Official monster AI policies are not recovered by these exports.

HMI action IDs need special treatment when comparing separate exports: the native `OY` constructor assigns `bbP = bbO++`, and `d()` returns that process-local ID. The supplement comparator ignores only that allocation ID and its `HMIAction.m_id` string representation. It rejects all other differences, including particle IDs, and retains the original supplemental records separately.

## General manual review

1. Run the existing-bundle command above. Expect the complete monster/ability counts in [VALIDATION.md](VALIDATION.md), with no missing native casting tables or casting-root metadata.
2. Open [LOW_LEVEL.md](LOW_LEVEL.md). Check all eight ordinary monsters above as one cohort: ownership, actor-level resolution, costs, range, root families, flags and state dependencies must agree with their native records. The report also includes low-level variants matching the same names.
3. Inspect `focus.json` or `inventory.json.gz` if a row needs detail; use the corresponding spell/state/root key in the compressed source documents. `runtime_status` must remain `not_validated`.
4. Do not use this extraction review as a client gameplay acceptance result. No live client probe is required for this change because it does not alter runtime behavior.

## Encounter exclusions

[Seven native encounter actors](ENCOUNTER_EXCEPTIONS_20261010.md) remain in the all-level inventory but are explicitly withheld from automatic activation until their minigame or mission exists. Of the other 22 members of the original pending cohort, 17 are now activated and five retain [native encounter or lifecycle prerequisites](REMAINING_NATIVE_ENCOUNTER_CONSTRAINTS_20261010.md).
