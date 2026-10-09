# PvM external marker review

The server and both observer captures prove delivery of external fight markers,
not their successful rendering. Fight 91 was published at 05:12:35 UTC and
received by the observer at 05:12:35.580. Fight 92 was published at 05:12:49 UTC
and received by the other observer at 05:12:49.019. Each received an owned NPC
12608 snapshot immediately before 13753. Their removal packets followed the
actual fight exits about eight seconds later.

Decoded marker topology anchors were (2, -163, 0) and (6, -162, 0), each 19 by
19 cells. The two leader IDs and native partition lists were present. Publication
does not prove that the recipient accepted the external presentation: original
`ckM.a(cuY)` creates its faP/map presentation only when local `biB.doI()` is null.
A lingering client fight attachment remains a possible cause, currently unproved.

The actual marker actor IDs exposed a separate concrete identity defect:
`2**62 + 91` and `2**62 + 92` convert to the same Java/Lua floating-point number.
`combat_multiplayer_wire.external_marker_actor_id` now allocates ephemeral
markers at `2**51 + fight_id`, preserving every signed-int32 fight identity in
both native int64 and the exact-integer range of the existing client number
bridge. This does not change gameplay actor IDs or require a database migration.
The regression checks consecutive observed markers and the largest allowed
fight ID. This correction is not a claim that the missing swords are manually
resolved.

The publication log now records the count returned by the existing world batch
sender. It distinguishes a serialized marker from a marker actually sent to
eligible map/instance peers, without logging private payloads.

## Deployment

The complete current server checkout was built as
`wakemu-world:multiplayer-markers-20261009-r50`, image
`sha256:09c44d7a18b911d9eaa984fb4d3f228ed4b7e50c72db2762cd40fc3f62995180`.
Runtime source hashes and Python syntax were verified in the image; the compiled
runtime catalog loaded successfully. The single world container was replaced
with this image and its health endpoint returned HTTP 200. The marker suite
passed 15/15 tests before deployment. Visual acceptance remains pending:
reconnect both players, start a fresh PvM fight with one player, join through
the outside observer's swords, complete it, then repeat with roles reversed.
