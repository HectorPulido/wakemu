"""Native207 may change effective affiliation, never physical ownership."""
import copy
import unittest
import test_tactical as fixture
from wakfu_ai.planning import tactical, planner, scoring


class NativeControllerTeamForecastTests(unittest.TestCase):
    def receipt(self):
        return dict(
            source="fdt.a.fdy.saH_saJ_saF_ebh.v1",
            producer="eWD207.eZd.fQM.actual",
            effect_class=207,
            effect_reference=340345,
            running_uid=501,
            target_id=1,
            caster_id=-2,
            controller_id=-2,
            current_team=1,
            original_team=0,
            original_controller=1,
        )

    def data(self):
        data = fixture.snapshot()
        actors = copy.deepcopy(data["actors"])
        actors[1]["team"] = 1
        actors[1]["nativeControllerTransfer"] = self.receipt()
        fixture.add_state(data, "control", actors)
        return data

    def test_actual_source_receipt_admits_effective_team_change_only(self):
        data = self.data()
        tactical.validate(data, planner.validate)
        for field, value in [
            ("producer", "guessed"),
            ("running_uid", 0),
            ("current_team", 0),
            ("original_team", 1),
            ("controller_id", 1234),
        ]:
            invalid = copy.deepcopy(data)
            invalid["states"][1]["actors"][1]["nativeControllerTransfer"][field] = value
            with self.subTest(field=field), self.assertRaisesRegex(
                ValueError, "ownership"
            ):
                tactical.validate(invalid, planner.validate)
        invalid = self.data()
        invalid["states"][1]["actors"][1]["controlled"] = False
        with self.assertRaisesRegex(ValueError, "ownership"):
            tactical.validate(invalid, planner.validate)
        invalid = self.data()
        del invalid["states"][1]["actors"][1]["nativeControllerTransfer"]
        with self.assertRaisesRegex(ValueError, "ownership"):
            tactical.validate(invalid, planner.validate)

    def test_scoring_uses_current_effective_affiliation(self):
        data = self.data()
        actor_id, states, weights, *_ = tactical.validate(data, planner.validate)
        root, state = states["root"], states["control"]
        state["actors"][1]["armor"] = 10
        _, components, _, _ = scoring.evaluate(root, state, actor_id, weights, {})
        self.assertGreater(components["armor"], 0)

    def test_source_bound_native_affiliation1030_uses_same_physical_ownership_guard(
        self,
    ):
        data = self.data()
        row = data["states"][1]["actors"][1]["nativeControllerTransfer"]
        row.update(
            producer="eYV1030.fdy.au.actual", effect_class=1030, effect_reference=340427
        )
        tactical.validate(data, planner.validate)
        row["producer"] = "eWD207.eZd.fQM.actual"
        with self.assertRaisesRegex(ValueError, "ownership"):
            tactical.validate(data, planner.validate)
