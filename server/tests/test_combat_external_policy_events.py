"""Focused contracts for server-owned combat event producers."""
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from wakfu_server.combat_attack_preparation import (
    attack_preparation_scope,
    deliver_attack_preparation,
)
from wakfu_server.combat_voluntary_movement_events import (
    deliver_voluntary_movement,
)


class AttackPreparationScopeTests(unittest.TestCase):
    def setUp(self):
        self.fight = SimpleNamespace()
        self.lifecycle = SimpleNamespace(preview=self.fight, plan={"spell_id": 8402})
        self.invocation = SimpleNamespace(
            caster_id=7,
            target_id=-7,
            state_uid=None,
            native_trigger_context=None,
        )
        self.effect = {"effect_class": 2}
        self.calls = []

        def phase(lifecycle, effect, invocation, **kwargs):
            self.calls.append((lifecycle, effect, invocation, kwargs))
            return (True,)

        self.phase_patch = patch(
            "wakfu_server.combat_ordinary_events.OrdinaryHealingEvents.phase",
            autospec=True,
            side_effect=phase,
        )
        self.phase_patch.start()
        self.addCleanup(self.phase_patch.stop)

    def deliver(self, uid):
        with patch(
            "wakfu_server.combat_ordinary_authority.ordinary_container_type",
            return_value=11,
        ):
            return deliver_attack_preparation(
                self.lifecycle,
                self.effect,
                self.invocation,
                uid=uid,
                final_modifier=None,
                runner_modifier=None,
            )

    def test_primary_attack_delivers_event500_once(self):
        with attack_preparation_scope(self.fight, 7):
            self.assertTrue(self.deliver(100))
            self.assertFalse(self.deliver(101))

        self.assertEqual(len(self.calls), 1)
        lifecycle, effect, invocation, kwargs = self.calls[0]
        self.assertIs(lifecycle, self.lifecycle)
        self.assertIs(effect, self.effect)
        self.assertIs(invocation, self.invocation)
        self.assertEqual(
            (kwargs["_event_ids"], kwargs["channel"], kwargs["uid"], kwargs["value"]),
            ((500,), 1, 100, 0),
        )
        self.assertNotIn("_local_policy_manager", kwargs)

    def test_nested_scope_restores_outer_state_and_new_cast_resets(self):
        with attack_preparation_scope(self.fight, 7):
            self.assertTrue(self.deliver(1))
            with attack_preparation_scope(self.fight, 7):
                self.assertTrue(self.deliver(2))
                self.assertFalse(self.deliver(3))
            self.assertFalse(self.deliver(4))

        with attack_preparation_scope(self.fight, 7):
            self.assertTrue(self.deliver(5))
        self.assertEqual([row[3]["uid"] for row in self.calls], [1, 2, 5])

    def test_foreign_fight_actor_and_non_damage_container_do_not_consume_scope(self):
        other_fight = SimpleNamespace()
        other_lifecycle = SimpleNamespace(preview=other_fight, plan={"spell_id": 8402})
        other_actor = SimpleNamespace(
            caster_id=8,
            target_id=-7,
            state_uid=None,
            native_trigger_context=None,
        )
        with attack_preparation_scope(self.fight, 7):
            self.assertFalse(
                deliver_attack_preparation(
                    other_lifecycle,
                    self.effect,
                    self.invocation,
                    uid=1,
                    final_modifier=None,
                    runner_modifier=None,
                )
            )
            self.assertFalse(
                deliver_attack_preparation(
                    self.lifecycle,
                    self.effect,
                    other_actor,
                    uid=2,
                    final_modifier=None,
                    runner_modifier=None,
                )
            )
            with patch(
                "wakfu_server.combat_ordinary_authority.ordinary_container_type",
                return_value=13,
            ):
                self.assertFalse(
                    deliver_attack_preparation(
                        self.lifecycle,
                        self.effect,
                        self.invocation,
                        uid=3,
                        final_modifier=None,
                        runner_modifier=None,
                    )
                )
            self.assertTrue(self.deliver(4))
        self.assertEqual([row[3]["uid"] for row in self.calls], [4])


class VoluntaryMovementEventTests(unittest.TestCase):
    def setUp(self):
        self.actor = SimpleNamespace(id=7, position=(1, 0, 0))
        self.opponent = SimpleNamespace(id=-7, position=(4, 0, 0))
        self.area = SimpleNamespace(native_running_effect_manager=True)
        self.inactive_area = SimpleNamespace(native_running_effect_manager=False)
        self.fight = SimpleNamespace(actors={7: self.actor, -7: self.opponent})
        self.dispatcher = SimpleNamespace(
            native_retention=SimpleNamespace(fight=self.fight),
            native_clone_authority=object(),
            replay_event=lambda event, **kwargs: self.events.append(
                (event, kwargs["authority"])
            )
            or (True,),
        )
        self.events = []

    def test_successful_step_routes_local_and_global_lifecycle_and_removal_masks(self):
        from wakfu_server import combat_global_pv_collections as global_pv
        from wakfu_server import combat_state_managers

        with patch.object(
            global_pv, "global_pv_iterator", return_value=(7, -7, 901, 902)
        ), patch.object(
            combat_state_managers,
            "registered_area_pv",
            side_effect=lambda fight, identity: {
                901: self.area,
                902: self.inactive_area,
            }.get(identity),
        ):
            result = deliver_voluntary_movement(
                self.dispatcher,
                actor_id=7,
                from_cell=(0, 0, 0),
                to_cell=(1, 0, 0),
            )

        self.assertEqual(result, (True,) * len(self.events))
        self.assertEqual(
            [(event.manager_actor_id, event.channel) for event, _ in self.events],
            [
                (7, 6),
                (7, 60),
                (7, 4),
                (7, 40),
                (7, 61),
                (7, 41),
                (-7, 61),
                (-7, 41),
                (901, 61),
                (901, 41),
            ],
        )
        self.assertTrue(all(event.event_ids == (1005,) for event, _ in self.events))
        self.assertTrue(
            all(
                event.uid is None
                and event.caster_id is None
                and event.target_id is None
                for event, _ in self.events
            )
        )
        self.assertTrue(
            all(
                authority is self.dispatcher.native_clone_authority
                for _, authority in self.events
            )
        )

    def test_zero_step_and_foreign_or_uncommitted_fighter_do_not_deliver(self):
        from wakfu_server import combat_global_pv_collections as global_pv

        with patch.object(global_pv, "global_pv_iterator", return_value=()):
            self.assertEqual(
                deliver_voluntary_movement(
                    self.dispatcher,
                    actor_id=7,
                    from_cell=(1, 0, 0),
                    to_cell=(1, 0, 0),
                ),
                (),
            )
            with self.assertRaisesRegex(ValueError, "actual moved fighter"):
                deliver_voluntary_movement(
                    self.dispatcher,
                    actor_id=99,
                    from_cell=(0, 0, 0),
                    to_cell=(1, 0, 0),
                )
            with self.assertRaisesRegex(ValueError, "actual moved fighter"):
                deliver_voluntary_movement(
                    self.dispatcher,
                    actor_id=-7,
                    from_cell=(3, 0, 0),
                    to_cell=(2, 0, 0),
                )
        self.assertEqual(self.events, [])
