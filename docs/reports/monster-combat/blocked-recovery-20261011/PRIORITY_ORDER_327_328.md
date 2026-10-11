# Native creature priority orders: families 327 and 328

## Exact installed contract

Installed runners are `eVX` (327) and `eVY` (328), both extending `eZR`. Both require a target but do not require a caster or target cell. They execute only for a target that is an actual `eGj` creature and a nonnegative calculated order ID. A different PV target does not receive an order.

For 327, calculation reads parameter zero through native `eVn.a(0, level, eVh.rpA)`; a missing definition sets amount -1. Execution calls `target.d(orderID, target)` and removal calls `target.e(orderID, target)` before superclass removal. Its extra serialized long field `rAh` is not consumed by calculation or execution: it must not be interpreted as a caster or redirected creature identity.

For 328, calculation initially sets amount -1 and copies the invocation target cell. A present parameter zero supplies the order ID. With at least three parameters, parameters one and two supply explicit X/Y; the native `VF.a(worldID, x, y, targetAltitude, 0)` determines Z for an actual creature target, otherwise Z is zero. Execution calls `target.d(orderID, copiedCell)`. Removal calls superclass removal first, then `target.e(orderID, copiedCell)`. The copied cell is serialized explicitly and preserved by runner cloning; reset clears it. Parameter expressions and altitude resolution cannot be replaced by guessed coordinates.

## Missing authority

The installed client `eGj.d(int,Object)` and `eGj.e(int,Object)` bodies are empty. They are extension hooks for the authoritative AI implementation, not proof that orders are intentionally irrelevant. The only `PriorityGoalType` occurrence in the installed client JAR is the family-328 description; no enum defining IDs or native AI consumer is present there. Existing `server/ai-service` code has no corresponding native priority-order producer/consumer or cancellation ledger.

Implementing an empty handler would falsely report compatibility while dropping movement/targeting mechanics. Implementing guessed priorities from state names would also change mechanics. Before registering either family, obtain source authority for order IDs, creature-vs-cell operand consumers, precedence, duplicate/stack and cancellation behavior, and integration with the existing AI planner. Existing retained runner lifecycle, evaluated parameters and PV identity infrastructure can be reused once that authority is available. Explicit-XY family 328 additionally needs the exact native altitude resolver.

## Representative and bounded evidence

Historical coverage identifies reference 704 Gorditofu (levels 14–18, spells 1434/1435) as missing only 327. Existing sealed state 266 `Furor Materno` includes effect 35173, family 327, parameters `[14, 0]`; the first parameter is order ID 14, not damage. State 1260 `Potencia de las Tinieblas` includes 327 effect 64951 with order ID 1, demonstrating reuse across distinct species/mechanics.

Historical reference 3903 `Chafer desorientado` (level 25) identifies missing 328; same-name reference 3894 is separately covered. These are distinct native definitions and should not be collapsed by display name. Sealed state effects include family-328 order IDs 1, 2, 3 and 6; spell effects 254726/322366/322374 have parameters `[3, 0]`. Historical counts are 19 references mentioning 327 and 20 mentioning 328; their overlap and current qualification were not inferred from those marginal totals.

Source disassembly: `.runtime/monster-blocker-recovery-20261011/next-family-runners/eVX-eVY.txt` and `eGj-orders.txt`. Bounded extracted effects: `priority-order-source-witness.json` in the same directory. No runtime, registry, tests, database, catalogs or services were changed for this audit. No activation claim is made.
