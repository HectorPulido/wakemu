# Owned live-fight reconnect restoration

Transport disconnect is distinct from explicit abandonment. A valid live PvE
placement/action fight remains in the shared registry and retains its native
FSM, runtime, resources, effect ledger and encounter lease. A subsequent owned
login checks the durable participant/phase, suppresses world HP regeneration,
and takes over the previous selected-session generation. Durable aborted fights
continue through the existing reconciliation/health-return path.

`Registry.takeover(..., recover_disconnected=True)` prepares all presentation
packets before the SQL generation fence. Persistence failure leaves membership,
ACK generations, connected peers and pending effects unchanged. A successful
fence migrates only that owner's ACK generation; already received ACKs remain.
A late finalizer belonging to the previous generation cannot abort the restored
shared fight. Other connected participants continue normally.

When the last PvE transport disconnects, the remaining active-turn deadline is
captured. Successful takeover resumes that remaining duration once. A multi-owner
fight with another connected participant retains its absolute deadline. No turn
start, spell cast, state application or server gameplay effect is executed by
restoration.

The owned active snapshot uses cvb/12847, not spectator cva/12044. It uses current
actor stats/effects and the authoritative Tc/SY timeline producer. Native ckP
looks up actors and does not construct missing summoned actors. Therefore the
snapshot also supplies each recorded original summon creation envelope, then
overlays current 13912/12873 actor effects/stats. Current retained carriers are
installed with execution disabled. The existing native ACTION transition and
cvn/12053 restore phase/timeline. An ACK-paused owner receives only the recorded
original 12502/13420 presentation when its ACK is still owed; gameplay deliveries
are never replayed from a disconnected socket's outbox.

This route restores the live process's shared fight. It does not claim complete
process-restart restoration. Missing native timeline/creation/retained authority
rejects snapshot construction before durable takeover instead of inventing state
or aborting a valid fight.

Implementation: `combat_shared.py`, `combat_session_adapter.py`,
`combat_reconnect_snapshot.py`, and the login/adoption/finalizer boundaries in
`local_game_server.py`. Timeline producers and recovery encoder are documented
separately by the timeline owner. Native source evidence: ckP/cvb actor lookup,
cjv/cvn -> buH.dZ -> fcc -> fcb.eG, existing native ACTION and retained-carrier
codecs. The disconnect/takeover timer policy is explicit Wakemu server policy.

## Delivery and verification

Delivered in `wakemu-world:complete-20261008-r28`, image SHA256
`52ec1a12e1b3f69b0f6664b7de91be89eac0918db70005b79b7516172780d8fc`.
Twelve production source hashes inside the image match the checkout; the private
delivery manifest records them. No active or placement fights existed before
deployment. Final focused validation passed24 tests without skips. The broader
shared-registry/reconnect batch passed54 tests, and the real summon-entry fixture
verified constructor replay once, current resource overlays and unchanged server
state. Native result delivery now places12755 before12238; routine checkpoint
saves no longer publish chat notices.

Manual acceptance: start a fresh PvE fight, place a beacon and spend AP/MP; close
the client and reconnect to the same character. Expect the same fight, current
resources and beacon, then continue attacking. Complete the fight and expect the
results dialog before returning to exploration. Repeat with another participant
remaining connected: their fight must continue and the reconnecting character
must return to that fight. No world restart is part of these acceptance steps.

Fight66's81-second settlement delay remains unlocalized. Existing structured
logs now include group-lock, SQL-lock, reward/loot and results-presentation stage
timings; no latency repair is claimed solely from these observations.
