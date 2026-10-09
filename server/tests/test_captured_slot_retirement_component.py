"""Individual descriptor availability is separate from owner all-slot teardown."""
from copy import deepcopy
from types import SimpleNamespace
import unittest
from wakfu_server.characters.captured_roster import (
    OwnedCapturedRoster,
    CapturedCreature,
)
from wakfu_server.combat_captured_roster_lifecycle import (
    release_captured_slot_on_retirement,
)


class CapturedSlotRetirementTests(unittest.TestCase):
    def fixture(self):
        slots = [None] * 10
        slots[3] = CapturedCreature(3, 5347, "Owned")
        slots[5] = CapturedCreature(5, 5115, "Other")
        roster = OwnedCapturedRoster(7, tuple(slots), (False,) * 10, 5)
        source = dict(
            native_symbiot_source="eZr324.after_common_factory_and_fan.lE_true",
            native_captured_owner_id=7,
            native_captured_slot=3,
            caster_id=7,
            native_relation_source="big.new_bje.fdt_initial_registration",
            ref=5347,
            level=153,
        )
        actor = SimpleNamespace(id=295, owner_id=1, native_summon_source=source)
        owner = SimpleNamespace(id=7, owner_id=1)
        fight = SimpleNamespace(
            actors={7: owner, 295: actor},
            native_summon_registrations={
                295: dict(
                    actor_id=295,
                    authority=dict(
                        native_summoned_from_symbiot=True,
                        breed_id=5347,
                        native_real_level=153,
                    ),
                )
            },
            native_captured_rosters={"7": roster.to_record()},
            native_captured_roster_updates={},
        )
        return fight, actor, roster

    def test_only_bound_slot_released_descriptors_selection_preserved(self):
        fight, actor, original = self.fixture()
        self.assertTrue(release_captured_slot_on_retirement(fight, actor, 7, 3))
        result = OwnedCapturedRoster.from_record(
            fight.native_captured_rosters["7"], expected_owner_id=7
        )
        self.assertEqual(result.slots, original.slots)
        self.assertEqual(result.selected_slot, 5)
        self.assertEqual(result.available, tuple(index == 3 for index in range(10)))
        self.assertEqual(
            fight.native_captured_rosters["7"],
            fight.native_captured_roster_updates["7"],
        )
        self.assertFalse(release_captured_slot_on_retirement(fight, actor, 7, 3))

    def test_replaced_descriptor_rejected_without_partial_publication(self):
        fight, actor, _ = self.fixture()
        actor.native_summon_source["ref"] = 5115
        before = deepcopy(fight.native_captured_rosters)
        with self.assertRaises(ValueError):
            release_captured_slot_on_retirement(fight, actor, 7, 3)
        self.assertEqual(fight.native_captured_rosters, before)
        self.assertEqual(fight.native_captured_roster_updates, {})
