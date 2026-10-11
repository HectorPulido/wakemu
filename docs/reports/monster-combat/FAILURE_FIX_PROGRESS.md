# Failure investigation and constrained fixes

Date: 2026-10-10. This follows the broad diagnostic run, not an activation certificate. Hector explicitly warned that changing tests can conceal regressions. Existing behavioral expectations are therefore retained while discrepancies are investigated; proposed expectation changes were withdrawn and saved privately for review.

## Production defects with targeted fixes

1. **NPC AI execution diverged from the common transaction.** `NativeOracle.cast` duplicated NPC resource payment and effect execution. It omitted the registered-fight argument required by native facing, changed AP/MP without the common raw-current update, and always compiled expanded NPC effects. Both NPC entry points now use `prepare_validated_npc_spell` after their existing ownership and native targeting validation. The oracle keeps its own authority factory and damage observer; catalog selection follows reference/level/spell rollout policy. Player casting retains its separate transaction route.
2. **Fresh summon sentinel rejected by actor-only compatibility allocation.** The native constructor assigns obstacle slot `-1`; the compatibility allocator expects `None` before allocation. Only the detached fresh actor's sentinel is translated. Invalid or duplicate registered slots still reject, failed allocation restores the sentinel, and an actor already in the roster cannot be allocated as fresh.
3. **Abandonment accepted an unregistered summon in the roster.** Clearing a summon's registration could make it resemble another character belonging to the account. Abandonment now rejects native summon markers lacking registration while retaining same-account hero participants. The original failing roster test remains unchanged and a separate hero/summon regression was added.

The focused run covering these allocation/roster fixes plus summon, melee and weapon tests passed **49 tests in 11.377 seconds**. Command:

```sh
.runtime/local/verification-venv/bin/python \
  .runtime/monster-failure-triage-20261010/run_selected.py \
  test_combat_dynamic_durable_roster test_fresh_summon_obstacle_compatibility \
  test_combat_summon test_combat_melee test_combat_weapon
```

The private runner sets PostgreSQL read-only mode, disables integration-test opt-ins and replaces Redis caching. No services or active catalog were changed by these runs. Fixture corrections are part of the evidence boundary and require review; passing a modified fixture alone is insufficient to prove live gameplay.

## Catalog defect independently verified

The 144 copied-book failures repeat eight missing references across 18 breeds. The active document contains 813 entries; the complete installed-client export contains 821. A fresh export against the currently published owned-spell list reproduced every candidate row exactly, with no missing entries and unchanged constructor bounds. All previously published flags remain identical.

The active revision checked was `1d428d93dd4eeea23c81d10230b33e7bfd897671930efaf8d56ac1c0e82b19f6`. The installed client JAR SHA-256 was `e3eb8b9b6a1fa0d42d2f06f0af3e841ed783b2998f5c81d3cd8312294106d3cd`. Evidence is under `.runtime/monster-failure-triage-20261010/copy-flags-*`.

An in-memory overlay passed **7 original coverage/staging tests**, including the former 144 failing subcases. Neither the original assertions nor the active database catalog were changed. Publication remains pending; this is not a claim that the active catalog is fixed.

## Spatial fixture contradiction

Two collision tests replaced QI actor slots and positions but retained the old QL byte-set topology. The strict consistency check correctly rejected contradictory occupancy. Their explicit synthetic setup now captures a fresh registration topology using the native registry constructor. Existing behavior assertions remain intact. All **3 collision-resource tests passed in 14.636 seconds**. No production topology guard changed.

## Independent client evidence for disputed expectations

- Native decoders `cvY`/13497 and `cvX`/12613 confirm different headers. The former reads family at byte 12 and payload at 18; the latter reads a flag at byte 12, family at 13 and payload at 19. An offline Java probe against the actual client decoders passed both layouts. The original controller test still reads the immediate envelope with retained offsets; its proposed parser correction remains unapplied.
- Actual client bytecode confirms local/global event delivery, maximum-value transform `-2`, and null area-facing locators. These conflict with several historical expectations. See [event investigation](EVENT_FAILURE_TRIAGE.md); the original tests remain visible rather than being silently rewritten.
- The original Aniripsa Cunejo 5459 cases now pass after the minimal mask-zero selection fix. A transmitted explicit PV was incorrectly expanded into both fighters, causing duplicate damage before healing. Installed-client bytecode and the published direct-target policy independently confirm singleton selection. The corpse guard remains unchanged. The focused run reported 35 passing executions and two failures of the same contradictory historical resolver test imported twice; its expectation remains intact. See [Aniripsa investigation](ANIRIPSA_5459_TRIAGE.md).
- The healing-area rejection expectation also contradicts a previously verified native contract. Class 24 inherits `eXs`; a registered area without HP preserves lifecycle delivery with value zero and suppresses healing notification. Adding a fighter-only rejection would break existing Feca area behavior. See [partial-area healing review](../combat-inventory/native-healing-partial-area-review-20261008.md). No such production guard was added and the disputed assertion remains visible.

## Assertion audit and remaining limitations

An AST audit compared all original test methods in nine directly reviewed files against HEAD: **83 original methods had unchanged assertion calls**. New regression methods were recorded separately. The audit does not prove fixture correctness, and it does not cover every concurrently edited file. Its exact scope is `.runtime/monster-failure-triage-20261010/assertion-audit.json`.

The strict under-level-10 candidate's 111 spell cost tables were inspected across baseline and conditional rules: no resource keys beyond AP/MP/WP (2/3/4) occur. Generic NPC handling of additional resource payment and cost-event replay still needs a separate completeness audit before broader activation; this check does not claim those paths are complete.

The broad suite remains unresolved. Subsequent final scoped validation passed 179 class/shared-combat tests against both baseline and candidate with stable sources and no added failures. All 30 completely passing references were deployed after their native AI commit/rollback checks; a post-deployment probe also passed for all 30 inside the actual AI container. See [deployment evidence](DEPLOYMENT_20261010.md). This does not claim the broad suite is green: current failure classifications remain in [general triage](FAILURE_TRIAGE.md), [AI triage](AI_FAILURE_TRIAGE.md) and [local diagnostic results](LOCAL_UNIT_VALIDATION.md).
