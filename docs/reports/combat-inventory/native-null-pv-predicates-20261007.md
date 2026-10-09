# Explicit-null native predicate recipients

## Native contract

Targeted original bytecode inspection uses `javap -c -p` against `client/lib/*`; no running server is involved.

- `eNv.a` (`IsCarried`) resolves an eHg with `eII.b`. Only an `eHH` can report carried status (`buX`). Null and a registered faV area are not eHH, producing native -1 (false).
- `eNw.a` (`IsCarrying`) resolves a typed eGj through `eII.a`. Its null result produces -1; otherwise `frA` reads the actual carried-actor reference. `eII.a` rejects a non-eGj eHg, including a registered area.
- `eND.a` (`IsCharacter`, lexer token301) returns -1 for null; otherwise it checks `eHg.a(eHh.pNi)`. pNi is CHARACTER. `faV.a(eHh)` delegates to EFFECT_AREA pNm ancestry; EFFECT_AREA has no CHARACTER parent.
- `eME`, `eMF`, and `eMG` resolve the selected eHg, then, if null, try context `ePy.fyI`. They return -1 only when that fallback is also absent. Qe/eZR do not implement ePy. A generic condition context without an explicit fallback fact remains unknown.
- A faV area remains a non-null eHg even with null Qf. `faV.rb` returns null immediately for null bax; state presence/equality tests consequently return false. The snapshot can attest empty state query results without inventing a state ledger.

## Producer and consumer boundary

`ConditionContext.null_actor_aliases` records proven null selectors independently from absent actor snapshots. `state_null_fallback_absent` separately attests the ePy fallback boundary. Predicates use these facts individually; no general unknown-to-false conversion exists.

The runtime adapter sources caster/target/controller and triggering caster/target identities from their explicit invocation or native trigger relationships. A literal None is recorded as null. A non-null identity must resolve to its authoritative registered actor or registered area PV; failed resolution raises instead of becoming null. A missing trigger relationship key stays unknown. Registered areas get native nonfighter/CHARACTER/carry type facts; actual Qf state snapshots remain distinct from the null-Qf state-query case. Fighter carry metadata and its existing unsupported nonempty-producer guards are preserved.

Verification: six focused unit tests cover null versus missing snapshots, ePy fallback authority, native typed nonfighter rejection, and preservation of actual true carry facts. No world, Docker, database, or AI operation was used.
