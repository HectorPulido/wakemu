# Placement checkpoint failure and registry cleanup

At 2026-10-08 17:42:50 UTC, boot `5895db3105ea422d974da2207193e65a` registered fight 64 for character 6, then failed in the ordinary request checkpoint with `AttributeError: 'CheckpointWorker' object has no attribute 'terminal_pending'`. At 17:43:12 the next start request failed with `Fight/actor already registered`.

Read-only inspection identified world image `wakemu-world:complete-20261008-r26`, image hash `e7167eff47d2d0869e794975ab875e8264263a241de8f4e76587dbcdbf66aeb9`, container `299b793a3b1f`. The deployed checkpoint worker lacked that method; its source hash was `bd15cc55193ef6d658ddb04c4a9c091431411828094fa7c80d909b76cd2b5a53`. The local worker already defined the required API. Deployment coherence is a separate prerequisite; no service was restarted during this investigation.

The second failure followed a general finalization bug: checkpoint save and flush ran before shared-session disconnect, and an invariant exception escaped the finalizer before durable abort and registry retirement. Finalization now reports checkpoint failures and continues to the existing disconnect and durable health/abort sequence. Normal request errors still propagate. Registry retirement remains after successful durable abort; checkpoint failure by itself cannot release a registered fight or encounter lease.

Changed code: `server/wakfu_server/combat/checkpoint_worker.py` and the checkpoint save/flush boundaries in `server/local_game_server.py`. The regression uses a real placement Fight and Registry, reproduces the missing worker API, verifies the disconnected placement remains registered until explicit post-abort retirement, and then successfully registers the next fight for the same actor.

Validation: `PYTHONPATH=server:server/tests /tmp/wakemu-combat-review-venv/bin/python3 -m unittest test_checkpoint_worker`: 8 tests passed. Both modified production modules passed `py_compile`. This does not claim the already-running deployment or its stale registry entry has been repaired.

## Automatic reconnect reconciliation

The next world deployment (`r27`, boot `fb71b36bc17541f083238806c7153420`) restored the missing worker API. The coordinator's read-only Store query confirmed fights 63, 64 and 65 are durably `aborted`. The new process has a fresh registry. This is recovery of that incident, not evidence that r27 includes the finalizer protection above.

A separate production reconciliation now runs during character selection before HP regeneration, position attachment and world bootstrap. It checks the previous shared participant against the currently selected replacement lease. Only an orphaned PvE placement/active fight with no valid live participant is eligible. Stale in-memory `connected` bits cannot prevent recovery, but another live owner's lease, a duel, settlement or the same current generation prevents it.

The registry claims reconciliation under its locks, then calls the existing durable shared-abort/health producer. That producer preserves the original durable participant roster and entry-health CAS; it authorizes only the matching current selected replacement generation for the reconnecting owner's HP write. The durable abort retains the original participant-generation fence. A previously aborted record with complete health receipts does not write HP again. A previously aborted record without any receipts can finish the exact source-authorized HP abort during owned reconnect; partial or inconsistent receipts reject recovery.

Only after persistence succeeds does the registry remove actor, character and join-alias indexes. Failure restores the original connected/pending state and retains all indexes. The login reloads persisted HP before ordinary world initialization, removes the abandoned public fight marker and records `shared_pve_reconnect_reconciled`. It awards no victory or rewards. Existing encounter-group abort policy restores the group in the same durable transaction.

## Delivery and acceptance

Delivered both protections in `wakemu-world:combat-20261008-r19`, after confirming no active or placement fights. The image includes the final complete durable-receipt guard; shared registry source hash is `6f78b1c04ee4c02b5b8dc77b5ce3defdfd12a829b50cc5c30c69ef313df89301`. Focused validation ran21 tests:12 passed and9 PostgreSQL health integration tests skipped because their explicit test DSN was unset. The reconnect tests cover failed persistence retaining ownership, a successful replacement-login retry allowing a new fight without restarting, the current replacement lease versus old durable participant fence, and preservation of another live participant's fight.

Manual acceptance: start a solo PvE fight, close the client during placement, reconnect and start another fight. Repeat after an active turn. The character must load normally into exploration and the next fight must start without `Fight/actor already registered`. No world restart or manual registry clearing is part of this acceptance sequence. This patch reconciles orphaned fights; it does not add restoration of an ongoing multiplayer fight with another live owner.

## Revised requested behavior: return to the current fight

The user subsequently selected restoration rather than abortion for a recoverable current fight. The implementation under validation retains live PvE placement/action state on transport disconnect, replaces only the expired participant lease, and sends an owned current-state bootstrap. Other participants' fight state, outboxes and acknowledged turns remain intact. A sole-owner transport interruption preserves remaining turn time; a fight with another connected player continues normally. Explicit surrender remains a separate exit.

The revised acceptance is one sequence: enter placement and reconnect; return to the same fight ID and placement. Start combat, spend AP/MP, apply a state and create a beacon or summon, then reconnect; return with the same resources, state and entity, without repeating damage or summon creation. Repeat with a second participant staying connected: their play must continue and the returning participant must rejoin that same fight. Finally finish or surrender normally and start a fresh fight without stale registration. This revised behavior is pending final validation and deployment; r19 above implements the earlier orphan-abort policy.
