# Shared fight 97 recovery

The Cra connection failed at 2026-10-09 15:00:50 UTC while processing ACK 13510.
The NPC turn serialized a registered beacon through AI NativeStats, which read
`Fight.map_id` although the domain Fight has no such member. The remaining Iop
could not advance that NPC turn. After Iop withdrawal, reconnect serialized its
historical, explicitly retired player as an active ordinary participant; its
removed QI slot (-1) correctly failed validation. The dungeon group remained
reserved by the active fight, so it was absent from the world rather than deleted.

Corrections carry the actual owner map through AI statistics and the placement
adapter; derive cell-group map from validated terrain provenance; omit certified
withdrawn participants from reconnect presentation while retaining server history;
retry unpublished NPC turns through the existing shared execution claim; and
remove only disconnected transports from a pending ACK barrier, preserving real
peer acknowledgements and the last-owner reconnect pause.

Validation: 87-test lifecycle batch had six initial PostgreSQL skips; the complete
21-test PvE withdrawal suite subsequently passed against isolated migration-test
schemas, including all six. QI registry 7/7, AI NativeStats 5/5, and the separate
16-test reconnect/retirement/idle suite passed. The complete image contains 623
verified current runtime files; the published compiled catalog loads successfully.
The world AI bridge is mounted from current ai-service sources, whose syntax and
focused statistics tests passed. No damage/spell catalog rules were changed.

The static map audit classifies all direct map/instance member accesses. A qualified
LOS versus OFF_PLAY occupation difference remains an investigation item, not a
claim of a confirmed defect or universal map correctness.

Manual acceptance: reconnect both players; confirm the same dungeon room has its
group; join a fresh fight; summon a Cra beacon; progress through several monster
turns; disconnect/reconnect either owner while the other stays; verify turn owner,
resources and spellbook; withdraw one owner and continue with the other; complete
the fight and confirm both world interfaces and the correct dungeon transition.
Repeat both withdrawal and disconnection with player roles reversed.

Deployment: `wakemu-world:shared-recovery-20261009-r51`, SHA256
`58abe7f9e24017286c7b1c3d52c0f308ca5c2cf8b9e88a0f0bf4d636fa77dc50`.
World is healthy and HTTP health returned 200. Read-only post-restart verification
confirmed fight 97 and its encounter aborted, original group available without a
fight or lease generation, and dungeon run active at room 2, revision 2.
