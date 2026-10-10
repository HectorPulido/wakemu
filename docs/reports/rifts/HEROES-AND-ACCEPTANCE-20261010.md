# Six-member rift company audit and complete manual acceptance

## Concrete correction

Entry already expands canonical selected mains into real owned heroes, freezes
all their character IDs, and counts every main/hero against the six-member cap.
Heroes share their actual main's account session; no synthetic session is created.
The general combat-company adapter admits those real characters and result
packets identify each inventory owner explicitly.

The audit found that both rift item rewards and the shared combat drop delivery
still required every recipient to be the selected character. An inactive owned
hero therefore rejected its own payout and rolled back the complete winning
settlement. The new `combat_reward_ownership.lock_recipient` preserves the normal
selected-main path. An inactive recipient additionally requires its current native
company slot, the selected company leader, and BOTH the main and hero recorded in
the same finished fight with the same real session generation and team. Merely
owning an inactive character is insufficient. Removed heroes, changed generations
and foreign or omitted mains fail before a committed payout.

The helper is used by rift rewards and existing combat drop delivery; no fight,
spell, damage, wave selection or reward probability behavior changed. Rewards
remain per actual eligible character, not per account. Bag/temporary updates carry
that character's identity and are delivered through its real main connection.

Three isolated PostgreSQL regressions pass: two mains plus four heroes enter as
six real frozen characters under two sessions, receive their own items and replay
without rerolling; removing a company hero rejects and rolls back the complete
payout; replacing a main's generation likewise rejects without partial grants.
This correction is source only, with no deployment or service restart.

## Current definitive-rift contract and gap

Native descriptors prove the following paid start contracts:

| Native map | Descriptor | Start action | Physical key | Cost |
|---:|---:|---:|---:|---|
| 1318 | 1457 | 1 | 28789 | 1, consume=true |
| 1324 | 1458 | 1 | 28790 | 1, consume=true |
| 1347 | 1477 | 1 | 29594 | 1, consume=true |

Action0 is the absent-key message and action2 is lore. Paid-start criteria exclude
heroes from initiating the interaction. The missing-key predicate checks the
initiating character's item quantity. The implementation still rejects definitive
entry/start and rejects enabling ultimate policy. It must not silently waive keys.
A complete implementation must freeze canonical six-member company eligibility,
validate native action1, debit exactly one owned supported key in the same
transaction as canonical start, retain an idempotent consumption receipt, restore
all ownership on failed fight creation/start, and avoid double consumption on retry.
No claim is made that this remaining contract is implemented.

## Complete manual acceptance: maximum six, including heroes

Use two existing test accounts with three REAL characters each, or six independent
accounts for the initial non-hero variant. The two-company variant consists of
main A + two owned heroes and main B + two owned heroes. Everyone must be at least
level21. To raise a disposable test character, select it and enter `!nivel 50`
(the increase is persistent), then reconnect to refresh its native sheet. Existing
characters above21 need no level command.

1. On each main, use the native Heroes panel to add its two owned characters.
   There must be three real characters per company. Invite main B into main A's
   party. The complete company/party must contain exactly six characters.
2. On BOTH mains enter `!tp 527 -192 -30 0`. The active company follows its main.
   These are the Astrub classic portal's native exterior map and coordinates.
   Main A interacts with the rift portal's normal Enter action.
3. Both mains must arrive in the same native interior (map1314); all four owned
   heroes must remain in their companies. There must be no extra client session
   or separate run for a hero. Main A uses the ordinary start activator, action0.
4. Placement must contain all six actual player/hero portraits, four native
   enemies and enough selectable player cells. The two mains control their own
   companies. No same-account hero may displace another participant or disappear
   from the roster.
5. Defeat the first complete native wave. A new wave must appear in the SAME fight;
   the cleared-wave/monster counters advance once. Continue to at least five
   cleared waves. All six and an optional late observer must see the same live
   enemy roster, including native reinforcements.
6. Reconnect main B while the fight is still active. Its real main and two heroes
   must recover in the same fight, with the current wave/actor identities and
   progression preserved. The other company must remain usable.
7. Survive the configured turn budget (default40 COMPLETE rounds). Passing every
   remaining player/hero turn is allowed. The result must include all six eligible
   original characters, with actual cleared waves/kills and individual loot.
   Five cleared waves guarantee five shard rolls EACH, 2–5 shards per roll;
   equipment/sublimation/costume pools remain random under the normal DEV policy.
8. Inspect each character's own inventory, switching company control as needed.
   Items must belong to the credited character. A cosmetic drop is a physical
   learnable item, not an automatic collection-wide unlock. Use it and verify
   exactly its appearance unlocks while that source item is consumed.
9. Repeat with one recipient's bags full. Its awarded items must remain in native
   temporary loot after reconnect and be claimable once a slot is free. Other
   members must still receive their own rewards. Reopening the result must not
   duplicate any items.
10. Exit through the native teleporter. Both main companies must return outside,
    including owned heroes. Re-enter and surrender a second run: it must close,
    permit exit/re-entry and grant no rift rewards. Before-start owner exit should
    instead cancel the complete frozen company atomically, without combat/payout.

Also verify a seventh real character cannot enter alongside six, and lore action1
inside a classic rift never creates a second fight. Six is an explicit local DEV
policy; the installed rift information text still describes the upstream four.
Graphical six-company acceptance remains pending; the user's successful solo
wave2 surrender validates only that narrower path.
