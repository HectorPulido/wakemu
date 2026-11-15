"""The Rii START listener binds the captured 8003 carrier to its hero owner."""

import unittest
from types import SimpleNamespace

from wakfu_server.combat_event_replay import NativeExternalEvent
from wakfu_server.rii_lesson_start_source import (
    permits_distance_floor_retirement,
    permits_lesson_floor_retirement,
    permits_movement_marker_population,
    start_caster,
)


class RiiLessonStartSourceTests(unittest.TestCase):
    def fixture(self, *, carrier=True, reference=8003, carrier_caster=-2):
        owner = SimpleNamespace(
            id=7,
            controlled=True,
            state_ledger=SimpleNamespace(
                entries=(
                    [
                        SimpleNamespace(
                            uid=91,
                            reference=reference,
                            level=1,
                            caster_id=carrier_caster,
                        )
                    ]
                    if carrier
                    else []
                )
            ),
        )
        sack = SimpleNamespace(id=-2, controlled=False)
        fight = SimpleNamespace(
            actors={7: owner, -2: sack},
            rii_distance_lesson_contract={
                "owner": 7,
                "target": -2,
                "native_lesson": True,
            },
        )
        source = NativeExternalEvent(7, (1003,), 61)
        entry = SimpleNamespace(manager_id=7, generic_effect=361178)
        original = SimpleNamespace(
            reference=361178,
            state_uid=91,
            caster_id=-2,
            target_id=7,
        )
        return fight, source, entry, original

    def test_owned_start_carrier_rebinds_to_hero_and_keeps_sack_as_source(self):
        fight, source, entry, original = self.fixture()
        self.assertEqual(start_caster(fight, source, entry=entry, original=original), 7)

    def test_ordinary_and_foreign_start_events_do_not_rebind(self):
        fight, source, entry, original = self.fixture()
        ordinary = SimpleNamespace(actors=fight.actors)
        self.assertIsNone(
            start_caster(ordinary, source, entry=entry, original=original)
        )
        foreign = NativeExternalEvent(8, (1003,), 61)
        self.assertIsNone(start_caster(fight, foreign, entry=entry, original=original))
        self.assertIsNone(
            start_caster(
                fight,
                NativeExternalEvent(7, (1001,), 61),
                entry=entry,
                original=original,
            )
        )

    def test_missing_or_mismatched_8003_carrier_is_rejected(self):
        cases = (
            self.fixture(carrier=False),
            self.fixture(reference=8004),
            self.fixture(carrier_caster=-3),
        )
        for fight, source, entry, original in cases:
            with self.subTest(carrier=fight.actors[7].state_ledger.entries):
                with self.assertRaisesRegex(ValueError, "captured carrier ownership"):
                    start_caster(fight, source, entry=entry, original=original)

    def movement_fixture(self, *, native=True, carrier_caster=-2):
        owner = SimpleNamespace(
            state_ledger=SimpleNamespace(
                entries=[
                    SimpleNamespace(
                        uid=91,
                        reference=8003,
                        caster_id=carrier_caster,
                    )
                ]
            )
        )
        fight = SimpleNamespace(
            actors={7: owner},
            rii_movement_lesson_contract={
                "owner": 7,
                "target": -2,
                "native_lesson": native,
            },
        )
        effect = {
            "effect_class": 330,
            "parameter_count": 0,
            "parameters": (),
            "criteria": 'HasState(8011, "target")',
            "area_class": "anD",
            "native_target_selector": {"class": "fcE", "mask": 1 << 47},
        }
        invocation = SimpleNamespace(
            reference=409652,
            state_uid=91,
            caster_id=7,
            target_id=7,
            wakemu_fresh_child_selection=True,
            native_preselected_target=False,
            native_explicit_target=True,
            native_trigger_context=None,
        )
        return fight, effect, invocation

    def test_movement_marker_requires_the_owned_carrier_and_native_descriptor(self):
        fight, effect, invocation = self.movement_fixture()
        self.assertTrue(permits_movement_marker_population(fight, effect, invocation))

        ordinary, effect, invocation = self.movement_fixture(native=False)
        self.assertFalse(
            permits_movement_marker_population(ordinary, effect, invocation)
        )
        foreign, effect, invocation = self.movement_fixture(carrier_caster=-3)
        self.assertFalse(
            permits_movement_marker_population(foreign, effect, invocation)
        )
        fight, effect, invocation = self.movement_fixture()
        with self.assertRaisesRegex(ValueError, "native program"):
            permits_movement_marker_population(
                fight, dict(effect, criteria=""), invocation
            )

    def test_distance_floor_retirement_is_owned_and_matches_native_program(self):
        target = SimpleNamespace(
            id=-2,
            state_ledger=SimpleNamespace(
                entries=[SimpleNamespace(uid=92, reference=7922, caster_id=-2)]
            ),
        )
        fight = SimpleNamespace(
            actors={-2: target},
            rii_distance_lesson_contract={
                "owner": 7,
                "target": -2,
                "native_lesson": True,
            },
        )
        effect = {
            "effect_class": 843,
            "parameters": (-1.0, 0.0),
            "criteria": "IsSpecificArea(1102) or IsSpecificArea(1103)",
            "area_class": "anA",
            "native_target_selector": {"class": "fcE", "mask": 1 << 51},
        }
        for reference in (367122, 367125):
            invocation = SimpleNamespace(
                reference=reference,
                state_uid=92,
                caster_id=7,
                target_id=-2,
                wakemu_fresh_child_selection=True,
                native_preselected_target=False,
                native_explicit_target=True,
            )
            with self.subTest(reference=reference):
                self.assertTrue(
                    permits_distance_floor_retirement(fight, effect, invocation)
                )
                ordinary = SimpleNamespace(
                    actors=fight.actors,
                    rii_distance_lesson_contract=dict(
                        fight.rii_distance_lesson_contract, native_lesson=False
                    ),
                )
                self.assertFalse(
                    permits_distance_floor_retirement(ordinary, effect, invocation)
                )
                foreign = SimpleNamespace(
                    actors={
                        -2: SimpleNamespace(
                            id=-2,
                            state_ledger=SimpleNamespace(
                                entries=[
                                    SimpleNamespace(
                                        uid=92, reference=7922, caster_id=-3
                                    )
                                ]
                            ),
                        )
                    },
                    rii_distance_lesson_contract=fight.rii_distance_lesson_contract,
                )
                self.assertFalse(
                    permits_distance_floor_retirement(foreign, effect, invocation)
                )
                with self.assertRaisesRegex(ValueError, "native program"):
                    permits_distance_floor_retirement(
                        fight, dict(effect, area_class="anu"), invocation
                    )

    def test_los_floor_retirement_requires_its_bound_8003_carrier(self):
        owner = SimpleNamespace(
            state_ledger=SimpleNamespace(
                entries=[SimpleNamespace(uid=93, reference=8003, caster_id=-2)]
            )
        )
        fight = SimpleNamespace(
            actors={7: owner, -2: SimpleNamespace(id=-2)},
            rii_los_lesson_contract={
                "owner": 7,
                "target": -2,
                "native_lesson": True,
            },
        )
        effect = {
            "effect_class": 843,
            "parameters": (-1.0, 0.0),
            "criteria": "IsSpecificArea(1808)",
            "area_class": "anD",
            "native_target_selector": {"class": "fcE", "mask": 0},
        }
        invocation = SimpleNamespace(
            reference=367610,
            state_uid=93,
            caster_id=7,
            target_id=-2,
            wakemu_fresh_child_selection=True,
            native_preselected_target=False,
            native_explicit_target=True,
        )
        self.assertTrue(permits_lesson_floor_retirement(fight, effect, invocation))
        ordinary = SimpleNamespace(
            actors=fight.actors,
            rii_los_lesson_contract=dict(
                fight.rii_los_lesson_contract, native_lesson=False
            ),
        )
        self.assertFalse(permits_lesson_floor_retirement(ordinary, effect, invocation))
        foreign = SimpleNamespace(
            actors={
                7: SimpleNamespace(
                    state_ledger=SimpleNamespace(
                        entries=[SimpleNamespace(uid=93, reference=8003, caster_id=-3)]
                    )
                ),
                -2: fight.actors[-2],
            },
            rii_los_lesson_contract=fight.rii_los_lesson_contract,
        )
        self.assertFalse(permits_lesson_floor_retirement(foreign, effect, invocation))
        with self.assertRaisesRegex(ValueError, "native program"):
            permits_lesson_floor_retirement(
                fight, dict(effect, criteria="IsSpecificArea(1102)"), invocation
            )


if __name__ == "__main__":
    unittest.main()
