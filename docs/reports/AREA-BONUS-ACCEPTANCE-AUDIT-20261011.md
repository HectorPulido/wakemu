# Issue 28: regional bonus acceptance audit

Scope: source/read-only catalog audit after the ecosystem list correction. No deployment, service operation, population mutation, client edit or monster catalog activation is included.

## Complete native effect coverage

The active protector catalog defines exactly four effects in each of its three satisfaction states:

| Wishes satisfied | Native state | Wisdom | Prospection | Planting profession XP | Harvest profession XP |
| --- | --- | --- | --- | --- | --- |
| None | 1917 | -10 | -10 | -10% | -10% |
| Some | 1915 | +30 | +30 | +10% | +10% |
| All | 1916 | +60 | +60 | +30% | +30% |
| No eligible wishes | none | 0 | 0 | 0% | 0% |

`territory_bonuses.stat_bonuses` handles native gain/loss effect classes 166/167 and 162/163. `profession_xp_percent` handles classes 2007/2008. Profession award callers apply the regional percentage before the account multiplier; receipt replay is idempotent. Combat attaches fresh nonpersistent regional statistics; exploration publication uses native13046 and explicitly clears zero values. These are all effect types actually present in these protector states.

No Almanax implementation or provider exists in the current server source. Almanax/calendar rewards are therefore an independent missing provider, not a hidden implementation of a fifth protector effect. This audit does not claim that all unrelated temporary bonuses in the game have been implemented.

## Regional population and installed monster catalog

Read-only catalog inspection found 2,874 monster references in 398 families; 367 families contain more than one breed. The population snapshot counts each living group member using the reference's native `family_id`, so different breeds aggregate into one family instead of generating UI rows. All families used by protector monster wishes resolve to at least one installed breed. Of the 105 positive ecosystem display families, only family6 has no installed breed; it is not used by a protector wish. No new breed, population or habitat was enabled during this audit.

The existing snapshot scopes both entity queries by map and instance, resolves every entity to a native region, excludes defeated groups, excludes resource stages0/16, omits fixed resources and monster seeds from plant counts, and fails closed on unresolved positions. Fighting groups remain alive and counted until defeat, consistent with the durable lifecycle. The separate list correction projects canonical regional display families; it does not change underlying population counters.

## Performance and ownership

The worker prepares at most64 scopes per invocation (default16), snapshots each online map/instance only once and rotates scope selection for fairness. SQL and geometry resolution run outside world ownership locks. Revision reads before/after population reject concurrent mutations. Owner-session delivery fences world epoch, revision, observation age, session generation, peer and exact position, and suppresses unchanged values. A recent direct context refresh supersedes older worker observations. No weather is resent by this publisher. Existing unit tests explicitly assert SQL does not run under the world lock and exercise one-slot fairness.

This bounds scopes, not entity rows inside one scope: a heavily populated instance still requires a complete population scan. No benchmark under production-scale populations was performed, so no millisecond latency claim is made. The inline movement path still refreshes a complete authoritative context; any future optimization should retain completeness/revision fences and be measured first.

## Full manual acceptance

Use the same character, equipment and active build for the whole sequence. No special item or admin command is required. Record the character's Wisdom, Prospection, HP, facing, region and ecosystem wish satisfaction before each step.

1. Open the ecosystem and character characteristic panels. In the current region classify the displayed protector wishes as none/some/all satisfied. Check the regional contribution against the table above, relative to the unchanged equipment/build baseline.
2. Walk across a region boundary into a region with different satisfaction. Check Wisdom and Prospection change by the difference between the two table rows. Walk back and repeat twice: the values must return exactly, never stack; HP and facing must remain correct.
3. In a region with a wish close to its threshold, plant/harvest or defeat living monsters of that wish's family until the satisfaction category changes. Then stand still with both panels open. After the ecology refresh, statistics must follow the new category without requiring movement. If no accessible threshold is close, record this subcase as untested; do not claim stationary acceptance from a region whose category never changed.
4. Perform one ordinary planting and one harvest with an already owned suitable seed/resource. Check profession XP changes use the regional percentage in the table and the existing account multiplier. A failed action must not grant XP or consume an additional seed; receipt replay must not award a second delta.
5. Reconnect in the same region and compare the same statistics and wish category. Start and finish a normal fight, then reopen the characteristic panel. Regional values must remain coherent across entry, combat rewards and return to exploration.
6. Move into a region without eligible protector wishes, when accessible. Its regional contribution must be zero, clearing previous positive or negative values.

Record the observed regions, satisfaction categories, before/after statistics and XP. This is one complete-system acceptance pass; only observed categories count as accepted. Automated checks do not establish graphical acceptance.

## Automated verification

Existing focused tests for territory states/effects, bounded stationary publication and durable population were requested from the verification agent against current integrated catalogs. Latest result/log is recorded after completion. The preceding ecosystem projection gate passed39/39 and independently covers all274 regions and four installed name locales.
