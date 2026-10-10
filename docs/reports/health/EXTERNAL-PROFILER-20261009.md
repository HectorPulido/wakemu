# Optional external profiling service

The optional Docker service `profiler` uses py-spy0.4.2 outside world. It can
start/stop independently without restarting the game. It shares only world's PID
namespace, has SYS_PTRACE, and exposes its API only at127.0.0.1:18082. It has no
Docker socket, host PID namespace or database credentials. CPU/memory/process
limits apply to the profiler. It uses nonblocking sampling; profiles can omit
inconsistent samples rather than stop the game for a consistent snapshot.

World retains lightweight fixed-label counters: request actions, scene/bootstrap,
combat AI/settlement/publication, dungeon transitions, mount publication,
background iterations, socket writes/lock waits, PostgreSQL pool and transaction,
request diagnostic snapshots, and native catalog stages. Deliberate background
sleep and waiting for the next incoming packet are excluded from feature timings.
Counters are bounded128labels and exported asynchronously every30seconds into
one atomically replaced private `performance-latest.json` file. No stack sampler
runs inside world from the chat commands. Its original checkpoint watchdog stays
active independently of the optional service.

## Exact operation

From the repository root:

```sh
bash client-tools/profiler.sh start
bash client-tools/profiler.sh status
bash client-tools/profiler.sh capture 30 cpu
bash client-tools/profiler.sh capture 30 waits
bash client-tools/profiler.sh report --sort cpu
bash client-tools/profiler.sh stop
```

Wait until the first capture finishes before requesting the second. Start always
recreates the profiler so it attaches to the current world namespace; after a
world replacement run start again. The script never starts/restarts world as a
dependency. Start may build the small profiler image. Stop leaves world running.

Administrative chat, once r58 is active:

```text
!perfil reiniciar
!perfil iniciar 30 cpu
!perfil estado
!perfil informe cpu
!perfil informe total
!perfil informe wait
!perfil informe max
!perfil iniciar 30 waits
!perfil detener
```

Commands never accept another process/PID, URL, SQL or arbitrary subprocess.
`reiniciar` resets feature counters only. `detener` stops the capture child only.
The aggregate `informe` works with the external service off; capture/status
report its unavailability without affecting gameplay. Light counters continue
when the external service is off.

Artifacts: `.runtime/local/profiler/capture-*.speedscope.json` and sanitized
sampler logs, retaining eight capture sets. Private feature summary:
`.runtime/local/logs/profiles/performance-latest.json`. APIGET/report reads that
summary; GET/artifacts lists the captured profiles. The host CLI renders a
ranked Markdown table. Profile artifacts can be analyzed with a local Speedscope
viewer. Do not treat an idle-thread stack as CPU consumption.

## Interpretation and acceptance

1. Start profiler; world health must remain200. Clear counters with `!perfil
   reiniciar`, begin30seconds CPU capture, and play normally: move, open inventory,
   equip a mount, enter/leave a bag and start a fight. Capture must finish with
   return_code0. Query feature rankings and inspect the saved profile.
2. Repeat capture in waits mode while running `!checkpoint`. The capture includes
   idle/blocked threads; compare it with feature CPU/wall timings and the native
   watchdog if a checkpoint exceeds five seconds.
3. Stop profiler while continuing to play. World remains healthy, gameplay works,
   and `!perfil informe` still works. Starting a capture while off must return a
   clear unavailable message. Start it again without a world restart.

Wall times and thread CPU are inclusive: nested spans overlap, so do not add them.
Non-CPU time is an estimate only for calls with measured thread CPU. Unknown CPU
coverage is explicit; direct catalog/DB observations are not falsely assigned to
waiting. p95 is a histogram upper-bound estimate. Samples are statistical Python
stack observations, not exact all-function CPU or per-SQL timings. Process CPU,
RSS and thread count come from `/proc` independently of the game's GIL. Exact
native-extension attribution and distributed AI-service spans remain future work.

## Verification

Core/integration gate:60tests passed with3DB-dependent omissions in an offline
run; the20native catalog/import tests were then rerun with PostgreSQL and passed
without omissions. External service11tests passed. Root reran30core/chat/storage/
request tests after final command changes, all passed. A100,000-iteration local
benchmark measured approximately1.53us per observation and3.28us per span; this
is an overhead estimate, not proof of production latency improvement.

Real CPU and waits captures against r57 both completed with return_code0. First
CPU profile had3thread profiles,46frames and9active samples. Stopping the sidecar
left world health200. Full r58 image SHA256
`71573c191982ed7c5e4ceacc08e74881fc9c350f306e8a012892cf85f1919c12` matched647
source/migration/tool files exactly. Deployment health is recorded separately
below after startup. No claim is made that existing freeze/performance defects
are fixed merely by installing diagnostics.

Sources: [py-spy documentation](https://github.com/benfred/py-spy) and
[Compose service configuration](https://docs.docker.com/reference/compose-file/services/).

Deployment: r58 health returned200; profiler health passed, internal world-to-
profiler command transport worked, and GET/report read populated counters.
A real CPU profile during r58 startup completed with return_code0. The report
CLI rendered CPU rankings successfully. No optimization was made; Hector
explicitly requested profiler completion and documentation only.

## Large finding recorded, not changed

During r58 startup, a five-second external CPU capture concentrated roughly
4.6sample-seconds in `merge_native_point_areas` and its identity comparison in
`combat_native_area_metadata.py`. This is a sampled startup hotspot, not proof
of its full end-to-end cost or the gameplay freeze cause. World cumulative CPU
was about209seconds and RSS about4.86GB after startup; these are a single cold
run's process observations, not a leak diagnosis or steady gameplay baseline.
No spell/area behavior or algorithm was changed in response. A future approved
optimization should measure repeated callers and prove identical resolved areas.

[Detailed startup finding](../admin-chat/PROFILER-STARTUP-FINDING-20261009.md):94.3% of123 samples belonged to scan/identity checks in one startup compilation.

Final toggle check: profiler.sh stop/start succeeded while r58 retained the same healthy process/image. Internal command capture completed with return_code0.

A later shared-checkout audit found source changes after the r58 build in `wakfu_server/combat/combat_effect_dispatch.py`, `wakfu_server/combat/combat_ordinary_events.py`. These were not made by the profiler work and are not present in the fixed r58 image. Profiler implementation remains the tested built version; no unrelated runtime edits were reverted or deployed.
