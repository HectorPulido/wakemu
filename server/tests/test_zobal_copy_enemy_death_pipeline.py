"""Actual owned NPC spell, not direct PA damage, kills Zobal copy or its owner."""
import os
import random
import unittest
from collections import deque
from copy import deepcopy

import test_zobal_copied_action_lifecycle as zobal_lifecycle
from wakfu_server.combat_hp_raw import set_hp_raw_current
from wakfu_server.combat_npc_spell import prepare_npc_spell
from wakfu_server.combat_qi_fight import current_registry
from wakfu_server.combat_summon_retirement import retired_summon_ids
from wakfu_server.fight_checkpoint_store import snapshot
from wakfu_server.combat_diagnostics import combat_diagnostic_scope


@unittest.skipUnless(
    os.environ.get("WAKFU_TEST_GRANTEDCAST") == "1", "native runtime opt-in"
)
class ZobalCopyEnemyDeathPipelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        zobal_lifecycle.ZobalCopiedActionLifecycleTests.setUpClass()

    def approach(self, fight, characters, monster, decks, victim_id, *, actor_id=-7):
        from wakfu_server.combat_tactical_ai import NativeProvider

        target = fight.actors[victim_id]
        enemy = fight.actors[actor_id]
        blocked = {
            actor.position
            for actor in fight.actors.values()
            if actor.id != enemy.id and actor.hp > 0
        }
        queue = deque([(enemy.position, [])])
        visited = {enemy.position}
        routes = []
        while queue:
            cell, path = queue.popleft()
            if cell[2] == target.position[2] and (
                abs(cell[0] - target.position[0]) + abs(cell[1] - target.position[1])
                == 1
            ):
                routes.append(path)
                continue
            if len(path) >= enemy.mp:
                continue
            neighbors = (
                destination for origin, destination in fight.edges if origin == cell
            )
            for neighbor in sorted(neighbors):
                if neighbor in visited or neighbor in blocked:
                    continue
                visited.add(neighbor)
                queue.append((neighbor, path + [neighbor]))
        self.assertTrue(
            routes, "Actual current enemy needs a paid path beside the victim"
        )
        provider = NativeProvider(
            characters[7],
            {-7: monster},
            decks[7],
            player_characters=characters,
            deck_blobs=decks,
        )
        failures = []
        for path in sorted(routes, key=len):
            if not path:
                return fight
            original = snapshot(fight)
            try:
                if enemy.controlled:
                    from wakfu_server.combat_area_transaction import (
                        prepare_area_movement,
                    )

                    controlled = deepcopy(fight)
                    origin = controlled.actors[actor_id].position
                    self.assertEqual(
                        controlled.actors[actor_id].owner_id,
                        characters[7]["account_id"],
                    )
                    controlled.move(characters[7]["account_id"], actor_id, path)
                    self.assertEqual(
                        controlled.actors[actor_id].mp, enemy.mp - len(path)
                    )
                    moved, _ = prepare_area_movement(
                        characters[7],
                        {-7: monster},
                        controlled,
                        decks[7],
                        actor_id=actor_id,
                        action_id=70,
                        path=path,
                        origin=origin,
                        rng=random.Random(17),
                        player_characters=characters,
                        deck_blobs=decks,
                    )
                    self.assertLess(moved.actors[actor_id].mp, enemy.mp)
                else:
                    moved = provider.preview(
                        fight, dict(type="move", path=path), 70, forecast=False
                    ).fight
            except ValueError as error:
                failures.append(str(error))
                self.assertEqual(snapshot(fight), original)
                continue
            self.assertEqual(snapshot(fight), original)
            return moved
        self.fail(f"All actual adjacent movement routes rejected: {failures}")

    def test_actual_enemy_spell_kills_copy_and_owner_with_foreign_owner_unchanged(self):
        helper = zobal_lifecycle.ZobalCopiedActionLifecycleTests()
        for kill_owner in (False, True):
            with self.subTest(kill_owner=kill_owner):
                fight, characters, monster, decks, clone_id = helper.create()
                victim = 7 if kill_owner else clone_id
                # Set a lawful wounded starting state; the zero-HP transition,
                # class link and QI retirement must come from owned NPC7962.
                set_hp_raw_current(fight.actors[victim], 1)
                fight = helper.reach(fight, characters, monster, decks, -7)
                self.assertNotIn(clone_id, retired_summon_ids(fight))
                fight = self.approach(fight, characters, monster, decks, victim)
                foreign_before = snapshot(fight)["actors"]["8"]
                original = snapshot(fight)
                trace = []
                with combat_diagnostic_scope(
                    lambda **event: trace.append(event), limit=4096
                ):
                    tx = prepare_npc_spell(
                        fight,
                        dict(
                            type="cast",
                            spellId=7962,
                            level=1,
                            targetId=victim,
                            target=list(fight.actors[victim].position),
                        ),
                        characters[7],
                        {-7: monster},
                        decks[7],
                        action_id=71,
                        rng=random.Random(17),
                        player_characters=characters,
                        deck_blobs=decks,
                    )
                self.assertEqual(snapshot(fight), original)
                self.assertTrue(any(tx.outcomes))
                self.assertEqual(tx.fight.actors[victim].hp, 0)
                if kill_owner:
                    # Native OFF_PLAY KO does not call fcb.E's recursive final
                    # controller unregister. Preserve the living copy's QI/PV.
                    from wakfu_server.combat_global_pv_collections import (
                        global_fighter_guards,
                    )

                    self.assertEqual(
                        global_fighter_guards(tx.fight, 7),
                        dict(baF=False, baG=True, baK=False),
                    )
                    self.assertNotIn(clone_id, retired_summon_ids(tx.fight))
                    self.assertIn(clone_id, tx.fight.order)
                    self.assertGreaterEqual(
                        tx.fight.actors[clone_id].native_obstacle_id, 0
                    )
                    self.assertEqual(
                        global_fighter_guards(tx.fight, clone_id),
                        dict(baF=True, baG=False, baK=False),
                    )
                    # The owned server producer currently emits1010 after
                    # OFF_PLAY. Native314659's own1010 mask admits its replay;
                    # child314660 has fKQ=false and no bcd bypass, so it must
                    # remain ineligible rather than acquire its parent's mask.
                    self.assertIn(
                        3813,
                        {
                            entry.reference
                            for entry in tx.fight.actors[7].state_ledger.entries
                        },
                    )
                    self.assertTrue(
                        any(
                            event.get("effect_reference") == 314659
                            and event.get("caster_id") == 7
                            and event.get("target_id") == 7
                            for event in trace
                        ),
                        trace,
                    )
                    self.assertTrue(
                        any(
                            event.get("effect_reference") == 314660
                            and event.get("status") == "skipped_native_eligibility"
                            and event.get("caster_id") == 7
                            and event.get("target_id") == 7
                            for event in trace
                        ),
                        trace,
                    )
                    self.assertTrue(
                        any(
                            receipt.get("actor_id") == 7
                            and receipt.get("ko_event_id") == 1010
                            for receipt in tx.fight.native_death_event_deliveries.values()
                        )
                    )
                else:
                    self.assertIn(clone_id, retired_summon_ids(tx.fight))
                    self.assertNotIn(clone_id, tx.fight.order)
                    self.assertEqual(tx.fight.actors[clone_id].native_obstacle_id, -1)
                self.assertEqual(snapshot(tx.fight)["actors"]["8"], foreign_before)
                self.assertEqual(tx.fight.phase, "active")
                current_registry(tx.fight)
                if kill_owner:
                    from wakfu_server.combat_summon_spellbook import actor_action_book

                    continued = helper.reach(
                        tx.fight, characters, monster, decks, clone_id
                    )
                    # Native7066 is linear, range1..3 with LOS. The enemy
                    # moved diagonally to hit the owner; pay a lawful aligned
                    # approach instead of disabling casting alignment checks.
                    continued = self.approach(
                        continued, characters, monster, decks, -7, actor_id=clone_id
                    )
                    clone = continued.actors[clone_id]
                    action = next(
                        row
                        for row in actor_action_book(clone)["actions"]
                        if row["reference"] == 7066
                    )
                    enemy_hp = continued.actors[-7].hp
                    paid = helper.cast(
                        continued,
                        characters,
                        monster,
                        decks,
                        clone_id,
                        action["uid"],
                        continued.actors[-7].position,
                        90,
                    )
                    self.assertEqual(paid.plan["costs"]["ap"], 3)
                    self.assertEqual(paid.fight.actors[clone_id].ap, clone.ap - 3)
                    self.assertLess(paid.fight.actors[-7].hp, enemy_hp)
                    self.assertEqual(
                        snapshot(paid.fight)["actors"]["8"],
                        snapshot(continued)["actors"]["8"],
                    )
