# General kill and current-characteristic runtime integration

The shared native factory now routes family28 to `NativeKillHandler` and all
twelve catalogued `eWX` families to one `NativeSetCurrentCharacteristicHandler`.
Both receive the ordinary stat execution context, transaction-owned RNG and
UID allocator. Kill receives the same exact property-counter authority used
by the existing fight-property handler. No spell or state IDs select these
routes.

When the ordinary healing lifecycle exists, both handlers use that lifecycle
and its prepare phase. The retained runtime admits these routes, and central
`NativeStatHandler.remove` delegates to their native removal implementations.
Kill removal discards the running effect without reversing HP, KO-clock or
permanent property changes. Setter removal reverses its captured setter delta,
with native bounds and mutability, rather than restoring an old snapshot.

Two shared-factory regression tests exercise actual dispatch plus central
removal. The setter test includes an intervening current-value change; the
kill test confirms resource changes survive effect removal. Existing handler
tests cover source contracts and lifecycle phases. Syntax compilation passed;
automated execution is delegated to the team's offline validation process.
Missing actor snapshots, property counters, expandable raw-current authority
and unsupported delivery domains retain the handlers' explicit rejection.
No running services or databases were changed.
