# Trigger caster and applied-state predicates

Original `eLD` (`GetTriggererEffectCaster`) accepts no arguments and reads the first native evaluation argument directly: null returns 0, a PV returns `Sn()`, and a non-PV throws `alA`. It does not read the triggering Qe caster. The shared evaluator resolves the authoritative caster PV identity and preserves known null versus missing authority.

Original `eLF` (`GetTriggeringApplyStateStateId`) obtains the source through `eII.aU` on argument3. Null and non-eWu return -1. An actual eWu returns its signed-short `ejo()` reference, independently of the source container's fyW reference. Its constructor does not validate or consume the supplied argument list; the shared route likewise ignores parsed arguments.

The actual state handler already passes its live `NativeRunnerStateLevel` through every source event phase. Replay now snapshots that controller's signed-short reference and verified eWu identity before removing transient controller objects from source context. Other supplied live runner controllers explicitly attest non-eWu. Restored descriptors missing this evidence remain unknown rather than borrowing container identity.

Validation: `PYTHONPATH=server:server/tests /tmp/wakemu-combat-review-venv/bin/python3 -m unittest test_combat_trigger_identifiers` passed 12 tests. Added regressions cover null source, non-state runner, unknown runner source, differing container/applied-state references, signed negative reference, and a trigger caster different from the first evaluation argument. Original bytecode was read with `javap -classpath 'client/lib/*' -p -c eLD eLF`; no services were touched.
