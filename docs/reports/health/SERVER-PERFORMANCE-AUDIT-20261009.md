# Server performance audit

The user authorized performance optimization after reporting minute-long combat
stalls. This audit separates sampled active work from lock waiting. Private raw
captures remain under `.runtime/local/profiler/`.

## Measured clone consumers

Continuous captures sampled at 25 Hz with idle threads included show these
Python stack occupancies. These values are sampled thread time, not exclusive
CPU measurements or independent incident durations.

| Capture suffix | Deep-copy application caller | Sampled seconds |
| --- | --- | ---: |
| 1791584386136070067 | `combat_shared.expire_current_turn` | 32.68 |
| 1791584680013536330 | `combat_timed_expiration.prepare_timed_expiration` | 17.28 |
| 1791584861532101438 | AI `native_oracle.NativeOracle.fork` | 35.76 |
| 1791584920842616985 | AI `native_oracle.NativeOracle.fork` | 6.80 |

The AI stack passes through `run_test_monster_turn`, native decision/query,
`preview_with_evidence`, and `fork`. Therefore fixing only direct player spell
handling would leave another demonstrated copying path.

Background resource growth, maturation and harvesting wrappers frequently wait
on shared group/harvest locks. Their roughly 20–50 sampled thread seconds per
minute are contention symptoms; the waits captures do not establish those
workers as CPU hotspots. Do not remove their locks or weaken atomicity based on
these counts.

## Narrow asset-copy boundary

`Fight.native_rail_movement_authority` can contain a registered summon authority
whose ordinary authority holds the native actor property catalog. This asset
is a process-lifetime definition source. The default ordinary authority now uses
the existing nested read-only `ImmutableCatalog` view. The public raw loader
retains its original dictionary/list contract. Deep copies retain the view's
asset identity while still copying actor, character, deck and custom mutable
catalog state. The authority itself is not globally shared.

A read-only benchmark in the running container measured the 2,874-NPC property
catalog at 0.006973 seconds for an ordinary deepcopy and 0.000147 seconds for
the immutable view. This reduction is useful but does not, alone, explain the
multi-second oracle captures. Runtime service callback graphs and redundant
turn-expiration copying require separate validation.

`test_combat_property_catalog_copy.py` verifies nested asset immutability,
shared asset identity, and isolation of custom mutable catalogs and owned state
through the registered rail authority graph. The host Python lacks psycopg and
the mounted native catalog; the complete suite must run in the configured test
environment before deployment.
