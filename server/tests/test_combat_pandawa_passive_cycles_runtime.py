"""Lawful Pandawa passive costs and end-turn movement, without injected states."""
import os
import unittest
from unittest.mock import patch
import test_combat_pandawa_runtime as fixture_module


@unittest.skipUnless(
    os.environ.get("WAKFU_TEST_GRANTEDCAST") == "1", "native runtime opt-in"
)
class PandawaPassiveCycleRuntimeTests(unittest.TestCase):
    fixture = fixture_module.PandawaRuntimeTests.fixture
    cast = fixture_module.PandawaRuntimeTests.cast
    next_owned_turn = fixture_module.PandawaRuntimeTests.next_owned_turn

    def test_master_drunkenness_pays_real_extra_cost_and_allows_next_turn_use(self):
        costs = {}
        for passive in (None, 4723):
            with self.subTest(passive=passive):
                fixture = self.fixture(() if passive is None else (passive,))
                # Ready constructs the initial timeline, while the runtime
                # publishes its table turn at an actual start boundary. Enter
                # an owned start before measuring native interval accounting.
                fixture = self.next_owned_turn(fixture)
                first = self.cast(fixture, 8592, target=fixture[2].actors[7].position)
                costs[passive] = first.plan["costs"]
                fixture = (*fixture[:2], first.fight, *fixture[3:])
                fixture = self.next_owned_turn(fixture)
                if passive is None:
                    with self.assertRaisesRegex(
                        ValueError, "Native spell cast interval has not elapsed"
                    ):
                        self.cast(
                            fixture,
                            8592,
                            target=fixture[2].actors[7].position,
                            action_id=30,
                        )
                else:
                    repeated = self.cast(
                        fixture,
                        8592,
                        target=fixture[2].actors[7].position,
                        action_id=30,
                    )
                    self.assertTrue(any(repeated.outcomes))
        self.assertGreater(
            sum(costs[4723][key] for key in ("ap", "mp", "wp")),
            sum(costs[None][key] for key in ("ap", "mp", "wp")),
        )

    def test_last_one_attracts_owner_towards_aligned_barrel_on_real_end(self):
        from wakfu_server import combat_server_spell
        from wakfu_server.combat_spell_grant import granted_spells
        from tools.class_spell_eligible_targets import eligible_cast_targets

        for passive in (None, 8601):
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
                    limit=256,
                    maximum_eligible=16,
                )
                position = fight.actors[7].position
                candidates = [
                    row["target"]
                    for row in selection["eligible"]
                    if (
                        row["target"][0] == position[0]
                        or row["target"][1] == position[1]
                    )
                    and abs(row["target"][0] - position[0])
                    + abs(row["target"][1] - position[1])
                    >= 2
                ]
                self.assertTrue(candidates, selection)
                created = self.cast(fixture, 4718, target=candidates[0])
                fixture = (*fixture[:2], created.fight, *fixture[3:])
                barrel = next(
                    actor
                    for actor in created.fight.actors.values()
                    if getattr(actor, "native_summon_source", None)
                )
                before = fixture[2].actors[7].position
                original = combat_server_spell.prepare_server_turn_end
                observed = []

                def observe_end(*args, **kwargs):
                    result = original(*args, **kwargs)
                    if kwargs["actor_id"] == 7:
                        observed.append(
                            (
                                result[0].actors[7].position,
                                result[0].actors[barrel.id].position,
                            )
                        )
                    return result

                with patch.object(
                    combat_server_spell, "prepare_server_turn_end", observe_end
                ):
                    self.next_owned_turn(fixture)
                self.assertEqual(len(observed), 1)
                after, barrel_after = observed[0]
                self.assertEqual(barrel_after, barrel.position)
                if passive is None:
                    self.assertEqual(after, before)
                else:
                    self.assertLess(
                        abs(after[0] - barrel_after[0])
                        + abs(after[1] - barrel_after[1]),
                        abs(before[0] - barrel_after[0])
                        + abs(before[1] - barrel_after[1]),
                    )

    def test_last_one_actual_attraction_stops_at_registered_enemy_blocker(self):
        from unittest.mock import patch
        from wakfu_server import combat_server_spell
        from wakfu_server.combat_spell_grant import granted_spells
        from wakfu_server.combat_effect_dispatch import EffectDispatcher
        from tools.class_spell_eligible_targets import eligible_cast_targets

        fixture = self.fixture((8601,))
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
            limit=256,
            maximum_eligible=16,
        )
        owner, enemy = fight.actors[7].position, fight.actors[-7].position

        def blocked(cell):
            return (
                owner[0] == enemy[0] == cell[0]
                and min(owner[1], cell[1]) < enemy[1] < max(owner[1], cell[1])
            ) or (
                owner[1] == enemy[1] == cell[1]
                and min(owner[0], cell[0]) < enemy[0] < max(owner[0], cell[0])
            )

        candidates = [
            row["target"] for row in selection["eligible"] if blocked(row["target"])
        ]
        self.assertTrue(candidates, selection)
        created = self.cast(fixture, 4718, target=candidates[0])
        fixture = (*fixture[:2], created.fight, *fixture[3:])
        barrel = next(
            a
            for a in created.fight.actors.values()
            if getattr(a, "native_summon_source", None)
        )
        observed, executed = [], []
        original_end = combat_server_spell.prepare_server_turn_end
        original_execute = EffectDispatcher.execute

        def end(*args, **kwargs):
            result = original_end(*args, **kwargs)
            if kwargs["actor_id"] == 7:
                observed.append(
                    (
                        result[0].actors[7].position,
                        result[0].actors[-7].position,
                        result[0].actors[barrel.id].position,
                    )
                )
            return result

        def execute(dispatcher, invocation, **kwargs):
            executed.append(invocation.reference)
            return original_execute(dispatcher, invocation, **kwargs)

        with patch.object(
            combat_server_spell, "prepare_server_turn_end", end
        ), patch.object(EffectDispatcher, "execute", execute):
            self.next_owned_turn(fixture)
        self.assertIn(418471, executed)
        self.assertEqual(observed, [(owner, enemy, barrel.position)])
