# Continuous external profiler — deployment and validation

The user's always-on requirement supersedes manual-only capture. The sidecar
automatically samples all threads at 25 Hz in consecutive 60-second Speedscope
files and persists process/feature summaries every five seconds. World summary
updates remain every 30 seconds; timeline rows include their age. Sampling is
not a lossless operation trace. Locals and game packets are not recorded.

Retention is a rolling hour at chunk granularity, with a default 1 GiB cap.
Earlier capacity eviction is exposed as degraded/truncated. Status reports
coverage, gaps and errors. Stop finalizes only the sampler child, never world.

## Deployment

Profiler image: `sha256:661dcf6f958f52b740845266c26c3a17c40d2b2d6e9774ea3e61a4c90445087f`.
`bash client-tools/profiler.sh start` rebuilt/recreated only the sidecar.
World remains container `a8880c6cbcec792bbf95785a4fe51a8745739d18c9e0d2dec08e928293db7793`,
image `sha256:71573c191982ed7c5e4ceacc08e74881fc9c350f306e8a012892cf85f1919c12`,
started `2026-10-09T20:57:14.849425747Z`. World health passed.
No world restart or gameplay optimization occurred.

Earlier captures were backed up before retention started:
`.runtime/local/backups/profiler-before-continuous-20261009T220311Z`.

## Validation

- External service suite: 14 passed. Python compilation and shell syntax passed.
- Focused server suite: 140 run, 139 passed, one missing-fixture skip.
- Live recording started without a capture request. Two normal chunks chained
  automatically; pause/resume finalized a third partial chunk and resumed.
  All returned 0, with 28, 29 and 27 thread profiles respectively.
- Saved timeline contains process metrics and feature summaries with metric age.
  Status showed recording enabled, no gaps/errors/truncation.
- One-hour expiry and capacity eviction passed controlled timestamp tests;
  an hour-long live soak has not been performed.

See [automated checks](PARALLEL-REVIEW-TESTS-20261009.md).

## Operation and acceptance

Recording is left **on**. Reproduce gameplay normally and report incident time;
no manual capture is required. Files stay private under `.runtime/local/profiler`.

```sh
bash client-tools/profiler.sh status
bash client-tools/profiler.sh artifacts
bash client-tools/profiler.sh stop
bash client-tools/profiler.sh start
```

`pause`/`resume` affect sampling while leaving the timeline service running.
After two minutes, completed chunks must increase and recording remain enabled.
Stop/start must preserve world container identity/start time. Recreate the
sidecar after world replacement to follow its new PID namespace. Sampling cannot
reconstruct intervals before recording was enabled.
