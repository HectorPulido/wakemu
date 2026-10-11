# Cautious optimization batch — 2026-10-10

## Change

Profiler artifact downloads now stream at most 64 KiB per read instead of loading the entire artifact into a bytes object. Content-Length comes from the opened descriptor; downloads stop at that advertised snapshot even if a live capture grows. Opening rejects symlinks and non-regular files, and disconnected clients close the descriptor cleanly.

Payload-buffer memory changes from O(file size) to O(64 KiB) per download, excluding HTTP/kernel buffers. This is not a claim that combat latency is resolved. No world, spell, AI, inventory or database semantics changed in this batch.

## Validation

Independent regression runner: profiler service 21/21 passed; performance acceptance 15/15 passed. New regressions cover bounded reads and content parity, growing artifacts, client disconnect and a symlink substituted after route validation. Full profiler source and pinned dependency manifest were compared byte-for-byte with the built image before replacement.

## Deliberately rejected changes

- Catalog document-hash caching: only two offline one-shot consumers, so no demonstrated runtime benefit.
- Inventory removal projection: full hydration currently enforces additional authority and malformed-state rejection. Replacing it with equipment-only SQL would change failure boundaries without an agreed contract.
- Combat-history cloning, AI reuse and global gameplay lock changes remain separate work requiring stronger invariants and focused regression coverage.

## Deployment and manual acceptance

Only the profiler container is replaced. Image: `wakemu-profiler:bounded-streaming-20261010`, also tagged as the Compose default `wakfu-local-profiler`. Previous profiler image retained as `wakemu-profiler:before-bounded-streaming-20261010`. World is not restarted. Replacing the recorder creates a short sampling gap; one-hour artifacts remain on the existing volume.

No game-specific manual action is required. Optional complete smoke test: start a normal fight, move/cast/end turn, use `!perfil estado`, finish or surrender, and move again. All game behavior should remain identical; profiler status should report the recorder active. A successful smoke test does not prove absence of pre-existing latency issues.

## Live verification

Deployment completed. World and profiler health endpoints both returned HTTP 200. Profiler status reported running=true, continuous_enabled=true, degraded=false. Running profiler service SHA256 matches the checkout: `5d7fed2d8ed9a38523cd21a0f9f902f6dbc961359d9976aa985b093592128236`. World remains image r73 with its original start time `2026-10-10T16:52:48.379013149Z`.
