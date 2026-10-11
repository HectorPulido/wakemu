# Pandawa and Ecaflip parallel implementation — 2026-10-10

User-provisional acceptance is **10/18**: Cra, Iop, Sacrier, Eniripsa, Osamodas, Ouginak, Zobal, Huppermage, Sram and Feca. The user defers manual acceptance until the final class batch. This workstream does not automatically accept Pandawa or Ecaflip.

## Working boundaries

Native authority is immutable PostgreSQL release `c97c921c35f4b1f808f0bc84970cba2aa09652763394440429a85e9f7f0fee46`. Implementation agents own separate class inventories and semantic scenarios; shared production changes require coordination. Independent Luna low validation runs serial catalog-heavy gates to avoid accidental shared-fixture contention. No service changes are part of the initial audit.

## Inventory

| Class | Owned actives | Owned passives | Additional actions | Main semantic risks |
| --- | ---: | ---: | ---: | --- |
| Pandawa | 21 | 17 | 5 | Carry/throw, barrel ownership and constructor states, drunkenness transitions, milk-cloud area, carried deaths and rollback |
| Ecaflip | 21 | 20 | 16 | Deterministic random branches, tarot actions and replacement, streak resources, fleas, summons, expiry and rollback |

Current class inventories replace historical dependency estimates; catalog presence is not gameplay proof. Exact roots and missing evidence are in the class reports as they are generated.

## Initial independent verification

- Shared runtime baseline: 48/48 tests passed against the pinned current catalog.
- Pandawa initial actual Ready/barrel, enemy carry/throw and drunkenness scenarios: 3/3 passed.
- Pandawa normal matrix: 36/36 legal Ready decks, stable sources/tools. Of 558 normal attempts, 450 prepared transactions (342 normal owned casts and 108 granted-action casts), and 108 lacked an eligible context. These cover 19 normal actives across 18 baseline/passive variants; the other two actives require a barrel. These are observations, not counts of unique spells or conditional branch coverage.
- Special contexts and passive-specific effects remain under active validation. A legal barrel spawn is not assumed to be a legal carry target; actual casting predicates must accept both steps.

## Completion criteria

For each class, reconcile every current owned active/passive, grants, initial states, summoned books and areas; exercise actual meaningful consequences and legal prerequisites; distinguish absent coverage from missing implementation. Protect previous classes with regression gates, preserve original gameplay assertions, and document any source-backed fixture correction. Produce one complete manual battery per class with exact commands and expected results. Visual rendering, real sockets and all multiplayer combinations remain manual evidence even after local gates pass.

## Prior-class regression verification

The first extended prior-class gate exposed Zobal actual Danza Macabra 7086 accepting a cast without reviving its ally. Fresh rebound child selection now preserves native criteria under the changed caster, while explicit Cunejo singleton and replay selection remain unchanged. Actual Zobal resurrection and Cunejo integration gates pass after the correction.

The subsequent serial class/healing/variant batch passed 44/47 initially; the three failures were confined to a new healing fixture that killed its only opponent and therefore legitimately settled the fight. Keeping a third living opponent through the actual Ready path corrected that fixture; its four tests now pass. Actual Ecaflip fleas, healing-handler tests, Cra beacon death, Sacrier Pact, Iop, Eniripsa and Zobal checks in that batch passed. This is scoped regression evidence, not exhaustive passive or client acceptance.

## Cra beacon death incident

The user reported a defeated beacon remaining visible at zero HP while actors could traverse its cell. AI commits retired authoritative geometry but omitted death presentation packets. The common AI commit boundary now stages newly registered deaths on the private candidate before adoption. It covers casts, movement reactions and end-turn reactions without beacon-specific production exceptions. Failed serialization leaves the live runtime unchanged; actors revived before the outer action settles do not receive stale death delivery.

The focused AI/death gate passed 12/12, including an actual NPC attack killing an actual Cra beacon, exact death recipient identity, QI retirement, duplicate suppression and delivery-failure rollback. The final broader AI bundle passed38/38 after source-qualified fixture corrections: summon serialization requires its owned encounter map, and a strict BACK route test requires a real damage advantage over the cheaper SIDE route. No AI production behavior was weakened to satisfy these assertions.

## Continued class verification

Pandawa Milky Instinct exposed a missing server turn-boundary fact: native-null event delivery could not qualify the actual starting actor for its countdown. A separate validated owned-turn context now supplies only that identity comparison, preserving the native-null triggering runner. The frozen production extension passed43/43 tests covering context validation, turn phases, actual countdown/death, barrel behavior, back-hit armor removal, Cra, Iop and Feca regressions. This extension is newer than the deployment recorded below and is not yet claimed deployed.

Ecaflip flea regeneration/spread and area1798 ownership/expiry passed2/2, including enemy exclusion and absence of dangling area-manager records. Class-specific remaining passive gates are tracked in the class inventories; no additional provisional acceptance is inferred automatically.

Deployment used a complete current-checkout world build (`sha256:cf1b4e5452d2365319ca5769593eaded8d61f62f12b0228f416690acf0d06ab1`) followed by an AI build from that image (`sha256:227e18d56010a320ef5a6163636f7faa6be0dfe57abbe954ef1671e13da03ac1`). All 634 world Python files matched the checkout. Both existing services were recreated; no additional world server was created. Both report healthy and the world HTTP health endpoint returns `ok: true`, `storage: postgresql`.

Deployed AI oracle hash: `7bec21edf7d9f7ecd0e230a850f5afce7e2696fbe76bc68776fc1978c69d46b0`; its copied combat death module hash: `195cf3419c56d37e7c037a75ff862e509172613bf00e2d55e89bc03ac75bc7fb`. The active catalog release remains unchanged. Client visual acceptance remains pending: in a fresh Cra fight, let a monster kill a beacon, verify that the beacon disappears, its cell is traversable, and subsequent turns continue normally.

## Final shared replay validation and remaining card context

Actual Ecaflip 2080 exposed nested native activation history and callback self-removal gaps. The common runtime now shares active native Qj triples across nested replay instances, resets immediate child ancestry for a fresh activation while retaining a depth limit, and permits a notifying stat effect to be removed by its callback without recreating it. The affected replay/stat/retention suite passed 66/66, the additional self-removal regression passed, and actual 2080 passed. After these changes, the prior-class gate passed 43/43 and the AI gate passed 38/38.

Further actual-passive tests qualified Ecaflip 5249 and 7954. The latter rewards each eligible healing recipient; this fixture has three actual recipients, producing three increments of five. Passive 7955 exposed a distinct cast-boundary anchor gap: validated distance reached the reaction, but the cell remained the listener's installation cell. A typed target-cell context extension is under focused verification; a successful self-swap is not accepted as proof of the intended transport.

A complete world and AI build was prepared, but the source equality check detected concurrent movement implementation changes after that build. This build is not claimed deployed. Preserve and validate those changes, then rebuild the complete shared checkout before any restart.

The final target-anchor gate passed63/63 (cast-boundary, replay and prior-class scenarios); actual native-oracle integration passed17/17 afterward. The concurrent sequential-movement module qualified6/6 cases after source-backed test-fixture corrections: ordinary NPC creation authority and maximum-MP snapshots must agree, and a lawful empty replanning result means no additional movement rather than a required first plan entry. Production movement code was preserved.

A complete rebuilt world image `sha256:af994a64bc39fe82ada08968143efc14f9b4b3114b42bd3bd5c3a7148a0ee588` matched all642 current server Python sources. AI image `sha256:c0dea31cb5d35f9713cc20d3c9fe71e2d0d45f91cc20a04acb6551054b898492` contains the same world sources. Both existing services were recreated; AI is healthy and world startup/health is being checked. This entry supersedes the earlier prepared-but-not-deployed build; the earlier deployed beacon hashes remain historical evidence only.

Deployment verification complete: both existing containers report healthy; `GET http://127.0.0.1:18081/health` returns `ok:true, storage:postgresql`. The deployed image IDs are the642-file world and matching AI IDs recorded above. No extra world container was created.

Ecaflip bounded source limits remain visible rather than being relabeled as failures or successes: passive7958's actual Batalla route executes its gain but the tested duration-limited sequence reaches only23/43 FEROCITY, below the >100 prerequisite for7999; its positive branch is unqualified. The7959 read-only scan covered1,227,366 indexed published records (31 identity/reference matches), with no attested consumer of marker359898; unindexed documents are outside that scan. These limits and deferred visual/multiplayer manual acceptance are retained in the class battery. User acceptance count remains10/18 until explicitly accepted.

## Final technical gate

Pandawa and Ecaflip passed the frozen182-test/51-module gate with zero failures, errors or skips. Both are technically prepared for manual acceptance; user acceptance remains10/18 until explicitly updated. [Final evidence and complete manual procedure](pandawa-ecaflip-final-acceptance-20261010.md) distinguish local qualification from the pending coordinated class/monster deployment.
