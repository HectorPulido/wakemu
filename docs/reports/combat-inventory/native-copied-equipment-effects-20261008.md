# Copied equipment effect source

## Native contract

`eGj.PJ(int)` does not store a title or copy a cosmetic component. Operand zero
returns immediately. A nonzero operand looks up the actual item definition with
`foA.ghV().Wc(reference)`; a missing definition also returns. A present definition
creates a fresh `fnR`, then applies each effect from its iterator in native
encounter order. Repeated effect references must remain repeated.

The invocation uses the fresh item as its PL, the destination actor as both
caster and explicit target, the actor's actual XYZ, its selected `fqE()` PN,
null PS, and the final boolean false. `fnR.aZY()` is 12 and `QF()` is the item
definition reference, independently of the fresh inventory object's UID.
`fnR.cmZ()` selects its actual fresh components before falling back to the item
definition level. `fqE()` selects `fqH()` only when present with nonzero `bag()`;
otherwise it uses the actor's `pGD` context. A normal spell context is therefore
not an interchangeable substitute.

`foA.Wc` reads the item definition map. The client implementation `bGt.w(bJp)`
inserts the definition through `foA.e` before its other category processing.
`bIJ` builds definitions from `aLO`; its effect-root loop preserves `aLO.cku()`
order through `fpC.v`. Fresh `fnR.iterator()` delegates to `fpC.gjg()` while its
modification component `kal` is null.

## Offline bulk tooling

`ExportNativeCopiedEquipmentEffects` snapshots each `aLO` within its load
callback, avoiding the loader's reused mutable object. It captures raw roots,
the fresh fnR level and type, the exact ordered effects, parameters, criteria
presentation and complete shared native effect metadata. The final completion
record is mandatory; skipped output cannot become a complete imported table.

`import_native_copied_equipment.py` verifies unique identities and completion,
validates every definition using the pure planner, and writes deterministic
gzip JSON with the original JSONL hash. No service or database is accessed.

`copied_equipment_plan` preserves the item PL and duplicate encounter order.
It requires a complete nonempty table to prove a missing nonzero definition.
Zero's native early return needs no catalog. Planning does not establish that
all item runners, criteria or PN contexts can execute in the server.

## Current boundary

The existing zero-operand route remains supported. Positive operands still
require the actual catalog plus a source-qualified application/context producer
and full retention support; the new planner alone does not enable them. This
dependency affects the shared copied appearance path used by class-character
copies and the property-101 summon visual-copy path.

New focused tests cover nominal actor authority, rejecting fictional
`verified=True` namespaces, item PL identity, duplicate order, catalog
completeness and malformed source records. Source compilation checks passed;
the bulk native export and focused test run are queued with the serial validator.


## Positive operand runtime integration

The copied operand is the selected category7/currentTitle value returned by the connected bjo `eSU.dzQ`, not an inventory-equipment clone. The completed native table contains20,230 item definitions. Zero keeps its original immediate return; missing nonzero definitions and empty ordered iterators also return from the proven complete table.

The enhanced exporter additionally captures `aZR` variant, `fKR/fKS` level bounds and `aKX` child order with recursive actual `bcA` child definitions. The runtime compiler rejects missing fields instead of borrowing variants, level bounds or flags from the parent spell. Every root is applied in encounter order, including duplicate references, with fresh fnR itemPL type12/reference/actual level, destination SELF, null PS and the destination's exact position. Source-qualified item definitions overlay only the nested factory/catalog and preserve shared originals.

Registered constructor PN differs from initial-state PN. Native big's private registration call invokes buH/fcb.a, fdt.a and fcb.C→eGj.a(fcb), which writes pGz=true **before** `ac→bPi→PJ`. `fqH` then selects `dnL→fcb.bbg`; fbX installs eVw, whose bag is1, so fqE selects the actual fight PN. The earlier detached initial-state eZQ context must not be reused here. Native `fnR.k` obtains a fresh UID and delegates exactly to the exporter’s `fnR.a(uid,definition)`; item PL type/reference/level are independent of that inventory UID.

Production307 and1002 constructors now have the ordered application hook. Their nested constructor outboxes are separate from parent packets and are not appended again: client307/1002 reconstruction performs the same native PJ call. Authoritative PA/Qf writes and retained item-container records remain. Final nonempty execution validation is pending the enhanced catalog import and delegated regression/actual constructor run; the earlier completed table alone intentionally cannot compile missing closure fields.


## Source-order qualification of the positive fixture

Actual paired run01 completes item2822/root19317/family20 twice for Sram307 before its ordinary state3667 initialization. That later original state group164834→164837/913 invokes164838/family16 at child level420. Its raw parameters[1,1,1,0] select value421 and set-maximum=true; eYO assigns HP current/max421, overwriting the preceding item maximum gains. Therefore the final paired Sram maximum delta is0, **not** an inferred+400. No constructor reorder is justified. The copied1002 fixture lacks that later Sram-only forced assignment and retains the measured2050→2250 maximum (+200).

The paired tool now checks those source-ordered outcomes and records HP/current maximum immediately before and after each actual PJ call, separately from the final actor state. A generic eYO regression checks that a later forced maximum replaces any preceding421/621/821 pool with421. This qualification changes the audit oracle and scalar evidence; it does not alter spell mechanics or native constructor ordering.
