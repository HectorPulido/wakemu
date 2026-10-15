"""Vectors verified against aAS/aBA in the real client JAR."""
import unittest
import random
from unittest.mock import patch
from types import SimpleNamespace
from wakfu_server.combat_displacement import (
    NativeDisplacementHandler,
    displacement_geometry,
)
from wakfu_server.combat_effect_dispatch import EffectInvocation
from wakfu_server.combat_transaction_rng import transactional_spell_rng


class DisplacementFacingTests(unittest.TestCase):
    def geometry(self, family, mode, source, target):
        return displacement_geometry(
            {"effect_class": family, "parameters": [2, 0, 0, 0, mode, 0]},
            1,
            source=source,
            target=target,
            cell=(10, 10, 0),
        )

    def test_push_caster_facing_all_native_directions(self):
        expected = [(0, -1), (1, 0), (1, 0), (0, 1), (0, 1), (-1, 0), (-1, 0), (0, -1)]
        target = SimpleNamespace(position=(4, 0, 0))
        for direction, vector in enumerate(expected):
            source = SimpleNamespace(position=(0, 0, 0), direction=direction)
            self.assertEqual(self.geometry(300, 7, source, target)["vector"], vector)

    def test_forced_override_and_native_null_fallback(self):
        source = SimpleNamespace(position=(0, 0, 0))
        target = SimpleNamespace(
            position=(4, 0, 0), direction=1, native_forced_direction=None
        )
        for family in (300, 301):
            self.assertEqual(
                self.geometry(family, 4, source, target)["vector"], (-1, 0)
            )
            target.native_forced_direction = 7
            self.assertEqual(self.geometry(family, 4, source, target)["vector"], (0, 1))
            target.native_forced_direction = None

    def test_unknown_override_rejects_and_random_push_maps_all_native_draws(self):
        source = SimpleNamespace(position=(0, 0, 0), direction=1)
        target = SimpleNamespace(position=(4, 0, 0), direction=1)
        with self.assertRaisesRegex(ValueError, "pGJ"):
            self.geometry(300, 4, source, target)
        expected = ((0, -1), (-1, 0), (1, 0), (0, 1))
        for draw, vector in enumerate(expected, 1):
            calls = []
            result = displacement_geometry(
                {"effect_class": 300, "parameters": [2, 0, 0, 0, 6, 0]},
                1,
                source=source,
                target=target,
                cell=(10, 10, 0),
                draw_direction=lambda: calls.append(draw) or draw,
            )
            self.assertEqual(result["vector"], vector)
            self.assertEqual(calls, [draw])

    def test_random_push_requires_one_valid_transaction_draw(self):
        source = SimpleNamespace(position=(0, 0, 0), direction=1)
        target = SimpleNamespace(position=(4, 0, 0), direction=1)
        arguments = dict(
            effect={"effect_class": 300, "parameters": [2, 0, 0, 0, 6, 0]},
            level=1,
            source=source,
            target=target,
            cell=(10, 10, 0),
        )
        with self.assertRaisesRegex(ValueError, "transaction-owned"):
            displacement_geometry(**arguments)
        for invalid in (0, 5, True, None):
            with self.subTest(invalid=invalid), self.assertRaisesRegex(
                ValueError, "direction draw"
            ):
                displacement_geometry(**arguments, draw_direction=lambda: invalid)

    def test_fixed_push_modes_and_pull_defaults_do_not_consume_random_direction(self):
        source = SimpleNamespace(position=(0, 0, 0), direction=1)
        target = SimpleNamespace(position=(4, 0, 0), direction=1)
        for mode in range(4):
            with self.subTest(mode=mode):
                result = displacement_geometry(
                    {"effect_class": 300, "parameters": [1, 0, 0, 0, mode, 0]},
                    1,
                    source=source,
                    target=target,
                    cell=(10, 10, 0),
                    draw_direction=lambda: self.fail("fixed push drew randomness"),
                )
                self.assertEqual(
                    result["vector"], ((0, -1), (1, 0), (-1, 0), (0, 1))[mode]
                )
        draws = []
        for mode in (6, 7, -1, 99):
            with self.subTest(pull_mode=mode):
                result = displacement_geometry(
                    {"effect_class": 301, "parameters": [1, 0, 0, 0, mode, 0]},
                    1,
                    source=source,
                    target=target,
                    cell=(10, 10, 0),
                    draw_direction=lambda: draws.append(True) or 1,
                )
                self.assertEqual(result["vector"], (1, 0))
        same_cell = displacement_geometry(
            {"effect_class": 301, "parameters": [1, 0, 0, 0, 6, 0]},
            1,
            source=source,
            target=SimpleNamespace(position=(0, 0, 0)),
            cell=(10, 10, 0),
            draw_direction=lambda: draws.append(True) or 1,
        )
        self.assertEqual(same_cell["vector"], (0, 0))
        short_pull = displacement_geometry(
            {"effect_class": 301, "parameters": [1, 0, 0, 0]},
            1,
            source=source,
            target=target,
            cell=(10, 10, 0),
            draw_direction=lambda: draws.append(True) or 1,
        )
        self.assertEqual(short_pull["vector"], (-1, 0))
        self.assertEqual(draws, [])

    def test_displacement_handler_draws_after_level_two_and_only_once(self):
        phases = []
        source = SimpleNamespace(
            id=1, team=0, position=(0, 0, 0), hp=10, physical_radius=0
        )
        target = SimpleNamespace(
            id=2, team=1, position=(2, 0, 0), hp=10, physical_radius=0
        )

        class Authority:
            def __call__(self, _fight, _actor):
                return SimpleNamespace(
                    is_carried=False,
                    is_carrying=False,
                    targeting={},
                    native_instance_id=None,
                )

            def properties(self, _fight, _actor):
                return ()

        fight = SimpleNamespace(
            phase="active",
            current=source,
            id=99,
            actors={1: source, 2: target},
            walkable={(x, y, 0) for x in range(-2, 5) for y in range(-2, 3)},
            edges=None,
            native_effect_areas={},
            _event=lambda *_args, **_kwargs: None,
        )

        def draw():
            self.assertEqual(phases, [2])
            return 2

        handler = NativeDisplacementHandler(
            fight,
            [],
            action_id=5,
            allocate_uid=lambda: 41,
            authority=Authority(),
            draw_direction=draw,
        )
        handler.event_lifecycle = SimpleNamespace(
            phase=lambda _effect, _invocation, **data: phases.append(data["channel"]),
            displacement_completed=lambda *_args, **_kwargs: None,
        )
        effect = {
            "effect_class": 300,
            "parameters": [1, 0, 0, 0, 6, 0],
            "native_effect_flags": [],
        }
        invocation = EffectInvocation(3016, 1, 1, 2, (0, 0, 0), native_running_uid=41)
        with patch(
            "wakfu_server.combat_displacement.native_definition_timing",
            return_value={"retained": False, "delay": False, "duration": 0},
        ), patch(
            "wakfu_server.combat_runner_target_life.runner_target_life_eligible",
            return_value=True,
        ), patch(
            "wakfu_server.combat_qi_fight.move_registered_actor",
            side_effect=lambda _fight, actor, position: setattr(
                actor, "position", position
            ),
        ):
            self.assertTrue(handler(effect, None, invocation))
        self.assertEqual(phases, [2, 3, 4])
        self.assertEqual(target.position, (1, 0, 0))

    def test_transaction_owned_rng_is_deterministic_and_rolls_back_on_failure(self):
        def vectors(seed):
            rng = random.Random(seed)
            return tuple(
                displacement_geometry(
                    {"effect_class": 300, "parameters": [1, 0, 0, 0, 6, 0]},
                    1,
                    source=SimpleNamespace(position=(0, 0, 0)),
                    target=SimpleNamespace(position=(4, 0, 0)),
                    cell=(10, 10, 0),
                    draw_direction=lambda: rng.randint(1, 4),
                )["vector"]
                for _ in range(8)
            )

        self.assertEqual(vectors(73), vectors(73))
        factory = SimpleNamespace(transaction_rng=random.Random(73))
        initial_state = factory.transaction_rng.getstate()

        @transactional_spell_rng
        def failed_transaction(*, runtime_factory):
            runtime_factory.transaction_rng.randint(1, 4)
            raise RuntimeError("later effect failed")

        with self.assertRaisesRegex(RuntimeError, "later effect failed"):
            failed_transaction(runtime_factory=factory)
        self.assertEqual(factory.transaction_rng.getstate(), initial_state)


if __name__ == "__main__":
    unittest.main()
