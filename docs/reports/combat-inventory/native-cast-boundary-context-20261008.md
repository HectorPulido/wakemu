# Validated cast facts at external cast boundaries

The existing Wakemu external 1024/1025 policy replayed listeners with a native
null Qe. Native subscription targeting therefore legitimately selected the
listener's SELF recipient. Using that recipient for cast-distance conditions
returned zero, even when the validated spell target was one, two or three cells
away. Null Qe also made the triggering-caster identity comparison false.

The server now attaches a separate `native_cast_boundary_context` to these
external events and their cloned invocations. It captures the actual validated
cast's caster, active spell and pre-cast footprint distance. It does not create
a running effect, UID, native Qe, triggering effect definition, or PL.

Within this explicitly named server policy, the criterion adapter supplies
the casting identity comparison and validated cast distance. Actual PZ
activation and element still use their existing native providers. Element 1
is native FIRE; Juicio 4776 belongs to FIRE. Subscription recipients, child
execution targets, source-null indirect predicates and all
other external events retain their existing semantics. Actual running-effect
sources take precedence over these separate policy facts.

This closes the shared context routes used by Juicio state 8912 root 397245
and Guerrero state 7553 root 397553. No spell-ID branch was introduced.
The original unavailable server event caller is not claimed to have been
recovered; this is an explicit extension of Wakemu's existing cast policy.

Focused validation: three pure regressions pass for distances 1/2/3, unchanged
pre-cast snapshot after movement, empty-cell selection, preserved null source,
and rejection of unsupported policy/event combinations. The legacy cast-events
suite requires the configured PostgreSQL catalog environment and is delegated
for integration validation. No deployment or restart was performed.

## Cross-class regression diagnosis

The Cra 4820 regression was compared with boundary facts enabled and disabled;
both reached the original 350554/352071/352072/352074 applications. Its old
assertion expected carriers 7758/7793 to remain in the final ledger, but both
have native duration zero. Their original children 347094 and 349856 install
persistent states 3430 and 7792. The level-3 carrier gives child3430 level30
through its original `0 + 10 * level` parameters. The regression now checks
those actual persistent children and absence of the transient carriers.
No production Cra behavior was changed to satisfy the assertion.

The actual Iop fixture initializes innate Guerrero state7553 rather than
placing that state reference in a passive spell slot. Juicio naturally applies
8912 to its enemy recipient through native selector9. Its next FIRE cast
reaches 397245/397246/397247, while an EARTH cast rejects that fire clause.
Charge selects 397665/397666/397667 from the validated pre-cast distance1/2/3.
The third branch can correctly return `no_effect` in a fresh fight: its native
children remove states or reapply already-present states, and none is fabricated
for the test. Post-Charge positions are not used to recompute the event distance.

Configured current-source runtime validation passed five tests: actual Cra
carrier/child sequence, Charge distance1/2/3 selection, Juicio followed by FIRE,
the EARTH negative clause, and naturally granted Uppercut followed by a legal
two-MP retreat and Charge at distance3. The latter raises the actual AP combo
state3448 from level1 to level2. Persisted retained-group invocations are also
checked to exclude the transient cast-boundary facts. These facts are cleared
at retention capture and only the casting actor's observer receives the
validated distance; unrelated global observers retain native own-distance
semantics.
