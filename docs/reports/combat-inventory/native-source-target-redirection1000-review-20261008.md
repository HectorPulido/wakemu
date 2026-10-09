# Native source target redirection (family 1000)

The original `eWK.C` reads an integer ratio (default -1) and a target-mode flag (true only for parameter 1 equal to 1). Its application first checks `Qe.bbs`, selects the actual triggering runner through `eZR.J`, then writes that runner's `bfs` through `Qe.f`. The caster and selected cell (`bfr` and `bft`) remain unchanged. A positive ratio invokes the actual source owner's amount modifier. Ratio -2 invokes `n(null)`, including calculation, modifier replay and context transfer; this branch remains guarded until those authorities are available.

The implementation binds execution-local target storage to the actual `NativeRunnerAmount` identity. Damage and healing bind it before their first event phase, refresh it before calculation, and refresh it after application-phase reactions before consuming resources and producing delivery packets. Event replay refreshes the source target between listeners. This is transient runner authority, not a persistent actor or retained-descriptor mutation.

`NativeRedirectRunnerHandler` is connected to the runtime factory, preparation, event lifecycle, retention and removal. Missing direct/PS source is a native no-op when no source was claimed. A claimed but missing or stale source rejects explicitly. Other source families without audited target consumption reject; the handler registration alone does not establish their execution coverage. Removal does not revert an already changed source target: the original runner has no such inverse.

The scoped inventory contains three definitions across class components 5 and 11 and captured component 2, with ratio 100. No per-definition exception was added.

## Verification

`PYTHONPATH=server:server/tests /tmp/wakemu-combat-review-venv/bin/python3 -m unittest test_combat_redirect_runner test_combat_damage_handler test_combat_healing_handler test_combat_trigger_value_modifier`: 40 tests passed in 0.221 seconds. New regressions exercise actual damage and healing consumers, target/caster/cell identity, stale source rejection, recalculation preflight rejection and preparation cleanup after native null-source application.

`sniffer/java/ProbeNativeRedirectRunner1000.java` compiles against the original client libraries and probes original `eWK.C/c` and `Qe.f` for nine ratio/mode cases, including `bbs=false`. Original native execution passed all nine cases and 27 assertions with a 128 MB JVM. No catalog or service was loaded. Client acceptance remains pending.

## Remaining source contracts

- Ratio -2 needs actual `n(null)` modifier replay and context transfer.
- Additional source runner families need audited consumers of their mutable `bfs`.
- Transformation family 933 needs its separate temporary-book identity and raw-reference authority; its scoped native profile export is independent of this change.
