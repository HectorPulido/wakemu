# Late spectator join: temporary combat stall

Status: open, investigation/documentation only. Hector confirms defeated-mob
removal in the first test. A second test, joining observation after combat had
started, appeared frozen and later recovered. The result screenshot reports
victory after two turns, duration2min21sec, and shows `Previous turn is not
synchronized`. No code was changed and world was not restarted for this review.

## Evidence

World boot `faa4761f4977427f85c14e36474f1238`, fight109, participant6,
spectator4. Times below are UTC (Bogota UTC-5).

- 21:12:22.630: start-fight request completed in4973.556ms.
- 21:12:28.112: placement ready completed, phase active, turn2.
- 21:12:40.906: late spectator entered at revision6.
- 21:14:30.120: spectator snapshot rejected during spell handling:
  `Unverified native remote effect container absence`.
- 21:14:30.131: the spell request finished rejected after103252.149ms (103.25seconds elapsed). This request spans the reported stall; elapsed time alone does not identify its blocking operation.
- 21:14:31.839: another cast rejected with `Previous turn is not synchronized` in26.579ms.
- 21:14:32.987,21:14:35.115,21:14:36.445: same rejection during turn acknowledgements.
  The server nevertheless advanced through turns3 and4.
- 21:14:45.058: final cast completed, fight finished, winner0 and monster HP0.
- 21:14:47.333: spectator terminal12925 acknowledged and world refreshed.

The serializer's remote-effect ownership/container validation raises this error
when absence is not explicitly verified or encoded container fields contradict
absence. This identifies a concrete snapshot correctness failure, not the exact
effect UID or proof of the entire preceding stall's cause. Do not bypass the
validation or attribute the whole pause to CPU, Redis or this rejection alone.

## Feature counters captured after recovery

The persistent counters retain four `request.cast_spell` calls totaling
110432.21ms wall and106491.36ms calling-thread CPU, with max103252.56ms and two
rejections. This aggregate strongly indicates substantial CPU work in the
spell-request interval, rather than treating the whole interval as database or
network waiting. It does not isolate the103-second call's exclusive CPU or its
inner function. Nested spans overlap. Preserved private feature summary:
`.runtime/local/profiler/incident-spectator-feature-summary.json`.

## Profile timing and limits

External waits capture `capture-1791580493513786193` ran21:14:53.522 through
21:15:23.027 and completed with return_code0. Thus it began about8seconds AFTER
the final cast: it does not sample the original frozen interval. An external
thread dump was also saved after recovery. Both are private under
`.runtime/local/profiler/`; neither should be presented as a deadlock trace.
The sampled post-recovery server remained responsive and checkpoint at
21:14:52.701 took2.892ms with zero positions. Hector's screenshot shows a manual
zero-position checkpoint taking0.003s. These observations do not close the older
checkpoint freeze issue or prove no earlier delay occurred.

## Next reproduction

Start `!perfil iniciar 120 waits` BEFORE the fight. A begins and takes a normal
turn; B joins observation after the fight is active. If it stalls, retain both
clients and record exact local time. Correlate the participant acknowledgements,
spectator snapshot rejection, current remote-effect ownership and wire container
fields against the captured deployed image. Check whether B exiting restores A
only if a targeted isolation probe is needed. Keep first-test mob-removal
acceptance separate from this late-join failure. No optimization is requested.
