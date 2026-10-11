# Remaining monster activation — 2026-10-10

Deployed and healthy: world and AI use catalog `548e1468d1c17a9542b34419c8a4f6c539696135fb4ffd4c03e8dae29c9f4edd`. The complete current server checkout was built and verified. Fishing and mining revision pins were preserved.

## Original 29 pending references

| Status | Count | Percentage of 29 |
| --- | ---: | ---: |
| Newly activated with complete owned books validated |17|58.62%|
| Explicit trainer/racing exceptions; not activated |7|24.14%|
| Still pending native encounter/lifecycle producers |5|17.24%|

The reviewed positive-level cohort now contains 57 activated references out of 69 (82.61%), 5 pending (7.25%), and 7 exceptions (10.14%). The all-level inventory retains all 2,874 references: 57 active (1.98%) and 2,817 not activated. The prior static 1669/2874 effect-family coverage (58.07%) is potential reuse, not an activation count.

## Newly enabled references

| Reference | Monster |
| --- | --- |
|1710|Rata de Astrub|
|2199|Rol duende gruñón|
|2203|Rol duende tímido|
|2204|Rol duende feliz|
|2227|Rol duende astuto|
|2601|Planta del Caos|
|2603|Shrederches|
|2617|Miaumiau blanco|
|2778|Espíritu de jalatín blanco|
|2819|Larva nutricia|
|3510|Planta guardiana del Caos|
|3907|Semilla|
|4012|Odalach, el Externo|
|5361|Luna|
|5698|Arakna menor hambrienta|
|5708|Cybwork patético|
|5710|Ordagova interdimensional|

Activation preserves native conditions. Espíritu de jalatín blanco 2778, Semilla 3907 and Luna 5361 have actions requiring actual encounter companions or buffs; ordinary solo spawning does not manufacture those prerequisites. Ordagova 5710 retains its native MP-cost requirement. Automated scenarios create genuine companions and commit real owned Xelor/Enutrof buffs. Higher-level companions are imported as data dependencies and are not enabled as wild monsters.

## Reusable changes and safety boundaries

- Append-only native imports cover cell groups, state resistance, recursive summon profiles/books and initial states. Existing class records and unchanged documents are checked against their published hashes.
- Constructor handling supports native minimum-resource effects, zero-duration instant states, retained child subscriptions and the original human-enemy range counter.
- Genuine registered summons pass transactional delivery validation and retain scoped action books on their own turns. Their authority requires an enabled ordinary NPC root, original caster chain, exact descriptor level and exact native book.
- Zero-range NPC recipient preflight is an explicit Wakemu server policy, not a recovered original server producer. It reuses shared native selectors, geometry, criteria and handlers while preserving costs, cooldowns, LOS, target identity and complete transaction validation. Player/class entrypoints remain unchanged. See [policy and limits](WAKEMU_NPC_AREA_PREFLIGHT.md).
- Trainer/racing actors are excluded by the common selection policy at every requested maximum level. See [seven explicit exceptions](ENCOUNTER_EXCEPTIONS_20261010.md).

## Verification

- 351 class/shared/activation tests and 38 additional SDK/movement/remote-effect tests passed: 389 total, zero failures, errors or skips. Existing behavior assertions were not relaxed.
- Full cohort: 158 native owned-spell/level cases; 153 pass across the 57 enabled references. Each of the five withheld references has one unresolved case. All 57 enabled references also pass real commit, immutable forecast, forced serializer-failure rollback and existing actor-identity preservation.
- Actual SDK proofs cover healing, enemy damage, global states and genuine spawned 735 own-turn damage. State 1579 has native base chance 75; the observational harness retains failed native draws and uses bounded independent fresh fights, without forcing RNG or retrying failed unit tests.
- Runtime, validator and test source hashes remained stable across final preview and commit/class validation.
- world: `sha256:01f4e3318f541327b2cb8920a07ea4eb276779cc4ba699ebac3db95081b69e20`; 775 files checked against the checkout, zero differences.
- ai: `sha256:175088b588d1f733e52faebe16d4711283ca4651b48db345efb182a602033c1f`; 875 files checked against the checkout, zero differences.

An initial deployment attempt was rejected because the images still pinned the previous catalog. Both images were rebuilt sequentially with the activated revision, verified again and recreated. The final deployment receipt confirms matching image IDs, matching catalog revisions, healthy services, world-to-AI communication and no startup tracebacks. Deployment tools must stage/finalize the package, update the revision defaults, then build world followed by AI before restarting. The CLI finalizer also requires its configured read-only database/catalog environment; a bare host invocation is insufficient.

Private evidence: `.runtime/monster-remaining-20261010/preview-final.json`,`validation-final.json`,`native-regression.json`,`sdk-recipient-policy.json`,`spawned-735.json`,`image-proof.json`,`deployment.json`, and `package-final/activation-receipt.json`.

## Remaining five and future levels

[Exact native prerequisites](REMAINING_NATIVE_ENCOUNTER_CONSTRAINTS_20261010.md): Jugador 3217 needs original cooking area objects 769/770/771; Infiltrado 3949 needs original glyph 1039; skeletons 3261/3263/3276 share the unresolved state 545→KO 1010→event 1026→restoration/state 546 lifecycle. They remain pending rather than receiving invented areas, states or events.

The same preparation pipeline accepts `--max-level 100` or another inclusive limit. It selects references whose entire native level range lies within that limit, recursively imports dependencies, excludes explicit exceptions, tests every owned spell at every selected level, and publishes only complete passing books. Static coverage is reused; execution evidence must be renewed for the actual candidate and code. Missing producers, uncertain summon level domains and unsupported dependencies remain inventory entries with explicit pending reasons.

## Manual acceptance

Follow [the complete manual acceptance workflow](MANUAL_REMAINING_COHORT_20261010.md). Current machine-readable state: [JSON](ACTIVATION_STATUS.json),[CSV](ACTIVATION_STATUS.csv). `PENDING_UNDER_10.csv` retains the original 29-reference cohort with its updated active/exception/pending statuses.
