import unittest
from types import SimpleNamespace
from wakfu_server.characters.captured_roster import (
    CapturedCreature,
    OwnedCapturedRoster,
)
from wakfu_server.combat_captured_summon import (
    captured_summon_plan,
    NativeCapturedSummonPipeline,
)


class CapturedSummonTests(unittest.TestCase):
    def roster(self, available=True):
        return OwnedCapturedRoster(
            42,
            (CapturedCreature(0, 71, "owned"),) + (None,) * 9,
            (available,) + (False,) * 9,
        )

    def plan(self, parameters=(), roster=None, allocate_uid=lambda: 99):
        return captured_summon_plan(
            {"effect_class": 324},
            {"parameters": parameters},
            self.roster() if roster is None else roster,
            caster_id=42,
            caster_level=153,
            caster_direction=3,
            caster_team=0,
            allocate_uid=allocate_uid,
        )

    def test_profile_level_control_name_come_from_actual_owner(self):
        plan = self.plan()
        self.assertEqual(
            (
                plan.specification.reference,
                plan.specification.level,
                plan.specification.self_controlled,
                plan.name,
            ),
            (71, 153, False, "owned"),
        )

    def test_identity_reserved_even_when_slot_unavailable(self):
        calls = []
        plan = self.plan(
            roster=self.roster(False), allocate_uid=lambda: calls.append(99) or 99
        )
        self.assertEqual(calls, [99])
        self.assertFalse(plan.allowed)
        self.assertIsNone(plan.specification)

    def test_native_two_parameters_only_scaling_rule(self):
        plan = self.plan((50, 125))
        self.assertEqual((plan.main_factor, plan.secondary_factor), (0.5, 1.25))
        plan = self.plan((50, 125, 1, -3))
        self.assertEqual((plan.main_factor, plan.secondary_factor), (1.0, 1.0))
        self.assertEqual(
            (plan.specification.timeline_anchor, plan.specification.timeline_offset),
            ("start", -3),
        )

    def test_source_callbacks_follow_factory_fan_lE_roster_order(self):
        order = []
        actor = SimpleNamespace(id=99)
        pipeline = NativeCapturedSummonPipeline(
            profile_descriptor=lambda entry, **kwargs: order.append(
                ("descriptor", entry.profile_id, kwargs["level"])
            )
            or object(),
            create=lambda *args, **kwargs: order.append("create") or actor,
            scale_characteristics=lambda actor, main, secondary: order.append("fan"),
            mark_symbiot=lambda actor, value: order.append(("lE", value)),
            commit_roster=lambda preview, roster: order.append(
                ("roster", roster.available[0])
            ),
        )
        self.assertIs(
            pipeline.execute(
                self.plan(), self.roster(), preview=object(), cell=(1, 2, 0)
            ),
            actor,
        )
        self.assertEqual(
            order,
            [("descriptor", 71, 153), "create", "fan", ("lE", True), ("roster", False)],
        )

    def test_failed_factory_does_not_consume_roster_or_mark_symbiot(self):
        order = []
        pipeline = NativeCapturedSummonPipeline(
            profile_descriptor=lambda *args, **kwargs: None,
            create=lambda *args, **kwargs: order.append("create"),
            scale_characteristics=lambda *args: order.append("fan"),
            mark_symbiot=lambda *args: order.append("lE"),
            commit_roster=lambda *args: order.append("roster"),
        )
        with self.assertRaises(ValueError):
            pipeline.execute(
                self.plan(), self.roster(), preview=object(), cell=(0, 0, 0)
            )
        self.assertEqual(order, [])

    def test_reactive_slot_change_keeps_original_prepared_descriptor(self):
        seen = []
        replacement = OwnedCapturedRoster(
            42,
            (CapturedCreature(0, 99, "replacement"),) + (None,) * 9,
            (True,) + (False,) * 9,
        )
        pipeline = NativeCapturedSummonPipeline(
            profile_descriptor=lambda entry, **kwargs: seen.append(entry.profile_id)
            or object(),
            create=lambda *args, **kwargs: object(),
            scale_characteristics=lambda *args: None,
            mark_symbiot=lambda *args: None,
            commit_roster=lambda *args: None,
        )
        pipeline.execute(self.plan(), replacement, preview=object(), cell=(0, 0, 0))
        self.assertEqual(seen, [71])

    def test_prepared_foreign_owner_is_rejected(self):
        def unused(*args, **kwargs):
            self.fail("Foreign owner reached native producer")

        pipeline = NativeCapturedSummonPipeline(
            profile_descriptor=unused,
            create=unused,
            scale_characteristics=unused,
            mark_symbiot=unused,
            commit_roster=unused,
        )
        with self.assertRaises(ValueError):
            pipeline.execute(
                self.plan(), OwnedCapturedRoster(99), preview=object(), cell=(0, 0, 0)
            )

    def test_missing_selected_plan_never_calls_factory(self):
        def absent(*args, **kwargs):
            self.fail("Unexpected provider call")

        pipeline = NativeCapturedSummonPipeline(
            profile_descriptor=absent,
            create=absent,
            scale_characteristics=absent,
            mark_symbiot=absent,
            commit_roster=absent,
        )
        self.assertIsNone(
            pipeline.execute(
                self.plan(roster=self.roster(False)),
                self.roster(False),
                preview=object(),
                cell=(0, 0, 0),
            )
        )


if __name__ == "__main__":
    unittest.main()
