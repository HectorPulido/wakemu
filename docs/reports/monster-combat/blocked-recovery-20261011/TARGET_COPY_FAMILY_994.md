# Family994 is a target-derived creature, not a removable marker

Installed registry`eVi.ruv` maps994 to`eZq`, whose parent`eZn` is also used by
existing character-copy support. Its exact native configuration is:

- Creature profile2349. The template is`eHK` subtype3, but its inherited
  factory creates actual`eHI` subtype1 (confirmed by a second installed oracle).
- Source is the selected TARGET (`faB.mC(false)`), not the caster.
- `faD` reads actual target`frL` spellbook order; retains elemental entries,
  excludes spells with current-level roots307 or324, takes the first four.
- Original spell objects/UIDs are retained (`fTf=false`); no synthetic book IDs.
- Optional ratio operand defaults100; this is not an effect probability.
- `eZn.C` builds descriptor from target breed/name/HP/level/book/characteristics.
  `eZn.c` performs actual creature creation and controller registration.

The installed Java oracle verifies runner identity, profile, capacity4,
target-source flag, borrowed-object flag, excluded classes307/324 and subtype3.
`ev(4)` is book capacity, not creature level.

A reusable pure `copy_target_book` primitive now implements the source-proven
selection. Two NEW unit tests pass: filter/order/capacity/object identity and
malformed-operand rejection. The additive handler is now registered locally, with a deliberately partial
source domain: only actual owned class targets with connected appearance and
complete native action flags are accepted. NPC target appearance remains
unsupported and fails closed. This is not full42-monster structural coverage.
Existing1002 support expects a class-owned caster source and class appearance.
The subtype1 descriptor layout is reusable, but invoking the complete1002
handler for994 would invent caster/class source authority. The shared codec
remains unchanged.

A new raw-record provider reuses owned character inventory, ordinary bPD,
registered bPD and actual morph/grant overlays, retaining raw UIDs and order;
it rejects mismatches with the separately attested current book. This is an
explicit server hook, since installed eGj.frL returns null.

2349 has source-proven empty abilities and initial states; its copied book is
dynamic. Native eHI applies breed curves only for eGE class sources, so ordinary
NPC sources use the existing characteristic-copy primitive with no class curves.
Runtime integration still requires current target fyF/eVg metadata, connected
appearance/equipment/model authority, and general copied-book installation and
retirement authority for2349. No affected monster is considered ready from
this audit. Private disassemblies and installed source-hash receipt are in
`.runtime/monster-blocker-recovery-20261011/family994/`.

## Local integration status

`NativeTargetCopyHandler` reuses common eHI characteristic/descriptor creation,
keeping caster creation/controller identity separate from the selected target's
copied source identity. Its book keeps borrowed source UIDs, uses the original
faD filter and includes the native spell-level trailer (`faB.fTc=true`).
`faB.fTh=false` skips the extra PJ source-equipment call. Constructor/retirement
records use explicit994/profile2349 provenance, never1002 markers.

NEW selection2 and source2 tests passed independently; NEW borrowed-book source
checks2 pass locally. The independent qualified gate passed35 tests, including actual profile2349
creation with `NativeSummonBuilder`, `RegisteredSummonAuthority` and packet12613,
borrowed UID/provenance/KO retirement checks, and29 existing affected tests.
The final raw-source guard change passed the affected creation2/source2 rerun.
Receipts: `offline-target-copy994-full-handler-tests.json` and
`offline-target-copy994-source-final-tests.json`. No planner or builder stub was
used for the creation tests. Profile2349 constructor metadata was provided by
a separate source-qualified private fixture; active release packaging and real
monster replay remain pending.
No monster activation or deployment was performed.

## NPC visual producer audit

The installed eHI constructor records source.bwX into cgI but never initializes
mGL. Its connected serialization requires mGL.toByteArray; only connected vJ
decode initializes that field through dS.ad(up.Su). Therefore profile aHf alone
does not supply the missing connected appearance. bje.bwX selects a current
nonzero eGj.pGT override before blj.aHf; eGj.Di mutates that override. Likewise
bje.don selects mutable big.igU before profile blj.ium. The existing ordinary
NPC publication is format11 and does not expose a matching dS/current-override
producer. The NPC domain remains closed until that actual publication/lifecycle
authority is implemented; no inferred appearance or empty categories are used.
