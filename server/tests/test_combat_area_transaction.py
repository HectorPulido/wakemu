import os, random, unittest
from types import SimpleNamespace
from unittest.mock import patch
from wakfu_server.combat_area_transaction import prepare_area_event


class AreaTransactionTests(unittest.TestCase):
    def test_disabled_policy_has_no_side_effect(self):
        with patch.dict(os.environ, {"WAKFU_NATIVE_AREA_CALLBACKS": "0"}):
            with self.assertRaisesRegex(ValueError, "disabled"):
                prepare_area_event(
                    {},
                    {},
                    SimpleNamespace(),
                    b"",
                    actor_id=7,
                    action_id=1,
                    event="turn_start",
                )

    @patch.dict(os.environ, {"WAKFU_NATIVE_AREA_CALLBACKS": "1"})
    def test_movement_requires_actual_final_coordinates_before_runtime(self):
        fight = SimpleNamespace(actors={7: SimpleNamespace(position=(1, 2, 3))})
        rng = random.Random(7)
        before = rng.getstate()
        with patch("wakfu_server.combat_server_spell.server_runtime") as runtime:
            with self.assertRaisesRegex(ValueError, "committed native coordinates"):
                prepare_area_event(
                    {},
                    {},
                    fight,
                    b"",
                    actor_id=7,
                    action_id=1,
                    event="movement",
                    from_cell=(0, 2, 3),
                    to_cell=(2, 2, 3),
                    rng=rng,
                )
            runtime.assert_not_called()
        self.assertEqual(rng.getstate(), before)
        self.assertEqual(fight.actors[7].position, (1, 2, 3))

    @patch.dict(os.environ)
    def test_path_callbacks_observe_every_native_step_without_mutating_source(self):
        os.environ.pop("WAKFU_NATIVE_AREA_CALLBACKS", None)
        from test_combat_movement_runtime import MovementRuntimeTests
        from wakfu_server.combat_area_transaction import prepare_area_movement

        runtime, _ = MovementRuntimeTests().setup_fight()
        fight = runtime.fight
        path = [(1, 0, 0), (2, 0, 0)]
        fight.move(7, 1, path)
        calls = []
        movement_events = []

        def factory(preview, plan):
            def movement(identity, **boundary):
                calls.append((preview.actors[identity].position, boundary))
                movement_events.append(
                    ("area", preview.actors[identity].position, None)
                )
                preview.actors[identity].hp -= 1

            from wakfu_server.combat.combat_global_pv_collections import (
                initialize_global_pv_collections,
            )

            initialize_global_pv_collections(preview, tuple(preview.actors))
            authority = object()

            def replay_event(event, *, authority):
                movement_events.append(("event", preview.actors[1].position, event))
                return (True,)

            return (
                SimpleNamespace(
                    native_area_events=SimpleNamespace(movement=movement),
                    native_retention=SimpleNamespace(fight=preview),
                    native_clone_authority=authority,
                    replay_event=replay_event,
                ),
                [],
            )

        with patch(
            "wakfu_server.combat_server_spell.server_runtime",
            return_value=(factory, None),
        ):
            candidate, _ = prepare_area_movement(
                {}, {}, fight, b"", actor_id=1, action_id=2, path=path, origin=(0, 0, 0)
            )
        self.assertEqual([position for position, _ in calls], path)
        self.assertEqual(calls[1][1], {"from_cell": (1, 0, 0), "to_cell": (2, 0, 0)})
        self.assertEqual(candidate.actors[1].hp, 58)
        self.assertEqual(fight.actors[1].hp, 60)
        self.assertEqual(candidate.actors[1].position, (2, 0, 0))
        self.assertEqual(
            [entry[0] for entry in movement_events],
            ["event"] * 8 + ["area"] + ["event"] * 8 + ["area"],
        )
        self.assertEqual(
            [entry[2].channel for entry in movement_events if entry[0] == "event"][:4],
            [6, 60, 4, 40],
        )
        self.assertTrue(
            all(
                entry[2].event_ids == (1005,)
                for entry in movement_events
                if entry[0] == "event"
            )
        )

    @patch.dict(os.environ, {"WAKFU_NATIVE_AREA_CALLBACKS": "1"})
    def test_early_lethal_path_rejects_without_partial_damage(self):
        from test_combat_movement_runtime import MovementRuntimeTests
        from wakfu_server.combat_area_transaction import prepare_area_movement

        runtime, _ = MovementRuntimeTests().setup_fight()
        fight = runtime.fight
        path = [(1, 0, 0), (2, 0, 0)]
        fight.move(7, 1, path)

        def factory(preview, plan):
            def movement(identity, **boundary):
                preview.actors[identity].hp = 0

            from wakfu_server.combat_global_pv_collections import (
                initialize_global_pv_collections,
            )

            initialize_global_pv_collections(preview, tuple(preview.actors))
            authority = object()

            def replay_event(event, *, authority):
                return (True,)

            return (
                SimpleNamespace(
                    native_area_events=SimpleNamespace(movement=movement),
                    native_retention=SimpleNamespace(fight=preview),
                    native_clone_authority=authority,
                    replay_event=replay_event,
                ),
                [],
            )

        with patch(
            "wakfu_server.combat_server_spell.server_runtime",
            return_value=(factory, None),
        ):
            with self.assertRaisesRegex(ValueError, "Early lethal"):
                prepare_area_movement(
                    {},
                    {},
                    fight,
                    b"",
                    actor_id=1,
                    action_id=2,
                    path=path,
                    origin=(0, 0, 0),
                )
        self.assertEqual(
            (fight.actors[1].hp, fight.actors[1].position), (60, (2, 0, 0))
        )
