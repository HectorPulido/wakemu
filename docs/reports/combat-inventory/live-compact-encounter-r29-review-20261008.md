# Running r29 compact encounter review

Read-only inspection found world image
`wakemu-world:dynamic-complete-20261008-r29`, image digest
`cf6f2d25b90a2abf96256a731a2301a90cc6856f812d66095708470c42ad3084`.
The running arena selection, terrain and durable placement policy source hashes
match the workspace exactly. Bootstrap differs from the latest workspace but
contains the NPC Actor-position → wire-coordinate relocation fix.

The latest captured encounter-start requests are fights71 and72 on map527,
2026-10-08T19:00:52Z and19:02:24Z. Both place player6 at(-230,-59,0), and the
single enemy at(-230,-56,0). Replaying the exact installed native map topology
selects347 cells /1132 directed edges inside bounds(-242,-71,-218,-47).
The exported directed path is:

`(-230,-59,0) → (-230,-58,0) → (-230,-57,0) → (-230,-56,0)`.

Reverse reachability also succeeds. The verified native surface catalog gives
`NativeSurface(z=0,bld=0)` and QI.j=True for all four cells. Therefore these two
captured placements do not establish an unreachable enemy or a stale combat
position. The visual screenshot alone cannot override the verified native
surface/path facts; another encounter's exact coordinates or a failed movement
request is needed to isolate a different boundary.

No services were restarted, no database writes were performed, and no speculative
terrain modification was applied during this review. World monster wandering
records are separate from the persisted combat Actor positions.
