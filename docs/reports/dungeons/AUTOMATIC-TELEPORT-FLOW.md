# Automatic native teleport sequence extraction

The second automatic pass covers all 29 entry routes previously classified as
native internal transport graph review. It uses native player exploration
geometry, literal destination coordinates, native approach masks/positions and
transport criteria. No room order is inferred from object IDs or distance.

| Result | Routes |
| --- | ---: |
| Unique directed native transport chain proved | 15 |
| Literal approach or arrival unresolved | 5 |
| Internal transports remain within one physical region | 5 |
| Native transport graph branches | 4 |

The fifteen candidates contain two to four physical room regions, with exact
native arrivals and a directed walking witness to each required transport.
Backward transports to already traversed regions are retained as native links;
branches to different new regions prevent automatic sequencing. Missing or
nonwalkable arrivals are never snapped to nearby terrain. Unverified criteria,
item costs, kama costs and instance-changing transports prevent unconditional
sequence approval.

Generated topology candidates remain in
`.runtime/local/native-teleport-topology-candidates/`; the complete evidence,
coverage and per-route candidate paths are in
[AUTOMATIC-TELEPORT-FLOW.json](AUTOMATIC-TELEPORT-FLOW.json).
They contain room cells, reachable candidate anchors, native arrivals and
literal transport source/destination bindings. They do not activate gameplay.

Remaining integration contracts include verified monster composition, native
exit binding, durable victory unlock and party transport tests, and boss
mechanics. A blocking interactive object's center can be nonwalkable while its
native approach belongs unambiguously to a room. Such a source must be resolved
through its verified object/approach binding, rather than inserting invented
walkable cells into the room. The new transport policy must also share the
validated native exterior command and exploration profile contracts.

Reproduce:

```sh
python3 server/tools/extract_native_teleport_flow.py
python3 -m unittest discover -s server/tests -p test_native_teleport_flow.py
```

Seven pure regression tests pass, covering native forward/backward sequences,
branches, invalid arrivals, unverified criteria, directed stairs, generated
native arrivals and refusal of ambiguous candidate generation. No production
module, migration or deployed configuration was changed during this pass.
