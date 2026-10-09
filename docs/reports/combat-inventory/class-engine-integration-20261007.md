# Class engine integration, 2026-10-07

Scope: class spells and their shared mechanisms. Monster spell implementation and AI changes are deferred. All changes below are local source/catalog changes; no world restart, deployment, live database write or Docker operation was performed.

## Casting contract

Normal and granted player casts now resolve the same complete native conditional casting definition. Baseline and conditional exports retain `range_modifiable`; category modifiers, live RANGE, carried status and native fight property 2 feed one shared range calculation. Missing authoritative snapshots remain explicit errors.

The offline native oracle compared 7,200 combinations, including integer overflow and conditional contracts, with zero discrepancies. This proves the tested range calculation; it does not certify client presentation or every complete spell interaction. See [native range evidence](native-range-contract-20261007.md).

Native effect 1066 (`eZg`) now updates category range modifiers through the general modifier handler. Stacking, reversal and expiration have regression checks. Its sign differs from the AP modifier 1065, as established from native methods.

## Bulk delivery metadata

The owner exporter now proves literal returns, transparent superclass delegation and immutable registry configuration. The local protocol catalog preserves all 287 previous known pairs and adds 16 proven pairs. Fifteen entries remain explicitly unresolved. Native prototype and clone verification covers all 303 proven pairs. See [ownership evidence](native-delivery-owner-review-20261007.md).

The original active audit had 60 ownership rejections affecting 23 spells across nine classes, all from family 315. The [fresh focused audit](owner-integration-smoke-20261007.json) ran 12 active definitions and 72 cases with stable sources: all 24 previous ownership errors now reach a later state lifecycle failure, `Ordinary healing actor absent`. Overall outcome counts therefore remain unchanged. This demonstrates progress through the execution path, not successful glyph lifecycle.

## Automated verification

The focused casting, initialization, transaction, granted-spell and modifier run passed 58 tests. Actor snapshot and checkpoint container/wire checks passed another 16. These are offline checks; database-backed tests were excluded.

The ownership integration area subset ran 15 tests and exposed two errors in the real Feca glyph test at levels 1 and 200: `Ordinary healing actor absent`. This is a later state/event lifecycle boundary involving an area manager. Investigation is in progress; no guessed actor defaults or spell-specific bypass was introduced.

The subsequent generic local event repair accepts registered area Qf managers. The [second stable 72-case audit](area-event-integration-smoke-20261007.json) reduced rejections from 24 to 10 and increased actor-state observations from 38 to 52. The remaining ten failures still concern state304 on empty-cell scenarios. At that stage, the combined 37-test regression run had two glyph subtest errors and two ordinary-event packet assertion failures. Areas without Qf and their own entry-trigger path required a separate native PV contract. See [event-manager proof](native-area-event-manager-contract-20261007.md) and [guard/nullable-manager proof](native-area-corpse-guard-contract-20261007.md).

### Subsequent PV and optional Qf integration

The shared resolver now distinguishes a valid registered area PV from its optional state manager. It validates the installed prototype, property12 and the actual ledger. With null Qf, state304 returns false after L1 and before L2/application; it does not abort the cast or synthesize a ledger. Local listener replay is omitted only for the actual null manager. Matching area entry masks remain explicitly unsupported rather than silently dropped.

Fresh area creation records native `Qq.bhi` and its constructor provenance. Qs unregister preserves that field. Clone original-area corpse guards and state target checks before/after L2 read that authority; missing old fields remain unknown. Clone coordinates resolve the PV, including areas without Qf.

The focused area/state/replay/retention run passed 34 tests, including real glyph creation and next-turn behavior at levels 1 and 200. Eight lightweight guard/null-Qf/clone tests also passed. The two ordinary-event packet assertions from that earlier run were stale: they counted observer opcode 13497, while the verified persistent, unsubscribed child correctly emitted full-application opcode 12613. The earlier 72-case audit predates this nullable-Qf repair and needs a fresh run.

### Shared registered-summon authority

Fresh summons now expose the direct native controller and initial mutable master separately from their recursive root. Both physical carry relations are explicitly empty. Registration and each subsequent authority read validate the owned source, relationships and complete independent AP/range modifier snapshots. Unknown legacy facts and unimplemented master/carry mutations remain explicit failures.

The generic local event producer now uses that authority for summons instead of rejecting all summoned recipients. Events address the summon's own manager, never substitute its master. The focused summon authority/registration run passed 21 tests. Creation effects, retained creation records, competing global recipients, counters and removal still need full integration and verification. See [native summon contract](native-class-summon-lifecycle-contract-20261007.md).

Historical inventories and verification ledgers predate these changes and must not be presented as current-source certification.

### Full active batch after area and registered-recipient repairs

[The complete batch](class-engine-active-review-20261007.json) covered all 383 active definitions and the same 1,714 scenario keys as the initial review, with unchanged source hashes during execution. Rejections fell from 161 to 103; actor-state observations rose from 1,345 to 1,399 and retention observations from 14 to 18. No-effect observations remained 136 and packet-only observations remained 58.

All 60 prior ownership errors disappear: 54 cases reach actor-state changes, four retention changes, and two expose an unsupported `IsAreaType` predicate. All six prior summoned-recipient lifecycle errors reach actor-state changes. Six previously accepted cases now expose an unsupported `GetSpellLevel` conditional casting predicate; the earlier baseline bypassed that casting contract. Thus 64 previous rejected cases progress, while six newly revealed errors yield a net reduction of 58. None of these observations proves full semantic or GUI acceptance.

Remaining grouped failures include 30 native-range rejections requiring scenario-legality review, 18 target carry-authority gaps, local criterion markers, deposit/area predicates, portal contracts, displacement flags/collision events and trigger maximum authority. The subsequent cost-overflow, spellbook, local marker and fresh creation lifecycle changes occurred after this batch and need their own validation.

The [class-only bulk closure](class-only-bulk-closure-20261007.md) finds no missing local trees/effects in the classified direct class closure: 813 spell trees and 20,831 effects. Thirty-eight summoned-entity ability trees remain a separate staged dependency set. Dynamic reachability remains unknown.

## Foundations added after the full active batch

`GetSpellLevel` now queries the complete owned player spellbook produced by the same inventory serializer as the client protocol. It distinguishes absent spells, a proven null book, player progression, and deck caps. Missing NPC or summoned spellbooks remain unknown. See [spell level evidence](native-spell-level-review-20261007.md).

The criterion parser accepts multiple native SHARP subexpressions, preserving precedence, aliases and localization metadata. Explicit null PV predicates distinguish a genuinely null target from missing actor authority; they do not manufacture carry or state relationships. The combined conditions, local-marker, null-PV, spell-level and cast run passed 55 tests.

Fresh family307 creation now follows L1, descriptor calculation, L2, actor registration and L3/L4 order. The immutable creature descriptor remains separate from the runner value transferred by context. Two phase regressions cover callback ordering and cancellation. A prior combined integration run passed 76 tests; it predates the latest null-PV change.

Category AP adjustments now wrap as signed Java integers before the nonnegative cost clamp; four overflow regressions pass. Configured eYQ family314 shares the verified creation handler with315 while retaining its actual family and target in the codec. Eight configured-area codec/removal tests pass. AURA prototypes require their own owner-following geometry and movement event contract; they are not treated as static glyphs.

These changes still need a fresh active batch. Existing complete batch numbers above remain explicitly historical. No running server or client was changed by deployment.

The [client delivery review](range-client-delivery-review-20261007.md) checks all813 spell IDs: no baseline or conditional range flags are missing. Thirteen range/modifier/import tests pass. Native RANGE characteristic11 and category modifier1066 follow separate client delivery paths; characteristic snapshots alone do not reconstruct the category map. Actual running-server freshness and client reception remain pending manual verification.

## Latest focused integration verification

The offline integrated batch passed 125 tests in one process, including casting eligibility, class initialization and cap 0, spell-level tables, gate area lifecycle, area authority/events/retention, null-Qf state behavior, and displacement/event/facing/collision regressions. The observed production source hashes were unchanged across the run. The fresh complete active audit is a separate run; earlier batch counts in this report remain historical until that audit finishes.

The displacement callback checks preserve eight native eVi phases and separately validate the emulated movement-completion event 2128 associated with reaction state 4801. The completion routes occur only after a real move; the no-movement case still exercises native phases and emits no 2128. The reversed 353389 listener selects the captured caster route on channel 30, and Qd5 rebinds caster 7 to target −7. Its guard and criteria pass. The persistent, unsubscribed 353390 child produces three 12613 applications with distinct UIDs 203–205 and targets 7, 8 and −7; it does not produce a child 13497 observer packet. Removing the retained listener prevents additional child applications.

The active-spell audit candidate generator now requires an installed native casting baseline and uses its range, free-cell, line-of-sight and linearity fields. It does not infer missing values from the older spell-tree export. Three pure regressions cover native-field selection and missing-baseline rejection; the existing legality checks and these new cases pass 6 tests together.

General area predicates now cover `IsAreaType`, `IsSpecificArea` and `IsOwnDeposit`, resolving actual null, cell, actor and area target forms. Deposit ownership reads verified PV identity rather than controller or team. Fifty-three combined tests and thirteen existing area checks pass. AURA/faN creation, owner-following geometry and native owner movement suppression pass23 focused tests. Retention now preserves the configured effect family and recipient separately from the Qf manager; integration verification follows.

The subsequent integrated regression run passed89 tests in20.60 seconds with identical before/after hashes for the observed production modules and fixtures. It covers real glyph entry, area events, AURA authority, retained area/group lifecycles, conditions and summon creation/relationships. New family314 retention regressions cover both actor and cell recipients: the original running payload retains its actual recipient/position, while removal addresses the actual caster Qf manager. An old displacement fixture was corrected to provide its actor's already explicit level1 to the complete spellbook producer.

## Fresh foundations scenario batch

The [fresh focused batch](class-foundations-focused-20261007.json) re-executes40 previously rejected scenarios across10 active definitions, with unchanged production source hashes. Thirty cases now change actor state, two change retention, two commit without an observed effect, and six remain rejected at later boundaries. All40 original error messages disappear. This is execution-path progress, not complete gameplay acceptance.

| Original mechanism | Actor changes | Retention changes | No observed effect | Later rejection |
|---|---:|---:|---:|---:|
| Multiple local markers |4|0|0|0|
| Area predicates |8|0|0|2|
| Null carry target |12|0|2|4|
| Configured area314 |0|2|0|0|
| Spell level lookup |6|0|0|0|

The six later rejections are two missing blocking-terrain teleport policies and four unsupported `GetDistanceToClosestSpecificArea` queries. The complete1,714-case batch has not been rerun after these changes; do not extrapolate a new total rejection count from this focused subset.

## AI integration boundary, read only

The AI service uses complete world context, source guards and native previews. It replans from fresh state and delegates authoritative execution to world handlers. The shared class mechanisms can later support monster mechanics; this work does not modify `server/ai-service/` or the NPC casting entry point.

## Complete active checkpoint after shared foundations

The [new complete batch](class-engine-general-review-20261007.md) covers383 active definitions and1704 scenarios, with379 tracked source/data hashes stable. It records1427 actor changes,20 retention changes,58 packet-only observations,142 no-effect observations and57 rejections. Thirty rejections are expected speculative self candidates outside their selected native range. The remaining27 rows span nine shared boundaries. Compared with the previous complete batch,46 shared rejected cases progress and no shared accepted case newly rejects; ten obsolete generated keys disappear under authoritative baseline eligibility. These are execution observations, not completed-spell counts. The expanded report documents source scope and pending semantic/client checks.

## Subsequent alignment, direction and selector checkpoint

[Ten previously rejected scenarios](class-foundations-alignment-selector-review-20261007.md) across five definitions were repeated with stable source/data hashes. Six now change actor state, two emit packets and two expose a later missing family339 area handler. All original messages disappear. The full active count above is not recomputed from this focused subset. The post-correction98-test validation records explicit PV/cell/controller distinctions and an unrelated concurrent source change separately.

## Ready route checkpoint for masks

The [54-case production Ready-and-two-turn batch](ready-basics-foundations-review-20261007.md) remains51 passing and3 Enutrof lifecycle failures, with stable observed hashes. It exposed incorrect numeric-only registration of the native boolean IsOnBorderCell criterion. The mask oracle remains valid independently; criterion wiring and its fixtures are being corrected before repetition.

## Corrected complete Ready checkpoint

The [repeated54-case batch](ready-basics-boolean-border-review-20261007.md) now passes54/54 with stable source/data hashes: every class at levels1,20,200 starts and completes two turn transitions, including all three Enutrof cases. It follows the boolean eOr correction, exact arena mask snapshots, area constructorbcN=-1 and shared eWN lifecycle. It does not equip passives or certify GUI/spell semantics.

## Complete passive lifecycle repetition

The [339-passive repetition](passive-foundations-activation-review-20261007.md) finished with stable tracked sources: 336 observed cycles, three blockers, 337 installations and 28 observed activations. All 17 previous Enutrof border blockers disappear. Remaining boundaries are native family1038 and HasState triggering actor selection. No passive is certified complete from these counts, and no service was restarted.
