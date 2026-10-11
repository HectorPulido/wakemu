# Native team-sized script repetition: family 1041

## Installed source and reusable primitives

The installed family-1041 runner is `eXM`, extending `eXN` and `eZM`. `eXM.G` returns zero for a null/non-`amO` caster, null/non-`eVw` context, or absent fight manager. Otherwise it obtains `fbX.bL(caster.bcM())`, subtracts one from collection size, and clamps to at least zero. `eXN.C` caps that result at 12. `eXM.H` is always false: empty or failed child PT results never stop later iterations.

The query is **not an alive-allies count**. `fcb.bL` calls `fdt.a(fdD.fF(team))`; `fdD.fF` creates `fdZ`, whose predicate compares only `fdy.bcM()` with the requested team. It does not test HP or IN/OFF/OUT status. The registered `fdt.saq` population determines membership; actual retirement removes an entry. Current team may differ from original team after native affiliation/controller changes.

`eXN.c` calls `eZM.l` once per iteration. The latter obtains the actual `fyE` script for the parent generic-effect reference, builds the eVt/PS context with `fPw=false`, and executes each script child in order. Because `eXM.bbA=true`, each child receives the actual target PV and that target's current coordinates, with the native explicit-PV argument. This is not a sequence of spell casts and must not use the cell-only family-949 target clearing.

## Local implementation

The existing `combat_repeated_group` typed-PT scheduler is reused; the dispatcher branch now handles 1041 separately when preparing its repetition specification. The optional `team_repeat_count` provider reads the actual global registered-fighter collection and the shared `combat_controller_registry.current_native_team` authority. It includes dead registered fighters, excludes explicitly retired fighters, and never infers current team from `actor.team` or HP. Missing legacy/detached current-team authority rejects. Null caster yields zero. Actual registered faV area casters implement amO through Qq; faV overrides Qq.bcM to return its own captured ebh affiliation. The helper requires the validated `faV.j(PV).bcM` producer receipt and reads that captured value, preserving it when the owner later changes team. Missing area affiliation authority rejects; it must not be replaced by zero or a live owner-team query.

The runtime binds this provider and the group subscription family list includes 1041. Child target PV, current target cell, PL level and eVt context remain explicit. Existing generic retained metadata and source guards remain required; missing native catalogs are not bypassed. No active catalog or registry-count document was changed.

## Evidence and qualification limits

Historical scope contains six companion definitions: 2828 Escario, 2830 Zíar, 2831 Cuerbax, 2832 Lúmino, 2833 Sombra and 3065 Protoflex. Five historically lack only 1041; Protoflex also mentions 1049. Existing sealed state effects are 108506/108513/108518/108528/108539/112548: each has no parameters and one actual script child. This is family scope, not proof of complete current monster execution.

The bounded installed-Java oracle `next-family-runners/ProbeNativeTeamRepeat1041.java` proves seven native eXN loop/cap cases and 12 actual fdZ/fdy predicate cases across teams and all native status values. Its loop subclass overrides only the supplied count and script-observer hook; the actual eXN calculation/execution loop is retained. It does not pretend to execute full native companion spells.

New tests additionally use the actual registration/controller producer APIs, prove dead-vs-retired membership and current-team mutation, preserve target/cell/context through dispatcher execution, exercise zero count and reject missing provider authority. Existing family-949 tests remain unchanged. Full initial-state/script closure replay, actual catalogs and activation remain separate parent-owned gates. No database, services or deployment operations occurred.

Final independent focused gate: 13/13 passed (five new 1041 tests plus eight original 949 tests), stable source hashes in `.runtime/monster-blocker-recovery-20261011/offline-team1041-area-final-tests.json`. The actual-created area test proves captured affiliation survives owner-team mutation and missing area authority rejects. The earlier ordinary-only receipt is historical, superseded by this final domain gate. No existing tests were edited.
