# Native monster summon dependencies

The monster inventory's original closure traversed groups, states and granted spells, but did not follow family307 into the summoned profile's own ability book and constructor states. Consequently an implemented summon handler could still fail with `Missing scoped native class summon ability profile`.

`server/tools/export_monster_summon_dependencies.py` follows that dependency recursively for arbitrary spell and initial-state seeds. It includes nested summons, profile constructor states, family304/321 state references, family315 areas, family649 granted spells, group children, and separately sampled level-zero references. Cycles are visited once. Missing native definitions are explicit failures.

The helper reuses `ExportOwnedCapturedProfiles.java`. That existing class exporter checks every summon edge against the installed native307 definition, converts the actual native profile, and verifies fresh native `bPD` action records at levels0,1,20,200,245. It exports the original override and maximum level, complete initial-state triples, and native fight properties. No class profile is changed or replaced. Existing document metadata and provenance remain intact; new NPC exports append separate provenance.

The helper returns two optional changed shared documents, `native-class-summon-abilities.json` and `native-class-summon-initial-states.json`, together with typed spell/state/area/effect/profile closure IDs. Those dependency IDs must also be imported through the existing spell/state/area exporters before candidate combat validation. Exporting metadata does not certify a monster's combat behavior or enable its AI.

A read-only export for monster2603's spell3799 discovered profile2612, its spell4595 and constructor state3114, with26 effect dependencies. The existing native exporter passed all5 ability-book checks. Receipts are retained under `.runtime/monster-remaining-20261010/summon-probe-2603/`; a separate zero-level-complete rerun is under `summon-probe-2603-zero/`.

Seven new unit tests verify recursive cycles, explicit missing-profile reporting, original evaluated reference curves, preservation of class fields, rejection of existing-profile conflicts, rejection of unsealed additions, and rejection of removed class profiles. Existing test assertions were not modified.

## AI delivery boundary

A second shared blocker appeared after metadata import: `NativeProvider.preview` rejected every changed actor roster, including legitimate native summon creations. The existing class spell commit already supports new actors through its current-fight serializer and atomic adoption boundary.

The NPC bridge now admits added actors only after the shared `registered_summon_stats` serializer validates their native registration, controller, descriptor and wire identity. Each added actor must also have its actual creation delivery in the transaction's packet list, with a matching native combat/action header, supported creation family and exact payload length. Removing an existing actor remains rejected. No ordinary class casting or commit path was changed.

Six new focused tests exercise forecast immutability, existing actor identity preservation, adoption of the actual new actor, complete rollback when new-actor serialization fails, missing registrations, missing/foreign/malformed creation delivery, and existing-actor removal. These contract tests use the real native creation codec and registered-summon serializer; the complete monster candidate validation separately exercises genuine owned summon spells.

## Subsequent summon turns

The production world bridge uses `wakfu_ai.native.native_oracle.NativeOracle`. That oracle already accepts positive-ID actors in `native_summon_registrations`, resolves their descriptor/map through `registered_source`, and casts their native owned spells through the common effect runtime. `NativeStats` and `SessionAdapter` already select `registered_summon_stats` for those actors. The existing native-oracle test `test_registered_creature_ownership_wire_and_supported_lifecycle_are_explicit` constructs a real registered summon5528 and executes its own spell on its turn. Controlled class summons keep their separate existing controller-chain authorization through `resolve_controlled_action`; no player ownership needs to be fabricated for NPC summons.

The smaller legacy `NativeProvider` NPC ownership function still requires an ordinary monster descriptor. Its forecast/commit support for the summoning parent's action does not certify the spawned actor's later turn. Subsequent-turn acceptance must use the production native oracle.

Monster2601 summons profile2624 and monster2603 summons2612. Both dependent profiles already have enabled NPC activation policies. Monster2819 instead summons735 at native minimum level8; its owned spell1948 was imported as a dependency, but profile735 has no enabled policy and its roots are absent from the preserved baseline. Therefore its autonomous later cast remains blocked by the deliberate activation gate until profile735's actual level8 cast/commit/rollback is validated and its dependency scope is enabled. Validating the parent's creation alone is insufficient.

## Scoped dependency activation proof

The reusable preparation report now includes per-seed spell profile dependencies and descriptor-level domains. Native mode−3 uses the exact original profile minimum; mode−2 is exact only for a directly rooted summon and an explicitly supplied parent actor-level domain. Mode−1 and unresolved nested caster-level contexts are marked `level_domain_exact=false`, so preparation must withhold their dependency scope rather than treating a broad evaluation domain as certification.

`wakfu_ai.native.native_summon_dependencies.registered_dependency_enabled` authorizes an imported dependency only through a genuine registered caster chain ending at an enabled ordinary NPC. Every chain node must match its original registered descriptor and fresh native action book. The enabled parent owns a separate `registered_summon_profiles` scope with explicit levels and complete spell references. This does not enable the same profile as an ordinary wild monster. Player/class roots, unrelated profiles, missing casters, cycles, changed registrations, unowned spells and levels outside the scope fail closed. Ordinary class activation behavior remains unchanged.

The genuine2819 proof commits owned spell4625 at parent level5, producing two registered profile735 actors at level8. After advancing the real fighter lifecycle to one spawned actor, the production `NativeOracle` reports owned spell1948 at level8. Its forecast leaves the source unchanged, injected delivery serialization failure rolls back completely, and the real12-packet commit reduces the player's HP from60 to49. The parent creation used10 packets. Receipt: `.runtime/monster-remaining-20261010/spawned-735.json`. This used a private candidate policy overlay and made no database activation.

Eight new SDK authority tests and ten exporter tests pass. The exporter tests additionally verify exact minimum-level mode, explicit parent-level mode and withholding uncertain container-level domains.
