# Coordinated deployment handoff — 2026-10-09

Hector requested that another agent perform the launch. No restart or deployment
was performed during this handoff. Preserve all concurrent agents' changes.

## Running and pending

Running world: `wakemu-world:chat-admin-20261009-r55`, image SHA256
`dfaaaf6afb3a7b60e3373b1f09d0c4aaf0aabddeea71c4120d12107398ac3346`, healthy at handoff.
This already includes Barrier renewal, explicit group target transmission,
serializable NPC retry claims, tackle/dodge and aptitude build validation.

Pending source: the general attack-preparation completion policy in
`combat_attack_preparation.py`, `combat_final_modifier.py` and
`combat_cast_events.py`. Successful primary attack modifiers construct the declared
native marker once; original cleanup criteria remove the state. Multiple target
damage UIDs are tracked, state/reactive damage is excluded, marker ancestor
criteria are respected, and probabilistic marker branches are not manufactured.
This is an explicit Wakemu policy; the original event-500 publisher is unrecovered.

Final preparation helper SHA256:
`61d979c2f5bb26ccbc7f270e8e0d847ff7093ffbe27f5bf9c86dc0b8b8851f9a`.
Luna verified this exact source in a fresh process: **16/16 PASS, 49.189 seconds**.
Modules: `test_combat_iop_preparation_movement_runtime`,
`test_combat_attack_preparation_policy`, `test_combat_aptitude_healing_runtime`,
`test_combat_cast_event_runtime`, `test_combat_aptitude_initialization`.
This includes actual Iop consumption/banner, five policy cases, actual allied
healing (+12, excluding self), Cra and initial armor (52). No gameplay DB writes.
The prior broad batch was 62/64; do not represent it as a final 64/64 pass.

## Launch procedure

1. Coordinate a production-source freeze with the other agent. The existing
   r56 image and `/tmp/wakemu-r56-manifest.json` are **stale**: both our final
   helper and other agents' production files changed after that build. Never
   deploy that image or use an overlay. Build the entire current checkout.
2. Read `AGENTS.md`. Confirm the active catalog remains
   `b0ed79766ae57e6ef26aa9321d05642522cf4c3d9baf7a22a4ea9d3cefc6f219`.
   Retain the running r55 image for rollback. Record production file hashes
   before building; compare the resulting image's `/app` files to those hashes.
3. Use a fresh unique image tag. Example build commands from repository root:

```sh
export WAKFU_WORLD_IMAGE=wakemu-world:coordinated-combat-20261009-r57
export WAKFU_CATALOG_REVISION=b0ed79766ae57e6ef26aa9321d05642522cf4c3d9baf7a22a4ea9d3cefc6f219
docker build --build-arg CATALOG_REVISION="$WAKFU_CATALOG_REVISION" -t "$WAKFU_WORLD_IMAGE" server
docker compose build ai
```

The AI build must copy from this same new world image. Its catalog build arg is
already present in `compose.yaml`. Do not trust the existing `wakfu-local-ai`
local tag: it was built from the stale r56 source. Update both world image
fallbacks in `compose.yaml` to the new tag after successful validation.

4. Re-run relevant regressions if tested production files changed. The known
   local test environment is:

```sh
export PYTHONPATH=server:server/tests
export WAKFU_DATABASE_URL='host=127.0.0.1 port=15432 dbname=wakemu_runtime user=wakemu'
export WAKFU_DATABASE_PASSWORD_FILE="$PWD/.runtime/local/secrets/postgres-password"
export WAKFU_TEST_GRANTEDCAST=1
/tmp/wakemu-combat-review-venv/bin/python3 -m unittest test_combat_iop_preparation_movement_runtime test_combat_attack_preparation_policy test_combat_aptitude_healing_runtime test_combat_cast_event_runtime test_combat_aptitude_initialization
```

Some native fixture test processes linger after the terminal unittest summary.
Only terminate the exact finished test PID after recording its summary; never
kill server or other agents' test processes. Do not expose secrets in output.

5. Once complete image validation and tests pass, stop world, recreate AI, wait
   for AI health, then recreate world. Starting world during AI initialization
   previously caused a startup failure. Use the one existing world service:

```sh
docker compose stop world
docker compose up -d --no-deps --no-build ai
# Wait until docker compose ps shows AI healthy before the next command.
docker compose up -d --no-deps --no-build world
docker compose ps
curl --fail http://127.0.0.1:18081/health
```

6. Verify the running world image SHA equals the built image; verify production
   source hashes, AI/world health and startup logs. If startup fails, capture
   the cause and restore r55 with its matching AI source rather than leaving
   services down. Record actual image SHA and deployment result in the README.

## Manual acceptance and limits

Cra + Iop are provisionally 2/18, not exhaustive certification.
Use `manual-iop-level60-acceptance-20261009.md` and
`aptitude-manual-acceptance-20261009.md` for full manual acceptance.
Prioritize multiplayer first turn, PvP/PvM join/readiness, alternating turns,
Preparation consumption, surrender/reconnect, end-of-fight UI cleanup and dungeon
progression; watch both clients and server logs. Include Barrier next-turn
renewal, healing received, armor and tackle costs. Do not claim every freeze
self-heals: deterministic missing implementations can still stop progression
with diagnostics; rails do not fabricate acknowledgments, turns or rewards.
