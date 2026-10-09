# Current combat inventory review — 2026-10-07

## Scope and evidence standard

This review covers the 18 playable classes, their active spells, passives, and shared combat mechanisms. It separates historical offline observations from current runtime evidence. A registered handler, successful initialization, emitted packet, or actor change does not establish that a complete spell behaves correctly in the client.

No base inventory regeneration was performed. Historical results below are not current-source certification. Subsequent offline engine checkpoints are recorded in [class-engine-integration-20261007.md](class-engine-integration-20261007.md); the latest complete active batch covers 383 definitions and 1,704 scenarios with 379 tracked hashes stable. It records 57 rejections, including 30 expected speculative self candidates outside the native selected range. No full class/client acceptance is claimed.

## Catalog and individual verification

The existing catalog lists **722 class spells: 383 active and 339 passive**, plus **91 extra spells**. The extra list does not establish exhaustive coverage of transformations or dynamic grants. `hechizos.csv` contains **702 spells without individual review**. Only spell **5028 (Sangre a Sangre)** and **5031 (Sangre Ardiente)** have `game_verified=True`; their evidence does not cover every level, branch, or condition.

`cast-evidence-index.json` combines the latest stored observation for each scenario across multiple historical checkpoints. Its 3,028 scenarios contain 513 rejections, 1,262 observations without an effect, 1,111 actor changes, 122 packet-only observations, and 20 retention changes. Every indexed row has `current_source_revalidated=False` and `client_verified=False`.

## All 18 classes

The following counts are historical observations from `cast-evidence-index.json`, joined to `hechizos.csv`. “Any change” counts distinct active spells with an actor or retention change in at least one scenario. “Any rejection” counts distinct active spells rejected in at least one scenario. These columns overlap and are **not completed-spell counts**.

| Class | Active spells | Any change | Any rejection | Complete individual verification recorded |
|---|---:|---:|---:|---:|
| Feca | 21 | 17 | 16 | 0 |
| Osamodas | 21 | 15 | 5 | 0 |
| Enutrof | 21 | 16 | 7 | 0 |
| Sram | 21 | 18 | 8 | 0 |
| Xelor | 21 | 16 | 9 | 0 |
| Ecaflip | 21 | 17 | 10 | 0 |
| Eniripsa | 21 | 16 | 3 | 0 |
| Iop | 21 | 19 | 4 | 0 |
| Cra | 21 | 19 | 6 | 0 |
| Sadida | 21 | 16 | 10 | 0 |
| Sacrier | 21 | 19 | 3 | 2 |
| Pandawa | 21 | 15 | 5 | 0 |
| Rogue | 21 | 15 | 13 | 0 |
| Masqueraider | 21 | 15 | 7 | 0 |
| Ouginak | 21 | 16 | 7 | 0 |
| Foggernaut | 21 | 15 | 8 | 0 |
| Eliotrope | 21 | 13 | 16 | 0 |
| Huppermage | 26 | 18 | 13 | 0 |

No complete class has sufficient evidence to be declared functional.

The subsequent [complete passive lifecycle checkpoint](passive-foundations-activation-review-20261007.md) observes 336 cycles and three blockers across all 339 passives, with stable tracked sources. It observes 337 installations and 28 activations; these remain separate from full semantic or client acceptance. The [Ready checkpoint](ready-basics-boolean-border-review-20261007.md) passes all 54 class/level cases without selected passives. These later checkpoints do not rewrite the historical per-class table above.

## Source freshness

SHA256 comparisons against the current checkout were performed for the stored source manifests. Missing files were counted separately. For manifests containing bare module filenames, paths were resolved under `server/wakfu_server/combat/`.

| Historical report | Recorded outcome | Tracked sources | Different hashes now | Missing now |
|---|---|---:|---:|---:|
| `active-native-start-recheck.json` (2026-10-04) | 1,514 scenarios; 464 rejected | 140 | 88 | 1 |
| `passive-activation-all-current.json` (2026-10-04) | 339 installed; 272 observed cycles; 67 blocked; 19 activations observed | 346 | 126 | 3 |
| `ready-current-recheck.json` (2026-10-04) | 464 initialization cases passed | 297 | 128 | 3 |

A report being source-stable during its original execution does not mean its sources match this checkout. The changed-source counts include implementation and protocol changes; they are a freshness check, not proof that every historical result regressed.

`ruta-de-cierre.md`, dated 2026-10-05, records a later matrix of 739/785 complete cycles, 42 cycle failures, and four Ready rejections. That matrix remains distinct from full spell verification and requires current-source confirmation.

## Runtime observations and boot provenance

Today's world logs contain **70 accepted casts and 31 rejected casts**, covering only ten actor/spell combinations and concentrated mainly on Cra spell 4813. These casts belong to earlier boots. Acceptance alone does not establish that effects, costs, or client delivery are correct.

- Cra spell **4807** rejected twice with `Summoned-actor lifecycle propagation remains unaudited`, last at 19:17:42 UTC in earlier boot `2b04a9ea7d084cef8fad805ea08998a7`. That guard existed when these logs were reviewed; subsequent shared registered-summon authority repairs remove that blanket rejection in local code. The historical log is not evidence of current runtime deployment or remaining code behavior.
- Twenty end-turn requests rejected with `Not current owned turn`; two casts reported `Previous turn is not synchronized` and two ACKs were stale/invalid. Several snapshots show `awaiting_ack`. These earlier-boot observations require correlated client evidence before assigning the cause.
- Earlier boots also recorded two percentage/bound snapshot-mutation errors, four missing-LOS-evidence errors and three missing-authoritative-direction errors. Intervening changes may have resolved some cases.

Current boot `22265da608c34b6aa3deaa5fb18956d6` started at 21:22:24 UTC and had no cast attempts when inspected. It recorded a spectator snapshot rejection at 21:28:59 UTC: `Native terminal event requires a resolved fight`. Historical cast failures must not be described as reproduced on this boot.

Availability changed during the review: initially healthy, world later became **unhealthy**, with nine consecutive failed checks at 21:32 UTC. Both host and container requests to `/health` timed out. A subsequent Docker measurement showed113% CPU and4.411GiB memory. Health recovered at 21:33 UTC without a restart, on the same boot.

The current boot also confirms long blocked requests: actor20/fight36 Ready started at 21:30:39.613 UTC and ended144.914 seconds later, rejecting `Turn ACK requires at least one live participant`. Actor19's withdrawal/return request took142.037 seconds and rejected an invalid session/character. The last recorded progress before the Ready gap was checkpoint `save_committed` at 21:30:40.397 UTC. Connections then closed and fight36 was retired. These observations establish an availability incident; its cause is not established. Shared fight locks, session validation while arming ACK, and socket write-lock waits are investigation points, not proven causes.

The user subsequently restricted this agent to unit/offline tests, code inspection, and documentation because another agent is operating world. No service restart, deployment, or runtime mutation was performed by this review. Any future restart requires the user's timing approval.

These runtime observations were supplied by the integration agent; this document's author did not independently re-read their underlying log extract.

## Pending work by shared mechanism

| Mechanism | Evidence and remaining verification |
|---|---|
| Turn, ACK, and action delivery | Earlier-boot `awaiting_ack`/owned-turn rejection plus historical cycle failures. Verify Ready, manual/automatic turn changes, acknowledgment, surrender, victory, return, and another fight using the production route. |
| Summoned actors and control | Spell4807 rejection on an earlier boot; its historical blanket guard was subsequently replaced locally by explicit registered-summon authority. Verify actor creation, ownership, shared lifecycle propagation, controller spells, turns, death/removal, and repeated use. Historical missing-own-summon errors are not proof of the current implementation state. |
| Zones and retained effects | Historical common failures reference missing central ownership machinery and area queries. Verify creation, ownership, footprints, entry/exit, duration, and removal on current sources. |
| Passive activation and event ordering | Historical installation succeeds for 339 passives, but only 19 activations were observed in the stored general audit. Test each passive with its actual triggering event and expected effect; initialization alone is insufficient. |
| Carrying and displacement | Historical authoritative-carry-status failures. Verify occupied cells, collision, height, carried actors, exchange, and restored ownership/client positions. |
| Values, damage, healing, and resources | Historical resistance-cap, transfer, light damage, and special-family failures may already be corrected. Revalidate values, equipment effects, costs, normal/critical branches, armor, resource limits, and rollback. |
| Class modes and transformations | Verify granted spells, resources, combos, appearance application/restoration, and relevant conditional branches. Osamodas appearance was historically reported unchanged despite mode activation. |
| Harness and semantic assertions | Generic state changes and no-effect observations are inadequate verdicts. Build legal scenarios and assert concrete expected effects and delivered packets. Record unconstructed scenarios explicitly. |

Historical frequent rejection reasons include families303/865/48/1083/305, owned-summon targets, zone predicates, retained ownership, and carry status. They should be reproduced before implementation work is assigned because intervening code changes may have resolved them.

## Documentation inconsistencies

- README describes critical selection as pending in one section and deployed in a later section.
- README describes a fixed roster and pending summons, then later references implemented summon-roster tests.
- Class pages and family-priority tables reflect older generated checkpoints. They cannot independently establish current missing handlers.
- `clases/2.md` still marks Desplume as lacking individual review while `ruta-de-cierre.md` records user confirmation in a specific scenario.
- Several system entries have a generic pending status and no reproducible next scenario.

Keep existing evidence and manual review notes. Update summaries around a coordinated checkpoint; do not reinterpret historical installation or cycle counts as class completion.

## Current automated validation and integration

An isolated Python environment was created under `/tmp/wakemu-combat-review-venv` with `server/requirements.txt`. The initial system-Python attempt lacked `psycopg`; those import errors are environment failures and are not counted as game regressions.

Current-source offline command:

```sh
WAKFU_NATIVE_AREA_CALLBACKS=1 PYTHONPATH=server /tmp/wakemu-combat-review-venv/bin/python3 server/tools/audit_ready_start.py --basics-only --turn-cycle --output docs/reports/combat-inventory/ready-basics-review-20261007.json
```

Result: **51/54 Ready-and-two-turn cases passed; three lifecycle failures**. All three are Enutrof/breed3 at levels1,20,200, with no selected passive. Native effect384594/family 349 fails with `Unsupported native predicate: IsOnBorderCell` during the turn lifecycle. Source/tool hashes remained stable; failed-stage fight and RNG rollback were preserved. The deployment gate is false. Evidence: [ready-basics-review-20261007.json](ready-basics-review-20261007.json).

This uses the common production functions with an offline, unequipped fixture and real exported terrain. It does not connect to world, accounts, databases, sockets, or the graphical client, nor does it validate all active/passive spells.

The unit baseline command is `PYTHONPATH=server /tmp/wakemu-combat-review-venv/bin/python3 -m unittest discover -s server/tests -p 'test_combat*.py'`. It completed 1,468 tests in 191.124 seconds, with **11 failures,13 errors,94 skips**. [Full grouped baseline](unit-baseline-review-20261007.md) records the individual failing names. PostgreSQL integration cases skip without an isolated test database; source stability was not captured for that run, so concurrent edits remain a limitation. Fixture defects and obsolete assertions must be separated from game defects before changing behavior.

## User-reported failures and bulk verification scope

The user reports that Cra client/server spell ranges disagree, and all tested summons are broken, including Osamodas summons and Cra beacons. These reports remain open independently of generic damage-handler coverage. The user will perform the final manual acceptance test after the offline work; individual probes are not the delivery workflow for this review.

The requested inventory must include every catalogued class spell, passive, extra/granted spell and their reachable effects/states, rather than a handler checklist. Bulk client-data extraction can populate definitions; it cannot implement their lifecycle. Per-case verification must separately check range and modifiers, costs and use limits, targets and geometry, concrete effects and values, triggers, creation/control/removal of actors and zones, and client delivery. Missing legal scenarios and absent semantic expectations stay pending.

## Fresh normal-cast matrix across all 18 classes

The normal-branch audit completed all 383 active definitions in 1,714 scenarios, with source hashes stable. Results:1,345 actor changes,161 rejections,136 no-effect observations,14 retention changes and58 packet-only observations. These are execution observations, not semantic or client passes. Critical branches, prerequisite-complete scenarios, equipped builds and every passive event remain outside this matrix.

| Class | Scenarios | Actor changes | Rejections | No effect | Retention | Packets only |
|---|---:|---:|---:|---:|---:|---:|
| Feca | 118 | 72 | 34 | 6 | 4 | 2 |
| Osamodas | 118 | 86 | 30 | 0 | 0 | 2 |
| Enutrof | 88 | 82 | 4 | 2 | 0 | 0 |
| Sram | 80 | 76 | 4 | 0 | 0 | 0 |
| Xelor | 96 | 77 | 17 | 2 | 0 | 0 |
| Ecaflip | 92 | 74 | 6 | 12 | 0 | 0 |
| Eniripsa | 96 | 82 | 6 | 0 | 0 | 8 |
| Iop | 80 | 74 | 0 | 2 | 4 | 0 |
| Cra | 82 | 78 | 2 | 2 | 0 | 0 |
| Sadida | 88 | 62 | 0 | 14 | 0 | 12 |
| Sacrier | 94 | 86 | 2 | 4 | 0 | 2 |
| Pandawa | 98 | 88 | 4 | 2 | 0 | 4 |
| Rogue | 88 | 40 | 6 | 30 | 0 | 12 |
| Masqueraider | 94 | 72 | 2 | 18 | 0 | 2 |
| Ouginak | 96 | 80 | 6 | 10 | 0 | 0 |
| Foggernaut | 96 | 78 | 2 | 4 | 4 | 8 |
| Eliotrope | 92 | 45 | 17 | 28 | 0 | 2 |
| Huppermage | 118 | 93 | 19 | 0 | 2 | 4 |

Evidence: [active-normal-review-20261007.json](active-normal-review-20261007.json). Largest observed rejection groups are missing delivery-owner routing (60 cases/23 spells/9classes), native-range rejection (30 cases/15 spells), and missing authoritative carry status (18 cases/3 spells). Range rejections can include inappropriate fixture targets; they are not all certified bugs. The separate native casting contract audit confirms conditional-range differences for 153active spells, conditional LOS differences for 22 and linear differences for 28.

## General mechanisms before individual verification

1. Complete and unify native data contracts. Bulk extraction now covers4,143 native spell trees,6,129 states,1,436 areas and81,965 distinct effects in isolated staging. Range-modification flags are separately recovered for 4,143casting definitions and800conditional rules. Validate runtime consumers and release the catalog set together before integrating it.
2. Correct the common casting-table selector and live range calculation for ordinary and granted spells. Validate every dependent definition automatically, including bonuses, conditional LOS/linear rules, zero-range spells, negative bonuses and native caps.
3. Resolve shared effect ownership/retention/delivery and event ordering. Native family presence is not evidence that a runner has complete authority or a correctly delivered result.
4. Complete actor and zone lifecycles: creation, ownership, control, triggers, turns, removal and synchronization. Summons and beacons are manifestations of these common contracts; avoid per-class patches.
5. Validate all generated spell/event cases against concrete expected behavior. Missing prerequisites and absent expectations remain pending. The user performs one complete manual acceptance route after the automated work and authorized runtime integration.

The fresh isolated structural inventory contains 722class spells and91extras. Manual review now records3historically verified spells (Desplume plus the two Sacrier spells), whereas the earlier saved CSV recorded2; neither is a current complete-class certification. Generated family registration uses static inspection and can miss specialized dispatcher/group routes: absence from that table is not proof that a handler is absent.

Artifacts: [bulk import review](bulk-import-review-20261007.md), [casting contract groups](casting-contract-review-20261007.md), [native range evidence](range-review-20261007.md), [complete per-spell verification ledger](verification-ledger-20261007.csv). The ledger covers813known spells,18-classes and355spells with fresh offline execution observations; it accredits no complete semantic/client spell checks from generic traces. Dynamic reference exhaustiveness remains unknown.

## Fresh passive event/cycle matrix

All **339 passives** were reviewed through native Ready, registered NPC damage, turn/ACK/expiry and ordinary own-cast scenarios. Sources remained stable and all traces were complete. **337 installed; 319 completed the observed cycle; 20 blocked; 27 had an observed activation.** Installation, cycle completion and activation are separate observations, not completed passive behavior.

The 20 blocked cases reduce to three shared causes:

| Shared cause | Passive cases | Classes | Installation |
|---|---:|---|---|
| Unsupported `IsOnBorderCell` | 17 | Enutrof | Installed; lifecycle blocked |
| No executor for family 1038 | 2 | Masqueraider | Not installed |
| Unsupported `HasState` actor selector | 1 | Sadida | Installed; lifecycle blocked |

A passive without an observed activation remains pending for its actual prerequisites and event producer; a generic damage/turn scenario cannot activate every passive. This matrix does not cover every deck combination or event.

Evidence: [passive-review-20261007.json](passive-review-20261007.json). Reproduce offline with:

```sh
WAKFU_NATIVE_AREA_CALLBACKS=1 WAKFU_NATIVE_GRANTED_CAST=1 PYTHONPATH=server /tmp/wakemu-combat-review-venv/bin/python3 server/tools/audit_passive_activation.py --output docs/reports/combat-inventory/passive-review-20261007.json
```

The unit qualification was also rechecked with the same consumer flags: 23 targeted tests produced one failure and one error, with stable sources. Granted-spell dispatch passes when its native consumer is enabled; summon lifecycle propagation still rejects and the berserker assertion still fails. The original baseline remains preserved rather than rewritten as a success. The new ledger, casting-contract and strict range-flag merge tools passed 23 pure tests, including the passive-ledger extension.

## Shared mechanism publication checkpoint

The [per-spell dependency inventory](class-dependency-coverage-20261007.md) now follows class innates and the published class-summon ability books, preserving the denominator of 722 class spells plus 91 extras. Class summons expose 43 unique abilities, including 38 newly imported trees and 297 imported effects, with a 623-effect transitive closure. This publication closes a definition gap; it does not establish effect execution or class semantics.

The [mechanism evidence ledger](class-mechanism-evidence-20261007.md) records exported/published data, implemented consumers, unit evidence, offline domain audits and manual client acceptance separately. New terrain, physical Sn and actor physics producers, controlled summon casting, synthetic collision resource execution and native Trove event collections are tracked with their actual integration gaps. A focused batch passed 51 summon/surface tests with unchanged tracked bytes. The reported map1134 comparison covers 37,157 selected XYZ cells, including 502 nonzero native surface indices, with zero errors; its final report remains pending and this review does not accredit it as published evidence yet.

The README's handler-priority table and `prioridades.csv` are explicitly historical. Entries such as family305 cannot be treated as current missing handlers after later shared implementation. Family1099 is structurally shared through native innates; that does not establish 813 broken spells. Its native runner and guarded reachability are under investigation.

Current work proceeds from complete native facts and shared producers to generic consumers, event/state/area lifecycle, summon ownership and delivery, then class-specific semantic contracts. Names of 122 criterion functions and 180 reachable families are dependency indices; they are not complete specifications of conditional domains, state transitions, events, class mechanics or graphical behavior. No global functional percentage is inferred.

## Final typed class component and gap index

The [combined class mechanic gap index](class-mechanic-gap-index-20261007.md) now joins the corrected native typed graph, all 764 state lifecycle rows,116 textual condition contracts and130 parsed structures,90 area prototypes,108 selector contracts and18-class component matrices. The native graph preserves complete criteria, target masks, subscription/timing metadata, native parameter samples and typed reverse edges. It separates direct spell dependencies from common innates and leaves guarded execution unknown.

The final graph contains 851 seeded spell definitions, including 38 new class-summon trees, 764 states (761 present and 3 natively absent),90 areas and21,207 effects. All raw state/area record identities are checked, and all 243 tracked native sources remained stable. The persisted/native comparator finds all21,207 effects definition-equal after the actual native point-area join, with 466 duplicate metadata differences classified and 554 HMI allocated-ID differences isolated. No redundant 461-row geometry rewrite was performed because the existing metadata join already supplies those native offsets.

The refreshed family metric remains 145/177 registered routes (81.9%), excluding 307/324/325 and creature-book expansion. It is not functional class completion. State statuses are 79 partial, 682 pending verification and 3 absent; condition statuses are 89 partial and 27 absent. Concrete native component gaps include ENUTROF_DEPOSIT/WALL creation contracts, selector bits 44/46, actual Symbiot/captured-ability authority, event/retention/timer/decurse domains and conditional transformation/reference semantics. No full class mechanic or client acceptance is declared.


Casting denominator checkpoint (2026-10-07): [complete casting-table inventory](class-casting-gap-inventory-20261007.md) records851 scoped spells,968 raw expressions,672 conditional rows,62 function names (5 casting-only), and2152 root selector/geometry definitions. Effect-only116 predicate names are a separate denominator. [Current combined gap index](class-mechanic-gap-index-20261007.md) supersedes historical selector44/46 gap rows;108 masks are now recognized. Overall functional/client completion remains unknown.
