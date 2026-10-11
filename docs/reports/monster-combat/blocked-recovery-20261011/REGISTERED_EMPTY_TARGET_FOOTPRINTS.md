# Empty target candidates must respect registered QI extents

The historical5390Protogolem probe selected empty target(-9,-7,-1), while
the registered QI occupant was caster-200. Both validation producers excluded
only exact actor XYZ centers. Native QI registration instead indexes the
inclusive XY square of the actual signed-byte physical radius, independent of
Z (`NativeQISnapshot`, `NativeQIRegistry`). Radius1 therefore occupies neighbors
and the same XY column on another floor.

A shared tooling-only `native_empty_target_predicate` now obtains the complete
actual population through `current_registry(fight).snapshot()` and excludes
candidates whose XY has any registered QI occupant. Missing/stale registered
lifecycle authority continues to fail closed. Unregistered advisory fixtures
retain their explicit center/static-cell exclusion; the helper never fabricates
a radius or a registration population for them.

Both free-cell proximity search and ordinary spell destination-order search use
the predicate. The ordinary producer retains its original order and two-target
budget. Bounded search retains its range, preferences, deterministic sort and
limit. Runtime target identity checks and collision behavior are unchanged.

Original search4 and alignment2 tests pass locally. NEW tests use actual Actor,
Fight and native slot registration, covering radius1 neighbors, different Z,
ordinary empty predicate reuse and stale positions. Their independent qualified
catalog gate passed both tests; the complete5390 monster replay remains pending.
