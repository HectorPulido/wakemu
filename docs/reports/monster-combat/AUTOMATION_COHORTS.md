# Reusing automatic activation for later native level ranges

Use the existing all-level extraction and family-coverage report. No per-monster spell generation or language-model call is required. Coverage is only the first gate; native constructor, complete owned-book execution and transactional delivery must also pass.

## Disjoint selection

A cohort uses the monster's **complete native level range**, not its minimum alone. After reviewing maximum native levels below 10, the next cohort is `10 <= max_level < 50`, with a positive native minimum. A Tofu whose native range is 8–12 belongs to the new cohort. Definitions whose whole range is 1–9 are not previewed again. For a later pass below 100, select `50 <= max_level < 100`.

Start with `select_candidates(coverage, maximum=ceiling)` in `server/tools/prepare_monster_spell_activation.py`, intersect the requested maximum-level interval, and pass the resulting reference IDs explicitly with repeated `--only-ref`. That selector applies the persistent native encounter and user-ignore policy. Preserve the active NPC activation policy and all previously enabled rows exactly.

The low-level exclusions are explicit snapshots: 382 references without owned books, incomplete actor 3118 and seven trainer/racing actors. They do not authorize ignoring every higher-level actor without spells.

## Gates

1. Check dependency closures per native seed. Missing definitions, unattested summon-level domains or summoned profiles without books stay pending. Do not guess descriptors or silently discard one owned spell.
2. Prepare append-only NPC casting/effect/state/area/summon data using `prepare_monster_spell_activation.py`. It checks existing class records and unchanged published documents against their hashes.
3. Run `validate_monster_spell_activation.py` with `--skip-class-tests`: every owned spell at every native actor level must have effectful native execution. Its finite target search may withhold encounter-dependent actions whose required scenario is not represented.
4. Extend the matching preview receipt with `--class-tests-only --extend-results`: real AI commits, immutable forecasts, forced serialization-failure rollback and the complete class regression scope must pass. Run the additional SDK/movement/remote-effect suites sequentially.
5. `finalize_monster_spell_activation.py` retains only complete passing books. It also requires exact candidate, base, runtime and validation provenance. `stage_monster_spell_activation.py` can stage that package as an inactive release. Neither command activates the database pointer or restarts services.
6. Build the complete current world checkout first, then AI against that image, with the staged catalog revision pinned. Verify deployed-source hashes, activate using the expected-base fence, restart the single world/AI services and verify health, revision and startup logs. Keep unrelated fishing/mining catalog pins.

`automate_monster_activation.py` already orchestrates preparation, previews, commits/classes, finalization and inactive staging. The published range reports record the explicit reference set and final operational verification. Activation remains a separate guarded publication step.

## Validation cost and failures

Use one native validation process on the current 16 GB development host. Four concurrent cold native catalog loads caused memory pressure and a connection interruption, with no catalog activation. Independent completed cases can be resumed only when the validator's candidate/base/runtime/test/native-source fingerprints still match. After changing executable sources, start fresh. A source-fence rejection may guide selection of a narrower inactive candidate; it is never accepted as execution proof. Validate every owned spell/level of that new candidate again on stable current sources.

The validator avoids constructing scenarios after their cast budget is exhausted and avoids an unused empty-cell search for ordinary spells. Missing native casting roots in advisory scene geometry produce a pending case. Unexpected exceptions and source mutation still fail the run. These tool optimizations change neither class production code nor the effectful/full-book approval rules.

A pending result is not evidence that the original client data is corrupt or that the monster can never work. Record the exact importer, constructor, resource, criteria or encounter blocker for a later shared fix. Re-evaluate that dependency group after a fix; leave previously activated ranges out of new per-monster previews, while continuing to run shared class regressions for every publication.
