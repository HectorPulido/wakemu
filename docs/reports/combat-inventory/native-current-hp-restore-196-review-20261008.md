# Native current HP restoration: family 196

Native runner `eXO` extends `eZR`. It targets actors (`bbA=true`, `bbB=false`),
admits corpse execution (`bcd=true`), has `bbz=false`, and advertises events
202 and 1. It is not the ordinary healing runner and must not inherit healing
resistance, healing event phases or live-HP eligibility by analogy.

Evidence is the installed bytecode dump `/tmp/cast-delivery-eXO196.txt`,
`PA`, `UP`, `Qe`, `eGj` and `eGZ`, together with native enum identities.

`C` resets percentage and original-controller restriction. No parameters set
the running value to 1. Parameter 0 enables percentage recalculation; optional
parameters 1/2/3 equal to 1 enable original-controller restriction, virtual HP
restoration, and AP/MP maximum restoration respectively. The native clone
copies only percentage and original-controller restriction; other calculated
fields depend on subsequent `C` or actual additional-data deserialization.

Execution first checks the original controller's actual `baF` when restricted.
It then requires the HP characteristic and absence of fight property 66
(`CANNOT_BE_RAISED`), otherwise cancels. With percentage mode and actual
`bbs` execution enabled, the amount is `max(1, UP.bt(float(maxHP)/100*percent))`.
Virtual HP amount is independently calculated from characteristic 92 maximum.
`UP.bt` is stochastic floor plus a Bernoulli draw for the fractional remainder;
it is not truncation or deterministic rounding. Existing
`stochastic_native_round` implements the shared primitive.

HP and optional virtual HP are set through `PA.on`; AP and MP use `PA.aZf`,
which calls `on(aYU())`. Actual clamp/frozen notifications must come from the
concrete PA source. This is current-resource assignment, not damage or an
ordinary heal delta.

Only when the target is `eGj` and the actual PS has a source runner whose
`oz(1010)` is true does the runner call `target.lD(true)`. `eGj.lD` delegates
to its actual `eGZ` strategy; the interface default is a no-op. This does not
prove a generic fdy membership, in-play or IsDead transition. Strategy-specific
behavior must be established before enabling that route.

AdditionalDatas serializes the virtual HP amount (field 10) and two restoration
flags (17 and 18), including explicit false values.
Percentage and controller restriction are private calculation facts, not
additional-data payload fields.

The shared factory now registers `NativeCurrentHPRestoreHandler` for the fresh
normal-source route, with native runner calculation/forced value and channels
1 through 4. It writes current resources directly and retains exact payloads;
removal inherits `eZR.d` and does not reverse assignments. Property 66 and
original controller eligibility use actual native property/status providers.
Expandable current values above effective maximum and triggered PS strategy
routes remain explicit unsupported boundaries. Regression cases cover fresh
one-HP assignment, forced amount, frozen HP, property 66, and nonreversing
removal through the real shared factory. Tests have been submitted to the
single validation agent; syntax checks passed. No complete spell gameplay
claim is made before those checks and nominal native pipeline evidence.
