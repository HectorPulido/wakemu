# Multiple deaths and next-turn synchronization

Fight80 failed at client15:46:45 after a beacon attack defeated two NPCs. Server12727 death actions were delivered, but the native SU removal occurs only after the full animation callback. The action queue can resume after250ms; an end-turn ACK therefore arrived while the client still retained both dead entries. Incremental13337 announced a different next actor and broke SU; recovery then exposed a null timeline row. This is not evidence of a missing scene/map packet.

The shared runtime now detects new native timeline removals and publishes the authoritative12053 snapshot with native12514 ACTION controller presentation at the next-turn boundary. It does not replay13482 turn-start against the old roster. Pending turn ACK regenerates the native absolute wall-clock deadline; server expiration remains monotonic. Subsequent unchanged turns keep ordinary incremental delivery. Explicit recovery uses the same authoritative controller presentation. Delayed native fem.eT callbacks check the exact UID and return when it is absent, so they cannot remove a different row after restoration.

Regression: a live roster-only beacon kills two NPCs in one resolution; both dead identities leave SU while the beacon stays alive outside turn order. End-turn and ACK restore exact current/order/deadline; the following normal turn does not duplicate snapshots. `test_combat_recovery` and `test_combat_runtime_messages`:14/14 PASS.

Manual acceptance: start a group fight, place a beacon, defeat two monsters with one attack, and end the turn promptly. The next living fighter must act, no recovery loop or empty timeline should occur, and later normal turns must continue. Repeat with an ordinary area attack to exercise the shared path. The separate report of one monster playing another monster's death animation remains under investigation.

Delivery: `timeline-death-complete-20261008-r35`, a one-module delta fromr34. Health and source hashes are verified separately after restart.
