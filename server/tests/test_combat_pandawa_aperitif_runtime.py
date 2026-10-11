"""Actual held-barrel throw establishes Pandaperitivo's restriction marker."""
import os
import unittest
import test_combat_pandawa_runtime as helper


@unittest.skipUnless(
    os.environ.get("WAKFU_TEST_GRANTEDCAST") == "1", "native runtime opt-in"
)
class PandawaAperitifRuntimeTests(unittest.TestCase):
    fixture = helper.PandawaRuntimeTests.fixture
    cast = helper.PandawaRuntimeTests.cast
    adopt = helper.PandawaRuntimeTests.adopt
    next_owned_turn = helper.PandawaRuntimeTests.next_owned_turn

    def test_constructor_marks_restriction_and_held_release_preserves_it(self):
        from wakfu_server.combat_server_spell import server_runtime
        from wakfu_server.combat_spell_grant import granted_spells
        from tools.class_spell_eligible_targets import eligible_cast_targets

        for passive in (None, 8600):
            with self.subTest(passive=passive):
                fixture = self.fixture(
                    () if passive is None else (passive,), actives=(4705,)
                )
                character, monster, fight, deck, rng = fixture
                _, adapter = server_runtime(
                    character, {-7: monster}, deck, action_id=2, critical=False, rng=rng
                )
                candidates = eligible_cast_targets(
                    fight,
                    character,
                    deck,
                    granted_spells(fight, 7)[4718]["uid"],
                    adapter=adapter,
                    line_of_sight=lambda *args: True,
                    actor_id=7,
                    limit=128,
                    maximum_eligible=16,
                )
                carried = None
                for row in candidates["eligible"]:
                    if row["target"][:2] == fight.actors[7].position[:2]:
                        continue  # 418439 requires construction distance >0.
                    born = self.cast(fixture, 4718, target=row["target"])
                    next_fixture = self.adopt(fixture, born.fight)
                    barrel = next(
                        a
                        for a in born.fight.actors.values()
                        if getattr(a, "native_summon_source", None)
                    )
                    self.assertEqual(
                        9368 in {e.reference for e in barrel.state_ledger.entries},
                        passive == 8600,
                    )
                    try:
                        carried = self.cast(
                            next_fixture, 6847, target=barrel.position, action_id=3
                        )
                    except ValueError:
                        continue
                    fixture = self.adopt(next_fixture, carried.fight)
                    break
                self.assertIsNotNone(carried, candidates)
                self.assertIn(
                    6776,
                    {e.reference for e in fixture[2].actors[7].state_ledger.entries},
                )
                # Constructor147236 already executes418439→418442. The
                # held release preserves that same-turn restriction; its
                # fresh positive requires actual expiry in the nearby test.
                thrown = self.cast(fixture, 4705, action_id=4)
                self.assertNotIn(
                    6776,
                    {e.reference for e in thrown.fight.actors[7].state_ledger.entries},
                )
                states = {
                    e.reference
                    for e in thrown.fight.actors[barrel.id].state_ledger.entries
                }
                self.assertEqual(9368 in states, passive == 8600)
                # The restriction is observed within its native turn window;
                # the repeated same-turn acceptance case is separate below.

    def test_repeated_same_turn_throw_respects_actual_restriction_marker(self):
        import random
        import struct
        from unittest.mock import patch
        from test_combat_pandawa_carry_death_runtime import (
            PandawaCarryDeathRuntimeTests,
        )
        from wakfu_server.combat_server_spell import (
            prepare_server_spell,
            server_runtime,
        )
        from wakfu_server.combat_spell_grant import granted_spells
        from wakfu_server.combat_effect_dispatch import EffectDispatcher
        from tools.class_spell_eligible_targets import eligible_cast_targets

        owner = PandawaCarryDeathRuntimeTests()
        fight, characters, decks = owner.fixture(
            carrier_level=200,
            carried_level=200,
            pandawa_passives=(8600,),
            pandawa_actives=(4705,),
            pandawa_aptitudes=[(2, 1)],
            pandawa_amulet=True,
        )
        fight = owner.reach(fight, characters, decks, 7)

        def cast(current, spell, target, action):
            uid = (
                granted_spells(current, 7).get(spell, {}).get("uid", (7 << 32) | spell)
            )
            return prepare_server_spell(
                struct.pack(">qqiih", 7, uid, *target),
                characters[7],
                {},
                current,
                3,
                decks[7],
                action_id=action,
                line_of_sight=lambda *args: True,
                critical=False,
                rng=random.Random(0),
                player_characters=characters,
                deck_blobs=decks,
            ).fight

        _, adapter = server_runtime(
            characters[7],
            {},
            decks[7],
            action_id=10,
            critical=False,
            rng=random.Random(0),
            player_characters=characters,
            deck_blobs=decks,
        )
        selection = eligible_cast_targets(
            fight,
            characters[7],
            decks[7],
            granted_spells(fight, 7)[4718]["uid"],
            adapter=adapter,
            line_of_sight=lambda *args: True,
            actor_id=7,
            limit=128,
            maximum_eligible=16,
        )
        chosen = None
        for candidate in selection["eligible"]:
            born = cast(fight, 4718, candidate["target"], 10)
            barrel = next(
                a
                for a in born.actors.values()
                if getattr(a, "native_summon_source", None)
            )
            try:
                cast(born, 6847, barrel.position, 11)
            except ValueError:
                continue
            chosen = born, barrel.id
            break
        self.assertIsNotNone(chosen, selection)
        fight, barrel_id = chosen
        # Spend the constructor's AP in the preceding turn. The next real turn
        # has AP8 from one major aptitude and the owned equipped native amulet.
        fight = owner.reach(fight, characters, decks, 8)
        fight = owner.reach(fight, characters, decks, 7)
        self.assertEqual(fight.actors[7].ap, 8)
        fight = cast(fight, 6847, fight.actors[barrel_id].position, 12)
        _, first_adapter = server_runtime(
            characters[7],
            {},
            decks[7],
            action_id=13,
            critical=False,
            rng=random.Random(0),
            player_characters=characters,
            deck_blobs=decks,
        )
        first_targets = eligible_cast_targets(
            fight,
            characters[7],
            decks[7],
            (7 << 32) | 4705,
            adapter=first_adapter,
            line_of_sight=lambda *args: True,
            actor_id=7,
            limit=128,
            maximum_eligible=16,
        )
        adjacent = [
            row
            for row in first_targets["eligible"]
            if sum(abs(row["target"][i] - fight.actors[7].position[i]) for i in (0, 1))
            == 1
        ]
        self.assertTrue(adjacent, first_targets)
        fight = cast(fight, 4705, adjacent[0]["target"], 13)
        self.assertIn(
            9368, {e.reference for e in fight.actors[barrel_id].state_ledger.entries}
        )
        fight = cast(fight, 6847, fight.actors[barrel_id].position, 14)
        self.assertIn(
            9368, {e.reference for e in fight.actors[barrel_id].state_ledger.entries}
        )
        executed = []
        original = EffectDispatcher.execute

        def observe(dispatcher, invocation, **kwargs):
            executed.append(invocation.reference)
            return original(dispatcher, invocation, **kwargs)

        _, adapter = server_runtime(
            characters[7],
            {},
            decks[7],
            action_id=15,
            critical=False,
            rng=random.Random(0),
            player_characters=characters,
            deck_blobs=decks,
        )
        targets = eligible_cast_targets(
            fight,
            characters[7],
            decks[7],
            (7 << 32) | 4705,
            adapter=adapter,
            line_of_sight=lambda *args: True,
            actor_id=7,
            limit=128,
            maximum_eligible=1,
        )
        self.assertTrue(targets["eligible"], targets)
        with patch.object(EffectDispatcher, "execute", observe):
            fight = cast(fight, 4705, targets["eligible"][0]["target"], 15)
        self.assertIn(418445, executed)
        self.assertNotIn(418447, executed)
        self.assertNotIn(418448, executed)
