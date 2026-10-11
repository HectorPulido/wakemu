# Ordinary NPC native initial-state construction

The ordinary constructor now reads exact `initial_state_triples` from the activated NPC policy record, bounded by its validated minimum/maximum level. Existing records without that component preserve their prior empty initialization; explicit malformed components reject. NPCs outside that cohort retain their existing behavior. No character decks or spell ownership are synthesized.

## Native evidence

- `.runtime/local/bje-target-context.txt`, `bje.aQc`: hydrate `blj`, load its ability book, call `c(blj)`, then `a(eGH)`.
- `.runtime/local/big.txt:1600`, `big.a(eGH)`: consume `cle()` short triples; level `-1` inherits `cmZ()`; pass flag `==0` to direct eWu construction; use SELF caster, null retained parent and `rBr` resistance bypass.
- `combat_summon_initialization.install_initial_states` already implements that shared big constructor, including permanent-state validation and actual retained child dispatch. Its detached scope enforces the real actor, SELF controller/recipient, team `-1`, obstacle `-1`, and a matching native state ledger.

## Implementation and proof

`combat_npc_initialization` constructs ordinary authority (`is_summon=False`) and executes the existing shared initial-state producer before native QI registration. It uses the imported NPC compiled effect catalog alongside the shared state definitions. Fresh ordinary breed fight/world property lists supply complete counters before constructor effects execute.

`initialize_fight_snapshots` runs this work on a deep private preview only when nonempty activated plans exist. Rejection preserves live actor identity, stats, ledger, effect UID and owned effect maps. Successful execution adopts the preview while retaining existing actor object identities. The producer emits `fight.native_npc_initialization_receipts[actor_id]` only after all states and their mandatory children execute, recording reference, descriptor level, raw triples and exact resolved state plans.

State application and current-stat guards admit only the actual detached SELF constructor without an active turn. They preserve all ordinary active-fight, source/target, characteristic, life and execution guards. No phase, turn counter, target or timeline is fabricated.

Eight focused tests pass using the read-only configured runner:

```
.runtime/local/verification-venv/bin/python .runtime/monster-failure-triage-20261010/run_selected.py test_combat_npc_initialization
```

The tests cover exact triple interpretation, activation bounds, malformed input, detached SELF scope, duplicate/registered scope rejection, source-qualified state application, unchanged empty-plan execution and constructor rollback. They are orchestration/guard tests; native candidate audit remains the acceptance authority.

## Native candidate proof and remaining unsupported branches

Probe 6 validated actual construction for 19 of 21 candidate references with initial states. All successful receipts include each direct state's actual `applied=True` return; a false/missing application aborts the private preview. The remaining two references reject on unsupported native eWV actor context and a finite initial-state timeline. The diagnostic is `.runtime/monster-pending-activation-20261010/constructor-probe.json`; earlier failed probes are retained separately.

The adapter now leaves the constructor cell context unknown when no QI exists. An actual eOV condition still rejects that unknown; unused cell context no longer demands a fabricated population. Retained groups accept actual detached SELF/caster-manager construction for known flags. Native `eYg.bcd()` returns true unconditionally, and the full eYg/eZR bytecode contains no rwN access. Native eVl identifies ID17/rwN as `BUFF_BYPASS_OUT_FIGHT_MAX`, rather than a combat-required flag; the constructor group guard therefore permits that unread flag while preserving normal active-fight requirements and the characteristic consumers’ actual cap/context guards. Extracted native evidence is in `.runtime/monster-pending-activation-20261010/{eYg,eVl,eWQ,eWR,eWt}-constructor-proof.txt`.

Finite state/effect clocks remain unsupported at this pre-timeline boundary and continue rejecting. A constructor requiring an actual QI cell query needs native source evidence; an unused criterion context must not force an invented QI population. Rift reinforcement construction has a separate admission path and has not yet been integrated with this ordinary initial-placement producer.

## Native client admission and retained bootstrap delivery

Read-only native inspection found that admission overlays the existing world actor rather than invoking its constructor again. `aVH.cXi` resolves `bio.jv(id)`/`fkK.sY(id)`, then calls `big.a(buH, stats, effects)`; it contains no fresh bje allocation or aQc call. Initial bootstrap `ckP` likewise resolves existing world actors before constructing the fight.

However, `big.a` first calls `dq(effects)`, which delegates to `eZV.a(byte[], PN)`. That native method clears the entire existing Qf population before decoding the incoming remote effects. Thus an empty placement myF would erase descriptor initial-state retention even though the server and serialized characteristics already contain its results. Replaying constructor notifications is not the solution.

The server now uses the existing full retained-effect serializer for receipt-qualified ordinary NPCs during placement. A private read-only serializer core serves both the unchanged active entry and a new placement entry that validates exact successful constructor applications. Controlled players and NPCs without receipts retain the prior empty placement payload. The central placement envelope and session admission both preserve these effects; the direct host fallback uses the post-constructor NPC characteristic snapshot as well.

Native `Qe.bbq()` only clears the bfD execution flag; `bcu.C` uses that reset and notification registration rather than rerunning the constructor. The ensuing `big.ev(stats)` deserializes the authoritative characteristic snapshot. These native methods support restoring Qf alongside current stats without a second cle application.

Native evidence files are `.runtime/monster-pending-activation-20261010/{aVH,ckP,bcu,eZV,Qe}-fight-overlay-proof.txt`, plus `.runtime/local/big.txt:3877` and `.runtime/java/eGj-bytecode.txt:2128`.

The dedicated placement probe serializes and decodes actual native retained effects before `Fight.ready`: 19/21 constructor references pass, with the same unsupported references 3510 and 5708. Evidence: `.runtime/monster-pending-activation-20261010/constructor-placement-probe.json`. Fourteen focused and existing remote-envelope tests pass; full native activation audit remains required before publication.

The host path rebuilds its pre-construction placement packets when either heroes joined or ordinary NPC constructor receipts exist. A new structural regression covers normal NPC fights without heroes, so post-constructor stats and retained effects reach that path as well. Empty-initialization NPC fights retain the previous bootstrap path.
