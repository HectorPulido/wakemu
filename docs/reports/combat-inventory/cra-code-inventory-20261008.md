# Cra implementation inventory — 2026-10-08

Current code and acceptance inventory for native breed9. This inventories
implementation and data; manual client acceptance is recorded separately. The
original source-only audit did not run new combat scenarios or change gameplay
code; later repairs and acceptance results are recorded below.

## Exact scope

| Domain | Count | Exhaustive reference list |
|---|---:|---|
| Active deck spells |21|4769,4774,4805,4806,4808,4809,4810,4811,4812,4813,4814,4815,4816,4817,4818,4819,4820,4821,4822,6842,7753|
| Passive deck spells |19|6945,6946,6947,6948,6949,6950,6951,6952,6953,6955,6956,6957,6958,6959,6960,6961,6962,6963,7795|
| Granted/temporary spells |6|4807,6349,7752,7792,7793,7807|
| Innate state seeds |2|3419,4464|

The full union contains1198 effect definitions,42 states,46 spell references,
three summon profiles and one effect area. Shared innate4464 contributes
cosmetic branches; it must not be mistaken for additional Cra attack mechanics.
Native effect roots vary by level and are separate from the46 spell references.

## Tracked implementation findings and current disposition

The detailed JSON/Markdown audits below were generated before the current repairs;
their `missing` statuses are historical evidence, not the current source state.
The table below is the current disposition after the r31 fixes and latest
focused regressions.

| ID | Finding recorded in the original audit | Current status |
|---|---|---|
|CRA-CODE-01|State decurse321 omitted produced lifecycle phases including2288 for350821,347121,352099,352104,352262; listener398436 uses2287/2288.|**Repaired, focused tests pass.** eZi decurse now emits its source-backed phases, including2288, through the lifecycle provider. Shared by Explorador4806 and passive6951.|
|CRA-CODE-02|External event1010 had subscribers but no owned publisher (351403→351404→351405/395194).|**Implemented as explicit Wakemu policy.** The owned KO/death boundary publishes the consumer-backed event and focused ordering/deduplication regressions pass. This is not a claim that the original server publisher was recovered.|
|CRA-CODE-03|Direct actor-targeted null400 omitted produced phases2177/2276 (352184,398818).|**Repaired, focused tests pass.** Direct null execution publishes the actual phases and registers retained applications before post-phase replay.|
|CRA-CODE-04|A positive equipped finisher lacks its source-verified external events; shared innate4464 refs185234/185235 and all38 descendants are1099-only.|**Implemented as explicit shared Wakemu policy.** Owned account selection, the original4464 tree,1099 delivery, reconnection and post-death cleanup are implemented. An actual initialized turn4 lethal cast reaches original leaf185395 on the defeated enemy. Visible client acceptance remains pending. See [exact finisher boundary](native-finisher-event-boundary-20261008.md).|

CRA-CODE-04 is shared conditional presentation, separate from core Cra combat.
Detailed historical source references remain in the passive and event audits.

## Present in code and data

- All46 spell definitions have native casting records and root-selector metadata.
- All1198 effect definitions and42 state definitions in this union exist in the
  actual compiled production catalogs. No absent handler family was found.
- All21 active spell routes, their18 conditional casting tables, and the28
  predicate functions used in their closure have identified source consumers.
- All19 passives have direct routes or actual deck-dependent innate/casting
  branches. A native400 marker is intentional and is not a missing passive.
- All three beacon profiles3798/3799/3800, constructor states7781/7780/7779,
  owner relationships, elemental reaction paths, creation delivery, removal and
  spell grants have code paths. The six granted spell references are included.
- Voltereta4774 and Retirada Balizada4805 reach the common teleport302 path.
  Placement now preserves exact native selected-surface indices/provenance;
  this fix is deployed in r14. Explorador4806 is a state/characteristic action,
  not a second teleport implementation.

“Present” does not declare every branch semantically correct. The recorded
integration findings require the separate repair/deployment status below.

## Native behavior that must not become a false missing-feature ticket

Balizas Discretas6947 applies property54, **DONT_BLOCK_LOS**, through effects
348453/348454/348455. It does not apply invisibility properties5/18. The native
beacon profile defaults also omit5/18. The current owner-visible beacon is
consistent with this property; do not implement invisibility from its name.

Several original leaves have a literalFalse criterion: beacon constructor damage
357565/357566/357567, the old Explorador151534 branch, Instinto de Cazador350835
and a Tiro Divergente348490 branch. Deliberately inactive native leaves are not
unimplemented features.

## Shared engine limitations, separate from missing Cra code

Twenty-seven legacy map archives lack decodable native terrain exports. Those
maps cannot satisfy native terrain/LOS prerequisites. Map527 has the required
data and is not among them. Critical rolling and external cast/turn/death event
origins include explicitly documented Wakemu server policies; the unavailable
original server implementation is not represented as recovered code.

An explicit authority guard is counted as a Cra defect only when its actual
native configuration requires a field/provider that production does not supply.
The detailed active audit preserves remaining guards rather than converting
every possible rejection into an invented missing spell.

## Detailed inventories and reproducibility

- [All21 active spells, costs/ranges/LOS/conditional rules and effect consumers](cra-active-casting-code-audit-20261008.md), [machine-readable details](cra-active-casting-code-audit-20261008.json).
- [All19 passives and innate reactions](cra-passive-code-audit-20261008.md), [machine-readable details](cra-passive-code-audit-20261008.json).
- [Three beacons, visibility, automatic/temporary books and movement](cra-beacon-book-code-audit-20261008.md), [machine-readable details](cra-beacon-book-code-audit-20261008.json).
- [Event subscriptions and production origins](cra-event-code-audit-20261008.md), [machine-readable matrix](cra-event-code-audit-20261008.json).
- [All48 root closures and current production data availability](cra-code-dependency-inventory-20261008.json).

Rebuild the data/route layer with
`python3 server/tools/build_class_effect_route_inventory.py`, then
`PYTHONPATH=server python3 server/tools/inventory_class_code.py --breed 9` using the project
Python environment with its dependencies installed. Source hashes identify the
audited code. Semantic code findings are reviewed source evidence, not a
percentage computed from registered families.

## Reuse across classes

The inventory tool accepts every native playable breed ID using `--breed`. Its
Cra entry remains a compatibility wrapper. Preserve graph closures, source hashes
and per-root metadata, then apply the [shared event audit method](class-event-audit-method-20261008.md).
Reverse-index shared gaps to affected class roots; never duplicate them as
spell-ID patches. No manual-test absence is classified as missing code.

The shared checkpoint worker also dereferenced an absent runtime during placement.
This closed the session before disconnect cleanup and left stale registered
actors. The placement fix passed six worker regressions and is included in r15.
This is an entry/lifecycle defect, separate from the four code findings above.

## Implementation follow-up

CRA-CODE-01 and CRA-CODE-03 now have general runtime repairs:321 produces
its actual runner phases/2288, and direct null400 produces2177/2276 and
registers retained applications before post-phase replay. The integrated
state-decurse/child-removal/stat/ordinary-event batch passed36 tests.
CRA-CODE-02 now has the explicit consumer-backed
`wakemu.owned-ko-and-death-v2` policy at the owned KO/death boundary, with
focused producer-order and deduplication regressions. It remains a Wakemu
policy, not recovered original-server code. See [external origin investigation
and implemented policy](native-external-event1010-review-20261008.md).

CRA-CODE-04 was originally an unsupported **positive equipped finisher presentation**
boundary, outside core Cra nominal play. The native category5 FINISHER list is
empty in the current fresh-account constructor. All38 leaves below185234 are
1099 death-animation scripts; none changes damage, healing, movement or HP.
The existing1099 handler and removal are implemented. See the [exact native
finisher classification](native-finisher-event-boundary-20261008.md) and
[all38 leaf definitions](native-finisher-event-boundary-20261008.json).
No guessed1012/1015/1018 publisher or cosmetic no-op was introduced.

The live Buscadora report in fight58 was a legal prerequisite failure:
Esquivo3420 level30 was present; Precision7792 was absent. The
[recorded diagnosis](cra-live-precision-state-diagnosis-20261008.md) preserves
request states and source criteria. It is not a new LOS defect.

The321/null400 repairs and [general cast diagnostics](combat-cast-diagnostics-20261008.md) are included in r17; the subsequent fixes are part of the current complete-20261008-r31 release. CRA-CODE-04 now has shared owned-finisher implementation and an actual native-tree regression; client acceptance remains separate. The release is not a100% class certification.

### Resolved live incident: Desbalizaje disabled before request

The user reproduced a grey6349 button with a visible destruction beacon and4AP. The capture at2026-10-08T17:24:39.076588Z showed owner6 was preserved; the native summon-count flag was reset in the later12873 actor snapshot. Native `eGn.zl` copies `eGj.dTE` to `pW.Uh`, and `eGn.zm` applies it through `eGj.ly`. `registered_summon_stats` now serializes the validated `is_summon=True` fact into that field for registered class summons; ordinary PC/NPC serializers keep the flag false. The fix is in complete-20261008-r31. Hector manually confirmed Desbalizaje works on r31. See [the source investigation and acceptance record](cra-desbalizaje-ui-criterion-20261008.md).

## Latest acceptance update

2026-10-08: Hector confirmed Desbalizaje works on complete-20261008-r31. The previously missing **positive equipped finisher** now has an owned-account producer and explicit shared Wakemu event policy. The original4464 tree and1099 assignment execute in the actual turn4 lethal-cast regression; this is not recovered original-server event semantics or manual client certification. The core Cra event/state gaps321/2288, direct-null400/2177/2276, and event1010 now have shared runtime implementations and focused automated coverage; event1010 is an explicit Wakemu policy, not recovered original-server code. No other Cra-only core gap is currently established by the inventory.

Manual acceptance remains separate from these source and automated results. Interior glyph targeting/trigger behavior and movement-stop animation have not been confirmed by Hector; the border callback now has five focused automated regressions, but its in-client presentation remains unverified. The shared Osa summon-count/reconnect gate also still needs Osa acceptance. This is not a manual certification of all21 active spells or all19 passives.

## Shared summon and finisher follow-up

The summon-recognition fix is general, including fresh307, captured324, copied1002, snapshots, retirement, and reconnect. Controlled summon movement now serializes the exact candidate fight instead of treating the summon as a player character. See [route inventory](class-summon-recognition-lifecycle-20261009.md). Shared1099 includes owned selection, original native criteria, assignment to the defeated actor before death, cleanup after12727, and immediate/retained reconnect delivery. See [whole-system acceptance](shared-finisher-manual-acceptance-20261008.md). The matching shared changes are delivered in `shared-finisher-complete-20261008-r34`; the final focused regression passes35/35. Manual finisher acceptance remains pending.
