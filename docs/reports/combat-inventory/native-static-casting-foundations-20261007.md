# Static casting and path-mask foundations

`combat_casting_alignment.native_casting_alignment` implements the independently verified static `fcj.a` branch: unrestricted success, cardinal linear acceptance, authoritative Sn callback when the aligned linear branch requires a path, then the diagonal alternative after a failed linear branch. Diagonal uses Java signed-int subtraction and `Math.abs(int)`, including INT_MIN; it must not reuse the squared-double IsInDiagonal criterion. Missing path authority remains unknown. The callback owns the real physical efR origin, footprint, target obstacle exclusion/restoration and Sn cleanup. This helper is not yet wired into normal casting or UseGateEffect.

`NativeQISnapshot.Z` now supplies the exact mask consumer required by selected cwN path policy. Unlike P, Q and R, native Z first computes signed-int W and checks the resulting index against biE; it does not check the coordinate rectangle with aK. Therefore coordinates outside the rectangle can alias a valid index. It tests signed-short mask bits 256 or 512.

The original-client `ProbeNativeQIPathMask` passed all 65,536 masks, row aliases, invalid indices and an int32 multiplication overflow alias. Its first overflow assertion used incorrect test coordinates; correcting the expected native index produced the passing result. No runtime approximation was added from that failed expectation.

```sh
javac -proc:none -cp 'client/lib/*' -d .runtime/combat-review-20261007/qi-mask-oracle sniffer/java/ProbeNativeQIPathMask.java
java -Xmx256m -cp '.runtime/combat-review-20261007/qi-mask-oracle:client/lib/*' ProbeNativeQIPathMask
```

Python regression validation for the static helpers passed 59 tests across conditions, runtime adaptation, casting alignment and QI snapshots. The exact command was:

```sh
PYTHONPATH=server:server/tests /tmp/wakemu-combat-review-venv/bin/python3 -m unittest test_combat_conditions test_combat_runtime_adapter test_combat_casting_alignment test_combat_qi_snapshot
```

The condition tests cover `HasState` and `HasStateFromLevel` selectors for caster, target, controller and triggering actors. Missing relationship authority remains unknown; a known null or a registered area PV that is not an `eHg` actor evaluates false. `eventTarget` remains unsupported because its producer is not available. The audit of passive 8152 (`Crecimiento Acelerado`, Sadida level 10) completed with stable sources and a complete trace; see [the focused passive report](passive-trigger-selector-review-20261007.json). It observed the internal cycle but no activation, and the attempted own cast was rejected as out of native range, so this is not gameplay verification.

Full Sn traversal, ordinary `fcj` eligibility and `UseGateEffect` remain separate unfinished integration boundaries. No game client or service was launched.
