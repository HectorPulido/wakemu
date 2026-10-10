# Parallel issue review — 2026-10-09

User requested parallel review of the current live failures. Review is separate
from implementation and deployment; accepted behavior remains accepted. Game
performance optimization remains explicitly out of scope. A subsequent request
requires continuous external profiling with one-hour retention; its implementation
and deployment evidence will be recorded separately.

| Area | Current evidence | Next work |
| --- | --- | --- |
| Dungeons | Generated first-room roster includes Tofu Real; generator cycles the full species pool, without final-boss exclusion. Actual gate traversal failure remains unresolved. | Verify native room composition/order and runtime entry-to-group reachability across the common configuration pipeline. |
| Spectators/beacons | Remote-effect snapshot validation rejects publication while created actors remain committed. Spell result labels can confuse spectator delivery errors with rejected gameplay mutations. | Separate mutation outcomes from publication failures; establish correct native effect encoding and beacon reaction flow without bypassing validation. |
| Mounts | Old unit remains referenced by inactive build 3; all-build ownership guard explains deletion refusal. Another unit was successfully deleted. No server XP-copy evidence. | Identify blocking build in feedback and validate two distinct native item/pet identities through refresh, destruction and reconnect. |
| Haven Bag | Account sharing and decoration persistence accepted. Central management control and visitor room/workshop use remain unaccepted; native room masks/trigger need evidence. | Establish native management action and explicit room/workshop authorization. Validate gem conservation, zaap and account chest separately. |
| Performance/checkpoints | One cast accumulated about 103 seconds; feature CPU evidence is substantial. Manual checkpoint flushes positions only and zero counts do not validate combat persistence. | Continuous capture/history and evidence-led diagnosis. Do not optimize or claim original freeze fixed. |
| Enchantment/equipment states | Identification accepted. Sublimation installation evidence does not prove combat bonuses; equipment initialization planner lacks a live caller. | Integrate and validate general equipment/state lifecycle separately from identification. |

Detailed evidence and complete future acceptance procedures:

- [Dungeons](../dungeons/PARALLEL-DUNGEON-REVIEW-20261009.md)
- [Spectator/beacon source review](SPECTATOR-BEACON-PARALLEL-REVIEW-20261009.md), [spectator incident](SPECTATOR-FREEZE-20261009.md) and [beacon reproduction](BEACONS-LATE-SPECTATOR-20261009.md)
- [Mount identity](MOUNT-IDENTITY-REVIEW-20261009.md)
- [Haven Bag](../haven-bag/PERMISSIONS-AND-REMAINING-ACCEPTANCE-20261009.md)
- [Performance incident review](PROFILER-INCIDENT-REVIEW-20261009.md)
- [Enchantment/state review](ENCHANTMENT-STATE-REVIEW-20261009.md)
- [Focused automated checks](PARALLEL-REVIEW-TESTS-20261009.md)

No gameplay runtime changes or world restarts were performed for these reviews.
The continuous profiler work is a new observability requirement, not a gameplay
optimization. Automated results cannot replace the failed live acceptance.
