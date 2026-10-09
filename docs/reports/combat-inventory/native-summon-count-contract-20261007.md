# Native summon count contract

Ready-access03 contains eight rejections with `Missing native filtered summon
count`. Ordinary fresh authority already supplies a complete zero total and an
empty breed histogram; the evaluator incorrectly interpreted every missing
breed key as unknown. It now accepts absent breed keys as zero only when the
producer explicitly attests `native_summon_counts_complete=True`.

Native ePs (`NbSummons`) selects eHg then invokes dTB or GF. eGj.dTB calls GF
with the native player-breed wildcard. With an actual fight, GF iterates
fcb.dLy, which is the fdt IN_PLAY/OFF_PLAY collection. It includes only actual
eGj actors with dTE true, dsA false, direct dpr equal to the queried actor,
different object identity, no property103 (`BYPASS_SUMMONS_COUNT`), and the
requested exact breed unless the wildcard is selected. QI cell occupancy is
not the population source. Out of a fight, GF uses dnC and has a distinct
wildcard/property-check ordering; that branch must not be flattened into the
fight rule.

Nonempty registered summon rosters now use the complete actual fdt producer
and native filters. Missing restored components remain guarded. Native dsA is independent
of HP and fdy corpse/participation status: it combines eGZ.mwD, dtM().dwv()==4
and world property eHQ.pSA. Persisting a guessed false value after creation
would conceal later lifecycle changes. A complete nonempty count producer
must own these current native facts and complete fdt population before
publishing a histogram. Fresh bje records actual bjm.mwD=false and inherited
dtM=null. Live world DEAD19 is distinct from fight NO_KO19. Emitting the actual
cvK12727 state2 applies the proven aTS.F gg(true) writer. The explicit transition
API preserves mwD for0/3 and clears it for1. Unknown legacy components stay
guarded unless an actual true component closes the native OR. This change does not approximate those counts with
registration length or live HP.

Verification:32 unit tests pass, including partial/unknown histogram rejection
and complete empty histogram acceptance. `ProbeNativeEmptySummonCount` invokes
original GF/dTB with an actual empty dnC collection: seven native assertions
pass, including signed32-bit filter boundaries.

The evaluator also accepts signed integer literals for the breed filter.
Original ePs evaluates its alP argument as a long, then performs `l2i` before
calling GF. The Python evaluator applies the same signed32-bit wrapping; the
native NONE wildcard is -1 and returns the authoritative total, never an
absent histogram key. Unknown totals remain unknown even when the histogram
is complete. Regressions cover negative filters, wrapped wildcard and breed
values, and rejection of floats, booleans, and out-of-range long constants.
`ProbeNativeSummonCountFilter` runs original ePs against an actor exposing the
received GF argument: eight conversions and the native NONE constant pass
(nine assertions). This verifies conversion separately from roster counting.
No service, database, client or Docker action was taken.

Native eGj.gg checks compound dsA before writing mwD: if it already equals the
requested bool, the setter is a no-op. In particular world DEAD19 can suppress
a true write; removing that world property must not leave an invented mwD=true.
The producer preserves this guard and invalidates unresolved legacy writes.
`ProbeNativeDeathStatus` executes original eGj/bjm methods: eight assertions pass.

Current producer verification: 31 tests pass, covering HP-independent native
transitions, world/fight property namespaces, live dsA and property103 count
exclusion. Broader actual cast/reconnect validation is delegated separately.
