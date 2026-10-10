# Corpses and account chest acceptance

Source changes only. Do not execute this acceptance until the complete shared
server is built, checked and deployed at Hector's chosen restart time.

## Preparation

Use two local clients, A with an admin character and B from a different account.
Leave enough empty inventory slots on A. Record all existing quantities before
testing. Use the normal Haven Bag entry and its account chest, not an admin
teleport into the bag. Keep the default corpse policy at 3600 seconds for the
one-hour acceptance. A database policy change affects newly created corpses;
existing deadlines remain stable.

## Complete journey

1. As A, run `!item 2504 9` and `!item 2024 1`. Record the resulting quantities
   and the cape's identification/socket state. Enter A's Haven Bag and open its
   account chest. Expect one local DEV compartment with 100 positions.
2. Deposit four units of item 2504. Expect the inventory to decrease by four and
   the chest to increase by four immediately. Deposit the cape, then withdraw
   it. Its identification and existing socket state must remain identical.
   Withdraw two units of item 2504; inventory and chest totals must be conserved.
3. Close and reopen the chest, then reconnect A. Expect the same contents. Select
   another character on A's account and open that character's own bag chest;
   expect the same account contents. Withdraw the remaining two units there.
4. Have B visit A's bag and attempt to open the account chest. Expect denial and
   no inventory change. Try depositing an item equipped in any build. Expect
   rejection without losing it. Test a full destination inventory and chest;
   rejection must preserve both source and destination quantities.
5. Outside the bag, in an outdoor map shared by A and B, run `!mob 1 10 1` as A.
   Defeat the monster and return to exploration. Expect a dead appearance at
   its original exploration position for both clients, ordinary rewards once
   for the fighter, and no reward for an observer. Record the finish time.
6. Move away and return, then reconnect. Expect the corpse to persist with the
   same deadline. Interacting with it must not create a fight, harvest or reward.
   Complete one Jalató room and revisit it within the same retained instance;
   its remains must persist without appearing in another party's instance.
7. Keep one client in the outdoor map until the one-hour deadline. Expect removal
   within the next one-second scheduler tick plus ordinary delivery latency.
   Reconnect and revisit afterward: no corpse may reappear. Each dungeon
   corpse uses its own creation deadline.

## Limits and follow-up

Corpses from partial kills in a lost encounter remain excluded because the
current encounter lifecycle restores that living group. Graphical death pose,
safe picking and chest window refresh require this client acceptance. Unit and
PostgreSQL tests do not certify those visual behaviors.

Do not request complete dungeon or ultimate-boss acceptance yet: the
[inventory](dungeons/INVENTORY.md) and [boss audit](dungeons/ULTIMATE-BOSS-AUDIT-20261009.md)
record known-invalid generated compositions and unverified access/progression.
