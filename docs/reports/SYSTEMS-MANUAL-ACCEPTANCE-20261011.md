# Complete systems manual acceptance — 2026-10-11

> **Historical release guide.** Use the [current single systems acceptance journey](SYSTEMS-ACCEPTANCE-20261011.md). Deployment, reward and NPC expectations below describe an earlier release and must not be used as current acceptance criteria.

## Release status and preparation

> New requested work, not deployed: dungeon Stasis/competitive authority,
> nation infrastructure, personal map objective/compass and rift XP/kamas50x
> ordinary-equivalent rewards are under implementation. The old zero-currency
> rift expectation below describes the prior release only; do not use it to
> accept the new reward implementation. Issue4 fixed1% display is now an
> accepted final limitation and issue6 is closed by Hector; its former native
> activation/visual steps below are historical optional diagnostics.


**Systems deployed and automatically verified at2026-10-11 08:07 UTC.** Complete shared World, AI, ecology and administrator images are healthy; migrations123 and live source hashes are verified. See [release evidence](SYSTEMS-DEPLOYMENT-20261011.md). That release's stable-source window and atomic lock were released. A separate combined release, `monsters-bulk-1297`, is now pending under [World coordination](../../WORLD_COORDINATION.md); its acknowledgements and source-stability commitments govern any next deployment. Graphical acceptance remains pending. Native planting bonus stays disabled in the ordinary profile; its optional native-display step requires the matching server profile and remains NOT RUN until that activation. This document does not request or perform another restart.

Use disposable characters on three accounts: A and B as players, C as an independent observer. Use a separate administrator account for dashboard and administrator-chat checks. Record starting items, kamas, levels and selected builds. Development commands below run in the local chat of an account already authorized to use them; omit a target to change only the selected character. Level increases and item grants persist.

Start with the normal existing client profiles. No client source, assets, scripts or agents are changed. Only the optional planting-display step below uses an existing launcher flag and a manual client relaunch. Record each section as PASS, FAIL or NOT RUN, with character names, time, screenshot and actual behavior. A missing prerequisite is NOT RUN, never PASS.

## 1. Public flora: complete planting, seed harvest and growth cycles

A needs the existing herbalist and lumberjack professions. Check the native profession panel first; do not assume a seed grant teaches a profession.

On A, enter:

```text
!tp 235 86 -161 25
!item 4275 10
```

Plant Cardo in the adjacent native cell `(85,-161,25)` by selecting its seed and clicking the cell. Successful planting consumes one seed and creates one plant. Wait for growth: configured ordinary transitions take about 30 seconds each. Normal maturity offers seed harvest action100 and crop action203. Collect seeds, then wait for the stage2 plant to grow again. Repeat the seed-harvest/growth cycle twice: it must continue growing after the first cycle. Harvest the ordinary crop: item2504, one reward operation and removal of the plant. Replant that same cell; it must behave as a new plant.

On A, enter:

```text
!tp 235 89 -158 27
!item 8063 10
```

Plant Fresno in adjacent cell `(88,-158,27)`. At ordinary maturity, collect cuttings with action538, wait for regrowth and repeat twice. Final cutting action99 grants wood item1723 and removes the tree. Replant, leave the map, reconnect and return: the resource must retain its actual growth state and remain harvestable. B must also be able to harvest public flora without a false ownership warning.

A rare optional variant may occur under the configured policy; actions1475/930 belong to the Cardo/Fresno special branches. Do not require every plant to become rare or count an ordinary mature plant as unfinished. The full-catalog automatic gate covers other species; this graphical sample does not certify every species separately.

## 2. Planting percentages, regional weather and area bonuses

First check the normal profile. If the existing open-planting override is enabled, its percentage display is fixed at1% by the existing override; this does not validate native probability or profession bonuses.

For an explicitly scheduled native-display check, close only the test client and manually launch:

```sh
env -u WAKFU_LAUNCHER_CONFIG WAKFU_OPEN_PLANTING=false bash client-tools/local-client.sh --profile planting-native-qa
```

This uses the launcher's existing flag and changes no client files. The coordinator must first confirm the matching server native profile (`WAKFU_OPEN_PLANTING=0` and `WAKFU_NATIVE_PLANTING_BONUS=1`); the launcher flag alone does not change server probability. Level bonus policy122 and its native effect lifecycle are prepared and automatically verified; activation still requires the coordinated native-profile deployment. Graphical publication remains to be accepted. Compare displayed and recorded server probability for the same seed, profession level, soil and weather. Forbidden soil stays forbidden. Test entry, reconnect, profession progression, hero switch and combat return before accepting a newly activated bonus; bonuses must not accumulate.

For weather, both A and B enter:

```text
!tp 1134 -23 -143 70
!pos
```

Confirm territory79201 and open the weather panel. Current weather and the five-day forecast must agree on both clients. On A only:

```text
!tp 1134 -39 -72 47
!pos
```

Confirm territory79301. A receives that region's independent weather/forecast; B retains79201. Return A to the first coordinate and reconnect: the correct region's state must load immediately, without a stale forecast. Open the area-bonus display while moving between these regions; any displayed bonus must belong to the current territory and survive reconnection without being added repeatedly. An area bonus refresh must not replace correct weather with an unrelated region's state.

For stationary area-bonus acceptance, keep A still with the character statistics panel open while B changes the same region's flora or monster population enough to cross a protector satisfaction threshold. Once the ecosystem panel reports the threshold change, A's Wisdom/Prospection must update automatically within10 seconds at the default worker cadence. A must not move, reconnect or enter combat. Restore the population and verify removal of the bonus. HP, selected build, equipment and direction must remain unchanged; repeated worker passes must not stack bonuses. Record NOT RUN if no threshold can be crossed during this session.

For accelerated weather acceptance, sign in at `http://127.0.0.1:18084`, open Settings, find `weather_simulation` and open its editor. Copy the entire JSON value into a local backup before editing. In the JSON editor change only `day_seconds` to `30`, then Save; keep both players in79201 for at least three model days (90 seconds). Both see identical updates; the first forecast day becomes current on the next modeled day. Repeated weather is allowed. Reopen the setting, replace the entire JSON with the exact saved value and Save again. If Save reports a revision conflict, reopen and record the latest value before retrying; do not overwrite another operator's changes. Do not use Service controls or restart a service for this check.

## 3. Chat recipients and administrative permissions

A and B exchange distinct messages through `/w`, `/p`, `/m`, `/c`, `/r` and local chat. For group chat, invite B normally and keep C outside the party. Move B to another map: public channels and party chat still reach their authorized recipients; local chat remains local. C must not receive private or party content. Preserve the already accepted contacts/ignored behavior rather than repeating its full original acceptance.

Put A and B in the same existing guild and keep C outside. Exchange `/g` messages across maps; only current guild members receive them. Remove B from the guild and retry: B must no longer send to or receive that guild's chat.

**Staged extension: the public aliases below are NOT DEPLOYED in the08:07 release.** Record this portion as NOT RUN until the combined deployment verifies the current chat source. Existing native nation routing is deployed; the alias gate passed63 combined item/chat tests without skips and an independent installed-client receiver oracle. Political and battlefield routing is backed by explicit SQL nation membership, not map location or client-supplied IDs. After deployment confirmation, on ordinary A and B use the public server aliases in local chat:

```text
/l !politica hola desde politica
/l !jcj hola desde jcj
```

Their content must appear in native Politics/Battleground tabs for the same nation, including neutral0 across maps. Enable the existing native chat filters for those tabs. C in a different authoritative nation must receive neither. Empty commands return helpful usage; immediate repeated sends respect the same configured rate limit. These aliases need no administrator/development-console permission and must not broadcast locally. Native slash-command send eligibility still requires actual government/battleground state; no rank or membership is fabricated. See [native eligibility and public aliases](NATION-CHAT-NATIVE-ELIGIBILITY-20261011.md).

With two administrator accounts, send `/a` or `/admin`. Both administrators receive the message; ordinary A/B/C receive nothing. An ordinary account must not send administrative content. ANKAMA `/d` uses a separate intergame service and is not accepted by testing `/admin`; record it separately as unsupported unless its actual service is provided.

## 4. Public Haven Bag rooms, guest gardening and crafting

On owner A, grant supplies:

```text
!item 4263 1
!item 4266 1
!item 4264 1
!item 6293 2
!item 17419 1
```

Enter A's bag. Install decoration, garden and crafting gems in three separate empty rooms. Use one plush tofu6293 to learn it, then place it from the furniture collection. Use17419 to learn the portable station and place it in an enabled room. Learning consumes its source item once; collection placement and packing must not refund a learning item. Record A's remaining inventory and furniture/gem positions.

On guest B, outside combat, grant:

```text
!item 4275 5
!item 2504 5
!item 6363 1
```

B needs herbalist profession72 for the suggested operations. Keep A inside its bag. Bring B near A's exterior bag and enter through its normal action. B must traverse decoration, garden and crafting rooms without “room inaccessible,” including bags with historical restricted room settings.

B plants an adjacent Cardo in the garden, waits for growth and harvests it. Seeds are consumed from B and output belongs to B; A's inventory stays unchanged. B opens the portable station from its native interaction cell and crafts recipe2227 once: consume item2504×5 and6363×1, produce8414×1 and normal profession XP for B. No materials or product come from A. Retry/reconnect must not duplicate the product or XP.

B tries to remove a gem, move/pack A's furniture, change A's layout or access A's account chest: these ownership-sensitive operations must remain denied. Public room-use masks do not grant ownership. A must still perform its normal management operations. A garden room containing a plant cannot be removed. Both exit, reconnect and repeat the visit; room layout and garden state persist. A sibling character on A's account shares the same account bag; another account retains its own separate bag.

## 5. Build/deck selection, modulation and progression

Use a disposable level49 character for the threshold sequence. If it is below49, run `!nivel 49`; never attempt to lower an existing character. Record the native sheet, current/max HP, equipment and selected deck. Create two legal builds through the normal interface with visibly different equipment, aptitudes and spell decks. Keep at least one legal spell exclusive to each deck.

Save and activate build B, reconnect, open the panel and start an ordinary fight. The effective deck and legal available spells must be B's. Return, activate A and repeat. Editing inactive B must not replace A's active combat deck. Switching, reconnecting and returning from combat must not duplicate equipment or increase HP beyond the selected build's maximum.

Raise the disposable character with `!nivel 50` and inspect the owned spellbook, roster and both sheets immediately, without reselecting or reconnecting; repeat with `!nivel 51`. Then reconnect and confirm those same values persist. The native interface's unlock behavior and effective sheets must agree, including any sheet explicitly fixed at49. Do not expect a forbidden downgrade to work. If testing modulation, use the existing native build-level selector and confirm effective level, HP and legal deck together before and after combat/reconnect.

For the full24-build capacity journey, follow the existing build interface: create until24, verify New is disabled, delete the active nondefault build, confirm a valid fallback and intact inventory, create one replacement and reconnect. Existing capacity acceptance is preserved; this run specifically adds selected-deck consumption and HP/modulation evidence.

## 6. Local NPC conversation trial — acceptance failed

Hector reports missing conversations and misplaced NPCs. These four placements
are local test locations, not accredited original world positions. The roots
below match native speakers but are not certified initial story roots. This
section checks interaction transport only; it must not close NPC placement or
dialogue completeness. A server-side re-audit is in progress.

On A, enter:

```text
!tp 1134 -12 -8 -1
```

Approach and select the native dialogue action for each speaker:

| Speaker | Local test position | Published test root |
| --- | --- | --- |
| Arh Kayuh | (-10,-8,-1) |6274|
| Laura Craft | (-12,-10,-1) |6554|
| Tristepin | (-14,-8,-1) |7122|
| Kabrok | (-12,-6,-1) |7279|

Each must show its native name, portrait and localized opening text. Arh Kayuh starts with “Hmmm...” and offers “Pero... ¿por qué?” in Spanish. Initial unconditional choices close without rewards. Reopen each conversation; its correct root returns. Walk away/change map during an open conversation and retry the old choice: no stale reward or unrelated dialogue may occur. Full quests, rewards and story branches are not implemented by this delivery.

## 7. Jalató corpse seeds and expiry

Use a character knowing Peletero. Find a native Jalató through normal travel or first identify its native reference with `!buscar mob jalato`; no guessed spawn reference is required.

Defeat one in the ordinary world. Open its corpse menu: hand harvest3722 and seed extraction3724 must be available; living-only3723 must be hidden. Choose seeds, wait the normal3-second occupation and verify item7361, “Semilla de jalato,” is granted according to the configured harvest quantity. The corpse disappears immediately. Reconnect and retry the old position: no second seeds or hand reward.

Defeat another and take the hand action: one ordinary corpse resource award, immediate removal. Check harvesting a living Jalató still follows its normal action/cooldown. Leave a third corpse unharvested: it should expire after the configured one-hour TTL; no resource may be harvested afterward. The TTL was previously accepted and need only be repeated if this complete run is intended to cover expiry again.

## 8. Account bans in the administrator dashboard

Open the configured local dashboard at `http://127.0.0.1:18084` and sign in with the existing administrator credentials. Use a disposable player account, never the only administrator account.

In Accounts, open the disposable account. Enter a reason and set “Ban until” about two minutes in the future using local time, then choose “Ban account.” Its active connection must close, new login/token use must fail and the account row must show the ban and correct expiry. Another player continues normally. After expiry, a fresh login succeeds without manually unbanning; old tokens remain invalid.

Ban the same account again with expiry empty: the detail must show permanently banned and login remains denied. Enter an unban reason and choose “Unban account.” A fresh login now succeeds; revoked tokens do not revive. Reopen/refresh the dashboard: reason, operator and timing persist. A malformed expiry or empty reason must be refused without an unintended ban. Ordinary players must not gain dashboard access.

## 9. Classic rift: forty complete rounds and surrender control

Use characters at least21. On a disposable lower-level character, `!nivel 50` is an existing persistent test command; reselect/reconnect to refresh the sheet. Prepare the complete party and owned heroes before entry, with at most six real characters.

On both mains, enter:

```text
!tp 527 -192 -30 0
```

Use the classic Astrub portal's normal Enter action. Both arrive in the same interior map1314. Main A uses its ordinary start action0. Verify all real party/hero portraits and coherent placement. Clear at least one wave; the next wave stays in the same fight. Survive the configured40 COMPLETE timeline rounds; a cleared wave alone does not finish/pay the run. Passing remaining legal turns is allowed.

Every eligible surviving character receives its own result and shard rolls: one cleared wave guarantees one2–5-shard roll; five waves guarantee five rolls under the current policy. Equipment begins at two waves, sublimations at four and costumes at five, with their configured random chances. XP and kamas remain zero under the current explicit policy. Reconnect one main during the run and verify its company recovers the current fight without resetting waves.

Repeat with one recipient's bags full: items must remain in temporary loot after reconnect and transfer once space is freed, without duplication. Exit through the native teleporter and confirm both companies return outside. Start a second run, surrender before the budget and verify no rift reward, normal return and ability to reenter. Definitive/keyed rifts remain outside this acceptance and must not silently bypass keys.

## 10. Identification and ordinary enchantment

Use a disposable character with unequipped unidentified socket-capable equipment and a separate duplicate. Record the item tooltips, wallet and shard reserve. Enter `!item 27083 100` for native common shards. Identify the target and select its elemental bonus: the question mark disappears, its sockets become visible, and equipping it succeeds. Reconnect and confirm the selected element and equipment persist.

Unequip it and open the ordinary enchantment interface. Install an eligible socket bonus and record the exact reserve decrease. Increase that same bonus: only the additional cumulative shard cost is consumed. Reopen, equip and reconnect; the bonus, reserve and supported character statistic must agree. Sacrifice the separate duplicate through the native window: only that duplicate disappears, the configured target charge/color/slot operation persists, and a replay or reconnect does not charge twice. A protected or equipped sacrifice must be rejected without cost.

If a target with contiguous blue/green/blue sockets is available, enter `!item 27123 2` and install Topología II once. Exactly one scroll remains. Reopen and reconnect: the attachment and remaining stack persist. Removing it clears the attachment without refund under the current local policy. Record NOT RUN if the required socket pattern is unavailable. EPIC/RELIC eligibility and general sublimation combat effects remain open; this inventory journey does not certify them. See the [deep review](../soluciones-wakemu/22-identificacion-elementos-y-encantamiento/SOURCE-REVIEW-20261011.md).

### Special sublimations — staged migration124

This extension passed the combined63-test gate and independent native attachment oracle, including fresh special-only state, coexistence and independent removal. It is **NOT DEPLOYED** in the release above. Run only after the coordinator confirms migration124 and the corresponding complete image. On a disposable character at least50, grant:

```text
!item 10272 1
!item 24130 2
!item 24309 1
!item 14186 2
```

Keep both targets unequipped. Target10272 is native EPIC rarity7, level20; scroll24130 is EPIC. Target24309 is native RELIC rarity5, level50; scroll14186 is RELIC. Install the matching special scroll through the native enchantment window. Each successful installation consumes exactly one scroll and occupies the special attachment slot without requiring a normal socket-color pattern. Reconnect and reopen: both attachments and remaining scrolls persist. Try the EPIC scroll on the RELIC target and the RELIC scroll on the EPIC target: both must fail without cost or consumption. If the target also has a valid BASIC sublimation, installing/removing the special attachment must preserve the BASIC attachment; removing BASIC must preserve the special one. Removing an attachment does not refund its consumed scroll under current local policy. This checks installation, ownership and native persistence; it does not certify general combat effects.

## 11. Ordinary combat drops and frozen encounter context

This checks issue10 separately from the custom rift policy. On A and B, record inventory stacks, temporary loot and character/build levels. Form a normal party and defeat one public-world monster group through its ordinary interaction. Record the fight ID and both character IDs from the session evidence. Each eligible player must receive their own result; any awarded item must appear exactly once in owned inventory or temporary loot. A legitimate random roll can award nothing, so an empty result alone is not a failure. Reconnect both characters: neither inventory nor temporary loot may gain a duplicate settlement.

The coordinator checks the stored receipts read-only using the recorded numeric IDs, replacing the example values before running this SQL through the existing database connection:

```sql
BEGIN READ ONLY;
SELECT fight_id, character_id, snapshot->'fight_context' AS fight_context,
       snapshot_sha256
FROM fight_drop_awards
WHERE fight_id = 123 AND character_id IN (456, 789)
ORDER BY character_id;
COMMIT;
```

The public-world receipts must contain `in_dungeon=false`, `in_infinite_waves=false` and `downscaled` equal to the current implementation comparison `winning_actor.effective_level < persisted_character.level` for each participant. This proves the frozen local comparison, not native competitive-mode parity: the native description includes modulated or at-level competitive dungeon play, whose authoritative mode contract remains under review. Save both hashes, reconnect and query again: the stored contexts and hashes must remain identical. A level-up from the victory must not rewrite the pre-award downscaling decision. Repeat through an actually supported native dungeon entrance and ordinary room fight: its durable encounter binding must yield `in_dungeon=true`, `in_infinite_waves=false`, including after leaving the room. If no supported dungeon is available, record that branch as NOT RUN; map appearance alone does not establish dungeon authority.

The [complete criteria audit](DROP-CRITERIA-COVERAGE-20261011.md) accounts for686 opaque-complex rows and3,869 separate simple rows missing authoritative Stasis, stele or score inputs. The160 downscaling rows still need native competitive-mode qualification. External tables have no demonstrated direct-monster reference and are not counted as an additional combat-drop deficit. Stasis, stele and score conditions currently have no authoritative production inputs; complex drop criteria remain unsupported. Do not count those rows as accepted from an ordinary successful drop, or infer their semantics from `rollMax`. General statistical drop-rate acceptance requires a separate adequately sized sample; this journey checks delivery, ownership, context and replay safety.

## Completion record

For each section record deployed image/source evidence, PASS/FAIL/NOT RUN, screenshots, account/character, timestamp and any blocking prerequisite. Send one consolidated result. Known native nation-chat eligibility and pending graphical planting-bonus acceptance must stay explicit; they do not invalidate independently completed bag, NPC, corpse or ban checks.

Source references: [planting policy](PLANTING-PROBABILITY-20261011.md), [regional weather](REGIONAL-WEATHER-20261011.md), [bag supplies and recipe](../soluciones-wakemu/26-insertar-y-retirar-merkagemas/HAVEN-BAG-SYSTEM-ACCEPTANCE.md), [build acceptance](../soluciones-wakemu/34-builds-personalizadas/PRUEBAS.md), [NPC contracts](npc-dialogue/NATIVE-NPC-DIALOGUE-20261011.md), [corpse actions](corpse-server-menu-visibility-20261011.md), [rift acceptance](rifts/HEROES-AND-ACCEPTANCE-20261010.md), [rift reward policy](rifts/DROPS-REWARD-AUDIT-20261011.md), [development commands](admin-chat/COMMANDS-20261009.md).
