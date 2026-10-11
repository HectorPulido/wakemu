"""Real Pandawa barrel constructor effects under legal passive decks."""
import os
import unittest

import test_combat_pandawa_runtime as pandawa_fixture


@unittest.skipUnless(
    os.environ.get("WAKFU_TEST_GRANTEDCAST") == "1", "native runtime opt-in"
)
class PandawaBarrelPassiveRuntimeTests(unittest.TestCase):
    fixture = pandawa_fixture.PandawaRuntimeTests.fixture
    cast = pandawa_fixture.PandawaRuntimeTests.cast

    def test_constructor_passives_apply_only_their_declared_native_states(self):
        for passive, required in ((None, set()), (4726, {6107, 9356}), (5152, {4163})):
            with self.subTest(passive=passive):
                fixture = self.fixture(() if passive is None else (passive,))
                result = self.cast(fixture, 4718)
                barrel = next(
                    actor
                    for actor in result.fight.actors.values()
                    if getattr(actor, "native_summon_source", None)
                )
                states = {entry.reference for entry in barrel.state_ledger.entries}
                self.assertTrue({1304, 4230} <= states)
                self.assertEqual(states & {6107, 9356, 4163}, required)

    def test_bottomless_barrel_auto_carries_adjacent_owned_barrel_only_with_passive(
        self,
    ):
        from unittest.mock import patch
        from wakfu_server import combat_server_spell
        from wakfu_server.combat_carrying import carrying_relations
        from wakfu_server.combat_spell_grant import granted_spells
        from tools.class_spell_eligible_targets import eligible_cast_targets

        for passive in (None, 4724):
            with self.subTest(passive=passive):
                fixture = self.fixture(() if passive is None else (passive,))
                character, monster, fight, deck, rng = fixture
                _, adapter = combat_server_spell.server_runtime(
                    character, {-7: monster}, deck, action_id=2, critical=False, rng=rng
                )
                selection = eligible_cast_targets(
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
                position = fight.actors[7].position
                adjacent = [
                    row["target"]
                    for row in selection["eligible"]
                    if abs(row["target"][0] - position[0])
                    + abs(row["target"][1] - position[1])
                    == 1
                ]
                self.assertTrue(adjacent, selection)
                created = self.cast(fixture, 4718, target=adjacent[0])
                fixture = (*fixture[:2], created.fight, *fixture[3:])
                original = combat_server_spell.prepare_server_turn_end
                observed = []

                def observe_end(*args, **kwargs):
                    result = original(*args, **kwargs)
                    if kwargs["actor_id"] == 7:
                        actor = result[0].actors[7]
                        observed.append(
                            (carrying_relations(result[0], actor), actor.direction)
                        )
                    return result

                direction = fixture[2].actors[7].direction
                with patch.object(
                    combat_server_spell, "prepare_server_turn_end", observe_end
                ):
                    pandawa_fixture.PandawaRuntimeTests.next_owned_turn(self, fixture)
                self.assertEqual(len(observed), 1)
                self.assertEqual(observed[0][0]["is_carrying"], passive == 4724)
                self.assertEqual(observed[0][1], direction)

    def test_aggressive_barrel_end_turn_removes_unheld_barrel_only_with_passive(self):
        from unittest.mock import patch
        from wakfu_server import combat_server_spell

        for passive in (None, 4725):
            with self.subTest(passive=passive):
                fixture = self.fixture(() if passive is None else (passive,))
                created = self.cast(fixture, 4718)
                fixture = (*fixture[:2], created.fight, *fixture[3:])
                barrel = next(
                    actor
                    for actor in fixture[2].actors.values()
                    if getattr(actor, "native_summon_source", None)
                )
                original = combat_server_spell.prepare_server_turn_end
                observed = []

                def observe_end(*args, **kwargs):
                    result = original(*args, **kwargs)
                    if kwargs["actor_id"] == 7:
                        observed.append(result[0].actors[barrel.id].hp)
                    return result

                with patch.object(
                    combat_server_spell, "prepare_server_turn_end", observe_end
                ):
                    pandawa_fixture.PandawaRuntimeTests.next_owned_turn(self, fixture)
                self.assertEqual(len(observed), 1)
                if passive == 4725:
                    self.assertEqual(observed[0], 0)
                else:
                    self.assertGreater(observed[0], 0)

    def test_aggressive_barrel_does_not_destroy_actually_carried_barrel(self):
        from unittest.mock import patch
        from wakfu_server import combat_server_spell
        from wakfu_server.combat_spell_grant import granted_spells
        from tools.class_spell_eligible_targets import eligible_cast_targets

        fixture = self.fixture((4725,))
        character, monster, fight, deck, rng = fixture
        _, adapter = combat_server_spell.server_runtime(
            character, {-7: monster}, deck, action_id=2, critical=False, rng=rng
        )
        selection = eligible_cast_targets(
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
        carried, rejected = None, []
        for candidate in selection["eligible"]:
            created = self.cast(fixture, 4718, target=candidate["target"])
            next_fixture = (*fixture[:2], created.fight, *fixture[3:])
            barrel = next(
                actor
                for actor in created.fight.actors.values()
                if getattr(actor, "native_summon_source", None)
            )
            try:
                carried = self.cast(
                    next_fixture, 6847, target=barrel.position, action_id=3
                )
            except ValueError as error:
                rejected.append(str(error))
                continue
            fixture = (*next_fixture[:2], carried.fight, *next_fixture[3:])
            break
        self.assertIsNotNone(carried, rejected)
        original = combat_server_spell.prepare_server_turn_end
        observed = []

        def observe_end(*args, **kwargs):
            result = original(*args, **kwargs)
            if kwargs["actor_id"] == 7:
                observed.append(result[0].actors[barrel.id].hp)
            return result

        with patch.object(combat_server_spell, "prepare_server_turn_end", observe_end):
            pandawa_fixture.PandawaRuntimeTests.next_owned_turn(self, fixture)
        self.assertEqual(len(observed), 1)
        self.assertGreater(observed[0], 0)
