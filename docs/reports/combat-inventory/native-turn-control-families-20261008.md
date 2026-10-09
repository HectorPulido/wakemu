# Native turn-control families and area snapshot dependency

## Family inventory

The original registration owner table maps 308 to `eYW`, 666 to `eWl` (lowercase final letter), 667 to `eXf`, and 668 to `eWL` (uppercase final letter). These names must remain distinct even on case-insensitive filesystems. They are not a single invisibility mechanism.

- 308 extends `eYQ`: after area creation, it copies source characteristics into the actual new area. The shared constructor now supports native `bcY`/`fbc` traps, including their ten actual damage/healing characteristics, ordered `PA.nG` additions and native bounds. Plain `faV` subtypes retain the native early return when they do not expose `sgQ`; walls validate their captured constructor level before that guard. Trap activation uses the area center and the original owner/current-turn movement guard. The owner-entry constructor/activation/exhaustion sequence passed in run02 below; independent enemy displacement passed in enemy01 below; live client acceptance remains pending.

Trap exhaustion uses the explicit Wakemu policy `wakemu.successful-activation.Qq.baD-v1`. The original native predicate is exactly zero remaining activations and no execution in progress. Its server cleanup caller is not present in the inspected client implementation. After a successful activation and child-retention capture, Wakemu applies that predicate to the same registered area row and invokes the existing central removal path. An exception does not invoke cleanup; an already removed area is not removed again. Central removal preserves surviving Qf/manager identities in the retired manager domain. Run02 below verifies that policy through actual owner movement.

The shared damage runner also preserves actual partial PVs. Original `eXt.C` returns before arithmetic when the target has neither `ffw.sgC` nor `ffw.shQ`; `eXt.c` then calls `mu(true)` and returns without resource consumption. Verified trap constructors expose ten damage/healing PCs and neither resource, while plain `faV` constructors expose no PCs. These targets now complete the surrounding four lifecycle phases without a damage packet, HP invention or block roll. The skipped `fOG` call does not add indirect event2268. Original `Qq.baB` returns null, so no `Sl.o` back event29 is derived from an invented area facing. Unknown characteristic constructors remain rejected.

Actual constructor/lifecycle evidence now includes immutable Sram run02: ordinary Ready grants5182 at level200, normal2AP+1WP cast creates TRAP778/UID226 with charge1, and legal owner movement activates the original children and removes the exhausted spatial area while preserving retired manager226. The actual final owner position remains its entry cell, so this run certifies owner activation and exhaustion, not a two-cell enemy displacement. `sram-trap-manual-02.json` SHA256`d598aedef0c557b917f6ed24b5502b7065445a24423c8eb4f89997f4481493ef`, source stable. Enemy activation is verified by enemy01 below; client acceptance remains pending.

Immutable enemy01 subsequently verifies the independent NPC route: origin(-22,-143,70), legal movement through(-22,-142,70) to trigger(-23,-142,70), final(-23,-140,70). This is the measured two-cell +Y displacement from the triggering cell with current callback source owner7 at(-23,-143,70). The spatial trap is removed and no surviving manager remains in this variant. This direction follows the explicit current server callback source; it does not establish the absent original server's caster-selection implementation. Report SHA256`749f8c2b9152711d983116fa7f628a6063edcdf710413da5daa41d2a6290f31a`, source stable. No HP-damage claim is made because that report does not capture before/after HP. Live client acceptance remains pending.
- 666 now computes an `SQ` relative position and inserts an additional turn through the source-backed current-cycle producer. It preserves both the raw `eWl.c` position gate and the separate modulo-slot gate in `Tc.p`; duplicate turns are removed by the existing native base-order round reset. Removing the retained runner does not reverse its already inserted turn.
- 667 controls start/end phase dispatch using the target fighter's `eGj.frN()` BitSet.
- 668 has an empty application method. Its retained presence and `fNF()` boolean influence a separate turn-duration consumer. Treating it as a generic stat mutation would invent its effect.

## Implemented shared 667 contract

`combat_turn_suppression.py` executes the source-backed `eXf` state, with retained ownership and removal wired into the central factory and retained runtime. The fresh characteristic installation captures the native empty `eGj.pGO` BitSet. Missing restored state remains unknown.

`eXf.C` starts with both booleans true. Exactly one logical parameter with value1 selects start only; value2 selects end only. Other values or arities preserve both. Application sets bits1/2, and `bbR` literally clears the selected bits. It does not reference-count overlapping effects. Unrelated bits remain intact.

The native `big.dnz()` guard differs from HP and `baF`: it requires native fight attachment/identity and `pGz`. The owned registration boundary corresponds to `eGj.a(fcb)` writing `pGz=true`; the explicit retirement boundary is separate from `OFF_PLAY` status. The actual detached summon constructor has no attached fight, so the application skips that mutation without inserting a fake actor into the roster.

The normal turn-event policy consults this state before local/reversed/global phase delivery, records a suppressed boundary once, and preserves the independent timed-expiration path. Original `fbX.A/z` checks these bits before armor resets and `fcT.A/z` dispatches `QP/QO`. This change reproduces suppression of the existing server phase delivery; it does not add previously absent native armor-reset machinery or change independent area/timer ownership.

The evaluated 12613 running-effect payload contains native `iN` field8 wrapping `ij` boolean fields17/18, which `eXf.f(iN)` restores. Retained removal uses the same serialized payload and 13560 path.

## Verification

`ProbeNativeTurnSuppression.java` loads the actual original `eXf`, verifies fresh defaults, serializes all four boolean combinations through its protected serializer, and restores them through the original decoder. Bounded 64MB JVM: **12 assertions PASS**, process terminal exit0. Partial protobuf construction is intentional because this probe tests the nested runner state independently of required running-effect identity fields; it avoids reflective generated-name lookup in the obfuscated protobuf classes.

Python source and regression files passed AST validation. The delegated immutable-snapshot suite is pending; no live server restart or manual class acceptance has been performed.

## Implemented 666 and shared round dependency

`combat_additional_turn.py` is registered in the normal factory with central retained ownership and removal. `SR.pv` maps0 to current fighter,1 to timeline beginning, and every other integer to the effect caster's first timeline position (or -1 if absent). Addition follows signed-int overflow. `eWl.c` rejects the raw position at/before the current fighter; `Tc.a` then applies floorMod by current list size+1, and `Tc.p` independently refuses a slot at/before its cursor. Both guards are preserved.

`ProbeNativeAdditionalTurn.java` records45 original `Tc`/`SQ` observations across five modes and nine offsets, including int boundaries. The raw gate is transparently transcribed from `eWl.c` bytecode; the slot computation and list mutation run in the original native classes. The pure Python insertion function matched all45 observations (AST-isolated comparison without runtime catalogs).

The previous turn-message code derived the global round from an actor's activation count. A duplicate turn could therefore expire round-owned effects prematurely. `Fight.native_timeline_round` now advances at actual list wrap and marks the first cycle once, while the per-actor activation/ACK counter remains independent. Turn-start/end expiration and recovery use this cycle producer. The new regression executes a duplicate turn and verifies a single round cleanup until the actual cycle completes, then verifies native base-order restoration and the next round.

The delegated Python runtime suite remains pending. A bounded constant-pool scan finds no typed `eWL`/`fNF` turn-duration consumer in the installed client beyond runner registration. The separate server policy below is therefore explicitly identified rather than attributed to missing original-server code.

## Authorized Wakemu duration policy for 668

`combat_turn_duration.py` preserves the original `eWL` constructor/C contract: defaultfalse; exactly one logical parameter equal1 sets `rCi=true` on an attached native fighter; original application itself is empty. The retained row carries this marker, and normal removal deletes it without changing a currently granted timer.

The user-authorized server policy `wakemu.previous-granted-turn-duration-v1` consumes the first matching668 record in the actual current fighter's Qf population. It keeps the previous fighter's granted duration when `rCi=false`, or adds it to this fighter's configured base when true. The first slot in a native timeline cycle has no preceding fighter and uses the base duration. This policy uses the preceding granted duration, not unobserved original-server time distribution or remaining clock time. Multiple markers use the first native population entry; this is an explicit policy choice, not a discovered original server callsite.

The selected duration is recorded once per actual turn ID and actor. Start packets13337/13482, server deadlines, and recovery consume that same value, so recovery or repeated serialization cannot add duration again. Missing authoritative retained population or malformed marker/history rejects rather than inventing a timer. Tests cover arity, keep/add, first-fighter behavior, current Qf ownership, once-per-turn recovery, overflow, actual marker application and removal.
