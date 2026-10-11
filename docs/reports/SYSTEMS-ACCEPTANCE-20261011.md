# Complete systems acceptance — 2026-10-11

This is the single acceptance journey for the next coordinated complete server deployment. It supersedes the obsolete zero-currency rift and trial-NPC expectations in the earlier manual guide. It does not claim that the pending image is deployed, or that staged integrations have passed graphical acceptance.

## Before starting

The coordinator records the deployed image, current shared-source fingerprints, applied migrations and enabled feature configuration. Use the existing client unchanged. Do not enable optional native planting flags: issue4 is closed with its accepted ordinary fixed visual1% limitation; that display does not specify the server's actual planting roll. Issue6 is already closed.

Use two disposable player accounts A/B, an optional observer C, and a separate existing administrator account. Record character IDs/names, real level, active build/deck, current/max HP, inventory stacks, account kamas and XP. Add owned heroes and form the ordinary party before grouped sections. Development commands require an already authorized account and persist their changes. `!nivel` only increases levels; do not use it to attempt a downgrade. Missing prerequisites or unintegrated source are NOT RUN, never PASS.

Record one result per section: PASS, FAIL or NOT RUN; time, selected actor, screenshot and actual behavior. Run the following as one journey after deployment confirmation.

## 1. Dungeon Stasis, competitive profile, drops and return

Durable selection, native scaling and custom automatic profile were confirmed in the complete20:24UTC deployment. Verify the current image before running; later score/allocation/Ranch/intergame/NPC changes require their own subsequent publication. Use the native Jalató route: source26842, destination2504, interior map1086. Luna independently verified the exact native approach cell below against active catalog677062ae… and published geometry. The object center(-245,-90,2) is not walkable; use its accredited approach instead.

On disposable A outside the dungeon, raise to200 only if needed; on disposable B below20, raise to20. Existing characters above20 cannot be downgraded:

```text
!nivel 200
```

On B only, if below20:

```text
!nivel 20
```

On each main:

```text
!tp 527 -245 -89 0
```

Use the adjacent dungeon entrance's normal action; do not teleport directly to the interior. Native destination2504 is map1086(4,-12,0). This route's competitive cap is20.

Choose Stasis5 and competitive mode in the existing native entrance interface. Record the recommended cap shown there. Use one disposable character above that cap and one exactly at it; both must receive the competitive entitlement. A forced-competitive dungeon must retain its forced mode. Never accept map appearance alone as proof of dungeon membership.

1. Before entry, record both actors' real level, selected build/deck, equipment and wounds (`maximum HP - current HP`). Enter normally with the existing party/heroes.
2. Verify effective level is `min(real level, native competitive band)` and the temporary automatic sheet is selected. The native bands are20,35,50,65,80,95,110,125,140,155,170,185,200,215,230. The owned build and inventory must remain intact.
3. The temporary profile is explicitly local balance policy: it replaces owned gear/aptitude contributions with native bare-character stats plus HP`10×L`, each elemental mastery`4×L`, each elemental resistance`floor(L/2)`, initiative`L`, critical chance`floor(L/10)` capped100, AP+1 at50 and another+1 at125, MP+1 at80. Breed WP/baseline remain. This is not official automatic-profile parity. Check HP/AP/MP and one mastery/resistance against the same actor's bare baseline; do not compare against its equipped outside values.
4. Verify the legal deck retains its slot positions, clears locked slots/spells and caps effective spell levels. Saving/activating/deleting the temporary sheet must be rejected. Switching heroes and reconnecting must recover the same authoritative profile, effective stats and coherent current/max HP.
5. Start an ordinary room fight. At Stasis5, native dungeon type0 HP/damage percentages are360/200; types1/2 are400/210; types3/4 are310/200. The coordinator identifies the actual native type before choosing an expectation. Damage uses native conditional value branches, so a random attack ratio is not sufficient proof. Check the authoritative maximum HP and frozen scaling receipt; use the automatic combat oracle for exact conditional damage. Its constructor-to-real-attack gate passed2/2 with stable source hashes and demonstrated100%→5damage and200%→10damage; this evidence does not claim a deployed image.
6. Finish the encounter. Competitive Stasis5 reward rate is400%; record the award and frozen encounter context. A random empty item roll is allowed; any awarded item must belong to the recipient once, or remain in temporary loot if full. Reconnect and confirm no duplicate XP, kamas or items. Ordinary XP/drop policy and rounding remain the project's documented reference policy.
7. Between settled rooms lower difficulty to3 through the native selector. The current dungeon interface must update without a full reload; the next encounter uses competitive140%. The prior encounter remains frozen at400%. Changing difficulty during an active fight, increasing it, or changing competitive mode must be denied without partial changes.
8. Leave normally, then repeat a shorter entry with surrender/exit and reconnect. Restore the original owned level/build/deck/equipment. Preserve wounds and death state through maximum-HP changes; no entry/exit healing or duplicated equipment. All owned heroes return and remain controllable.

Stele loot is authorized only by the actual paid native selection and frozen item allowlist; unselected rows must not become globally eligible. The686 opaque criteria stay disabled. Run the [Stele journey](NATIVE-DUNGEON-STELES-20261011.md) and [score/rarity extension](LOCAL-DROP-RARITY-ALLOCATION-20261011.md) after their recorded deployment. These explicit local adaptations do not certify official whole-state parity. Numeric checks use durable receipts, not a separate random outside fight.

## 2. Classic rift: forty rounds,50× currency and six real characters

Use characters at least21. Only for a disposable lower-level character, `!nivel 50` is a verified persistent command. Use two mains with two real owned heroes each, or a smaller existing party. Prepare the companies before entry; six is the supported local maximum.

On both mains:

```text
!tp 527 -192 -30 0
```

1. Use the classic Astrub portal's ordinary Enter action. Both companies enter the same interior map1314. Main A uses the normal start action0. All real party/hero portraits must appear once, with coherent placement/control.
2. Clear at least one wave; reinforcements remain in the same fight. Continue to five cleared waves if practical. Reconnect main B during combat: its company recovers the same fight, wave and actor identities.
3. Survive40 COMPLETE timeline rounds; a cleared wave alone does not settle/pay the run. Defeat some enemies in the final unfinished wave as well. Passing legal remaining turns is allowed.
4. Every eligible survivor receives ordinary-equivalent XP and kamas for actual original enemies defeated, multiplied by50. Planned enemies, living enemies and summons contribute nothing. The coordinator compares final amounts against the recorded `fight_reward_policy_receipts.snapshot.ordinary_baseline`, including its single kama draw; final amounts equal the baseline×50 except documented storage/native limits. Do not demand the same kama draw from a separate fight.
5. Physical rewards retain their separate policy: one shard roll per cleared wave, each2–5shards; equipment begins at two waves, sublimations at four, costumes at five, with random chances. Full bags retain awarded items in temporary loot. Free space and claim once; reconnect/reopen must not duplicate any settlement.
6. Exit through the normal teleporter. All company members return outside. Start a second run and surrender before the budget: no currency/items are awarded, exit/re-entry works. A surviving zero-kill run also has zero currency. A seventh real participant must not join a full six-character run.

Definitive/keyed rifts remain outside this journey; do not bypass their physical keys. The old zero-XP/kama success expectation is obsolete after the new currency implementation is deployed.

## 3. Authoritative nation, group/guild state and nation channels

**Staged nation chooser:** the public command and original native chooser are prepared; final chooser verification and deployment must be confirmed. Use disposable neutral characters at level1 or higher. On each main enter:

```text
/l !nacion
```

Choose the same displayed nation on A/B and a different one on C, then confirm through the original native dialog. The chooser uses native actions30–33 and confirmation, not arbitrary client-supplied affiliation. Already-affiliated actors must not silently switch nation. No fabricated government/battleground rank is required.

Record affiliation before entry/reconnect/hero switching; the selected actor, company projection, guild member projection and recipients must agree with the actor's stored nation, independently of its current map. An unselected sibling remains neutral0; selecting a nation must not silently affiliate every character on its account. Reconnect and confirm the individual membership persists.

Native channel sending remains open; the rejected Politics/PvP command aliases
have been removed. Use only original native channels for acceptance:

- `/b acceptance battlefield`: the original client sends only from a world
  whose installed battleground flag is true. World1134 is not such a world.
- `/f acceptance politics`: the original client requires an actual government
  office as well as citizenship. Enrollment alone does not satisfy this gate.
- `/a acceptance admin`: requires genuine administrative authorization. Test
  with authorized administrator accounts only once their native rights
  publication is verified; ordinary accounts must remain unable to send.
- `/d recipient message`: is intergame direct messaging, not administrative
  chat. It requires a separate connected intergame service and recipient
  directory. The native backend and authenticated HAAPI token endpoint are now implemented; World and Shop must both include the qualified changes before testing. Use the recipient account name and decimal tag from the native directory, for example `/d "<B-account-name>#<B-account-ID>" Native intergame acceptance`. A sees the native echo and B receives exactly one message; C receives none. Ignored/DND recipients must reject delivery, and revoked sessions must not keep sending.

Native UI channel selection uses the same command gates. Do not fabricate a
world type, government office or administrative privilege to run this test.
Same-nation routing must exclude C when a legitimate send route exists; repeat
after reconnect and hero switching. Keep private/party/guild behavior intact.
Original descriptor registration and world-catalog oracles passed independently;
they do not establish ordinary native sending or rendered-interface acceptance.
See [native contracts](NATION-CHAT-NATIVE-ELIGIBILITY-20261011.md).

## 4. Personal destination, minimap and compass

**No verified complete repair.** Hector clarified the original gesture:
dragging an icon from **Marcadores**. Installed original bytecode routes that
to a local personal note, with no compass action. Independent reachable-drag
oracle passed; the reported minimap visibility of the actual note is still
unverified. Exploratory screenshots do not establish acceptance. No client
files, preferences or assets were modified.

1. Outside combat, open the current map with `M`, open **Marcadores**, and drag
   a palette icon onto a reachable cell at least ten cells away. Release, enter
   a distinctive note description and apply. Close the map and check the note
   icon on the minimap with the personal-note filter enabled. No compass is
   expected from this gesture. Reopen the map and check cell/text; reconnect
   and verify local note persistence separately.
2. For a genuine compass creator, right-click another visible owned character's
   name in native chat and choose **Mostrar**. Use a private message only
   between characters belonging to the same user; no public test message or
   fabricated author. That actor must be loaded, visible and farther than ten
   cells. The original action creates its target from the actor's real position.
3. Close the map and inspect the target and compass. Walk toward an accepted
   target; native near-target cleanup is valid. A created objective can be
   dragged to relocate it; static map points of interest cannot create the
   initial objective. Repeat after hero switching and map changes when these
   prerequisites exist. Do not assume reconnect persistence. Mostrar graphical
   acceptance remains pending; its native menu/action route is proven.

Record rejected gestures separately from accepted targets that fail to render.
Do not change client files or invent a server acknowledgement. See the
[exact native contracts and observation limits](minimap/NATIVE-PERSONAL-DESTINATION-20261011.md).

## 5. Ecosystem list, regional weather and area bonuses

On A/B:

```text
!tp 1134 -23 -143 70
!pos
```

Confirm territory79201. Open ecosystem and weather: both clients show the same regional family set, current weather and five-day forecast. On A:

```text
!tp 1134 -39 -72 47
!pos
```

Confirm territory79301; only A changes to its regional state. Return/reconnect: correct region/weather/forecast load immediately. Ecosystem entries must not repeat family IDs or display empty unnamed sentinels; the original native panel has three slots, so do not require every global family to appear in every region. Region79101's qualified family set is113/219; no unverified teleport coordinate is invented for that region.

With A stationary and its statistics open, have B legitimately change the same region's population across a protector threshold. After the ecosystem panel changes, Wisdom/Prospection refresh within10seconds at the default cadence without movement/reconnect/combat. Restore the population and expect removal. Repeated refreshes must not stack bonuses or alter HP/build/equipment/direction. Record NOT RUN if no threshold can be crossed. Weather and population display alone do not prove every regional protector provider is implemented.

For complete issue28 coverage, also perform one ordinary planting and harvest
in that same region. Profession XP must include its native regional percentage
before the existing account multiplier: none/some/all wishes satisfied means
-10%/+10%/+30%. Check both actions against the unchanged baseline and durable
receipt, with no duplicate reward on retry. Wisdom/Prospection alone do not
verify these two profession outputs. See the [complete four-output regional
acceptance](AREA-BONUS-ACCEPTANCE-AUDIT-20261011.md).

The accepted fixed1% client planting display remains its recorded limitation; do not infer a failed server planting bonus solely from that display.

## 6. Wells, candles and persistent ordinary lights

**Staged:** migration129/domain gate5/5 and final dispatcher/timer/scene gate29/29 passed with unchanged fingerprints through migrations1–129. The complete deployed image must be confirmed before running; no deployment is claimed. The initial service supports public instance0, not independent dungeon-instance lamps.

Use verified walkable destinations:

```text
!tp 1134 144 8 4
```

Interact with nearby well25457 at144,9,4. Stay still: before2seconds receive no water; afterward receive exactly100 of item2340. Repeat: another100. Move during a third interaction: no reward. Return and retry. Reconnect/retry cannot duplicate a completed reward. Fill the base inventory without a mergeable water stack: completion must fail atomically; free space and retry without a partial award.

```text
!tp 1135 48 63 -60
```

Well31111 at49,63,-60 grants the same100 water after3seconds, but only an authoritative non-hero actor. Test the main character and a controlled hero: the hero receives no reward. Combat or another active occupation must reject interaction. No client timer animation is claimed; no guessed harvest occupation message is sent.

```text
!tp 472 -9 -40 -80
```

Timed light17397 uses ordinary template16. Toggle off/on, leave and return, reconnect and observe the persisted state. Turn it on and wait180seconds: it reverts off and stays off after re-entry. A nearby observer sees the same state within the normal idle reconciliation (about1second); distant clients must not receive out-of-scope object updates. Other verified ordinary templates2/6/9 have persistent toggles without this invented timeout. Balloons, quest candles and unknown scripted objects are not ordinary light switches. Doors, worktables, transport, stools and bag operations must continue working.

## 7. Dashboard account bans

**Pending correction:** the live-lease/FK deadlock fix must be included in the coordinated complete World and administrator images; migration119 already provides the feature schema. No new migration is needed for this correction.

Open `http://127.0.0.1:18084` and sign in with existing administrator credentials. Use only disposable player B for sanctions, never the only administrator. Keep A online as the unaffected control.

1. In Accounts open B, enter a reason, set **Ban until** about two minutes ahead in local time and click **Ban account**. B's live native connection closes, including its active owned company; new login fails. Repeat a sanction while B is actively moving or performing a permitted inventory operation: the request must complete without hanging behind a lease/FK deadlock. A continues normally. Refresh: reason/operator/expiry persist.
2. After expiry, a fresh login succeeds automatically. Old revoked tokens remain invalid.
3. Ban B again with empty expiry: permanent ban is shown and login fails. Enter an unban reason and choose **Unban account**. Fresh login succeeds; old tokens do not revive.
4. Empty reasons and malformed expiry are refused without unintended sanctions. Ordinary players cannot enter the dashboard. Leave B unbanned at the end.

Authenticated HTTP/domain and actual native socket closure were independently verified in the earlier release; rendered controls still require this graphical journey. Interface text must be English.

## 8. NPC quarantine and existing world actors

After migrations126/132 and the additional NPC objective-facts migration139 are confirmed, follow the [complete native NPC acceptance](npc-dialogue/NATIVE-NPC-COMPLETE-COVERAGE-20261011.md), including Grugal, Huly, Kheperalia and Airyna at their accredited positions. After additive142 is deployed, also test Otomaï with `!tp 1385 20 17 1`: click his original dialogue action1244, expect root5772 with native protector424 attribution, then close and reopen. Verify the other four scenes still work and no quest progress/reward is invented. Dialogue availability must follow current native objective facts; no quest reward or progression is invented. To verify the original quarantine separately, use:

```text
!tp 1134 -12 -8 -1
```

The four noncanonical local trial placements (Arh Kayuh, Laura Craft, Tristepin, Kabrok around this cell) must be absent. Their disabled rows remain for review; a deliberately replaced/custom actor is not removed by the guarded migration. Do not expect their old trial roots or treat quarantine as dialogue implementation.

Captured original Guarda de Amakna at11,-13,0, Wuan Tazo at-17,9,-1 and Magnum Deskhalzo at16,8,0 must remain in normal scene publication when in range. Their positions are evidence, not verified teleport destinations. Wuan Tazo/Magnum have native dialogue actions, but no accredited initial text roots or audiovisual response opcode; textual conversation remains NOT IMPLEMENTED. Do not count a silent click as accepted dialogue, send root0/-1 or assign another NPC's text. Existing monster interactions/combat must remain unchanged.

## 9. Haven Bag portal and private return

Follow the [seven-step portal journey](HAVEN-RANCH-PORTAL-20261011.md) as one
round trip: native bag HUD → stairs → adjacent(-8,5,4) → “Entrar en el merkalugar”
→ map1440(28,6,4) → inventory/build refresh → native return → exact prior bag
location → HUD exit → exact saved exterior. Verify wounds and inventory persist,
hero switching is rejected responsively inside, and reconnect returns outside.
Other five empty-model biome choices must reject without changing scene. This
is the Ranch/Merkalugar portal, not an ordinary Zaap destination selector.

## 10. Combat signaling and random borders

Start an ordinary fight with A and B allied, an owned hero, and an opposing
account where available. During placement use the native cell signal action
or `R R`, then click a valid terrain cell. A and B both see the short signal;
the enemy and spectator see none. Repeat with the hero and after the five-second
cooldown. No AP/MP or turn change occurs. Add square, circle, cross, heart,
flower, triangle, skull and moon icons; move and remove them. Both allies see
replacement/removal. Reconnect B: current icons return, old transient pings do
not. Finish and start another fight: no old icons leak. See the
[full tactical acceptance](COMBAT-TACTICAL-MARKERS-20261011.md).

Across several fights, check the selected native border is46 or48 and remains
fixed within its fight, including reconnect. Both are eligible; randomness does
not guarantee alternation or both outcomes in a small sample. Other101 native
borders are inventoried but not certified for the current random pool. Existing
spell, movement, end-turn and reward behavior must remain intact.

## 11. Ordinary seats and interaction cleanup

After migration141 is deployed, approach a common stool within four horizontal
cells and one height unit and choose its native sit action. The selected actor
must sit; a nearby second account must see the matching seated animation and
must be unable to occupy that same seat. Stand, move away, switch selected
heroes and enter combat: each action must release the prior occupancy. Reconnect
and verify that a disconnected actor does not permanently reserve the stool.
While seated, well/light actions must reject without a second active interaction.
Restricted and missing-template placements remain unavailable. The
[per-object inventory](ENVIRONMENT-OBJECTS-20261011.csv) identifies original
placements; do not substitute guessed coordinates for the captured heights.

## 12. Public Haven Bag guests and conserved inventory

This verifies issue26 separately from the owner-only Ranch portal. Use A as the
bag owner and B on a different account; do not teleport B into the private map.
A needs installed garden and crafting rooms and a learned portable herbalist
station. Existing authorized development accounts may prepare missing supplies:

```text
!item 4266 1
!item 4264 1
!item 17419 1
```

Install the garden/crafting gems in empty rooms. Use station item17419 once to
learn it, then place it from the native furniture collection. Do not consume a
second learning item when placing it. On B, prepare only missing test materials:

```text
!item 4275 5
!item 2504 5
!item 6363 1
```

1. Record each account's inventory and exact exterior position. A opens their
   bag; B enters through its actually published nearby entrance. Historical
   lock/deny settings must not block B under the requested public policy.
2. B traverses all installed room types. In the garden B plants a thistle seed,
   waits for mature growth and harvests it. Only B's seed/inventory/profession
   state changes; A's inventory remains unchanged. Ordinary planting rolls
   remain authoritative; the accepted visual1% limitation is not a failure.
3. B uses the deployed portable station from its native interaction cell. With
   herbalism profession72 available, recipe2227 consumes item2504×5 and6363×1
   and produces8414×1, with XP credited only to B. Reconnect and check the
   conserved totals; reloading must not replay the completion.
4. B must be denied the owner's chest, gem changes, furniture packing/moving
   and bag configuration. A retains those owner operations. Public room use
   does not grant ownership or entry to the separate Ranch child session.
5. B exits normally, then A exits. Each returns to their own saved exterior
   and retains their own inventory; re-entering preserves layout, station and
   surviving garden resources. Record NOT RUN for an unavailable installed
   room or recipe prerequisite, rather than treating it as tested.

See the [current public-policy authority](HAVEN-BAG-PUBLIC-GUEST-AUDIT-20261011.md).
Historical ACL-revocation acceptance is superseded by this public policy.

## 13. Build unlock, level refresh and owned manual modulation

This covers34/E06 beyond the automatic dungeon profile in section1. Use
separate disposable characters initially at49,50 and51, or one at49 that can
advance through both boundaries. `!nivel` increases actual levels only; never
try to restore an original lower level with that command. Keep all level
changes on disposable actors and record actual versus effective sheet level.

1. At49, open the build manager and spell library. Record native availability,
   active sheet, deck, HP and one spell whose actual unlock boundary will be
   crossed. On that actor run `!nivel 50`, close/reopen both panels without
   reconnecting, then run `!nivel 51` and repeat. The native build unlock is51;
   the roster and spell library must reflect the actual new level immediately.
   Do not mistake a lower fixed active sheet's casting cap for missing real-level
   spell ownership. If no spell unlock is crossed, record that subcase NOT RUN.
2. At an unlocked level create a named lower-level manual sheet, select legal
   equipment/aptitudes/spells and save it. Switch to the normal sheet and back.
   Its effective level and distinct choices return while actual level stays
   unchanged. Reconnect and verify selected sheet/deck persistence.
3. With a fixed level49 sheet selected on a disposable actual-level51 actor,
   run `!nivel 52`. Actual level becomes52 while effective level remains49.
   Health, XP and selected sheet must remain
   coherent across reconnect; editing an inactive sheet must not replace the
   active combat deck.
4. Start and finish an ordinary fight on the lower sheet. The legal selected
   deck and effective-level statistics must apply, with no stacked bonuses or
   inventory loss. Editing/switching during combat must reject atomically.
5. Continue into section1 with this same manual sheet selected. Automatic
   competitive modulation must restore that exact owned selection on normal
   exit and recovery, retaining wounds rather than healing through maximum-HP
   changes. Reopen both owned sheets after reconnect and compare their choices.

The [complete build acceptance](MODULATION-PROFILE-ACCEPTANCE-20261011.md) also
covers configured nonpermanent sheet capacity and delete/recreate conservation.
Known graphical acceptance remains pending; automatic transaction/native
consumer tests alone do not certify these visible transitions.

## Final record

Send one consolidated result with each section's PASS/FAIL/NOT RUN, deployed source/image identity, selected actor/party, screenshots and timestamps. Closed issues4/6/14/16/39/E09/E13 do not reopen merely because this journey has unrelated failures. Issues29/33 and graphical/system boundaries remain open until Hector's explicit acceptance. Full catalog activation, official formula parity and unsupported quests are not implied by passing this journey.

References: [difficulty authority](DUNGEON-DIFFICULTY-AUTHORITY-20261011.md), [native Stasis percentages](dungeon-stasis/NATIVE-STASIS-PERCENTAGES-20261011.md), [automatic profile](builds/DUNGEON-AUTOMODULATION-CONTRACT-20261011.md), [rift50×](RIFT-CURRENCY-REWARDS-20261011.md), [map objective investigation](minimap/NATIVE-PERSONAL-DESTINATION-20261011.md), [environment contracts/inventory](ENVIRONMENT-INTERACTIONS-20261011.md), [NPC quarantine](npc-dialogue/NPC-ACCEPTANCE-FAILURE-20261011.md), [ban readiness/correction](ACCOUNT-BANS-READINESS-AUDIT-20261011.md), [earlier deployment evidence](SYSTEMS-DEPLOYMENT-20261011.md).
