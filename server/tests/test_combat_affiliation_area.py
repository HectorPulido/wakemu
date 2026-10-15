"""Native eYV1030 accepts faV PV targets and respects actual Qf ownership."""
import unittest
from types import SimpleNamespace

from wakfu_server.combat_affiliation_effect import (
    NativeAffiliationHandler,
    remove_affiliation,
)
from wakfu_server.combat_effect_dispatch import EffectInvocation
from wakfu_server.combat_state_ledger import StateLedger
from wakfu_server.combat_stat_handler import StatExecutionContext


def area(uid, *, manager):
    row = {
        "uid": uid,
        "native_area_contract": "fbb",
        "native_running_effect_manager": manager,
        "native_fight_affiliation": 1,
        "native_fight_affiliation_source": "faV.j(PV).bcM",
    }
    if manager:
        row["state_ledger"] = StateLedger(uid)
    return row


class NativeAffiliationAreaTests(unittest.TestCase):
    def handler(self, fight, packets, *, retained):
        ids = iter((701,))
        return NativeAffiliationHandler(
            fight,
            packets,
            action_id=8,
            allocate_uid=lambda: next(ids),
            rng=lambda: 0.5,
            context=lambda *_: StatExecutionContext(True, True, None, retained, b""),
            authority=lambda *_: SimpleNamespace(targeting={"is_amO": True}),
        )

    def invocation(self, target_id=10):
        return EffectInvocation(392384, 1, 7, target_id, (2, 3, 0))

    def test_null_qf_area_mutates_bcM_without_inventing_retained_effect(self):
        target = area(10, manager=False)
        fight = SimpleNamespace(
            id=78,
            phase="active",
            actors={7: SimpleNamespace(id=7, team=0)},
            native_effect_areas={10: target},
            native_retired_area_managers={},
            owned_stat_effects={},
        )
        packets = []
        handler = self.handler(fight, packets, retained=True)

        self.assertTrue(
            handler(
                {"effect_class": 1030, "parameters": [130, 0]}, {}, self.invocation()
            )
        )
        self.assertEqual(target["native_fight_affiliation"], -126)
        self.assertEqual(fight.owned_stat_effects, {})
        self.assertEqual([opcode for opcode, _ in packets], [13497])

    def test_qf_area_retains_and_removes_against_registered_pv_uid(self):
        target = area(10, manager=True)
        fight = SimpleNamespace(
            id=78,
            phase="active",
            actors={7: SimpleNamespace(id=7, team=0)},
            native_effect_areas={10: target},
            native_retired_area_managers={},
            owned_stat_effects={},
        )
        packets = []
        handler = self.handler(fight, packets, retained=True)

        self.assertTrue(
            handler(
                {"effect_class": 1030, "parameters": [130, 0]}, {}, self.invocation()
            )
        )
        self.assertEqual(target["native_fight_affiliation"], -126)
        self.assertEqual(fight.owned_stat_effects[701]["target_id"], 10)

        remove_affiliation(handler, 701)
        self.assertEqual(target["native_fight_affiliation"], 1)
        self.assertEqual(fight.owned_stat_effects, {})
        self.assertEqual([opcode for opcode, _ in packets], [13497, 13560])

    def test_qf_area_retirement_removal_does_not_require_fighter_ledger(self):
        target = area(10, manager=True)
        fight = SimpleNamespace(
            id=78,
            phase="active",
            actors={7: SimpleNamespace(id=7, team=0)},
            native_effect_areas={10: target},
            native_retired_area_managers={},
            owned_stat_effects={},
        )
        packets = []
        handler = self.handler(fight, packets, retained=True)
        handler({"effect_class": 1030, "parameters": [130, 0]}, {}, self.invocation())

        del fight.native_effect_areas[10]
        fight.native_retired_area_managers[10] = target
        remove_affiliation(handler, 701)

        self.assertEqual(target["native_fight_affiliation"], 1)
        self.assertEqual([opcode for opcode, _ in packets], [13497, 13560])

    def test_unregistered_or_unproven_area_target_is_rejected(self):
        for target in (
            {"uid": 10, "native_area_contract": "fbb"},
            {
                **area(10, manager=False),
                "native_fight_affiliation_source": "owner.team",
            },
        ):
            fight = SimpleNamespace(
                id=78,
                phase="active",
                actors={7: SimpleNamespace(id=7, team=0)},
                native_effect_areas={10: target},
                owned_stat_effects={},
            )
            handler = self.handler(fight, [], retained=False)
            with self.assertRaises(ValueError):
                handler.prepare(
                    {"effect_class": 1030, "parameters": [1, 0]},
                    {},
                    self.invocation(),
                )


if __name__ == "__main__":
    unittest.main()
