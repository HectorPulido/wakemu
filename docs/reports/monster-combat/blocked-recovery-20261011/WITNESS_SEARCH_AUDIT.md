# Blocked monster witness search audit

The published filtered inventory contains 808 blocked references: 802 native-execution and six dependency-import entries. The historical `blocker-groups.json` covers only the 690 deferred references in the previous exact cohort and is not the whole inventory.

Cheap substring grouping of all 808 published blocker records finds overlapping groups:

| Recorded symptom | References |
|---|---:|
| Casting result twI | 436 |
| Casting result twV | 189 |
| Casting result twE | 141 |
| Insufficient ordinary spell resources | 42 |
| Native zero-level activation unsupported | 41 |
| Invalid maximum-resource actor/fight context | 27 |
| Native timing lacks active actor turn | 26 |
| Unverified cell-group manager | 25 |
| Missing original summon level mode | 25 |
| Placement delivery missing initial-state carriers | 17 |
| Invalid eZb fight/caster context | 17 |

These symptoms overlap; counts do not predict how many monsters a correction will unlock.

## Representative diagnosis

`run_case` historically spends at most two attempts per scenario. Its first targets are the enemy and caster. Consequently, later enemy placements and ordinary empty-cell witnesses are never examined once those attempts fail. The published evidence illustrates why an eligibility code alone is not a root cause:

- Reference 870, Dragopavo salvaje, spell 1602 at level 70: the enemy cast was legal but its three outcomes were false. The remaining self-target failed twI. This monster is not established fixed by increasing search coverage.
- Reference 872, Stropajo del desierto, spell 1582 at level 75: first enemy twV, then self twI. No later scene witness was attempted.
- Reference 1166, Maltrahzero, spell 6624 at level 97: first enemy twE, then self twI. Two other owned spells passed, but the blocked spell had no later scene witness.
- Reference 1620, Jamajam, spell 7351 at level 1: both attempts lacked resources. More target cells cannot repair that; inspect the actual selected costs, current resources and native preparation prerequisites.

Native `combat_casting_eligibility.py` defines twI as range rejection, twV as failed cell/object criteria or actor property restrictions, and twE as rejection by every native root selector. These are ordinary rule outcomes, not evidence that the rule implementation is incorrect.

## General recovery mechanism

`run_case(..., recovery_search=True)` enables a bounded, independent budget for each real enemy scene and target class (caster, other actor, empty cell). Default callers retain the previous budget semantics. Runtime casting guards, resources, selectors, collision, initial states and effect execution are unchanged. A successful native effectful transaction remains required.

The normal and recovery paths now retain actual exception diagnostics: native casting result, consumed native hook trace, conditional casting selection and resource validation code where present. At most 24 records are retained per case. Diagnostics describe failures; they do not authorize bypasses.

Quick verification:

```sh
PYTHONPATH=server:server/tests .runtime/local/verification-venv/bin/python -m unittest test_monster_validation_budget test_monster_validation_missing_geometry test_monster_recovery_witness_search
```

Result: 16 tests passed. Existing tests were not edited. Full native representative executions and bulk recovery counts are separate evidence and must not be inferred from these unit tests.

## Follow-up families

1. twV/twE: use the retained actual hook trace to choose a native ally, summon, wounded actor, breed or encounter prerequisite. Prepare native prerequisites through normal construction or committed owned spells, never arbitrary state assignment.
2. Resource failures: record selected AP/MP/WP costs and current/maxima, distinguish missing turn initialization, owned resource-generating setup and genuine encounter prerequisites. Do not inflate actor resources.
3. Initial-state context failures: inspect one representative per constructor/registration family; repair missing actual fight/actor authority shared by that family rather than special-casing references.
4. Zero-level and mission actors: retain explicit exceptions unless their native context is implemented.
5. Dependency imports: five entries need attested summon level domains; Bruja (2096) has a summoned profile without an owned spellbook. These require dependency authority, not target-search changes.

## Recovery prerequisites and physical placement

Recovery mode also recognizes only an entire positive `HasState(id, "caster")` criterion. It discovers constant native state applications on direct family-304 roots of zero-range **owned** spells, excluding the blocked spell itself. It proposes same-turn and next-turn ordinary preparation commits, capped at four recipes. It does not infer negated, compound or unknown criteria. Actual commit eligibility and effects remain authoritative.

For native actors with nonzero physical radii, an adjacent fixture enemy may overlap the caster's registered footprint. QI can then correctly resolve the caster at the requested enemy cell. Recovery mode discards overlapping fixture scenes and tries up to 16 alternative placements drawn from the existing arena cells, using both actual radii and the existing native footprint function. Requested target identities and runtime QI guards are preserved. Actual identity-mismatch diagnostics are retained.

The focused budget, geometry, reference-evaluation, recovery-search and state-recipe tests now pass 47 checks. Actual native execution outcomes remain separately recorded by the recovery coordinator.

## Cheap preliminary screening

Recovery accepts optional positive integer caps: API `recovery_attempt_cap` / `recovery_scene_cap`, CLI `--recovery-attempt-cap` / `--recovery-scene-cap`. Both require recovery mode; defaults remain unlimited by these additional caps. Recovery scenes alternate scenarios at each enemy placement, giving preparation recipes an early probe. Initialization failures count toward the scene cap, and a reached attempt cap prevents another fixture construction or cast. Receipts retain both configured caps and `scenes_attempted`.

A preliminary screen can use eight cast attempts and four fixture scenes per case. This is deliberately incomplete evidence: pending cases may need later targeted searches, and final full native matrices should omit these screening caps. The focused suite now passes 53 checks.
