# Aura runner families 316 and 338

## Original runner contracts

Original `eVi.rtZ` is family 314 and `eVi.rua` is family 338. Family 316 registers `eZF`, whose computation is empty. Application snapshots the recipient PV's owning Qf iterator into an ArrayList, selecting only these two family IDs, then calls `Qe.bbN()` on each captured runner. It does not apply the generic dispellability, state or source-spell gate. `bbN` delegates to its owning Qf's removal; without an owner it invokes normal runner removal directly. Both owner flags are true and `bbz` is false.

Family 338 registers `eYJ`. Computation evaluates parameter 0 at `fRR()` into `aSg` and captures `PN.bae().baj()` as the new area identity. Application resolves the actual `faN` prototype and requires both the bound target PV and selected cell. It constructs `fbm` with that area identity, selected coordinates, current PN, target PV identity, target PV object, runner level and target PV direction. It calls application notification before registering the resulting area in Qs. Removal unregisters that exact area from Qs, then executes inherited runner removal. Additional codec data serializes the captured area identity; clone copies both that identity and the actual area object.

These constructor inputs differ from configured eYQ's caster owner and optional parameter fields. Therefore family338 cannot safely be implemented by merely adding its ID to the existing eYQ whitelist.

## Implemented family316 boundary

`combat_aura_removal` selects the complete retained view's subsequence belonging to the actual recipient manager. This preserves each Qf's native insertion order and distinguishes manager ownership from the serialized target. Shared retained removal preflights all selected runners and owned children before the first mutation. Unknown removal families reject explicitly.

The factory now registers `NativeAuraRemovalHandler` for 316. It uses the actual shared runner amount, supplied execution context and timing/container authority, ordinary lifecycle phases, existing owned application packet, and central retained registration before phase3. Retained removal removes the eZF record without recreating previously removed auras. Four focused tests pass, including snapshot order, absent-family atomic rejection and actual handler phases with registration before phase3. This is bounded unit verification; a full native factory/production invocation regression remains pending.

## Implemented family338 constructor

`NativeTargetAuraHandler` now prepares the actual runner identity, calculates the original reference and captures a distinct area identity during C. A sealed construction record binds both identities, recipient and level. The shared area builder accepts this exact eYJ construction branch while preserving configured eYQ/eYS/eYU behavior. Target identity supplies the faN owner/anchor and its direction; runner level is used directly and optional eYQ parameters do not override it. Context amount forcing is applied exactly once.

The dedicated additional-data codec emits only original ij field21, without configured eYQ level/orientation/keep fields. The existing owned cvY13497 codec carries application notification before Qs/global registration and creation callbacks. Retained registration uses actual original owner_on_caster metadata and seals the corresponding manager provenance; the complete view validates that provenance rather than assuming every area runner belongs to the caster Qf. Central registration precedes callbacks which can inspect the complete view. Removal reuses exact-area Qs removal with keep_after false, followed by inherited runner retirement.

The current faN geometry authority supports registered fighter anchors. An actual nonfighter PV anchor or an unsupported direction rejects explicitly. Two constructor/codec tests use an original faN prototype and verify target direction/anchor, level, notification order and exact additional fields. Combined with aura-removal and existing configured-area codec tests, ten tests pass. Full factory regressions remain pending.
