# Native carry direction consumers

The shared `set_registered_direction` producer implements original `eGj.a(aAS)`:
changing a carrier orientation rotates its carried actor by the carrier delta
through the eight planar orientations, then updates both directions and the
registered carry-pair seal. Changing the carried actor alone updates its side of
the same seal. Native special orientations NONE, TOP and BOTTOM are supported
by the producer; its original-JVM oracle belongs to the carrying source review.

The following consumers now call this producer instead of assigning direction:

| Consumer | Registered authority |
| --- | --- |
| Normal spell script facing | Actual actor in transaction preview fight |
| Shared NPC transaction script facing | Actual actor in transaction preview fight |
| Owned placement/turn orientation | Actual actor in runtime fight |
| Native orientation effect family303 | Actual rebound or selected actor in handler fight |
| Client and shared server movement wrapper | Actual actor in copied validation fight, then actual live actor |

Movement validates and serializes a complete copied fight before committing.
This preserves reciprocal carry coordinates, the reserved unindexed carried QI
slot and the direction seal during codec preview. Successful execution moves
and rotates the live pair once. A codec failure leaves live directions,
coordinates, MP, registry and action counter intact.

The regression fixture uses the fresh native QI slot/topology producer and real
`carry_registered`, not a replacement direction setter. Tests verify carrier
delta wrap, directly carried rotation, cast actor identity, resource-neutral
owned orientation, and movement failure followed by successful execution.

Validation:

```sh
env PYTHONPATH=server:server/tests /tmp/wakemu-combat-review-venv/bin/python3 -m unittest test_combat_carry_direction_consumers test_combat_cast_facing test_combat_orientation_effect test_combat_carrying test_combat_movement_runtime.MovementRuntimeTests
```

Result: **30 tests passed**. The HTTP-backed AI movement test class was excluded;
no services, world process, database or client were started or restarted.

This review covers those shared consumers. Tactical policy code and constructor
initial direction assignments are separate boundaries, not certified here.
Live client presentation remains part of the final manual acceptance run.
