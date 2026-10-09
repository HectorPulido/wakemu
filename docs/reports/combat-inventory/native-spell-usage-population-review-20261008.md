# Native spell usage population

The shared usage validator now uses the actual native `bak()` population instead of historical `fight.actors` rows. Retired fighters remain in combat history but are absent from usage targets. Native OFF_PLAY fighters remain eligible population members. Registered Qs areas participate in target validation; their actual Qr `raw_bcR` flag controls consumption, independently of validation.

Source: `fcO.a` calls `fyS.c` for the null-target global checks, then iterates `fcb.a(aBn)` and calls `fyS.a(..., amP)` for each returned PV. `fcb.a(aBn)` delegates to `fcb.b(III)`, which iterates `bak()` and tests `ala.a(PV,x,y)==0`. The third coordinate is intentionally ignored. The client accounting caller `aVn.cby` uses the same population lookup. `fyS` consumption skips faV with `bcR()==false`; validation does not apply that exclusion.

The adapter supplies a separate authoritative condition context for each PV and for null-target checks. Global interval/per-turn rules use the null target; each matching PV can select its own conditional per-turn/per-target rule. Actor and area footprints use the shared Java integer geometry implementation.

Native `fyS` uses spell definition reference plus Java PV identity hash. Wakemu preserves spell reference and stable registered PV UID identity; it does not claim to emulate JVM identity-hash collisions. Extras without a typed PV producer reject explicitly.

Validation: `PYTHONPATH=server:server/tests /tmp/wakemu-combat-review-venv/bin/python3 -m unittest test_combat_spell_usage test_combat_pve_departure` passed 10 tests. Regressions cover retired history, OFF_PLAY population, overlapping actor/area population, native XY behavior across heights, and both bcR consumption values. These are focused offline regressions; full actual-cast integration remains delegated to the immutable validation batch.
