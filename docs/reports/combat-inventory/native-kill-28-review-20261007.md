# Native kill family 28 contract

The shared `NativeKillHandler` implements native `eXc` for actual fight actors
with authoritative HP, KO-clock and required property-counter snapshots. The
factory, ordinary lifecycle, retained-effect gate and central removal route use
this general handler. No spell or state reference selects special behavior.

Native preparation reads parameter zero only when the declared parameter count
is positive. Exactly value 1 enables the private `rCL` flag; the runner amount
remains zero, including when an execution context carries a forced amount.
Application assigns HP to its actual minimum, then optionally adds permanent
property 65, then sets the KO-clock raw maximum to zero through its native
bounds. Frozen HP does not suppress the independent property and clock effects.
Frozen clock raw current remains untouched while its effective read clamps to
the new maximum. Removal discards the owned running effect without restoring
HP, clock bounds or permanent property counters.

The native event prototype is `[0, 192]`. Preparation and application preserve
the four ordinary lifecycle phases, transaction-owned UID, live L2 snapshot
validation and cancellation cleanup. Completed application uses opcode 12613
with amount zero; explicit removal uses opcode 13560. A positive-to-zero HP
transition supplies the existing ordinary corpse lifecycle without recording a
damage event. This server lifecycle does not prove native `IsDead`: `eXc` never
sets the distinct native dead flag or death-status producer.

`ProbeNativeKillContract.java` exercised original native preparation and real
characteristic setters in 384 rows: levels 0, 1, 20, 200, 245 and 32767; absent
and present parameters; values -1, 0, 1 and 2; HP minima 0 and 5; and independent
HP/clock freezing. The native export completed successfully, and the eight
handler tests include differential comparison against that private export.
Offline validation snapshot `luna-factory28-ewx-01` passed 51 tests including
the handler suite. After correcting a fixture key type, the actual shared
factory/removal test passed in a separate two-test rerun. The JSON companion
records the validation manifest and source hashes.

Native `eXc` does not serialize its private boolean through an additional-data
override. The decoded client clone receives amount zero and does not rerun
preparation before application. Accordingly, the implementation does not
invent a wire amount or extra effect to convey that flag; client property-65
parity remains unproven. No GUI acceptance has been claimed.

Null, area, non-fighter, absent KO-clock and unavailable counter authority are
explicitly rejected until their producer contracts are closed. Native supports
a broader optional-target domain. The typed dependency graph contains 55
family-28 definitions; that structural count does not establish executable
coverage of every original guard, state or class ability. No services,
containers, databases or AI code were changed.
