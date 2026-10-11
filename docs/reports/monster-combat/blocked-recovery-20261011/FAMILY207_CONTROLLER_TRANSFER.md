# Family207: temporary controller transfer

Family207 maps to installed runner `eWD`, extending `eZd`. The frozen inventory contains26 affected owned-spell monster references. A concrete representative is2784 (Bworkbolero, level50), whose reachable definitions105629/105631/105633 use family207 with no parameters, selector1 and flag17. Its spellbook includes recruitment spells4027/4028/4029. This record also illustrates why broad missing-family counts include special encounter mechanics rather than only ordinary attacks.

## Exact source behavior

`eWD.C` sets `rBJ` only when evaluated parameter0 equals1, defaulting false with no parameter. The extracted207 definitions audited here use the no-parameter branch.

`eWD.c` requires both source and recipient PVs and actual eGj instances. It chooses the source's current controller (`dpu`) when `rBJ=true` and that relation exists; otherwise it chooses the source itself. It calls source `q(recipient.Sn, controller.Sn)`. The route is `eGj.q` → `fcb.q` → `fdt.e(controlled, controller)`. The latter updates the recipient's fdy with the controller identity and controller's current team.

The fdy fields are distinct: `saH` is original controller (`dTD`), `saJ` is nullable current controller (`fXZ`), `saF` is original team (`fXW`), and `ebh` is current team (`bcM`). `fdy.a(Long,byte)` updates only current controller/team. `fdt.aX` restores current values from original controller/team; the runner's removal calls actor-specific `dnO`, whose producer must be recovered for each supported actor contract.

After changing control, `eWD.c` captures the recipient's existing `fqL` AI-control boolean in `rBI`. If the source is AI controlled, it sets the recipient AI controlled. `eWD.bbR`, when executed, calls recipient `dnO` and restores that captured AI boolean. This differs from family325/eYH, whose removal restores the actor's native baseline rather than the preceding value.

The fresh runner's additional serialization writes `rBJ` through `il.r`; retention, restoration and notification cannot be replaced with an empty success handler.

## Existing building blocks and missing authority

`set_native_ai_control` already provides the typed eGj.lx mutation. Existing affiliation machinery can represent team changes, but neither alone supplies controller transfer. Ordinary authority currently attests self `dpu_id` and original `native_controller_id`; summon registration also stores original owner/controller relationships. Those identities are not interchangeable with fdy's nullable current controller.

A correct general implementation needs a source-qualified current/original controller and team table, resolver/control-routing updates, actor-specific restoration, and retained runner capture/removal and wire delivery. No family207 handler was registered in this audit. Reusing325 or changing only an actor's team would silently omit native behavior.

Private bytecode evidence is retained under `.runtime/monster-blocker-recovery-20261011/`: `eWD-family207.javap`, `eGj-family207.javap`, `fcb-family207.javap`, and `fdy-family207.javap`.

## Shared registration producer

`combat_controller_registry` now stores separate original/current controller
and team fields from explicit native registration operands. Fresh PvE/duel
registration initializes ordinary self controllers; joined and rift actors
follow that live producer. Registered summons supply their actual registration
controller, rather than inferring it from current ownership. Withdrawal removes
the row. Existing legacy/advisory topology initialization remains separate and
does not manufacture controller authority.

The shared API samples the controller's current team during transfer and restores
constructor originals during reset. A clear operation retains nullable current
controller and team -1 exactly. Family1030 apply/removal updates only current
team; original team remains unchanged. `ProbeNativeControllerState` passed
against installed fdy for constructor, transfer, affiliation, null clear and
original restoration. NEW registration tests await the qualified offline gate.
This producer enables current-team consumers but does not alone implement207:
current-controller routing, retained runner AI snapshot/removal and native wire
publication must all be connected before registering that family.

The current-controller authority overlay now reads the explicit registry for
ordinary and registered summon targeting.dpu_id, while preserving original
native_controller_id. An unresolved stored controller resolves to null, matching
fdt.P. The native additional-data controller-mode flag is protobuf field17:
eWD.b calls il.r, whose xf boolean is written by ij.writeTo as writeBool(17).
This field is independent of the numeric runner value.

NEW5 registration/controller mutation tests passed independently in Luna's
offline gate (`offline-world449-controller207-tests.json`, combined24/24).
The original ordinary-authority suite could not start because its state catalog
fixture is absent; no assertion failure was observed or hidden.

Further source recovery found that parent eZd.fQM constructs an additional
controller-facing book. Its known-element, non-elO rows exclude root families
307/347/324 at the running effect level. It sorts two lists by descending native
short spell level, keeping stable ties; up to2 non-elemental rows precede enough
non-neutral rows to fill capacity8. Slicing precedes RC.f UID duplicate rejection
and therefore duplicates do not backfill. A new pure selector reproduces this
behavior (NEW2 local tests pass), but it is not yet connected to207 publication.
The parent's serialized inventory and actual bbs execution-side branch must be
qualified before treating the boolean17 wire field as a complete packet.
