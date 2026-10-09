# Native healing on partial area PVs

The bulk class-cast failure for spell8242/effect386023/family1084 addresses a registered area PV (target227), not an absent fighter. Original eXs.C first requires non-null source/target and target PV.a(ffw.sgC); when the target has no HP characteristic, it returns before healing arithmetic. eXs.c checks the same condition and calls mu(true), suppressing PR notification while preserving the surrounding Qe lifecycle and runner value.

Source: `.runtime/local/native-eXs-24-current.txt`, methods C(Qe) and c(Qe, boolean). The shared partial-area contract verifier already proves that plain supported faV contracts and verified fbc/faW snapshots lack both HP and armor. Healing now uses this exact proven subset without constructing fighter statistics, healing resistance, or mastery. Actual registered areas can receive lifecycle events through their Qq/Qf routes. Wall/fbd healing and unknown/null PVs remain explicit gaps; this change does not claim their characteristic writers are implemented.

Regression `test_combat_healing_area_guard.py` uses actual retained Feca area carriers, checks L1/L2/L3/L4 with zero initial value, no heal packet, no fighter context lookup, and unchanged fight state. Runtime tests and an actual spell8242 cast are pending refreshed offline validation. Existing ordinary fighter healing tests must remain passing.
