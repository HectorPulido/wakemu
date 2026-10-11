"""Real ENIRIPSA innate grants, Contra Natura and complete Cunejo branches."""
import random
import struct
import unittest

import test_combat_spell_transaction as fixture_module
from wakfu_server.combat_qi_fight import move_registered_actor
from wakfu_server.combat_server_spell import (
    prepare_server_initialization,
    prepare_server_spell,
)
from wakfu_server.combat_spell_grant import granted_spells
from wakfu_server.combat_summon import fresh_summon_slot_owned
from wakfu_server.combat_summon_spellbook import actor_action_book
from wakfu_server.fight_checkpoint_store import snapshot
from wakfu_server.spells import encode_deck


class AniripsaGrantSummonPipelineTests(unittest.TestCase):
    def fixture(self, *, level=200, passives=(), caster_aptitudes=()):
        (
            character,
            monster,
            fight,
        ) = fixture_module.SpellTransactionTests().native_server_fixture(
            7, level, native_qi=True, target_hp=20000, caster_aptitudes=caster_aptitudes
        )
        move_registered_actor(fight, fight.actors[-7], (-7, -7, -1))
        deck = encode_deck([630, 779, 645], list(passives))
        rng = random.Random(7)
        initialized, _ = prepare_server_initialization(
            character,
            {-7: monster},
            fight,
            3,
            deck,
            action_id=1,
            rng=rng,
            fight_start=True,
        )
        return character, monster, initialized, deck, rng

    def cast(self, fixture, reference, cell=None, *, action_id=2):
        character, monster, fight, deck, rng = fixture
        before = snapshot(fight)
        transaction = prepare_server_spell(
            struct.pack(">qqiih", 7, reference, *(cell or fight.actors[7].position)),
            character,
            {-7: monster},
            fight,
            3,
            deck,
            action_id=action_id,
            line_of_sight=lambda *args: True,
            critical=False,
            rng=rng,
        )
        self.assertEqual(snapshot(fight), before)
        self.assertTrue(any(transaction.outcomes))
        return transaction

    def adopt(self, fixture, fight):
        return (*fixture[:2], fight, *fixture[3:])

    def end_current_turn(self, fight, fixture):
        from wakfu_server.combat_runtime_messages import RuntimeMessages
        from wakfu_server.combat_server_spell import (
            prepare_server_turn_end,
            prepare_server_turn_start,
            server_runtime,
        )
        from pathlib import Path
        import sys

        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
        from combat_audit_turns import advance_actual_turn

        character, monster, _, deck, rng = fixture
        runtime = RuntimeMessages(
            fight,
            turn_end_provider=lambda p, **b: prepare_server_turn_end(
                character, {-7: monster}, p, deck, rng=rng, **b
            ),
            turn_start_provider=lambda p, **b: prepare_server_turn_start(
                character, {-7: monster}, p, deck, rng=rng, **b
            ),
            expiration_runtime_factory=lambda *, action_id: server_runtime(
                character,
                {-7: monster},
                deck,
                action_id=action_id,
                critical=False,
                rng=rng,
            )[0],
        )
        advance_actual_turn(runtime)

    def next_player_turn(self, fight, fixture):
        self.end_current_turn(fight, fixture)
        for _ in range(20):
            if fight.current.id == 7:
                return
            self.end_current_turn(fight, fixture)
        self.fail("Player turn did not return")

    def test_grants_come_from_actual_innate_and_respect_real_level_six(self):
        for level in (5, 6, 200):
            with self.subTest(level=level):
                fixture = self.fixture(level=level)
                grants = granted_spells(fixture[2], 7)
                self.assertEqual(
                    set(grants), set() if level < 6 else {7977, 7978, 7979}
                )
                self.assertTrue(
                    all(
                        row["uid"] == key and row["level"] == level
                        for key, row in grants.items()
                    )
                )

    def test_contra_natura_toggles_native_states_with_once_per_turn_rollback(self):
        for passives in ((), (7992,), (7998,)):
            with self.subTest(passives=passives):
                fixture = self.fixture(passives=passives)
                first = self.cast(fixture, 7977)
                states = {
                    s.reference for s in first.fight.actors[7].state_ledger.entries
                }
                self.assertTrue({3867, 8020} <= states)
                self.assertEqual(first.plan["costs"]["wp"], 2)
                adopted = self.adopt(fixture, first.fight)
                stable, rng_before = snapshot(first.fight), fixture[4].getstate()
                with self.assertRaisesRegex(ValueError, "maximum casts|turn"):
                    self.cast(adopted, 7977, action_id=3)
                self.assertEqual(snapshot(first.fight), stable)
                self.assertEqual(fixture[4].getstate(), rng_before)
                self.next_player_turn(first.fight, adopted)
                second = self.cast(adopted, 7977, action_id=3)
                states = {
                    s.reference for s in second.fight.actors[7].state_ledger.entries
                }
                self.assertNotIn(3867, states)
                self.assertNotIn(8020, states)
                self.assertEqual(
                    set(granted_spells(second.fight, 7)), {7977, 7978, 7979}
                )

    def test_four_cunejo_branches_create_correct_owned_book_and_registered_cells(self):
        expected = {
            (False, False): (182, {986}, 3863),
            (False, True): (1775, {5457, 5458, 5459, 986}, 3892),
            (True, False): (5528, {7988}, 8029),
            (True, True): (5533, {5457, 5458, 5459, 7988}, 3892),
        }
        for (dark, upgraded), (profile, abilities, state) in expected.items():
            with self.subTest(dark=dark, upgraded=upgraded):
                fixture = self.fixture(passives=(7991,) if upgraded else ())
                if dark:
                    toggle = self.cast(fixture, 7977)
                    fixture = self.adopt(fixture, toggle.fight)
                transaction = self.cast(fixture, 7978, (-8, -6, -1), action_id=3)
                summons = [
                    a
                    for a in transaction.fight.actors.values()
                    if getattr(a, "native_summon_source", None) and a.hp > 0
                ]
                self.assertEqual(len(summons), 1)
                summon = summons[0]
                self.assertEqual(summon.native_summon_source["ref"], profile)
                self.assertEqual(summon.native_summon_source["caster_id"], 7)
                self.assertEqual(summon.native_controller_id, 7)
                self.assertEqual(summon.owner_id, 3)
                self.assertEqual(summon.team, 0)
                self.assertEqual(summon.position, (-8, -6, -1))
                self.assertFalse(summon.native_controlled_by_ai)
                self.assertIn(state, {s.reference for s in summon.state_ledger.entries})
                book = actor_action_book(summon)
                self.assertEqual(
                    {row["reference"] for row in book["actions"]}, abilities
                )
                self.assertTrue(
                    all(
                        row["uid"] == row["reference"] and row["level"] == 200
                        for row in book["actions"]
                    )
                )
                self.assertTrue(fresh_summon_slot_owned(transaction.fight, summon))
                self.assertIn(summon.id, transaction.fight.native_summon_registrations)
                self.assertEqual(transaction.plan["costs"]["ap"], 2)
                if upgraded:
                    from wakfu_server.combat_summon_retirement import retired_summon_ids

                    retired = retired_summon_ids(transaction.fight)
                    self.assertEqual(len(retired), 1)
                    old_id = next(iter(retired))
                    self.assertEqual(
                        transaction.fight.actors[old_id].native_obstacle_id, -1
                    )
                    self.assertTrue(
                        all(
                            row is None or row["identity"] != ["actor", old_id]
                            for row in transaction.fight.native_qi_slots
                        )
                    )

    def test_all_cunejo_actions_use_owned_turn_and_produce_semantic_effects(self):
        from wakfu_server.combat_hp_raw import set_hp_raw_current
        from wakfu_server.combat_summon_retirement import retired_summon_ids

        for dark, upgraded in (
            (False, False),
            (False, True),
            (True, False),
            (True, True),
        ):
            fixture = self.fixture(passives=(7991,) if upgraded else ())
            if dark:
                fixture = self.adopt(fixture, self.cast(fixture, 7977).fight)
            fixture = self.adopt(fixture, self.cast(fixture, 7978, (-8, -6, -1)).fight)
            character, monster, fight, deck, rng = fixture
            summon = next(
                a
                for a in fight.actors.values()
                if getattr(a, "native_summon_source", None) and a.hp > 0
            )
            for _ in range(20):
                if fight.current is summon:
                    break
                self.end_current_turn(fight, fixture)
            self.assertIs(fight.current, summon)
            abilities = ([5457, 5458, 5459] if upgraded else []) + [
                7988 if dark else 986
            ]
            for ability in abilities:
                with self.subTest(dark=dark, upgraded=upgraded, ability=ability):
                    set_hp_raw_current(fight.actors[7], 100)
                    before = snapshot(fight)
                    transaction = prepare_server_spell(
                        struct.pack(
                            ">qqiih", summon.id, ability, *fight.actors[7].position
                        ),
                        character,
                        {-7: monster},
                        fight,
                        3,
                        deck,
                        action_id=4,
                        line_of_sight=lambda *args: True,
                        critical=False,
                        rng=rng,
                    )
                    self.assertEqual(snapshot(fight), before)
                    self.assertTrue(any(transaction.outcomes))
                    player = transaction.fight.actors[7]
                    if ability == 986:
                        self.assertEqual(player.hp, 142)
                    elif ability == 7988:
                        self.assertEqual(player.hp, 100)
                        self.assertIn(
                            8030, {s.reference for s in player.state_ledger.entries}
                        )
                        self.assertEqual(player.effect_stats[27], -50)
                    elif ability == 5457:
                        self.assertEqual(player.position, (-8, -8, -1))
                    elif ability == 5459:
                        self.assertEqual(player.hp, 69)
                        self.assertIn(
                            3869, {s.reference for s in player.state_ledger.entries}
                        )
                    elif ability == 5458:
                        self.assertEqual(player.position, (-8, -6, -1))
                        self.assertGreater(player.hp, 100)
                        self.assertIn(summon.id, retired_summon_ids(transaction.fight))
                        self.next_player_turn(transaction.fight, fixture)
                        adopted = self.adopt(fixture, transaction.fight)
                        for _ in range(10):
                            try:
                                resummoned = self.cast(
                                    adopted, 7978, (-8, -7, -1), action_id=5
                                )
                                break
                            except ValueError as exc:
                                if "cast interval" not in str(exc):
                                    raise
                                self.next_player_turn(transaction.fight, fixture)
                        else:
                            self.fail("Cunejo native cooldown did not expire")
                        living = [
                            a
                            for a in resummoned.fight.actors.values()
                            if getattr(a, "native_summon_source", None) and a.hp > 0
                        ]
                        self.assertEqual(len(living), 1)
                        self.assertNotEqual(living[0].id, summon.id)
                        self.assertTrue(
                            fresh_summon_slot_owned(resummoned.fight, living[0])
                        )

    def test_upgrade_boundary_failure_rolls_back_original_fight_and_rng(self):
        from unittest.mock import patch
        from wakfu_server.combat_summon_retirement import retire_protected_summon

        fixture = self.fixture(passives=(7991,))
        before, rng_before = snapshot(fixture[2]), fixture[4].getstate()

        def fail_after_retirement(fight, actor):
            self.assertTrue(retire_protected_summon(fight, actor))
            raise ValueError("Injected failure after protected summon QI retirement")

        with patch(
            "wakfu_server.combat_summon_retirement.retire_protected_summon",
            fail_after_retirement,
        ):
            with self.assertRaisesRegex(ValueError, "Injected failure"):
                self.cast(fixture, 7978, (-8, -6, -1))
        self.assertEqual(snapshot(fixture[2]), before)
        self.assertEqual(fixture[4].getstate(), rng_before)
