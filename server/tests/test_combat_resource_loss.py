import unittest
import json
from pathlib import Path
from types import SimpleNamespace
from wakfu_server.combat_resource_loss import (
    resolve_resource_loss,
    apply_resource_loss,
    collision_ap_packet,
    stochastic_native_round,
    remove_resource_loss,
    resource_loss_event_ids,
)


class ResourceLossTests(unittest.TestCase):
    def plan(self, **kw):
        args = dict(
            stat_id=2,
            requested=1,
            current=6,
            minimum=0,
            maximum=6,
            caster_willpower=0,
            target_willpower=0,
            same_actor=False,
        )
        args.update(kw)
        return resolve_resource_loss(**args)

    def test_collision_one_is_stochastic_not_fixed(self):
        self.assertEqual(self.plan(random_fraction=lambda: 0.49).actual, 1)
        p = self.plan(random_fraction=lambda: 0.5)
        self.assertEqual((p.actual, p.calculation_status, p.event_override), (0, 3, 58))
        with self.assertRaisesRegex(ValueError, "RNG"):
            self.plan()

    def test_forced_value_follows_calculation_without_rewriting_native_status(self):
        from wakfu_server.combat_value_transfer import transfer_value_context

        plan = self.plan(
            target_willpower=100, value_context=transfer_value_context(b"", 2)
        )
        self.assertEqual((plan.calculated, plan.actual, plan.after), (2, 2, 4))
        self.assertEqual((plan.calculation_status, plan.event_override), (3, 58))
        self.assertEqual(plan.state_5227_parameters, (5227, 0, 20, 0, 100, 0))
        clamped = self.plan(
            caster_willpower=100, value_context=transfer_value_context(b"", 10)
        )
        self.assertEqual(
            (clamped.calculated, clamped.actual, clamped.after), (10, 6, 0)
        )
        self.assertEqual(
            (clamped.calculation_status, clamped.event_override), (0, None)
        )

    def test_negative_forced_value_restores_its_signed_actual_delta(self):
        from wakfu_server.combat_value_transfer import transfer_value_context

        plan = self.plan(
            current=3,
            target_willpower=100,
            value_context=transfer_value_context(b"", -2),
        )
        self.assertEqual((plan.calculated, plan.actual, plan.after), (-2, -2, 5))
        self.assertIsNone(plan.state_5227_parameters)
        self.assertEqual(
            remove_resource_loss(
                current=5, minimum=0, maximum=6, actual=plan.actual, frozen=False
            ),
            3,
        )
        bounded = self.plan(
            current=5,
            target_willpower=100,
            value_context=transfer_value_context(b"", -2),
        )
        self.assertEqual((bounded.actual, bounded.after), (-1, 6))
        self.assertEqual(
            remove_resource_loss(
                current=6, minimum=0, maximum=6, actual=bounded.actual, frozen=False
            ),
            5,
        )

    def test_willpower_same_actor_and_flag30(self):
        self.assertEqual(self.plan(caster_willpower=100).actual, 1)
        self.assertEqual(self.plan(target_willpower=100).actual, 0)
        self.assertEqual(
            self.plan(
                same_actor=True, caster_willpower=100, random_fraction=lambda: 0.8
            ).actual,
            0,
        )
        self.assertEqual(
            self.plan(
                ignores_willpower=True,
                caster_willpower=100,
                random_fraction=lambda: 0.8,
            ).actual,
            0,
        )

    def test_clamps_and_native_state_based_on_actual(self):
        p = self.plan(requested=8, current=2, random_fraction=lambda: 0)
        self.assertEqual((p.calculated, p.actual, p.after), (4, 2, 0))
        self.assertEqual(p.state_5227_parameters, (5227, 0, 20, 0, 100, 0))
        self.assertIsNone(
            self.plan(frozen=True, random_fraction=lambda: 0).state_5227_parameters
        )
        self.assertIsNone(
            self.plan(
                suppresses_loss_state=True, random_fraction=lambda: 0
            ).state_5227_parameters
        )

    def test_callbacks_required_before_preview_mutation(self):
        actor = SimpleNamespace(ap=6, effect_stats={2: 6})
        fight = SimpleNamespace(actors={2: actor})
        plan = self.plan(random_fraction=lambda: 0)
        with self.assertRaisesRegex(ValueError, "5227"):
            apply_resource_loss(
                fight,
                caster_id=1,
                target_id=2,
                stat_id=2,
                plan=plan,
                native_guards_verified=True,
                executable=True,
                secondary_state=None,
                after_apply=lambda *a: None,
            )
        self.assertEqual(actor.ap, 6)
        events = []
        apply_resource_loss(
            fight,
            caster_id=1,
            target_id=2,
            stat_id=2,
            plan=plan,
            native_guards_verified=True,
            executable=True,
            secondary_state=lambda *a: events.append(("state", a)),
            after_apply=lambda *a: events.append(("events", a)),
        )
        self.assertEqual((actor.ap, actor.effect_stats[2]), (5, 5))
        self.assertEqual(events[0][1][:3], (2, 2, (5227, 0, 10, 0, 100, 0)))
        self.assertEqual(events[1][0], "events")

    def test_removal_restores_owned_actual_and_respects_current_bounds(self):
        self.assertEqual(
            remove_resource_loss(
                current=1, minimum=0, maximum=6, actual=2, frozen=False
            ),
            3,
        )
        self.assertEqual(
            remove_resource_loss(
                current=5, minimum=0, maximum=6, actual=2, frozen=False
            ),
            6,
        )
        self.assertEqual(
            remove_resource_loss(
                current=1, minimum=0, maximum=6, actual=2, frozen=True
            ),
            1,
        )

    def test_synthetic_native_definition_uses_real_inherited_timing(self):
        from wakfu_server.combat_native_timing_context import native_definition_timing

        path = (
            Path(__file__).resolve().parents[1] / "protocol" / "collision-effect.json"
        )
        definition = json.loads(path.read_text())
        self.assertEqual(
            (definition["reference"], definition["effect_class"]), (-13, 55)
        )
        self.assertEqual(
            native_definition_timing(definition, 1),
            {"retained": False, "delay": False, "duration": 0},
        )

    def test_verified_native_event_mutations_by_lifecycle(self):
        p = self.plan(random_fraction=lambda: 0.9)
        self.assertEqual(
            resource_loss_event_ids(
                stat_id=2, phase=1, plan=p, extra_event_ids=(2254,)
            ),
            (0, 77, 2254),
        )
        self.assertEqual(
            resource_loss_event_ids(
                stat_id=2, phase=2, plan=p, extra_event_ids=(2254,)
            ),
            (0, 58, 77, 2254),
        )
        self.assertEqual(
            resource_loss_event_ids(
                stat_id=2, phase=3, plan=p, extra_event_ids=(2254,)
            ),
            (0, 58, 2254),
        )

    def test_up_fraction_boundary_and_packet_synthetic_id(self):
        self.assertEqual(stochastic_native_round(0.5, lambda: 0.5), 0)
        self.assertEqual(stochastic_native_round(0.5, lambda: 0), 1)
        opcode, body = collision_ap_packet(
            1, 1, uid=10, caster_id=1, target_id=-2, amount=1
        )
        self.assertEqual(opcode, 12613)
        self.assertEqual(int.from_bytes(body[13:17], "big"), 55)
        self.assertIn(b"\x18\xf3\xff\xff\xff\xff\xff\xff\xff\xff\x01", body)


if __name__ == "__main__":
    unittest.main()
