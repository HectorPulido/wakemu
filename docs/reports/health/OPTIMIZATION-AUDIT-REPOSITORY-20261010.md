# Repository Performance and Spanish Comment Audit — 2026-10-10

## Scope

This is a static review of first-party client launch/configuration files, root Compose configuration, and root build/runtime scripts. It is not a runtime benchmark, and no files beyond this report were changed.

Reviewed client-side first-party files: `client/zaap-start.sh`, `client/post_update_mac.sh`, `client/config.properties`, `client/log4j.properties`, `client/sentry.properties`, `client/zaap.yml`, `client/manifest.json`, `client/migration.launcher.json`, `client/zaap/settings.json`, and the custom theme XML files under `client/themes/theme_Ymoka_Nightflow/`. The checkout exposes no first-party Java/Kotlin/JS source for the game client; its executable client code is distributed in packaged JARs.

Reviewed root/runtime configuration and build entry points: `compose.yaml`, `compose.profiler.yaml`, `compose.remote.yaml`, `launcher.sh`, `tools/build-local.sh`, `server/Dockerfile`, `server/local-server.sh`, and `database/docker/20-restore-runtime.sh`. The profiler, cron, client-tools, and sniffer implementation trees were excluded because they are owned by the profiling/storage audit. Their source was not counted as reviewed here.

Excluded from source/comment review: binary assets and native libraries; packaged client JARs and resources; third-party libraries, licenses and bundled JRE; decompiled or otherwise native-client code; generated catalogs, captures, fixtures and runtime data; Markdown and TXT documents. Localized game strings and protocol/config identifiers were treated as data/contracts and were not candidates for translation.

## Findings

No Spanish developer comments or explanatory prose were found in the reviewed first-party client scripts/configuration or root build/configuration files. Client copyright headers include the French legal phrase “Tous droits réservés”; it is a retained upstream notice, not Spanish developer prose. No source changes were needed.

The following are concrete configuration points for performance validation. Static inspection alone does not establish that they are causing a live slowdown:

1. **Redis synchronizes every append-only write.** [compose.yaml](/Users/hectorpulido/Documents/wakfu-experiment/compose.yaml:127) starts Redis with `--appendfsync always` and disables periodic RDB snapshots. This favors durability but can add storage latency to write-heavy paths. Compare command latency and fsync time under representative combat/position workload before changing the durability policy.
2. **Position checkpoints run every two seconds by default.** [compose.yaml](/Users/hectorpulido/Documents/wakfu-experiment/compose.yaml:50) sets `WAKFU_POSITION_FLUSH_SECONDS=2`; [local_game_server.py](/Users/hectorpulido/Documents/wakfu-experiment/server/local_game_server.py:161) accepts 0.1–30 seconds and records per-batch timings. More frequent cycles can increase checkpoint work; the existing timing events make this tunable with evidence, while the interval also bounds how long buffered positions remain unflushed.
3. **World and AI image defaults diverge.** [compose.yaml](/Users/hectorpulido/Documents/wakfu-experiment/compose.yaml:25) defaults the world image to `wakemu-world:performance-20261010-r73`, while the AI build argument at [compose.yaml](/Users/hectorpulido/Documents/wakfu-experiment/compose.yaml:105) defaults to `wakemu-world:shared-aptitude-recovery-20261009-r54`. An explicit `WAKFU_WORLD_IMAGE` keeps them aligned; without it, AI may build against a different/older world image. This is a reproducibility and build-cache concern that can also invalidate comparisons between performance runs.

Other inspected runtime probes are lightweight local HTTP or Redis health checks (2–10 second intervals); no evidence from source inspection alone makes them a material performance hotspot. The client launch script delegates JVM heap sizes and options to Zaap, so client memory/performance cannot be assessed from this repository wrapper without the actual launch arguments and a client profile.

## Coverage limit

This report covers only the paths enumerated above. It does not claim a repository-wide audit or a measured performance diagnosis. Source owned by profiling/storage, including client-tools and sniffer tooling, remains outside this review; packaged native client code and third-party dependencies were deliberately excluded.
