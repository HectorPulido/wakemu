# faW characteristic constructor blocker

Offline source audit. No runtime modifications or activation claims.

## Concrete representative2690

The failed spell3843, evaluated at141, reaches normal chain101926→101927→101928 and critical chain101930→101931→101932. The leaves are family339, parameter area566. Its native `bcQ`/FAKE_FIGHTER definition has raw_bdh `[0,8,0,1,1,1,0,1,0,-1]`: it creates an 8HP characteristic, blocks movement and visibility, owns a running-effect manager, disables owner activation and allows other activation.

Installed `faW.aQc` does not treat this as a plain area. At offsets95–107 it includes `ffw.sgC` when p1 differs from-1;193–218 construct `eRF` and call its default initialization. Offsets407–464 compute Java float32 `p1 + level*p2`, cast to int, set `PA.or(maximum)`, then `PA.aZf()` resets current value from the initialized maximum. Discarding this PA would create an indestructible or incorrectly targetable obstacle, so the rejection must remain until the actual resource producer exists.

## Shared pattern across seven references

| References | Spell | Areas | Constructor branches |
| --- | --- | --- | --- |
|2690|3843|566|HP=8, no damage snapshot PC|
|2770,2795|4004|614,616,617,618|HP=100 plus ffw.sgQ damage PC, copy mask0|
|2771,2797,2824|4012|614,616,617,618|Same|
|2774|4020|614,616,617,618|Same, normal and critical leaves|

Machine-readable exact effect paths/parameters: `.runtime/monster-blocker-recovery-20261011/faw-characteristic-branches.json`.

## Required general primitive

Reuse the source-backed eRF characteristic model established for traps, but produce an actual faW-owned PC set and current/min/max records from the native subset. This must include constructor level authority, float32 arithmetic, ffw/fff defaults, p9 owner-copy-mask handling and optional four-parameter characteristic records. Missing owner PCs must follow native absence branches rather than defaulting arbitrary values.

Current trap installation handles a sealed fixed fbc subset, not dynamic faW PCs. Current `group_pa`, `area_damage_guard`, `area_damage_snapshot` and `NativeAreaTarget` intentionally have no qualified nonempty faW characteristic lifecycle. These consumers must receive actual area-owned authority before enabling the constructor: target selection, damage/death/removal, state/resource effects and snapshot copying cannot borrow ordinary fighter values.

This is one reusable missing primitive affecting all seven references, rather than seven spell-specific failures. It is larger than a safe constructor allowlist change. No runtime rejection was relaxed and no existing tests were changed. Installed source evidence: `.runtime/local/native-fake-fighter-faW.txt`.

## HP-only producer prototype qualified independently

`combat_fake_fighter_resources.py` now contains a pure HP-only producer. It requires actual bcQ/type15 identity, a signed native container level0..32767, exactly ten parameters, p1!=-1 and p9=-1. All damage-copy/optional characteristic branches remain rejected. It performs separate float32 multiplication/addition and Java saturated truncation, and emits the actual current/min/max/absolute bounds without admitting the area to combat.

An installed Java subclass invokes the real `faW.aQc` (not a rewritten constructor). Sixty differential cases cover levels0/1/141/32767, base values8/0/-2/100/16777216 and per-level0/.1/.184. All generated PA records match Python. Native HP characteristic ID1 has minimum0 and absolute maximum2147483647. Four NEW pure tests pass, including exact area566 8HP and continued runtime constructor rejection. The sealed native fixture is `server/tests/fixtures/monster_faw_hp_native.json`; private oracle `.runtime/monster-blocker-recovery-20261011/faw-pa/ProbeFakeFighterPA.java`.

### Minimal integration boundary (not implemented by this prototype)

- `combat_fake_fighter.py`: admit only the qualified HP-only branch when a level and persisted producer receipt exist; continue rejecting p9/optional records. Preserve every obstacle/QI and immutable constructor guard.
- `combat_effect_area.py`: create the actual PA receipt plus mutable current HP before callbacks/publication, analogously to fbd. Existing plain faW snapshots remain unchanged.
- `combat_group_pv.py` and area state/resource consumers: resolve present HP1 to the owned PA and absent PCs to native null, rather than borrowing a fighter snapshot.
- `combat_area_damage_guard.py` / `combat_damage_handler.py`: reuse registered-Qq architecture from walls with an HP-only snapshot. A faW has no wall resistance/damage PCs: these must remain absent, not copied from fbd's fixed table. Damage and retained events must keep actual area identity and mutable HP.
- `combat_runner_target_life.py` / lifecycle: native `faW.baD` first delegates faV.baD, then tests present HP<=0. Qq baG/baK and QI registration are separate and must not be equated to zeroHP. Removal uses the existing actual Qq callback/manager lifecycle.
- Checkpoint/rollback: persist and deep-copy owned current/min/max/source in the existing native_effect_areas containers, validate restored receipts before use, and test mutation→rollback plus removal/replay. No extra live monster roster entry.

The larger 100HP+sgQ branch can use the same representation once native damage-PC defaults and owner-copy logic are proved; its p9=0 still creates a real PC and cannot be treated as absent.

## HP-only integration gate

The shared implementation now supports the qualified branch behind the explicit `NativeEffectAreaHandler(fake_fighter_hp_enabled=True)` producer policy. Its default remains false; the normal combat runtime has not yet enabled it at this gate.

- Creation stores a JSON-safe immutable PA constructor receipt and separate mutable current HP before callbacks. Existing native fakefighter/QI manager checks remain authoritative.
- `group_pa` returns actual HP current/max and native null for absent PCs. The damage-copy guard proves the HP-only area has no sgQ.
- NativeDamageHandler's registered-area route supports qualified faW resources using exactly `{1: currentHP}`; it does not synthesize the wall's eight additional PCs, fighter armor, barrier or virtual HP.
- Damage changes owned area HP and emits ordinary12613 packets while keeping area identity out of Fight.actors. ZeroHP does not automatically unregister Qq/QI; the actual owned removal callback still performs that separate operation.
- `fake_fighter_hp_wire` matches native faW.fTl maximum/current int32 bytes. Java real-area lifecycle with actual raw_bde=-1 confirms HP8/3 has baD=false, HP0 has baD=true, and baG/baK remain false in all three cases. An earlier unconfigured Java prototype had default bfB=0 (expired); the final lifecycle oracle sets the actual area's unlimited activation count before testing.
- Persistent resource receipts survive actual `_plain` checkpoint encoding and JSON decoding. Fight checkpoint recovery intentionally marks interrupted fights aborted rather than resuming a native timeline; no new recovery behavior is introduced.

Four NEW integration methods cover actual creation→registered PA→damage8→3→0→native HP bytes→deepcopy rollback→owned QI removal, absent-PC guards, checkpoint resource receipt/tampering and disabled default/damage-copy rejection. Combined with the four producer tests and six untouched original fakefighter tests,14/14 pass in the isolated native catalog harness. Receipt `.runtime/monster-blocker-recovery-20261011/faw-pa/integration-tests.log`.

The historical extracted owner registry had unqualified null bbA/bbB entries for315/339. The isolated harness now uses real installed eVi registry runner calls proving both have bbA=false and bbB=true, with only those two fixture rows supplemented. Proof `faw-pa/ExportAreaOwnerFlags.java` and `area-owner-flags.txt`. This is a local test authority supplement, not live catalog equivalence or publication.

## Offline runtime integration

Independent Luna validation passed14/14core and20adjacent tests with stable selected-source hashes. Four additional adjacent cases could not run because historical offline fixtures lack native-trap-characteristics and native-trove-byte-set catalogs; these are fixture-availability errors, not passing assertions or confirmed runtime failures. Receipt `.runtime/monster-blocker-recovery-20261011/offline-faw-hp-integration-tests.json` and companion log.

After that gate, the shared runtime now explicitly constructs NativeEffectAreaHandler with fake_fighter_hp_enabled=True. Other standalone callers retain defaultfalse. No further behavioral changes were introduced by wiring; syntax compilation passes. Actual2690 full native replay remains pending because sandbox PostgreSQL access is unavailable; no monster activation readiness is claimed and no catalog/service was changed. The p9damage-PC branch remains rejected.

### Adjacent fixture gate closed

Existing Java exporters supplied the missing native trap characteristic contract (10PCs/70 setter observations) and Trove byte-set contract (12000 native lifecycle oracle steps) in the private isolated harness. Only the four previously errored adjacent methods were rerun;4/4 pass. With the earlier34 passing methods, all38 scoped core/adjacent methods now have clean passing evidence. Original failed bootstrap output is preserved. This does not resolve live catalog equivalence or substitute for native2690 replay.

## Zero owner-copy mask producer and integration

The six remaining references use actual areas614/616/617/618, each with raw parameters `[0,100,0,0,0,0,1,1,0,0]`. Native faW.aQc installs both sgC(1) and sgQ(20) when p9=0. Zero is an empty owner-copy mask, not absent damage-PC authority. The actual sgQ defaults are current0, minimum-5000 and maximum50000, including its absolute bounds. Forty-eight calls to installed Java faW.aQc cover float32 arithmetic and those defaults; sealed fixture `server/tests/fixtures/monster_faw_hp_damage_native.json`.

The shared resource producer now preserves both actual PA records, immutable constructor authority and separately mutable currents. Registered group lookup, target-health operands and damage snapshots consume this presence without inventing other PCs. Damage/death, rollback and owned removal reuse the already qualified HP path. A separate default-disabled producer policy admits only normal eYQ315 creation after all preflight checks. eYW308 still rejects before UID allocation because its elemental/snapshot copy authority is not implemented; direct snapshot copying also fails without mutation. Nonzero masks and optional characteristic records remain rejected.

Seven NEW pure/integration tests pass locally, covering all four real definitions, exact PC20 bounds, actual registered health ordering, damage to zeroHP, rollback/removal and eYW rejection before allocation. Receipt `faw-pa/zero-copy-integration.log`. The private historical owner fixture was supplemented for308 using installed eVi runner bbA/bbB calls, in addition to the previous315/339 proof. No active catalog was changed. Independent gate is pending; the normal runtime zero-copy policy remains disabled at this writing. The six references require actual native replay before any activation-readiness claim.

### Zero-copy independent gate and offline wiring

Independent Luna gate passed21/21 methods: seven NEW zero-copy methods and fourteen affected HP producer/core methods, with stable source hashes. Receipt `.runtime/monster-blocker-recovery-20261011/offline-faw-zero-copy-tests.json` and companion log. After that gate, the normal runtime explicitly enables `fake_fighter_zero_copy_enabled=True` alongside the existing HP policy. This is the sole post-gate source wiring change; syntax compilation passes. Standalone handler defaults remain false. No deployment, live catalog mutation or full-reference replay was performed; six real references remain candidates for native replay rather than activation-ready monsters.
