# Configured eYQ actor/cell area creation

## Shared native runner

Original `eVi` registration constructs family314 with `new eYQ(false,true,true)`; family315 uses its default constructor `(false,false,true)`. Those three facts are bbz (caster required), bbA (actor route) and bbB (cell route), respectively. Clone `eYQ.fQC` copies all three fields. Authoritative registry metadata already contains both verified configurations.

The creator uses the native running coordinate bft directly when constructing fbm. It does not recenter on target position. The actual owner is bfr/current caster via bch, independently from bbc/current target. The explicit evaluated direction overrides caster direction; the keep flag is parameter2 exactly equal to1. Level comes from parameter1 signed-short conversion or current evaluation level. Duration remains the common Qe timing/retention contract, with `bbR` unregistering the area only when Ty and not keep.

The packet wrapper carries the actual action family, and common running-effect field7 carries the actual non-null target. eYQ additional fields remain level14, direction16, keep17 and area UID21. Existing family315 packets are unchanged.

`NativeEffectAreaHandler` now accepts verified eYQ owner configurations instead of a single numeric family, validates actor recipients against the registered actor/area PV populations, and preserves actual family/target in packets and retained owned rows. Unsupported area subtypes remain explicit.

## AURA is a separate lifecycle boundary

The currently uncovered class effect308018 references prototype1527, an AURA (type4), ring shape1–1, properties3, entries10000/10001/10006 and exits10002/10011. This is evidence for identifying the outstanding case; there is no implementation exception for either identifier.

Its original subtype is `bcD extends faN`, not faY or faZ. `faN.bcz/bcA/bcB` resolve the actual owner coordinates; its coordinate setter is a no-op. Thus an aura follows the actual owner and must not be registered as a fixed glyph footprint. It ignores actual-owner movement entry/exit10001/10002, special-cases owner event10004, and otherwise delegates the generic faV lifecycle. `faN.c/n` selects the actual supplied event recipient; e(amP) is true. Its bcT registration callback is a no-op. bcD adds actual client visual actor tracking.

The shared registered-area resolver, guard consumer, event callbacks and geometry currently support only faY/faZ. Enabling AURA requires an authoritative faN owner anchor, refreshed footprint at every query/event boundary, subtype trigger filtering, and actual registered PV/Qf metadata. Relabeling it faY would erase real movement and recipient semantics. The present patch deliberately retains the unsupported subtype boundary pending those common producers/consumers.

Validation: four new configured codec tests and four existing area codec/removal tests pass; both changed production modules compile. No services were touched.

## Implemented faN boundary

The creator now records actual `native_area_contract=faN` for AURA, immutable `native_anchor_id=owner_id` and `native_anchor_source=faN.bgZ`. It preserves the original running-effect target/family separately from the area owner and cell. Common `_rows` query and registered-PV/Qf boundaries refresh the projected owner coordinates and shape footprint through `refresh_area_geometry`; missing owner/provenance rejects explicitly. The actual Qq fresh lifecycle guards and optional property12 Qf remain independently verified.

`NativeAreaEventRuntime` now applies the exact faN owner10001/10002 BitSet suppression both for movement delivery and native running-source delivery, including the entire parent faV callback/removal path. Other recipients follow the existing generic faV mask/charge/state cleanup contract. No owner movement rescan or synthetic entry event is invented: Qs native movement delivers only its actual moved PV through entry10001/internal10008/exit10002 lists. The unimplemented special owner10004 event producer remains unsupported.

Four new unit tests validate owner-following geometry and area range queries, current registered PV position, fresh null-Qf and Qq provenance, missing anchor rejection, and own movement suppression versus another actual recipient. The existing codec tests remain unchanged. Retained effect records must preserve actual configured family/target in central retention consumers; older numeric315 assumptions in those separately owned modules were reported to root.
