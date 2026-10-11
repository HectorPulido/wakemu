"""Generic Qe local phases must reach real area managers without fighter stats."""
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from wakfu_server.combat_ordinary_events import OrdinaryHealingEvents
from wakfu_server.combat_state_ledger import StateLedger


class AreaEventPhaseTests(unittest.TestCase):
    def setUp(self):
        self.sources = []
        self.definitions = {
            "111": dict(type="GLYPH", native_area_properties=[12], entry_masks=[])
        }
        self.actor = SimpleNamespace(id=7)
        self.preview = SimpleNamespace(
            actors={7: self.actor},
            native_summon_registrations={},
            native_effect_areas={
                91: dict(
                    uid=91,
                    reference=111,
                    cell=(2, 3, 0),
                    native_running_effect_manager=True,
                    native_area_contract="faY",
                    state_ledger=StateLedger(91),
                )
            },
            native_owned_group_effects={},
        )
        authority = lambda preview, actor: True
        self.events = OrdinaryHealingEvents.__new__(OrdinaryHealingEvents)
        self.events.preview = self.preview
        self.events.adapter = SimpleNamespace(actor_authority=authority)
        self.events.retention = SimpleNamespace(
            container=lambda invocation: (
                dict(
                    container_present=False,
                    container_type=None,
                    container_is_spell=None,
                    spell_protected=None,
                ),
                None,
            ),
            definition=lambda effect, invocation: dict(
                event_suppresses_level_one=False
            ),
            view=lambda: SimpleNamespace(entries=()),
        )
        self.events.authority = None
        self.events.replay = lambda source, **kwargs: self.sources.append(source)
        self.effect = dict(
            effect_class=304,
            native_effect_flags=[],
            target_masks=(None,) * 7,
        )
        self.invocation = SimpleNamespace(
            reference=101,
            caster_id=7,
            target_id=91,
            cell=(2, 3, 0),
            native_trigger_context=None,
        )

    def phase(self, **kwargs):
        with (
            patch(
                "wakfu_server.combat_ordinary_events.source_cost_descriptor",
                return_value=None,
            ),
            patch(
                "wakfu_server.combat_trigger_identifiers.source_identifiers",
                return_value={},
            ),
            patch(
                "wakfu_server.combat_effect_area.native_effect_areas",
                return_value=self.definitions,
            ),
        ):
            return self.events.phase(
                self.effect,
                self.invocation,
                uid=123,
                value=0,
                channel=kwargs.pop("channel", 1),
                **kwargs,
            )

    def test_generic_state_phases_deliver_actor_then_actual_area(self):
        for channel in (1, 2, 3, 4):
            self.phase(channel=channel, _event_ids=(0,))
        self.assertEqual(
            [(s.manager_actor_id, s.channel) for s in self.sources],
            [(7, 10), (91, 1), (7, 20), (91, 2), (7, 30), (91, 3), (7, 40), (91, 4)],
        )
        self.assertNotIn(91, self.preview.actors)

    def test_registered_null_qf_area_skips_only_area_listener_delivery(self):
        self.preview.native_effect_areas[91]["native_running_effect_manager"] = False
        self.preview.native_effect_areas[91].pop("state_ledger")
        self.definitions["111"]["native_area_properties"] = []
        self.definitions["111"]["entry_masks"] = [10000]
        self.phase(_event_ids=(0,))
        self.assertEqual(
            [(s.manager_actor_id, s.channel) for s in self.sources], [(7, 10)]
        )

    def test_null_qf_area_overlapping_own_entry_masks_rejects(self):
        self.preview.native_effect_areas[91]["native_running_effect_manager"] = False
        self.preview.native_effect_areas[91].pop("state_ledger")
        self.definitions["111"]["native_area_properties"] = []
        self.definitions["111"]["entry_masks"] = [0]
        with self.assertRaisesRegex(ValueError, "lifecycle callback authority"):
            self.phase(_event_ids=(0,))

    def test_actual_area_qf_precedes_own_l1_callback(self):
        order = []
        self.definitions["111"]["entry_masks"] = [10016]
        self.events.replay = lambda source, **kwargs: order.append(
            ("Qf", source.manager_actor_id)
        )

        def callback(effect, invocation, **kwargs):
            order.append(("Qq", kwargs["source"].manager_actor_id))
            self.assertTrue(kwargs["qf_delivered"])
            self.assertIs(kwargs["area_row"], self.preview.native_effect_areas[91])
            self.assertEqual(kwargs["source"].event_ids, (10016,))
            return (True,)

        self.events.retention.area_events = SimpleNamespace(running_source=callback)
        self.phase(_event_ids=(10016,))
        self.assertEqual(order, [("Qf", 7), ("Qf", 91), ("Qq", 91)])

    def test_actual_null_qf_still_receives_own_l1_callback(self):
        calls = []
        self.preview.native_effect_areas[91]["native_running_effect_manager"] = False
        self.preview.native_effect_areas[91].pop("state_ledger")
        self.definitions["111"]["native_area_properties"] = []
        self.definitions["111"]["entry_masks"] = [10016]

        def callback(effect, invocation, **kwargs):
            calls.append(kwargs["source"])
            return (True,)

        self.events.retention.area_events = SimpleNamespace(running_source=callback)
        self.phase(_event_ids=(10016,))
        self.assertEqual(
            [(source.manager_actor_id, source.channel) for source in self.sources],
            [(7, 10)],
        )
        self.assertEqual(
            [(source.manager_actor_id, source.channel) for source in calls], [(91, 1)]
        )

    def test_area_own_callback_is_not_repeated_at_other_channels(self):
        calls = []
        self.events.retention.area_events = SimpleNamespace(
            running_source=lambda *args, **kwargs: calls.append(kwargs) or ()
        )
        for channel in (2, 3, 4):
            self.phase(_event_ids=(10016,), channel=channel)
        self.assertEqual(calls, [])

    def test_area_qf_presence_must_match_native_properties(self):
        self.preview.native_effect_areas[91]["native_running_effect_manager"] = False
        with self.assertRaisesRegex(ValueError, "area PV authority"):
            self.phase(_event_ids=(0,))

    def test_unregistered_area_rejects(self):
        del self.preview.native_effect_areas[91]
        with self.assertRaisesRegex(ValueError, "actor absent"):
            self.phase(_event_ids=(0,))

    def test_healing_still_requires_authoritative_fighter(self):
        self.effect["effect_class"] = 24
        with self.assertRaisesRegex(ValueError, "actor absent"):
            self.phase()


if __name__ == "__main__":
    unittest.main()
