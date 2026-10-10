# Cra beacons and late spectator snapshot failure

Status: open; review/documentation only, no runtime edits or restart.

Hector's sequence: Cra starts and readies, creates several destruction beacons,
starts profiler; Iop joins observation and sees Cra/monster but not beacons;
attacks directed at beacons do not trigger the expected activation/explosion;
manual checkpoint completes, then Cra kills the Jalató directly.

## Correlated server evidence

Bootfaa4761f4977427f85c14e36474f1238, fight110, Cra6, spectator4; UTC:

- 21:29:59.040 start-fight completed4953.231ms, original actors Cra and Jalató.
- 21:30:39.711 spell request ends labelled rejected because spectator snapshot
  serialization failed, but the owned fight already contains new actor33,HP130.
- 21:30:40.628 spectator snapshot rejects `Unverified native remote effect
  container absence`; entry nevertheless records spectator4 at revision5.
- 21:30:45.015 another cast ends with the same rejection and new actor60,HP130.
- 21:31:05.825,21:31:14.513,21:31:20.037 subsequent casts retain both added actors
  atHP130 and Jalató atHP66; the same spectator snapshot rejection recurs.
  These requests take roughly0.89–1.02seconds, not103seconds as in fight109.
- Turn acknowledgements also record the same snapshot validation rejection.
- 21:31:34.081 final direct cast completed2310.829ms; JalatóHP0, both added actors
  stillHP130. Screenshot confirms victory/rewards and manual checkpoint#2 with
  zero positions in0.004seconds.
- 21:31:38.153 spectator terminal12925 returned and refreshed world.

The fight snapshot confirms two added actors persisted server-side, consistent
with beacons, while the user reports their absence in the spectator client.
The exact actor/template identities and damage-trigger callbacks must be checked
before claiming the beacon mechanic cause. Spectator serialization failure is
confirmed and can explain missing snapshot content, but does not by itself
prove why the Cra's own beacon-trigger attacks failed.

Important diagnostic distinction: request status `rejected` here reports a
publication/snapshot failure after fight mutations are visible. Do not interpret
it as evidence that every associated spell mutation was rolled back. Keep these
issues separate: late-join entity/effect publication; beacon elemental activation
and explosion; request outcome versus authoritative committed state.

## Profiler evidence

External waits capture1791581420848618318 ran21:30:20.864–21:32:19.634,120seconds,
return_code0. Unlike the earlier capture, it covers this reproduction. It contains
28thread profiles and is preserved privately as
`.runtime/local/profiler/capture-1791581420848618318.speedscope.json`.

Most all-thread samples are condition waits, socket accept or SSL reads; this is
expected in waits mode and is not a CPU ranking. Stacks containing cast/spectator
functions include native snapshot/varint serialization, effect resolution and
PostgreSQL waits, with no evidence from this capture of a new103-second cast.
The screenshot's old maximum103252.6ms belongs to cumulative counters from the
previous incident unless counters were reset. Long background maxima around
103seconds overlap the same historical interval; do not sum inclusive timings
or attribute these to separate demonstrated freezes. No optimization requested.

## Remaining acceptance

Late spectators must receive existing beacons with correct ownership/effects;
matching elemental attacks must trigger their native activation/explosion;
publication failures must not misreport already committed gameplay mutations.
Zero-position checkpoint completion does not close the original checkpoint
freeze or prove position persistence. Preserve ordinary direct spells and
spectator reward exclusion while investigating these defects.
