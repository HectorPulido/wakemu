# Native PR completion boundary and Wakemu policy

## Native source evidence

`eWA.c(Qe, boolean)` clears fight properties 65, 66, 19, and 12, calls inherited `eZR.d(Qe, boolean)`, sets the target's HP to its minimum, then writes zero to the raw maximum of `KO_TIME`.

`eZR.d` is guarded by its completed flag, selects the parent's PR observer through either `bbc` or `bbb` according to the boolean, stores the parent effect's `fRZ()` index (or `-1`) in `mzn`, and invokes the selected `PR` callback. The `buG` implementation routes this to `beS.c(eZR, boolean)`; its `d(Qe)` delegates to the same callback path.

`beS.c` delegates to `bfb.c`. That method walks the effect's ordered OY list. `eVn.i(OY)` and `eVn.j(OY)` are independent membership checks against two distinct lists (`rze` and `rzg`). For each OY, the private `a(eZR, boolean, OY)` callback runs when `i` is true, followed by `b(eZR, boolean, OY)` when `j` is true. The loop records the runner UID after callbacks. These private callbacks dispatch OY descriptor kinds to `beS` presentation methods, including animation, string, scale, and other visual operations. They are client presentation observers, not HP, captured-roster, QI, or global-fighter mutations.

Evidence files: `.runtime/combat-review-20261007/osa-family-gaps/eWA.txt`, `.runtime/local/native-eZR-current.txt`, `.runtime/local/issue16-buG-live.javap.txt`, `.runtime/local/coverage-beS.txt`, `.runtime/local/mount-bfb-current.txt`, and `.runtime/local/native-effect-core.txt`.

## Wakemu policy boundary

Wakemu has no corresponding client OY renderer. Successful fresh fight snapshot initialization therefore installs an explicit server policy with an empty ordered watcher list; this is a Wakemu implementation choice, not a claim that the native client observer list was empty. A restored fight without this provenance is rejected by the recall handler. When typed Wakemu observers are registered, the policy invokes each observer's `i` slot and then `j` slot in registration order, and records the completed runner UID plus the server's parent UID only after all callbacks succeed.

The server `parent_uid` remains distinct from native `fRZ()`'s parent index; the latter is not currently produced by the server invocation model. The handler preserves native state order: properties, PR completion boundary, HP minimum, KO raw maximum zero. It emits no invented recall-specific fight events. No eHP captured slot, QI slot, fdt membership, or global PV registration is retired by this family. A positive-to-zero HP transition continues through the shared, separately evidenced death/status path.

Validation: `PYTHONPATH=server:server/tests /tmp/wakemu-combat-review-venv/bin/python3 -m unittest test_combat_summon_recall test_combat_kill` — 15 tests passed. After moving fresh-policy installation to the successful snapshot boundary, `PYTHONPATH=server:server/tests /tmp/wakemu-combat-review-venv/bin/python3 -m unittest test_combat_summon_recall test_combat_actor_snapshot test_owned_native_bootstrap` — 18 tests passed.
