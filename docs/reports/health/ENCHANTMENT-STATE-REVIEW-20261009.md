# Enchantment and equipment-state follow-up — 2026-10-09

## Scope and outcome

Read-only source review following Hector's parallel issue-review request. No
gameplay implementation, database rows, services, or client files were changed.
Identification modal, elemental selection, and visible sockets have graphical
acceptance. This does not accept sublimation combat behavior.

Sublimation installation has previous directed codec/SQL verification, but
actual sublimation effects remain unconnected to live combat initialization.
Equipment effects that grant states also remain a separate open coverage gap.
Neither should be described as working merely because its tooltip or attached
scroll is visible.

## Current source evidence

- `server/wakfu_server/combat/combat_equipment_initialization.py:16` defines
  `plan`, selecting owned active-sheet equipment, ordinary passive state roots,
  and attached sublimation fields 24/32. It requires explicit attachment
  eligibility and retains the parent gear's native container context.
- Repository-wide Python references to this module currently occur only in its
  directed test module. No live server path calls this planner. Its existence
  therefore does not establish state initialization during combat.
- `server/wakfu_server/items/equipment_stats.py:151` reports effects that cannot
  be evaluated as supported characteristic bonuses as
  `unsupported-native-effect`; it does not execute a state-granting effect.
- `server/wakfu_server/items/shard_bonuses.py` iterates socket entries (tag 10)
  and evaluates their passive bonuses. It does not execute the attached
  sublimations in tags 24/32.
- `server/wakfu_server/combat/combat_actor_snapshot.py:244` partitions the
  unsupported effects through `combat_initialization_policy`. The explicit
  development fallback preserves supported bonuses and emits skipped-effect
  diagnostics. It does not turn the omitted state into a working effect.
- Hector's captured diagnostic for item 18682, effect 119215, family 400 is
  consistent with an explicitly omitted unsupported effect. This alone does
  not prove a defect in the separately accepted level-scaled mount mastery.

The previous detailed review in
`docs/soluciones-wakemu/22-identificacion-elementos-y-encantamiento/SUBLIMATION-REVIEW-20261009.md`
records 388 enabled BASIC patterns and native state-granting definitions,
including Topología II (27123), state 5992 at level 2. Those counts and the ID
mapping are prior catalog evidence, not a newly queried runtime census.

## General remediation boundary

The next implementation needs a common owned-equipment initialization path,
not individual patches for one scroll or item. Establish native lifecycle
ordering, merge complete root/child definitions before constructing the runtime
catalog, resolve attachment eligibility and parent gear level/identity, and
execute the closure transactionally. Unsupported closures must retain explicit
diagnostics and restore runtime state, outbox, and RNG if execution fails.
Apply the same authority to ordinary equipment states and attached scrolls.
Do not replace conditional or triggered states with invented flat bonuses.

## Exact bounded manual acceptance

Installation only; combat effects are not ready for acceptance:

1. Use an unequipped, already identified item with **blue / green / blue**
   sockets, in that order. Hector's earlier La Cola had this pattern; a freshly
   generated copy is not guaranteed to have it.
2. Run `!item 27123 2` to obtain two Topología II scrolls, using the previously
   verified reference above.
3. Open the item's enchantment window, select Sublimations, select Topología II,
   and apply once. Expect one scroll consumed, one remaining, an attached
   sublimation shown, and unchanged socket colors.
4. Reopen the window and reconnect. Expect the same attachment and remaining
   quantity. Repeating an already applied identical request must not consume
   another scroll.
5. If testing removal, expect the attachment to disappear and no scroll refund
   under the current explicit removal policy. Reconnect and confirm it remains
   removed.

Do not ask Hector to measure this scroll's combat bonus until the live
initializer is connected and its native conditions have an exact acceptance
specification. A matching tooltip is insufficient. No new tests were run for
this documentation-only review; historical test results remain in the linked
issue report and are not presented as a new full-suite validation.
