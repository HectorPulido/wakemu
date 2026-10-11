# Scoped native monster spell activation below level 10

Date: 2026-10-10. The selected cohort requires the **entire native level range to be within 1–9**, owned spells, all effect families already implemented, and no candidate dependency gaps. Higher-level monsters and epic/ultimate bosses remain inventory-only.

See [lessons learned](LESSONS_LEARNED.md) for the reuse architecture and preservation rules. The original deployment enabled 30 references. The [subsequent automated activation](AUTOMATED_UNDER_10_20261010.md) now enables 40 references in total; 29 remain disabled. The historical evidence below describes the original 30-reference release. See [deployment evidence](DEPLOYMENT_20261010.md) and the [complete manual acceptance test](MANUAL_ACCEPTANCE.md).

## Scope and preservation

There are 69 selected native references, owning 111 distinct spell references after dependency closure. Existing class exporters and converters generate their NPC effect trees; the existing `prepare_npc_spell`, shared native dispatcher, condition evaluation, costs, targeting and transactional commit execute them. No effect family was reimplemented and no missing behavior is treated as a no-op.

The candidate modifies the NPC effect-tree document and adds missing casting-root entries. Every existing root, spell and effect definition is preserved. Native ownership remains unchanged. A rollout policy selects the expanded compiled NPC catalog only for approved reference/actor-level/spell combinations. Other NPC casts retain the original compiled class/shared effects plus the exact preserved NPC baseline; this preserves abilities already supplied by class dependencies even when their spell IDs were absent from the old NPC spell list. Temporary grants retain their ownership route and use the same scoped catalog selection. Player spellbooks and the player casting entry are unchanged.

The shared runtime also requires `native-spell-resource-costs.json`. It was missing from the initial active release, so the first offline candidate included the complete 4,143-spell export prepared by the class resource-cost review (SHA256 `fb10cfe102215efac81153552aa112a3a92d95d91dff76e53fb036d754f827b0`). Another workstream subsequently published exactly that document, producing active revision `1d428d93dd4eeea23c81d10230b33e7bfd897671930efaf8d56ac1c0e82b19f6`; no other base document changed. The NPC candidate was regenerated against that revision and now changes only its two NPC/root documents. Existing class, cost, state, area, actor and world catalog documents retain their original checksums. An already-present shared resource-cost document cannot be replaced through this activation tool.

## Validation gates

- Strict eligibility, unchanged native ownership, level bounds, original class/shared NPC capabilities, temporary grants and separation from player casts.
- Conflict rejection and exact preservation of existing definitions, including overlapping spell-level prefixes and opaque effect metadata.
- Read-only catalog preparation and dry-run staging, immutable source hashes, active-revision fencing, unchanged class-document checks, and rejection of unrelated document replacement.
- Real native NPC transactions on installed map 1134, every owned spell at every selected native actor level, effectful results and unchanged source fights after successful or rejected previews.
- NativeProvider forecasts, actual serialized commit delivery and rollback on serializer failure before a reference can be selected for rollout.
- Existing class and shared-combat regression suites against both the candidate and the shared-cost-only baseline.

A finite target search is not a proof that a pending spell is broken. Conditions, healing needs and initial states can require additional scenarios. Twenty-one selected references have native initial states; they remain pending unless their actual initialization is validated. Merely having implemented families never overrides these gates.

## Current delivery status

The complete 2,874-reference inventory is available as [JSON](ACTIVATION_STATUS.json) and [CSV](ACTIVATION_STATUS.csv), including native level bounds, owned spells, family coverage and native boss/archmonster/dominant flags. The inventory separates static coverage from execution validation and runtime activation.

The active release is `c97c921c35f4b1f808f0bc84970cba2aa09652763394440429a85e9f7f0fee46`. It enables all 30 completely validated references. The 39 pending candidates remain disabled: 21 require an ordinary-NPC initial-state construction path; others have missing native data, unproven semantics/conditions, resource constraints or scenarios not demonstrated by the finite target search. Their exact execution errors and reasons remain in the complete inventory. The other 2,805 references remain inventory-only.

The offline preparation, ownership, import, finalization and staging regression command currently passes 83 tests:

```sh
PYTHONPATH=server:server/tests:server/tools .runtime/local/verification-venv/bin/python -m unittest test_npc_casting_root_import test_monster_combat_extraction test_monster_spell_activation test_monster_activation_staging test_monster_activation_finalize test_stage_mining_navigation_catalog test_combat_active_spell.ActiveSpellTests.test_current_scope_restores_even_on_failure_and_nested_cast
```

These fast tests are separate from the final native audit: all 69 candidates and 169 actor-level/spell combinations were evaluated, with 129 effectful cases and 30 references completely passing. All 30 passed native AI forecast, serialization, actual commit and forced serializer-failure rollback. Final baseline and candidate each passed 179 class/shared-combat tests with no errors, failures or skips and no added failures. Production-source, test-dependency, validator and native-authority fences remained stable. An additional post-deployment probe exercised the actual AI container's NativeOracle for all 30 enabled references, confirming effectful packets and unchanged source fights against the active catalog.

The complete current world, AI and ecology implementations were built and recreated together under the user's renewed restart authorization. Image checks matched 633 world/AI server files and 632 ecology server files to the current checkout, including concurrent Huppermage, Sram and Feca changes. All three services are healthy and pinned to the same active catalog release. The wider historical diagnostic suite still contains unresolved fixtures and independently documented contradictory expectations; the selected passing regression suite is not a claim that every repository test is green.

## Tools

1. `server/tools/prepare_monster_spell_activation.py` exports only the eligible native spell domain and writes a full status inventory plus a fenced candidate.
2. `server/tools/validate_monster_spell_activation.py` tests the candidate in a private in-process overlay; it never publishes catalogs or commits live fights.
3. `server/tools/finalize_monster_spell_activation.py` narrows the rollout to references passing every execution/commit gate and class regressions.
4. `server/tools/stage_monster_spell_activation.py` defaults to read-only dry-run; `--stage` requires validation and creates an inactive release only.

## Manual acceptance after coordinated deployment

Use one existing class character with its normal deck and equipped items. Complete this sequence as a single system test after the actual rollout list is confirmed:

1. In local chat, enter `!mob 5525 1 2`. Attack the group, cast normal class spells, and end your turn. Wonejo attacks, damage, movement and turn completion must still work.
2. Enter `!mob 2616 4 2`. Attack, stay adjacent to a Miaumiau and end your turn. Its native attack must produce animation and damage; its conditional support spell need not fire every turn.
3. Enter `!mob 6 4 2`. Attack and end your turn in reachable range. Baby Tofu must produce its native attack without freezing combat.
4. Enter `!mob 2 4 2`, then repeat separately with `!mob 39 4 2`. The Jalatíns must attack at legal native range; positive MP/AP loss must update the corresponding resource and follow its native resistance rules.
5. Throughout these fights, use damage and class support/state spells, then end turns, finish a victory and start another fight. Check costs, damage/healing, states, packet delivery and absence of stale effects between fights.

Only test new references actually enabled by the final rollout list. Pending references and high-level/epic entries must not be presented as newly activated. Graphical animation, full AI tactics, encounter scripts and rewards remain outside the automated spell transaction checks.
