# Installed achievements: inventory and implementation boundary

Status: inventory complete; no achievement has been activated by this audit. Mission-dependent achievements stay blocked under Hector's explicit policy. The native journal can display progress for installed definitions without client changes.

## Exact installed inventory

The shared native catalog contains **3,278 definitions, 6,029 objectives and 5,593 reward rows**. Original `bdD.ded()` tests the category's recursive ancestor4 through `bdL.Bb(4)`: **1,441 definitions are mission-category nodes; 1,837 are outside that mission tree**. Visibility and activation still depend on native criteria. `aeV` is the quest presentation enum NONE/EPIC/MAIN/SECONDARY/REPEATABLE/EVENT, not the mission-versus-achievement discriminator. In particular,15 NONE records are missions and4 EVENT records are outside the mission tree.

Every installed definition, objective, literal dependency, original criterion, variable rule, reward parameter and raw metadata value is retained in [the complete machine ledger](installed-definition-ledger.json). [CSV index](installed-definition-index.csv) and [exact summary](inventory-summary.json) support filtering without reading the full document.

| Inventory bucket | Definitions | Interpretation |
| --- | ---: | --- |
| Mission-category nodes | 1,441 | Excluded from this implementation scope |
| Outside mission tree with literal/transitive mission dependencies | 1,389 | Blocked by current user policy |
| Additional outside-tree records mentioning mission/quest objectives | 19 | Blocked pending reviewed dependency mapping |
| Kill candidates | 54 | Descriptive review candidates;28 have variable rules on every objective |
| Dungeon candidates | 34 | Descriptive review candidates; no complete client variable-rule producer |
| Kill and dungeon candidates | 74 | Includes boss-first/last, seasonal and Stasis conditions |
| Other or opaque | 267 | Exploration, professions, metas, unknown event rules and other families |
| **Total** | **3,278** | Each row belongs to exactly one bucket |

The literal graph scans both definition expressions, both objective expressions and every variable dependency expression. Objective references resolve through their actual owning definition. Closure follows dependencies to mission-category nodes, with self references excluded. A negated/alternative mission reference is still a dependency for this conservative policy; this inventory does not claim every literal reference is a mandatory positive prerequisite. One literal reference remains unresolved and is preserved. Textual classification supplies review queues, never executable rules or automatic grants; localized names alone cannot establish events or dependencies. Unknown or indirect meta dependencies may remain in the other/candidate buckets and must pass rule qualification before activation.

A significant restriction is native achievement2192, **Pledge Your Allegiance**, in the mission tree. Numerous dungeon and ultimate-boss achievements require `GetRealLevel() >= 25 and IsAchievementComplete(2192)`: for example1028,1332 and3498. The server must not fabricate completion2192 or waive it merely to enable those achievements. With mission dependencies blocked, these remain blocked even if the dungeon itself is playable.

## Eligible families and missing contracts

The initial162 kill/dungeon candidates are not162 immediately executable achievements. Examples with original, explicit counter expressions include238–242 (Gobball Pokemob) and243–247 (Tofu Pokemob). Objective617 uses `GetAchievementVariable("nbBouftonBlancKilled") == 1` and native variable51; other objectives retain their exact comparisons. The achievement must latch an objective when its expression becomes true. Batched victories must process relevant unit counter transitions in deterministic order, so a delta crossing an exact equality does not silently skip it. Do not rewrite native equality as >= without an explicit server policy.

The client exposes variable names and dependencies but does not provide a universal variable-to-monster-breed event binding. A future server-owned binding catalog must join verified native breed identities, not fuzzy translated names. The original objective text is useful evidence for reviewed bindings. Ultimate counters such as278 (`nbBUExcarnusKill`) have clear native thresholds but their achievements currently depend on mission2192.

Simple dungeon completion candidates include2204 Gobball Pastures I/objective4347,2209 Tofuhouse I/objective4354,818 Larventura I/objective1638 and3111 No More Bow Meows I/objective6519. These objectives have no client-side event parameter or variable producer: bind their installed IDs to the server's accredited dungeon catalog in an explicit reviewed rule catalog. The result must come from final owned dungeon victory, not entering a map, killing an unrelated matching breed or clicking the journal. Stasis variants additionally require the frozen difficulty and, where authored, effective modulation level. Boss-first/last variants require an authoritative death-order trace; the current final victory receipt alone is insufficient. Timed, equipment, state, summon, challenge and seasonal conditions require their specific event facts and eligibility checks.

The installed `aJN` objective schema contains ID, flag, criteria, markers and variable dependencies; it does not contain a universal event type, NPC/monster breed or event parameter array. Empty criteria are not auto-completion. See [the original native extraction audit](../npc-dialogue/NATIVE-QUEST-DEFINITIONS-20261011.md).

## Repeatability and rewards

Native consumer audit establishes cjM=shareable, cjN=repeatable after completion, cjR=followable, cjL=cooldown seconds (loader converts to milliseconds), getDuration=duration seconds, cjT=recurrence anchor and cjU=recurrence period. **582 definitions are repeatable (cjN),625 have cjU>0 and10 have a positive cooldown (cjL)**; preserve the original representation and boundary consumer, not an inferred reset for every login/day. Opaque cjO/cjV and other flags remain raw. Sharing an entry is distinct from sharing rewards or progress. Snapshot flagV5 is not accredited as a reward-claimed flag.

| Reward type | Installed rows |
| --- | ---: |
| GIVE_PLAYER_ITEM | 2,796 |
| GIVE_PLAYER_XP | 1,405 |
| GIVE_PLAYER_XP_PER_MOB_XP | 574 |
| GIVE_KAMAS | 380 |
| GIVE_PLAYER_TITLE | 349 |
| REGISTER_ZAAP / REGISTER_DRAGO | 38 / 22 |
| GIVE_PLAYER_EMOTE | 14 |
| GIVE_PLAYER_LANDMARK | 6 |
| GIVE_PLAYER_SPELL | 4 |
| GIVE_GUILD_POINTS | 3 |
| LEARN_RECIPE | 2 |

The19 native reward enum types include12 actually used types. Counts are definition rows, not delivered quantities. Keep exact params and flags. Type17 XP-per-mob-XP needs its original base/formula contract; do not interpret its params as fixed XP. A definition with any unimplemented reward handler must not claim successful delivery. Item, wallet and progression primitives can be reused transactionally, but a fight reward receipt is not an achievement reward receipt.

## General server integration proposal

1. Import a versioned installed definition catalog, dependency graph and explicitly qualified event rules. Enforce the mission block transitively before activation. Preserve raw and loader-derived criteria; `aZx` can augment eligibility beyond cjI.
2. Add durable per-character variable/objective/definition/cycle state, tracking, event receipts, reward receipts and notification outbox. Event identities should include source fight/run plus character/rule/cycle; reward uniqueness is character+definition+cycle+reward row. Completion, grants and outbox must commit atomically. Reconnect restores state without paying again.
3. Feed the engine inside existing settlement transactions. `combat_lifecycle.prepare_finish` and `prepare_finish_shared` already own winning durable participants and loot/reward settlement. The actual finalizer supplies original monster references, never client-reported kills or summoned copies. `dungeon_progression.settle_encounter` validates the bound current encounter, locks its run, persists victory/completion/revision and recognizes replays. Use its completed final victory plus frozen dungeon identity/difficulty; aborted/defeated/replayed events cannot add another completion.
4. Keep `character_achievement_authority` synchronized with the new committed state. Its existing running/completed/objectives snapshot currently supplies dungeon criteria only; an initialized empty baseline is not a progression engine. NPC, transport and dungeon evaluators must read the same authority.
5. Encode version5 ACHIEVEMENTS bootstrap from committed state and publish native updates only after commit. Handle13175 tracking with session ownership;12533 is sharing, not reward claiming;13397 activation needs its native eligibility contract. Packet/body contracts:13295 variable absolute value,13832 objective completion,13422 definition completion,13205 activation,13371 tracking. Existing [wire audit](../../soluciones-wakemu/E19-logros/PROTOCOLO.md) includes layouts and original consumers. Current world dispatcher has no handlers for these three requests and wire still supplies the default ACHIEVEMENTS section.
6. Luna qualification should cover distinct eligible victories, replay, reconnect, shared heroes/teammates, unrelated breeds, defeated/aborted/summoned actors, exact-equality counter crossing, blocked mission dependencies, concurrent reward attempts, inventory capacity, unsupported reward rollback and recurrence boundaries. A complete manual acceptance should use an eligible installed kill achievement and a reviewed simple dungeon completion, then reconnect and verify progress/rewards remain unchanged.

No combat or spell decisions need modification. Integration should consume accepted settlement facts through a domain module.

## Custom achievements without client changes

The proven native protocol transmits **state**, not new definitions or text. Original `bdM.dT` looks up definition IDs in its installed registry and warns/ignores unknown IDs; objectives are similarly looked up. Arbitrary new IDs, titles, descriptions or objective text therefore cannot be published into the native journal using the established state messages. Reusing an installed ID with unrelated custom semantics would display misleading original text and is not proposed.

A server-authored achievement using an existing installed definition and matching its text/objectives is feasible after event/reward qualification. Truly new tasks can use an existing server-owned messaging/dashboard surface, with original custom IDs and text there; they would not become native journal definitions. No additional definition/text injection protocol has been accredited, so none is claimed.

## Evidence and reproduction

Reused source `.runtime/local/native-quest-definitions.json`, SHA256 `aa58f226c13fc30c4be6fdc5812a40889472432f26dfb7a98330957eeda2ec48`. The machine ledger retains its source hash. Inventory builder: `.runtime/local/achievement-inventory-20261011/build_inventory.py`; execution completed exit0. Existing installed consumer disassembly plus targeted128MiB javap receipts are in the same private directory, `native-contracts.md`, `contracts.javap`, `registry.javap`, `views.javap`, `periods.javap`. No duplicate bulk export, heavy runtime import, database mutation, client edit or service operation was performed.

This inventory is a concrete implementation map. It is not a deployment or gameplay acceptance receipt. Root owns subsequent README status and coordination of the event/reward engine.
