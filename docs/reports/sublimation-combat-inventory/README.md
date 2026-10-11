# Complete sublimation combat inventory — 2026-10-11

All 467 installed-native sublimation definitions have been inventoried. Their
inventory attachment implementation and their combat execution are separate.
The current owned-player combat path does not install these equipment roots.
This report specifies the remaining integration work; it implements none of it.

## Denominator and current result

| Inventory | Total | Interpretation |
|---|---:|---|
| BASIC / EPIC / RELIC scrolls |388 / 32 / 47|Every native scroll, including tiers with distinct references|
| Passive item roots |467|One native class 304 root per scroll|
| Transitive effect definitions |2,036|Item roots, ordered groups, all referenced state levels and implicit resource-loss state 5227|
| State definitions |289|Complete potential closure; branches need not run together|
| Effect classes |88|Every class has a handler, characteristic-registry route or dispatcher group branch|
| Roots absent from compiled runtime |467|All other1,569 closure effects are present|
| Required subscription event IDs |112|Activation/removal masks retained separately in the mapping|
| Event IDs with candidate producers |99|Presence does not establish reachable delivery for a scroll|
| Event IDs without an identified producer |13|Affect35 scrolls:32 BASIC and3 RELIC|
| Criterion functions |50|49 have validated parser/signature support; one evaluator is missing|
| Effects rejected by criterion validation |21|`HasWeaponType`, affecting18 BASIC scrolls|

The current published catalog revision is
`677062aedeeb9fa0deaad21e0c9a40989e5c8b64cc13b1ebba7200f684d3437d`;
the actual compiled runtime snapshot contains 63,020 definitions. The installed
client JAR SHA256 is
`e3eb8b9b6a1fa0d42d2f06f0af3e841ed783b2998f5c81d3cd8312294106d3cd`.
SQL document hashes, integrated combat source hashes and input snapshot hashes
are recorded in [inventory.json](inventory.json). Runtime-only Classes
candidates were not treated as integrated source or as published catalog data.

No missing native item definitions, referenced effect/state definitions,
retained-definition metadata or native item-filter authority were found in
this denominator. No unsupported characteristic-registry parameter count or
maximum-resource parameter length was found. These are structural checks,
not successful execution of every native parameter mode or context provider.

## Exhaustive machine-readable mapping

- [inventory.json](inventory.json): each scroll reference/name/type; root and
  full effect/state closure; parameters and level bounds; raw criteria and
  validation result; target masks, native selector, flags, timing and probability;
  retained/subscription metadata; primitive route, compiled-runtime presence;
  event producers and exact per-scroll gaps. Includes every class and state.
- [scrolls.csv](scrolls.csv): all 467 scrolls and their pending dependencies.
- [states.csv](states.csv): all 289 states and their selected effect references.
- [classes.csv](classes.csv): all 88 classes, effect/scroll references, native
  characteristic runner/stat where applicable, and observed parameter counts.
- [events.csv](events.csv): all 112 event IDs, mask positions, subscribers,
  affected scrolls and candidate producer evidence.
- [criteria.csv](criteria.csv): every nonempty effect criterion and the actual
  existing validator's syntax/signature result.

An effect class marked `handler_or_group_present_requires_contract_validation`
means its route exists. It does not mean the effect has run successfully for an
owned equipment container. Event candidates likewise include compiled extra
masks, native intrinsic-event catalogs and explicit server policies; they are
not an execution ledger. The union follows every state level and group branch
rather than claiming all branches are simultaneously reachable.

## Work required

### 1. Integrate owned equipment before start events

All 467 scrolls are blocked here. The existing planner returns source groups
but has no production caller; its only imports are in its tests. It explicitly
preserves the equipped parent item's container identity and level, including
roots originating in attached BASIC/special scrolls. See
[owned planner](../../../server/wakfu_server/combat/combat_equipment_initialization.py:14).

The current [owned initialization](../../../server/wakfu_server/combat/combat_server_spell.py:276)
constructs its factory, initializes class roots, initializes conditional
aptitudes, then optionally publishes start events. It never calls the equipment
planner. The [compiled catalog](../../../server/wakfu_server/combat/combat_server_spell.py:23)
merges spell/state/area/aptitude definitions, omitting the467 item roots.

Classes must establish native relative ordering of ordinary equipment,
attachments, class roots and aptitude roots; merge complete definitions before
factory construction; then register each eligible owned source once before
start subscriptions execute. Preserve item PL type12, parent equipment ID and
level, null/applicable native source context and explicit SELF targeting.
Preserve the current flat-stat snapshot ownership to avoid double bonuses.

The existing [copied-equipment initializer](../../../server/wakfu_server/combat/combat_copied_equipment_execution.py:92)
is a different native PJ path requiring a registered summon destination. It
cannot simply be called on an owned player to bypass those guards.

Acceptance: all 467 roots initialize through the actual owned entry point;
active sheet changes and multiple equipment pieces preserve source identity;
repeated readiness/start/restore never duplicate registrations; class/aptitude
and ordinary equipment statistics remain identical in controls without scrolls.

### 2. Bind authoritative attachment eligibility at combat entry

The planner's `attachment_authority(gear,state,reference,field_tag)` has no
production binding. It must use the current enabled catalog, BASIC ordered
colors versus special native rarity, correct tag24/32 and active owned sheet.
Persisted attachments alone are insufficient authority. The prepared inventory
eligibility code is reusable authority data, not a combat lifecycle hook.

Acceptance: enabled/disabled or incompatible attachments, both slots on one
item, effective build level and parent item level are tested through owned
initialization. Invalid metadata fails atomically without applying a partial
root population. Keep inventory mutations and combat setup separate.

### 3. Implement the missing `HasWeaponType` evaluator and provider

Exactly 21 effect criteria in 18 BASIC references use this unsupported predicate:
27186,27187,27188,27195,28798,28803,28804,28805,28807,28893,28900,28901,
28902,28903,28904,28905,28908,28909. Their names and exact affected effect IDs
are in the mapping. All21 currently fail the real criterion syntax/signature
validator with `Unsupported native predicate: HasWeaponType`.

Installed native lexer token233 constructs `eMV`. Its actual contract checks
both native weapon positions `fnO.sHt`/`sHu` on the caster, using the fight
inventory `fnZ` when present and the owned equipment/inventory components as
fallback. It walks `fpY.gkj()` category parents, comparing short-narrowed
requested category IDs at every ancestor. This is not a current-spell-element
or one-slot weapon check. Private disassembly:
`.runtime/local/sublimation-combat-inventory/eMV.javap`.

Acceptance: both weapon positions, category inheritance, multiple category
arguments, absent items/components, cast-time active sheet and negative
controls match native `eMV`; test the actual 18 scrolls through initialization
and trigger replay. The 49 existing predicate/function signatures still require
real owned context values, not default zero/false callbacks.

### 4. Resolve 13 subscription producer contracts

| Native event ID | Affected scroll references |
|---|---:|
|70,78,80,168,208|3 each|
|74|2|
|166,2258|6 each|
|1004|1|
|1016|17|
|1032|4|
|1048|2|
|2257|3|

These sets overlap. The complete 35-scroll mapping, masks and effect IDs are in
[events.csv](events.csv). No integrated producer was identified after comparing
compiled definition extra masks, current-stat/maximum-resource intrinsic
catalogs, native displacement producers and audited external boundaries.
This is a missing producer-contract investigation, not proof that 13 new
primitive handlers are needed. Dynamic providers or newly integrated Classes
work may resolve a gap; establish an actual caller before declaring it closed.

Do not synthesize notifications merely because a listener exists. Native event
IDs are distinct from delivery channels and effect classes. Retain event
source/caster/target, local/global/reversed channels, priority, execution limits,
level suppression and removal masks. Existing start/turn/cast/movement/death,
paid-cost and preparation boundaries include explicit Wakemu policies where
original server publishers were unavailable. Event 500 and native displacement
184/187/188/193/194/197/198 already have integrated candidate producers and
are deliberately excluded from this missing list.

Acceptance: each identified missing ID gets a native/source-backed producer
contract or an explicitly documented server policy, followed by real positive
and negative delivery receipts for every affected listener branch. Qualify
reversed/global delivery and removal, not just publication of an integer.

### 5. Qualify existing primitives in the equipment context

No new effect class is structurally required by the 2,036-definition closure.
The remaining work is execution qualification and any defects it exposes.
The 88-class inventory includes resource/characteristic modifiers, null400,
state304/removal321, dispel421, group330 and level-dependent groups,
triggering-runner amount430, final modifier1093, armor1013, damage/healing,
and fight property447. [classes.csv](classes.csv) enumerates every remaining
class rather than limiting support to this summary.

Run all observed parameter modes, criteria branches, area/selector modes,
chance paths and relevant equipment levels through the real dispatcher. Check
live triggering Qe/final-modifier identity instead of inventing flat bonuses.
Include implicit state 5227 from actual AP/MP loss; its original scaled chance,
level and transaction RNG must survive. Native child-state nesting, duration,
refresh/stacking, removal/reversal and resistance remain essential.

Acceptance: a per-scroll semantic ledger records actual root/child execution,
state levels, numeric changes and negative controls. A passing class-level
unit test alone is insufficient evidence for an attachment's full closure.

### 6. Complete transactional lifecycle and whole-system acceptance

Initialize equipment together with class/aptitude roots on a private fight
preview; later failure must discard every earlier mutation and outbox packet.
Verify controlled heroes, join/restore, death/retirement, turn expiry, sheet
switching and new fights. Preserve source parent identity across subscriptions
and reconnect/restore; do not leave stale retained runners or repeat ordinary
bonuses. Any fallback must be explicit and observable, never silently turn an
unsupported sublimation into flat statistics.

Automatic acceptance should enumerate all 467 definitions, exercising each
unique semantic branch with native positive/negative controls and keeping the
per-reference ledger. Include combined existing combat/class regression gates.
Then perform one complete graphical equipment acceptance: identify, enchant,
attach BASIC+special, equip, enter/finish multiple fights, compare effects,
remove either slot, switch build and reconnect. Native UI state appearance is
additional evidence; numeric and trigger behavior must agree too.

Exact inventory commands already available for future end-to-end acceptance:
`!item 10272 1`, `!item 24130 2` (EPIC level20/Inflexibilidad) and
`!item 24309 1`, `!item 14186 2` (RELIC level50/Robusto). For a concrete future
numeric control, native Inflexibilidad's state 5073 subscribes1028 and applies
class 126 `FINAL_DMG_IN_PERCENT` +15 only when caster maximum AP is at most10;
its separate +10 WILLPOWER branch requires caster level at least100. The test
must compare eligible/ineligible builds with the same parent gear and record
both branches independently. These commands do not imply that this currently
unwired combat behavior is ready for a user acceptance test.

## Reproduction and limits

Run `python3 docs/reports/sublimation-combat-inventory/audit.py` from the
repository root. It reads fixed private snapshots under
`.runtime/local/sublimation-combat-inventory/` and writes only these reports.
The criterion check reuses the actual existing parser and full signature
validation, stopping before context-dependent evaluation. It imports no live
combat runtime or database connection. [audit.py](audit.py) and
[enrich.py](enrich.py) document the exact traversal and classifications.

The snapshot documents are native-copied-equipment-definitions,
combat-state-definitions, effect-characteristic-registry, spell-effect-trees,
native-retained-effect-metadata and item-equipment-effects, obtained through
read-only published `native_catalog` reads. `runtime-effects.json` and
`runtime-producers.json` come from the real `compiled_runtime_catalog()`.
Other small snapshots contain intrinsic-event catalogs, characteristic aliases
and native set-current contracts. Patterns were freshly re-exported with
`ExportNativeSublimations` into the private directory, with 467 rows and zero
export errors. No game/server/client/service content was modified by this audit.

This is an exhaustive static inventory of the installed-native denominator,
not graphical acceptance or a claim that every branch can already execute.

## Owned integration preparation (staged, not enabled)

The follow-up implementation adds an immutable enabled SQL attachment authority
and a pre-factory source-closure composer in `combat_owned_equipment.py`. Its
initial admissible shape is structural: a permanent SELF state, no predicates,
subscriptions, groups, chance or clocks, containing only fixed non-resource
scalar characteristic gains through the existing `eWQ` runner. It does not use
a scroll allowlist and does not claim coverage of all 467 definitions. Sources
outside this contract produce an explicit deferred reason.

The transactional helper applies qualified sources only to a private owned
fight preview, retains the parent equipment PL identity/level, rejects repeated
initialization and returns packets for the caller's atomic commit. Ordinary
flat equipment bonuses remain owned by the existing player snapshot, avoiding
double application. These helpers currently have no production caller.

Production integration still needs two shared contracts before activation:

1. Establish the native relative order of equipment roots, class/passive roots
   and aptitude initialization. The observed `eHi.doT` order proves equipment,
   shard and set refresh ordering; it does not prove their position against the
   server's class/aptitude initializer. Initial predicates and characteristic
   limits make a guessed order unsafe.
2. Pin the equipped-source and enablement snapshot to the fight, then compose
   its definitions before **every** `server_runtime` factory, including later
   casts and turns. A one-shot initialization override is insufficient for
   retained effect identity and inverse execution. Re-reading mutable inventory
   during an active fight would silently change the authority.

The shared hook belongs in `combat_server_spell.server_runtime` and its owned
initialization coordinator, coordinated with Classes. No client, shared combat
primitive, spell behavior, service or production lifecycle was changed by this
staged preparation. Automated qualification is recorded separately after the
new native runtime and authority tests finish; graphical acceptance remains
pending.

Qualification of the staged helpers: FastLuna independently passed all 14 tests
in `test_sublimation_eligibility`, `test_combat_attachment_authority` and
`test_combat_owned_equipment`; all six watched source/test hashes were stable.
The actual native dispatcher applies Influjo27152's root283591/state6026 at
level2 and increases the owned actor's characteristic9 by6. It retains parent
item10272's PL, leaves the original fight unchanged, rejects replay/foreign
ownership/uncomposed factories and discards a partially processed private
preview when a later source fails. Negative tests reject empty area with mask1,
nonself mask2 and nonpoint areas. The native state has turn duration-1 and
realtime duration-1000, both indefinite under the existing native state timing
contract. This qualifies that structural example and helper boundary, not a
production caller, complete scroll coverage or graphical acceptance.

Command: `PYTHONPATH=server:server/tests python -m unittest
 test_sublimation_eligibility test_combat_attachment_authority
 test_combat_owned_equipment` (with the project's isolated native-catalog test
environment). Private evidence:
`.runtime/local/verification-fast-20261011/owned-equipment/final-tests.log`.

### Preview-aware follow-up

The fight pin now validates the actual equipment build once, stores detached
immutable qualified source definitions with a canonical integrity digest, and
survives a plain checkpoint JSON roundtrip. Four new tests passed independently:
actual equipment plan/owned native +6/later factory after inventory mutation;
checkpoint restoration and mutation rejection; repeated pin/foreign owner
rejection; disabled attachment exclusion. The previous five real owned-dispatcher
tests remain green. No shared caller has been enabled.

Native entry review distinguishes actual12847 from world rebuild and13912
refresh. The actual owned12847 path restores/deserializes native running effects,
executes eligible restored runners, then rebuilds aptitudes and owned equipment
through `eHi`; its final `myE` statistics are server-authoritative. Other rebuild
paths have different orders, so they cannot substitute for this entry trace.
This establishes a client restoration boundary, not the unavailable original
server's fresh class-root criterion evaluation order. Integration preserves the
existing class/aptitude order and will append only qualified owned equipment
before first1028/1003 events.

A separate preview-aware factory wrapper is staged for qualification. It binds
pinned source metadata to the actual `factory(preview, plan)` argument, including
expiration factories created before readiness. Its bounded process cache retains
only static compiled definitions and serialized source metadata; no fight,
actor, SQL authority, callback or transaction RNG enters the cache. Relative and
random group authorities receive private definition bindings, preserving the
original factory. Shared factory/initialization hooks remain subject to Classes
coordination; neither this note nor native metadata availability activates467
scrolls.

The preview wrapper's three real-native tests now pass independently with stable
source/test fingerprints, including cache identity reuse, unchanged original
group authorities, factory creation before pinning, actual native stat gain,
rollback after actual native mutation and corrupted restored-pin rejection.
Evidence: `.runtime/local/verification-fast-20261011/owned-equipment/factory-gate.log`.
Shared initialization/factory hooks are still unedited pending Classes scope
coordination, so these results remain staged integration qualification.
