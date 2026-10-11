# Family 803: fight-cell callback

## Representative scope

Conde Kontatrás (5155 and 5164, level 200; 5760, level 3000) and Nox (5761, level 3000) have family 803 as their sole missing family in the sealed inventory. Separate definitions are retained; shared names do not prove duplication of combat behavior.

## Installed evidence

The runner is `eWH extends eZR`. It has no parameters and selects a cell (`bbB` true, `bbA` false). Application first requires an `eVw` context and a non-null `PN.bad()` grid. It checks the selected cell through `QI.R(x, y)` and returns early when that check fails. Otherwise it calls `eVw.fLY().av(selected_aBn)` with the complete selected cell object.

The installed base `fbX.av(aBn)` implementation returns immediately. This is a callback boundary, not evidence that the server-side mechanic is intentionally inert. Registering a no-op handler would falsely remove the blocker from all four definitions.

## Recovery path

Identify concrete fight-manager implementations and their overrides or a source-qualified server publication contract for `av(aBn)`. Establish what the callback changes and which later consumers observe it. Reuse the existing grid eligibility and cell dispatch once that mutable authority is recovered. Do not infer a teleport, map-center update, or arena mutation from the method name alone.

The installed bytecode is retained privately as `next-family-runners/eWH.txt` and `fbX.txt`. No family 803 handler, activation, or full-monster qualification is claimed.

A bounded class-hierarchy scan of the installed `wakfu-client.jar` found `buH` as the only descendant of `fbX` in that jar. Its bytecode declares no `av(aBn)` override. This narrows the search but does not prove absence of an implementation in another jar or on the original server. The scan receipt records the jar hash and exact scope in `fbX-descendants.json`.
