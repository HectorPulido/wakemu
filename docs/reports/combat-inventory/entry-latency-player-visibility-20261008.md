# Combat entry latency and local player visibility

## Observed boundaries

Fight 84 was requested at 22:13:23 UTC and placement was published at
22:14:46 UTC. The approximately 83-second interval is not attributable to
terrain alone: the recorded forced-terrain operation took 3.47 seconds and
started approximately 58 seconds after the request. An independent cold local
selection of map 527 took 4.07 seconds and selected 1,537 cells. These readings
do not establish the production bottleneck.

`local_game_server.py` now emits `combat_entry_stage` records for group
selection, arena selection, resource construction, durable placement freezing,
placement construction, and actor snapshot initialization. Each record carries
wall time and current-thread CPU time since the preceding boundary.
`storage/native_catalog.py` logs reads exceeding 250 ms with Redis, PostgreSQL
pool acquisition, and query timings and payload size; catalog contents and
credentials are excluded. Catalog validation and cache policy are unchanged.

Validation: `test_native_catalog` passed 10 tests. The server entry module
compiled successfully. No latency improvement is claimed before production
stage measurements become available.

## Invisible local player

The 22:04 UTC session selected character 6 and published the world bootstrap.
The recorded sequence included full character seed 12666, scene reset 13256,
then position/scene installation 13974. Subsequent world movement committed.
This is distinct from the later inventory parser failure.

Native evidence in `.runtime/local/ctB-handler-ciu.txt` shows the 13974 handler
calling `ciu.a(big,long,biB)`. That helper obtains the local `beS`, invokes
`setVisible(true)`, attaches it to the current scene and controller, sets its
position/direction, and registers it with `Zi` before refreshing the renderer.
Thus a second invented own-actor spawn is not justified by the inspected
bootstrap sequence.

At 22:34:15 UTC the live inspector reported `player_present=false`. It cannot
provide the historical renderer state at the time of the screenshot. The next
useful diagnostic is the actual local actor's graphic identity, visibility,
model identity and scene membership while the symptom is present. Actor-list
membership alone is insufficient evidence that the graphic is rendered.

The capture agent's `/actor-registry` endpoint now exposes these read-only
fields under `graphic`, using actual `dhw`, `isVisible`, `bwX`, and identity
membership in `cdE.exP`. The agent build passed. This additive diagnostic needs
the rebuilt agent to be loaded at the next client launch; no client or world
process was restarted here. Absence from that particular scene list is a
measurement, not by itself proof that all renderer registries lack the object.

No speculative bootstrap or gameplay modification was made. No service was
restarted for this investigation.
