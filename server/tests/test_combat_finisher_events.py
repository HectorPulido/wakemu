import unittest
from types import SimpleNamespace
from wakfu_server.combat_event_replay import NativeEventSource
from wakfu_server.combat_finisher_events import (
    prepare_owned_finisher,
    finish_owned_finisher,
)
from wakfu_server.combat_native_events import subscription_actor_ids


class FinisherBoundaryTests(unittest.TestCase):
    def fixture(self, *, equipped=True, spell=False):
        caster = SimpleNamespace(
            id=7,
            native_cosmetic_state=dict(
                selected_values={5: (20753,) if equipped else ()},
                active_cosmetics={5: (20753,)} if equipped else {},
            ),
        )
        fight = SimpleNamespace(
            actors={7: caster},
            native_active_spell_id=7312 if spell else None,
            native_active_spell_container=(
                dict(present=True, is_spell=True, spell_id=7312, level=1)
                if spell
                else None
            ),
        )
        source = NativeEventSource(
            101,
            327627,
            46,
            7,
            -7,
            (2, 3, 0),
            (1013,),
            6,
            -7,
            None,
            False,
            False,
            False,
            True,
        )
        return fight, source

    def test_nonspell_arming_and_exact_source_binding(self):
        fight, source = self.fixture()
        calls = []
        event = prepare_owned_finisher(
            fight, source, replay=lambda s, **kw: calls.append(s), authority=object()
        )
        self.assertEqual(
            [(s.event_ids, s.channel, s.manager_actor_id) for s in calls],
            [((1018,), 60, 7), ((1012,), 60, 7)],
        )
        self.assertEqual(
            subscription_actor_ids(
                target_code=5,
                caster_code=2,
                original_caster=7,
                original_target=7,
                manager_actor=event.manager_actor_id,
                source_caster=event.caster_id,
                source_target=event.target_id,
                source_present=True,
            ),
            (7, -7),
        )
        self.assertEqual(event.uid, source.uid)
        calls.append("lethal_delivery")
        finish_owned_finisher(
            event, replay=lambda s, **kw: calls.append(s), authority=object()
        )
        self.assertEqual(calls[-2], "lethal_delivery")
        self.assertEqual((calls[-1].event_ids, calls[-1].channel), ((1015,), 40))

    def test_spell_already_armed_and_empty_component_unchanged(self):
        for equipped, expected in ((True, [(1012,)]), (False, [])):
            fight, source = self.fixture(equipped=equipped, spell=True)
            calls = []
            prepare_owned_finisher(
                fight,
                source,
                replay=lambda s, **kw: calls.append(s),
                authority=object(),
            )
            self.assertEqual([s.event_ids for s in calls], expected)

    def test_unknown_lethal_source_rejected(self):
        fight, _ = self.fixture()
        with self.assertRaises(ValueError):
            prepare_owned_finisher(
                fight, None, replay=lambda *a, **k: None, authority=None
            )
