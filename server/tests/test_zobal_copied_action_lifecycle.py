"""Actual Zobal8559 creation, allocated attack and isolated PA death lifecycle."""
import os
import random
import struct
import unittest
from copy import deepcopy
from functools import partial

import test_combat_aptitude_healing_runtime as allied_fixture
from wakfu_server.combat_server_spell import (
    prepare_server_spell,
    prepare_server_turn_end,
    prepare_server_turn_start,
    server_runtime,
)
from wakfu_server.combat_runtime_messages import RuntimeMessages
from wakfu_server.combat_spell_grant_book import grant_record
from wakfu_server.combat_summon_spellbook import actor_action_book
from wakfu_server.combat_summon_retirement import retired_summon_ids
from wakfu_server.fight_checkpoint_store import snapshot


@unittest.skipUnless(
    os.environ.get("WAKFU_TEST_GRANTEDCAST") == "1", "native runtime opt-in"
)
class ZobalCopiedActionLifecycleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        allied_fixture.AptitudeHealingRuntimeTests.setUpClass()

    def fixture(self):
        helper = allied_fixture.AptitudeHealingRuntimeTests()
        helper.active_retained_metadata = (
            allied_fixture.AptitudeHealingRuntimeTests.active_retained_metadata
        )
        fight, characters, monster, decks = helper.fixture(
            active_spells=(7066,),
            caster_breed=14,
            level=200,
            injury=0,
            caster_aptitudes=(),
            compact_arena=False,
            enemy_position=(-6, -7, -1),
            second_player_position=(-9, -7, -1),
        )
        # eZw serializes the actual class source character name. The allied
        # healing fixture deliberately omits presentation-only names.
        for identity, name in (
            (7, "Zobal copy owner"),
            (8, "Foreign owner"),
            (9, "Second ally"),
        ):
            characters[identity]["name"] = name
            # Connected character appearance is input to the ordinary entity
            # encoder; native_class_copy_model derives its actual model proof.
            characters[identity]["appearance"] = {"sex": 0, "clothIndex": 0}
        return fight, characters, monster, decks

    def reach(self, fight, characters, monster, decks, identity):
        from combat_audit_turns import advance_actual_turn

        kwargs = dict(
            player_characters=characters, deck_blobs=decks, rng=random.Random(17)
        )
        runtime = RuntimeMessages(
            fight,
            turn_end_provider=partial(
                prepare_server_turn_end,
                characters[7],
                {-7: monster},
                deck_blob=decks[7],
                **kwargs
            ),
            turn_start_provider=partial(
                prepare_server_turn_start,
                characters[7],
                {-7: monster},
                deck_blob=decks[7],
                **kwargs
            ),
            expiration_runtime_factory=lambda *, action_id: server_runtime(
                characters[7],
                {-7: monster},
                decks[7],
                action_id=action_id,
                critical=False,
                **kwargs
            )[0],
        )
        for _ in range(32):
            if runtime.fight.current.id == identity and runtime.awaiting_ack is None:
                return runtime.fight
            advance_actual_turn(runtime)
        self.fail("Actual copied actor turn not reached")

    def cast(self, fight, characters, monster, decks, actor_id, uid, target, action):
        original = snapshot(fight)
        tx = prepare_server_spell(
            struct.pack(">qqiih", actor_id, uid, *target),
            characters[7],
            {-7: monster},
            fight,
            characters[7]["account_id"],
            decks[7],
            action_id=action,
            line_of_sight=lambda *args: True,
            critical=False,
            rng=random.Random(17),
            player_characters=characters,
            deck_blobs=decks,
        )
        self.assertEqual(snapshot(fight), original)
        return tx

    def create(self):
        from class_spell_eligible_targets import eligible_cast_targets

        fight, characters, monster, decks = self.fixture()
        fight = self.reach(fight, characters, monster, decks, 7)
        grant = grant_record(fight, 7, 8559)
        self.assertIsNotNone(grant, "Actual native Ready must grant8559")
        _, adapter = server_runtime(
            characters[7],
            {-7: monster},
            decks[7],
            action_id=20,
            critical=False,
            player_characters=characters,
            deck_blobs=decks,
        )
        eligible = eligible_cast_targets(
            fight,
            characters[7],
            decks[7],
            grant["uid"],
            adapter=adapter,
            line_of_sight=lambda *args: True,
            actor_id=7,
            limit=128,
            maximum_eligible=16,
        )["eligible"]
        self.assertTrue(eligible)
        enemy = fight.actors[-7]
        target = min(
            (tuple(row["target"]) for row in eligible),
            key=lambda cell: abs(cell[0] - enemy.position[0])
            + abs(cell[1] - enemy.position[1]),
        )
        foreign_before = snapshot(fight)["actors"]["8"]
        tx = self.cast(fight, characters, monster, decks, 7, grant["uid"], target, 21)
        fresh = set(tx.fight.actors) - set(fight.actors)
        self.assertEqual(len(fresh), 1)
        clone_id = fresh.pop()
        clone = tx.fight.actors[clone_id]
        self.assertIsNotNone(getattr(clone, "native_copy_pa_source", None))
        self.assertEqual(snapshot(tx.fight)["actors"]["8"], foreign_before)
        return tx.fight, characters, monster, decks, clone_id

    def test_actual_allocated_7066_pays_three_ap_and_damages_exact_enemy(self):
        fight, characters, monster, decks, clone_id = self.create()
        fight = self.reach(fight, characters, monster, decks, clone_id)
        clone = fight.actors[clone_id]
        book = actor_action_book(clone)
        action = next(row for row in book["actions"] if row["reference"] == 7066)
        self.assertNotEqual(action["uid"], (7 << 32) | 7066)
        self.assertNotEqual(action["uid"], (clone_id << 32) | 7066)
        enemy_before = fight.actors[-7].hp
        owner_before = fight.actors[7].hp
        foreign_before = snapshot(fight)["actors"]["8"]
        tx = self.cast(
            fight,
            characters,
            monster,
            decks,
            clone_id,
            action["uid"],
            fight.actors[-7].position,
            40,
        )
        self.assertEqual(tx.plan["costs"]["ap"], 3)
        self.assertEqual(tx.plan["costs"]["mp"], 0)
        self.assertEqual(tx.plan["costs"]["wp"], 0)
        self.assertEqual(tx.fight.actors[clone_id].ap, clone.ap - 3)
        self.assertLess(tx.fight.actors[-7].hp, enemy_before)
        self.assertEqual(tx.fight.actors[7].hp, owner_before)
        self.assertEqual(snapshot(tx.fight)["actors"]["8"], foreign_before)
        animation = next(body for opcode, body in tx.packets if opcode == 12588)
        self.assertEqual(
            struct.unpack_from(">qih", animation, 20),
            (action["uid"], 7066, action["level"]),
        )

    def test_actual_copy_retirement_isolated_under_trusted_pa_death_stress(self):
        from wakfu_server.combat_hp_raw import hp_raw_current
        from wakfu_server.combat_cast import resolve_owned_spell_action

        fight, characters, monster, decks, clone_id = self.create()
        clone = fight.actors[clone_id]
        action = next(
            row
            for row in actor_action_book(clone)["actions"]
            if row["reference"] == 7066
        )
        for victim in (clone_id, 7):
            with self.subTest(victim=victim):
                preview = deepcopy(fight)
                foreign_before = snapshot(preview)["actors"]["8"]
                # Explicit PA lifecycle stress, not a claim an enemy spell killed
                # the copy. Creation and its allocated attack use real spells.
                with preview.effect_resolution():
                    preview.apply_effect_damage(
                        -7, victim, hp_raw_current(preview.actors[victim])
                    )
                self.assertEqual(snapshot(preview)["actors"]["8"], foreign_before)
                if victim == clone_id:
                    self.assertIn(clone_id, retired_summon_ids(preview))
                    self.assertNotIn(clone_id, preview.order)
                    self.assertEqual(preview.actors[clone_id].native_obstacle_id, -1)
                    with self.assertRaises(ValueError):
                        resolve_owned_spell_action(
                            dict(actor_id=clone_id, spell_uid=action["uid"]),
                            characters[7],
                            preview,
                            characters[7]["account_id"],
                            decks[7],
                        )
                else:
                    # fcb.aC OFF_PLAY is reversible KO. Recursive controller
                    # removal belongs to fcb.E, not this HP-zero transition.
                    from wakfu_server.combat_global_pv_collections import (
                        global_fighter_guards,
                    )

                    self.assertEqual(
                        global_fighter_guards(preview, 7),
                        dict(baF=False, baG=True, baK=False),
                    )
                    self.assertNotIn(clone_id, retired_summon_ids(preview))
                    self.assertIn(clone_id, preview.order)
                    self.assertGreaterEqual(
                        preview.actors[clone_id].native_obstacle_id, 0
                    )
                    self.assertEqual(
                        global_fighter_guards(preview, clone_id),
                        dict(baF=True, baG=False, baK=False),
                    )
