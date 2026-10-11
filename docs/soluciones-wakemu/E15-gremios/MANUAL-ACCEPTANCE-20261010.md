# E15 complete manual acceptance guide — 2026-10-10

## Readiness and boundaries

This guide is for the first live acceptance session **after deployment preparation**. The new guild/chest work was not deployed and its migrations were not applied by this task. Do not expect an already-running world to contain these changes. See [PENDING-20261010.md](PENDING-20261010.md) for the outstanding preparation.

No build, migration or restart is authorized by this document. It contains future test commands and steps; none was executed to prepare this guide. Hector requested no launch during implementation. Do not test Haven Worlds, combat bonuses or automatic guild reward formulas in this session.

Allow approximately 60–90 minutes for the full session. The first useful checkpoint is creation, invitation and item conservation with two clients; complete the rest in the same test system rather than starting unrelated probes.

## 0. Operator preparation and run manifest

Before Hector spends time testing, the operator must finish isolated PostgreSQL validation, the current full-server build, reviewed policy, backup and an authorized deployment. Confirm migrations 101 and 106 are present through the normal complete ordered migration chain. Do not apply just those two files out of order.

Record this manifest:

| Field | Record before testing |
| --- | --- |
| Running checkout/image/commit | Actual deployed identity, not just local source |
| Date and time zone | Include the start time for log correlation |
| A | Exact founder character name and account; admin grant permission |
| B | Exact character name on a different account; initial ordinary-member rank |
| C | Exact third account/character; initially outside A's guild |
| Guild name | Fresh native-valid name, e.g. `Audit Guild Alpha`; names remain reserved after dissolution |
| Creation cost/item | Example policy: 10,000 kamas and one item 16942; verify actual policy |
| Emblem | One configured-valid emblem, identified before the session |
| Bank | Actual configured public map, object ID, position and browse parameter |
| Compartments | Which IDs among 0–3 are enabled/unlocked; each is 40 cells |
| Rank rights | A's full rights; B's view/deposit rights, with withdrawal initially absent |
| Treasury | Enabled/disabled, permission bits, starting balances |

Suggested public bank example from the installed object export: map **527**, object **27021**, position **(92, -45, 8)**. This is an object position, not a verified teleport landing tile. Reach it through normal travel. The operator must validate the current published map/object and browse parameter before adopting this example. If that map is not available in the test world, configure another installed public GuildStorageBox and record its exact location in the manifest.

For the documented chest policy example, compartment-1 management uses native bit **11** (mask **2048**) and item withdrawal uses bit **5** (mask **32**). A rank with 2048 has view/deposit/move according to that example, but cannot withdraw. Adding withdrawal produces mask **2080**. UI labels may vary with client language; use the verified configured mapping. Never substitute arbitrary rights if deployment policy differs.

The UI uses human-facing “first compartment”; the wire ID is **0**. Do not confuse it with ID 1, the second compartment.

## 1. Open clients and prepare evidence

From the repository root, open each existing configured profile in a separate terminal:

```sh
bash client-tools/local-client.sh --profile guild-a
bash client-tools/local-client.sh --profile guild-b
bash client-tools/local-client.sh --profile guild-c
```

These profile labels do not create the required accounts or grant privileges. Use existing test profiles/account credentials; replace labels if your profiles already have different names. Log A, B and C into the same test world. Do not run this launcher merely to verify code while deployment preparation is incomplete.

On A and B, send this command in local chat:

```text
!pos
```

Expected: a local position report containing map, instance, x, y, z. At the public guild bank, instance must be 0 and map must match the manifest. A missing/denied admin command is a permissions setup problem; ordinary accounts normally only have `!ayuda` and `!pos`.

Optional read-only terminal evidence:

```sh
docker compose ps
docker compose logs --since=10m --tail=300 world
```

These commands inspect the stack; they do not deploy or restart it. Record the start time, character names, guild name and bank position. Keep logs/captures private and share only relevant redacted excerpts.

## 2. Create the guild and verify one charge

Skip creation only if the operator supplies a prepared disposable guild; record that creation was not manually tested.

1. On A, record current kamas and current quantity of creation item 16942.
2. From A's authorized local chat console, run:

   ```text
   !item 16942 1
   !kamas 20000
   ```

   `!kamas` **adds** money; it does not set the total to 20,000. Record the resulting balance before creation.
3. Use the creation item through its native inventory interaction. Fill the fresh configured-valid guild name, a configured-valid emblem and valid leader/member rank names.
4. Confirm once. Do not repeatedly click while waiting for a response.
5. Expected under the 10,000-kamas policy: exactly one creation item disappears and the balance decreases by exactly 10,000 from the immediately preceding balance. The guild panel contains A once, with the leader rank. Local identity and B's view of A show the same guild name/emblem.
6. Close and reopen the guild panel. Expected: same guild and founder, no second charge and no duplicate member/ranks.

If the creation screen does not appear, the name/emblem is rejected, or the server says the system is disabled, record the exact message and stop dependent guild tests. Do not guess a new emblem policy or repeatedly grant/consume items to get past the problem.

## 3. Invite B; reject once, then accept

1. On A's guild management panel, invite B using its exact character name.
2. On B, verify inviter and guild names; reject the invitation.
3. On A, verify B is still absent from the member list. B must not gain guild chat or chest access.
4. Invite B again. On B, accept once.
5. Expected on both clients: A and B appear once each, B has the ordinary member rank, and online presence matches the two connected characters.
6. Close/reopen both panels. Expected: two members and stable ranks.
7. Keep C outside the guild. C must not receive this private roster or invitations addressed to B.

## 4. Configure B's test rights

1. On A, create a test rank such as `Chest Tester` or edit a disposable nonleader rank.
2. Grant the configured first-compartment management/view/deposit permission, leaving item withdrawal disabled.
3. Assign B to it. Expected: both guild panels agree on the rank and rights.
4. Try assigning B a rank with greater rights while acting as B. Expected: denied; B cannot grant itself withdrawal or leader rights.
5. Attempt to delete an occupied rank or the protected master/bottom rank only if the UI offers the action. Expected: rejected, without removing members or breaking rank assignment.

Do not destroy the founder's permission mask. The server checks permission bits even for the leader.

## 5. Guild chat across maps

1. Put A and B on different public maps; keep C connected outside the guild.
2. On A, select the native guild chat channel and send:

   ```text
   Guild test A — ñ á é 123
   ```

3. Expected: A and B receive the text once with the correct sender; C receives nothing. It must not appear as public local chat.
4. Reply from B. Expected: A receives it across maps.
5. Return both to the configured bank. Run `!pos` again and record the location.

No arbitrary `/g` alias is assumed; choose the actual guild channel in the client.

## 6. Open the guild chest on both clients

1. Stand near the configured bank, at the correct elevation, outside combat/spectator/haven-bag/private-instance activity.
2. On A, use the installed guild-bank object's browse/open action. On B, do the same.
3. Expected: the same enabled first compartment and the same contents. Other compartments appear disabled if locked/unavailable under policy; they must not reveal items.
4. C may be unable to open a guild bank while guildless; if it opens any UI, it must not show A's contents.
5. Close A's bank view and reopen. B's existing view must remain usable.

An enabled compartment has 40 cells. A different capacity, permanent spinner or missing panel is a failure to record. Do not use the personal Haven Bag account chest as a substitute.

## 7. Controlled item-conservation test

Use a tradeable, unequipped stack of reference 2504. On A's authorized console:

```text
!item 2504 9
```

Before continuing, A must have exactly nine **test units** of that reference, B zero and the selected compartment zero. If any account/chest already owns that reference, count the baseline separately or use a fresh disposable test setup. Count all matching stacks, not only the first visible cell.

Perform these operations in order:

| Step | Action | A units | B units | Chest units | Total |
| --- | --- | ---: | ---: | ---: | ---: |
| Initial | Nine test units granted to A | 9 | 0 | 0 | 9 |
| 1 | A deposits exactly 4 | 5 | 0 | 4 | 9 |
| 2 | B attempts withdrawal without permission | 5 | 0 | 4 | 9 |
| 3 | A grants B withdrawal; B withdraws exactly 2 | 5 | 2 | 2 | 9 |
| 4 | B deposits exactly 1 | 5 | 1 | 3 | 9 |
| 5 | A withdraws the remaining 3 | 8 | 1 | 0 | 9 |

For every row:

1. Use the normal native drag/quantity interaction and enter the stated quantity if asked. If it moves the whole stack unexpectedly, stop and record it; do not continue with incorrect ledger assumptions.
2. Check the initiating character's inventory immediately.
3. Without closing B's/A's already-open view, check the other member sees the changed chest count.
4. Close/reopen only after recording whether the live update worked. If reopening fixes a stale count, report “custody persisted, live update failed”.
5. Confirm A+B+chest stays nine after success and after denial.

A denied withdrawal may be hidden in the UI. If the client offers no withdrawal action, record “UI correctly prevents it”; the prepared automated tests cover direct unauthorized requests. Do not install a packet injector for this manual session.

## 8. Reorder and, optionally, move between compartments

1. Starting from ledger step 5, deposit two units from A. Expected: A=6, B=1, chest=2, total=9.
2. Move the pile to another empty cell in the same compartment. Expected: the source empties, destination contains two, both views agree and the total stays nine.
3. If a second compartment is explicitly enabled, move the pile there. Expected: the first compartment empties and the second has two. Move it back before the concurrency test.
4. If two test piles occupy different cells, swap their positions. Expected: the quantities/properties follow the items; no cloned or missing pile.

Do not unlock compartments through bonus purchases in this session. Mark the cross-compartment case `NOT RUN — second compartment disabled` if only one is configured.

## 9. Simultaneous withdrawal of the last pile

1. Make sure both A and B now have withdrawal rights and both bank views are open and current.
2. Leave exactly the two test units in one chest pile; A=6, B=1.
3. Arrange a countdown and have both clients try to withdraw that whole two-unit pile at the same time, each into a free inventory destination.
4. Expected: exactly one withdrawal commits. Either A=8/B=1/chest=0, or A=6/B=3/chest=0. Total remains nine.
5. The losing client may receive a stale/source-unavailable error, see the pile disappear, or have its opening invalidated. It must not receive two extra units.
6. Close/reopen both views and verify the final counts again. Wait/reconnect if necessary to distinguish presentation delay from persisted duplication.

Two sequential clicks are not a meaningful concurrency attempt; record if you could not overlap them. Exact duplicate packet replay and transaction rollback are automated-test cases, not something a double-click can prove.

## 10. Full inventory and item restrictions

**Full inventory:** use a test character with every eligible inventory cell occupied by nonmergeable items. Make sure no compatible destination stack can absorb the withdrawal; otherwise a successful merge is correct. Put a test pile in the chest and attempt withdrawal. Expected: failure and unchanged chest/inventory counts. Free one eligible cell, reopen if required, and withdraw successfully. If preparing a full bag is time-consuming, record `NOT RUN — full-bag fixture not prepared`; do not modify real inventories destructively.

**Equipped item:** choose a known tradeable equipment item already owned by A. Equip it in any saved build, including an inactive build, then attempt deposit. Expected: denied and item still equipped/owned. Unequip it from every build and retry. Expected: transfer succeeds if all other rules permit it.

**Bound/nonexchangeable item:** use an existing test fixture explicitly identified as bound or nonexchangeable. Attempt deposit. Expected: denied with unchanged ownership. Do not guess an item reference or change its binding directly for this session. Mark the case not run if the operator did not provide a suitable fixture.

## 11. Metadata preservation

Use an existing prepared item with visible element selection, shards, named pet/mount or other supported state. Do not use an important personal item.

1. Take a screenshot of the full tooltip before deposit. Record name/reference, quantity, chosen elements, sockets/shards, pet name/level/health and any visible binding state.
2. Ensure the item is exchangeable and unequipped from every build. Deposit it as A.
3. Withdraw it as B into a free cell.
4. Compare the tooltip property by property. Expected: all supported state preserved; no random reroll, reset pet name/XP or lost shard.
5. Reconnect B and compare again. Expected: the same persisted state.
6. Deposit/withdraw it back to the intended test owner at the end.

If a bound pet is rejected, that is expected access control; it does not test metadata transfer. Exact UID and opaque metadata equality belong to the prepared PostgreSQL tests or an operator's read-only database inspection.

## 12. Isolation and immediate revocation

1. While B has its guild chest open, remove B's compartment view/withdraw rights through A's rank management.
2. Expected: B's corresponding contents are cleared/disabled; it cannot withdraw from its old opening. A retains access. Regrant the test rights and reopen B's chest.
3. Expel B while its chest is open. Expected: B loses guild identity/panel access and its old chest contents are cleared. Later chest/chat requests are rejected. Objects deposited by B remain owned by the guild.
4. Reinvite and accept B before the next cases.
5. If C belongs to a separate disposable guild, open C's bank. Expected: C sees its own guild's contents only; A's objects do not appear. Put a different marker item in C's guild only if the operator prepared one; record both baselines.
6. Open the personal/account chest separately, where already available. Expected: it remains distinct from the guild chest and keeps its original contents. Do not enter or change Haven Worlds.

## 13. Session/activity changes

For each case, open the guild bank first, perform the change, then attempt another chest action if the UI still permits it:

| Change | Expected |
| --- | --- |
| Move away from the bank | Old opening unusable; return and reopen |
| Enter another map | No remote chest access |
| Enter combat/spectator activity | Storage actions rejected while active; ordinary combat still works |
| Enter the personal Haven Bag | No old public guild-bank authority inside the private instance |
| Switch selected hero | Old character's opening cannot operate as the new hero; guild identity follows that character |
| Disconnect and reconnect | New session reads persistent contents; old session cannot keep mutating |

Keep A/B/guild membership and inventories recorded through hero switching; a different character need not belong to the same guild. Resume testing with the intended A/B characters afterward.

## 14. Optional treasury test

Run only if the manifest says treasury is enabled and the expected rights are configured. Otherwise mark `NOT RUN — treasury disabled`.

1. On A, run `!kamas 1000`; it adds 1,000. Record A's resulting wallet `W` and treasury `T`.
2. Deposit 100 through the native bank money UI. Expected: wallet `W−100`, treasury `T+100`; B's open balance updates.
3. Withdraw 40. Expected: wallet `W−60`, treasury `T+60`; the sum remains `W+T`.
4. Try withdrawing more than available. Expected: denial and unchanged balances.
5. Remove money-withdraw rights from B and try withdrawing as B. Expected: denial and unchanged balances.
6. Record the committed treasury balance, reconnect and reopen. Expected: same treasury and wallet values.
7. Settle the disposable guild's treasury through the verified authorized UI before dissolution. Never assume repeated clicks simulate a native retry; replay is covered automatically.

## 15. Reconnect and basic combat regression

1. Leave a known small pile in the guild chest and record all quantities and any treasury balance.
2. Disconnect A and B fully, reconnect, and reopen guild management/bank.
3. Expected: membership/ranks/rights and exact contents/balances are restored; disconnected members are not falsely online.
4. Walk between maps normally. Start one ordinary test fight and cast familiar spells with the same equipment as before this test. Expected: movement, spell availability/costs/effects, HP and combat completion behave as before.
5. Do not expect guild combat bonuses or automatic guild points; these were deliberately deferred.

A client reconnect checks persistence under a new session. It does not establish whole-server restart durability.

## 16. Optional leadership and final cleanup

Run leadership transfer only on the disposable test guild and after the chest scenarios:

1. Transfer leadership A→B using the native master-rank assignment. Expected: exactly one leader, B gets master rank, A loses that rank, and both panels agree.
2. Transfer leadership back B→A so the cleanup owner is clear. Record if the UI cannot offer the action.
3. While an item still remains in the chest, attempt guild dissolution as the current leader. Expected: rejected; the item and membership remain.
4. Withdraw every guild item and settle treasury money. Confirm all enabled compartments are empty.
5. Dissolve as leader. Expected: guild membership, chat authority and projected guild identity disappear for former members; no remaining storage access.
6. Reconnect the former members. Expected: no guild identity or roster returns. Historical names/receipts remain retained, so use a new guild name on a later run.

**Server restart durability remains a separate pending step.** It requires an authorized window, a complete current-checkout build and a real restart of the existing world. Do not restart services merely because this guide mentions the case.

## Failure report template

Report the first failing step before doing cleanup that would erase useful state. You may continue independent scenarios if item ownership is intact; stop custody mutations if quantities differ from the ledger.

```text
E15 test date/time/time zone:
Deployed build/commit from manifest:
Step number:
Character names and roles:
Guild name:
Map / instance / x y z (from !pos):
Compartment and source/destination cells:
Item reference / tooltip name / quantity:
Before: A= , B= , chest= ; total=
Action:
Observed exact message/behavior:
Expected:
After: A= , B= , chest= ; total=
Did the other already-open client update?
Did close/reopen fix the display?
Did reconnect change the result?
Relevant screenshot(s) and redacted log excerpt:
```

Useful server event names include `guild_chest_opened`, `guild_chest_open_rejected`, `guild_chest_request` and `guild_chest_rejected`. Exact wording of UI errors may vary; preserve the message instead of paraphrasing it. Do not share passwords, tokens, full database dumps or unrelated private captures.

Mark every scenario `PASS`, `FAIL`, or `NOT RUN — reason`. The session is accepted only for the scenarios actually run; untested advanced fixtures, PostgreSQL cases, restart durability and deferred bonus/reward systems stay pending.
