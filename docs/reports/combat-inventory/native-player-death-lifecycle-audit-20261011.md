# Native player death lifecycle audit — 2026-10-11

## Concrete finding

Current `combat_death.death_messages` always emits fighter-state2 for a settled HP-zero player, but `complete_ordinary_qi_death` deliberately skips controlled/positive-ID actors. The resulting server OFF_PLAY corpse retains its QI obstacle while the client is instructed to finalize it OUT_OF_PLAY. This is a concrete phase mismatch; it does not establish that every player HP-zero transition should become final. Reversible resurrection requires OFF_PLAY, not OUT_OF_PLAY.

## Native source contracts

Bytecode is from the local original `client/lib/wakfu-client.jar`; this is client behavior, not a recovered original server death publisher.

- `/tmp/wakemu-native-aTS-death-source.txt`, `aTS.D(big)`: a fighter with `doI()!=null` uses `E(big)`, the fight-owned branch. Its state0 calls `buH.aC`, state1 calls `buH.be`, and state2 calls `aC` if not already `baG`, then `aD` once `baG`. State3 additionally sets `lC(true)` before the same finalization. There is no positive-ID, controlled-player or breed exclusion.
- `.runtime/combat-review-20261007/fcb-current.javap`, `fcb.aC`: OFF_PLAY transition (`fdt.bv` through `aN`), lifecycle `B`, then `baE`. `fcb.aD`: final transition (`fdt.bw` through `aO`), `baJ`, then `H`. `H` calls `aQ`, which invokes `QI.g(fighter)` to remove the obstacle.
- `/tmp/buH.javap`, `buH.H(eGj)`→`aS(big)` delegates to `fbX.H` before additional client callbacks. Therefore the native final-QI removal also applies to player `bje`, without the server helper's ID filter.
- `.runtime/xelor-readonly-20261011/native-fdt-death.txt`: `bu`, `bv`, `bw` request IN_PLAY, OFF_PLAY, OUT_OF_PLAY respectively. `native-fdy-death.txt`, `fdy.a(fdx)`, rejects transitions from a state other than the required predecessor. `native-fdx-death.txt`, `fXS`, explicitly maps required predecessors: IN_PLAY requires OFF_PLAY; OFF_PLAY requires IN_PLAY; OUT_OF_PLAY requires OFF_PLAY. Thus final OUT_OF_PLAY cannot be directly resurrected through the ordinary IN_PLAY transition.

The non-fight `aTS.F` only writes world/visual death state and is not interchangeable with the fight-owned transition above.

## Area lifetime is a separate contract

Do not remove all owned portals or microbots merely because their owner reaches zero HP.

- `/tmp/buH.javap`, `buH.B(eGj)`→`bg(big)` delegates to **`fbX.B`**, an override of the simpler base `fcb.B`.
- `/tmp/fbX.javap`, `fbX.B`, performs source-specific running-effect cleanup and calls **`Qs.l(owner)`**.
- `.runtime/xelor-readonly-20261011/native-Qs-death.txt`, `Qs.l`: selects only areas owned by that exact PV **and** with `Qq.bcY()==true`. The verbose dump `native-Qs-verbose-death.txt` BootstrapMethods5 resolves this predicate to `Qs.a(PV,Qq)`; BootstrapMethods4 for `Qs.k` resolves to the different owner-only predicate. Confusing these methods would wrongly delete persistent areas.
- `native-eYQ-death.txt`, `eYQ.C`, reads index2 into `rGS`; `eYQ.d(faV)` sets `area.bc(!rGS)`. `Qq.bc` sets the field returned by `bcY`. Therefore **keep_after=true excludes the area from this OFF_PLAY cleanup**.
- `eYQ.bbR` also removes its created area only when `!rGS && Ty()`. The server `combat_retained_effects.area_remove` mirrors this rule with `executed && !keep_after`.

The current published metadata snapshot `.runtime/steamer-review-20261011/portal-microbot-lifetime-source.json` alone reports empty entry/removal masks for823/978; empty masks do not prove a missing owner-death producer. Actual created row `keep_after`, ownership and the precise death phase must be captured. A finalization-specific additional override may still require separate investigation; this audit does not claim all final area behavior qualified.

## Current server producer and resurrection constraints

`Fight.damage` registers an actual adjacent damage/death pair and sets OFF_PLAY. `combat_death_events.deliver_owned_death` requires exact guards `(baF=False,baG=True,baK=False)`, publishes KO1010 then death1013 using an explicitly documented Wakemu consumer-backed policy. Those events are not proof of the original server's finalization timing. `combat_death.death_messages` subsequently emits state2 for all players and NPCs, while only ordinary NPCs are finalized in QI/server guards.

`combat_resurrection.prepare_resurrection` currently accepts OFF_PLAY and requires its retained indexed QI slot; OUT_OF_PLAY is intentionally final. Therefore simply removing the player exclusion everywhere would disable current resurrection after settled delivery. The generic fix must first distinguish **reversible state0** from **explicit final state2**. HP0 or KO1010 alone must not decide finality.

## Runtime-only candidate and required regression expectations

A candidate helper is staged at `.runtime/native-pc-death-audit-20261011/combat_ordinary_qi_retirement.py`. It removes the unsupported controlled/positive-ID checks and requires an explicit keyword `fighter_state=2` before final QI completion. Summons remain on their separate verified lifecycle. This is unintegrated and untested; callers must supply the actual requested state, and no production source was edited.

Required generic regressions:

1. Actual damage to a controlled positive-ID fighter, with a living ally keeping combat active: reversible state0 leaves OFF_PLAY, indexed QI and saved resurrection position; valid native resurrection restores IN_PLAY and a legal future turn. Do not infer this from raw HP0 snapshots.
2. Explicit final state2 for the same actual corpse: remove QI exactly once, set OUT_OF_PLAY, retain fighter history, reject ordinary resurrection. Repeat for an ordinary NPC; no breed or ID-specific branch.
3. Unknown HP0/IN_PLAY snapshots and unregistered deaths cannot acquire retirement receipts; failure rolls back QI, guards, packets and RNG.
4. Capture actual owner-area rows before KO. OFF_PLAY removes only matching-owner `bcY=true`/keep_after=false areas, preserving foreign-owned areas and keep_after=true areas. Validate real native source cleanup rather than asserting all823/978 must vanish.
5. Finalization, fight settlement and complete client reconnect require distinct tests: no stale live obstacle, no duplicate death delivery, no trapped timeline, correct owner lease/group/dungeon cleanup. Area lifetime after finalization remains qualified separately from OFF_PLAY.

## Authorized coherent wire-policy candidate

The parent authorized preserving the existing reversible player resurrection policy and aligning wire delivery with it. The staged `combat_death.py` now defaults controlled-player registered deaths to **state0**, preserving OFF_PLAY/QI. An explicit `fighter_state=2` request finalizes a real ordinary corpse, including positive-ID controlled players; a prior reported state0 permits that one later final transition, while duplicate state0/state2 requests reject. NPC default delivery remains the official state0→state2 pair. Summons remain on their separate verified retirement path. No arbitrary HP threshold chooses finality.

The helper preserves the existing receipt source/schema for checkpoint compatibility and validates a requested state2. Existing direct NPC helper calls retain their previous implicit-state2 API default; production wire callers explicitly pass state2. No `native_death_status` change is needed: its existing state0 preserves `mwD`, state1 resets it, and state2 sets death status.

Three new staged regressions use actual NPC ability damage against the existing multi-player native resurrection fixture, with living allies keeping combat active. They check reversible KO wire0/QI/resurrection, explicit final wire2/QI removal/ordinary resurrection rejection, and duplicate/unregistered/interrupted removal rollback. Existing native resurrection interruption/turn/second-death tests and NPC capture/QI tests are requested in the same serial Luna validation. Candidate validation is pending; server source and services remain unchanged.

### Review corrections before validation

The KO default is limited to controlled **ordinary players** without `native_summon_source`; controlled summons retain their verified default final-state2 path. A small wire-classification control covers this exclusion without claiming new summon gameplay qualification.

The first candidate's runtime-only stage dictionary was removed. `combat_native_death_status` now records actual state0/state3 delivery in its existing checkpointed `last_writer` field while preserving `mwD`. A new RuntimeMessages instance can derive a previous KO and permit one explicit final transition; resurrection writes state1, so a later genuine death starts a new cycle. The checkpoint store serializes actor dictionaries, including this existing field.

Before final QI commit, `death_messages` preflights the native status write on a private actor copy. The helper's QI registry is private (`NativeQIRegistry` deep-copies slots and byte topology), and the candidate computes all serialized QI outputs before committing global status, actor slot and retirement receipt. Existing pure legacy synthetic tests without native global authority retain their documented compatibility path; real native-owned HP0 requires registered adjacent damage/death provenance.

Current frozen candidates: death00cf9093, native-status ebab47da, QI-helper f75620f2, test f3288263. No production edits; serial runtime-overlay validation pending.

### Final atomicity and second-life checks staged

The wire candidate now serializes `_prefix`, both fighter-state bodies and `_flush` on a shallow runtime preview before final QI/global commit, preserving the real runtime action counter if serialization fails. Its prepared native death-status snapshot is assigned only after successful finalization. New failure controls interrupt both `serialized_slots` and byte-topology serialization after private registry removal, plus prefix/flush preflight; all must leave fight checkpoint, counter and reported identities unchanged.

The actual second-life test uses the existing production `RuntimeMessages.prepare_delivery` resurrection path, which already clears the resurrected identity from `_reported_deaths`; no redundant reset or writer1 bypass was added. It then applies actual NPC lethal damage again and checks state0 delivery with both the same runtime and a new runtime. Durable state0 provenance is used only for genuine KO→explicit-final transitions across runtime replacement.

Latest pinned bundle: death3726df0c, native-status ebab47da, QI-helper f75620f2, tests20ce6075 (five methods). Serial validation is pending.


### First serial candidate gate and baseline controls

The first current-release677 overlay ran26 tests without skips:22 passed, two failed and two errored. Four of the five new lifecycle methods passed, including fresh-runtime explicit finalization, interrupted serialization/QI rollback, controlled-summon default wire classification, and actual resurrection followed by a second lethal NPC attack. The remaining new method lost its PostgreSQL connection during Ready catalog loading, before its behavior assertions.

The existing resurrection test reached its second real death and failed only its old state2 expectation; the prepared replacement expects native reversible player KO0. Original source remains unchanged. Two other original-test failures were reproduced without the candidate: capture used a nonretained context but expected retained13497 instead of immediate12613; the QI-only spectator fixture lacked native characteristic metadata required by the actor serializer. These baseline results distinguish fixture problems from candidate regressions. The capture owner staged a qualified replacement and obtained3/3 passes.

A separate staged QI serializer fixture constructs a fresh same-ID NPC, installs the actual native5525 snapshot before damage, preserves its existing QI slot/property authority, and then exercises the original damage/retirement/reconnect assertions. It supplies real native wire metadata rather than relaxing serializer checks. This correction and the full candidate rerun remain pending.

Pinned additional staged test replacements: resurrection6196b3b8cb3e78ef037706ba9de2310834d87a4879f6050e3a7e272a0d535141; QI fixture42de8d98e538172fdcad90bc0236fb0c0eb7c69ec6c87d46c55326bf9b5af913. Initial gate evidence: `.runtime/native-pc-death-audit-20261011/bundle-final-result.json`; paired controls: `capture-qi-baseline-result.json`. No server source, migrations or active catalog changed.


### Corrected serial gate: PASS27/27

The qualified staged bundle passed all27 tests with zero skips, failures or errors on actual published release677, unchanged from start to finish. All five new PC lifecycle methods passed, including actual KO/resurrection, explicit positive-ID final QI retirement with a fresh runtime, private-QI and serialization failure rollback, controlled-summon wire exclusion, and the same/fresh-runtime second lethal lifecycle. Existing NPC death, native death status, controlled summon, Ecaflip summon, corrected native-wire spectator/reconnect, resurrection and retained/nonretained capture controls passed.

Terminal artifact: `.runtime/native-pc-death-audit-20261011/bundle-corrected-result.json`; log: `bundle-corrected-current.log`. Source-tree and migration hashes were unchanged throughout the overlay run. Candidate source remains staged only: death3726df0c50f4f717c09beef4a2e072169a4790df6e1cb523e8bb0ba9cbc9ceed, status ebab47daf45b5c9b8d6ef619930dfe14908445f509ec38f34e6bea7410c86d5d, helper f75620f21b80cacdeeae42884b40c898076306bcef5c7326ad61b3de72770826. This qualifies the lifecycle candidate for integration review; it does not claim a deployed fix or complete owner-area/manual client acceptance.


### Explicit withdrawal compatibility: separately versioned candidate

The broader18-class gate exposed three real withdrawal errors: `plan` first retires QI/global participation through `retire_pve_actor`, then writes HP0 and records `withdrawn`, not a damage/death pair. Requiring `registered_ordinary_death` for this distinct source rejects legitimate departures; default player KO0 also contradicts explicit departure. The original qualified3726df0c candidate remains pinned and unchanged. Withdrawal revisions are isolated under `withdrawal-v2/` and `withdrawal-v3/`, not silently substituted into that qualified bundle.

The staged96ca4478 death candidate accepts an independently validated `retired_pve_actor_ids` receipt only for explicit final-state2 delivery. It bypasses ordinary QI completion because typed departure already removed that slot. Uncertified flags cannot supply this authority; ordinary HP0 still requires damage/corpse provenance. The producer supplies explicit2. A further source branch requires final delivery outside `if target.hp >0`: an already-KO0 player also needs public final2 when withdrawing. Version3 includes this branch and an actual NPC-KO→withdrawal regression, alongside live departure, duplicate/new-runtime, malformed-authority and interrupted-encoding checks.

Version3 pins: death96ca44782a1d02131628c74f52cca13a170d1892ae4ad1fbdaa42ab94cf5cec8; withdrawalbd93d5c6808592841ed414bd321b28bf0e86a8d9b0a2e283a509356e54af2cf6; departure tests881cd6fd5fe462b56484007123298392a476cb4414bd8b583b5b2b426bf293c5. Qualification is pending serial paired controls and withdrawal plus previous27-test lifecycle gate. No server source changed.


### Withdrawal-v3 qualified: original30/30 and candidate61/61

Serial paired validation passed the30 original withdrawal tests unchanged, then all61 candidate tests without skips, failures or errors. The candidate combines the previous27 lifecycle controls,30 withdrawal controls and four new typed-departure tests. The actual NPC-KO0→explicit withdrawal case delivers public final2, removes the retained QI slot once and preserves surviving owners. Live withdrawal, new-runtime duplicate rejection, forged authority rejection and interrupted encoding also pass.

Artifacts: `.runtime/native-pc-death-audit-20261011/withdrawal-v3/baseline2-pg-result.json` and `bundle-v3-result.json`. Both runs used actual release677 unchanged at start/end;2310 source files and124 migrations remained unchanged. The earlier baseline runner import guard failure occurred before tests and was fixed in a separately versioned runner; its first successful test invocation lacked PostgreSQL-test opt-in and skipped seven cases, so the subsequent30/30 no-skip run is the accepted baseline.

Qualified replacement source remains separately staged: `withdrawal-v3/combat_death.py`96ca4478 and `withdrawal-v3/combat_pve_withdraw.py`bd93d5c6, with native status/helper unchangedebab47da/f75620f2. The originally qualified3726df0c death candidate remains preserved. No integration, server restart or deployment is claimed by this report.
