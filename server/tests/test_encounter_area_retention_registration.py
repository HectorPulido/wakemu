"""A reconstructed area publisher runs after the real central Qf registration."""
from copy import deepcopy
import unittest

import test_combat_retained_areas as retained_fixture
from wakfu_server.combat_effect_dispatch import EffectInvocation
from wakfu_server.combat_retained_runtime import NativeRetainedRuntime


class EncounterAreaRetentionRegistrationTests(unittest.TestCase):
    def test_parent315_is_complete_before_publisher_and_failed_preview_can_retry(self):
        base, _, _ = retained_fixture.NativeRetainedAreaTests().fixture(True)
        source_row = deepcopy(base.native_owned_area_effects[902])
        source_area = deepcopy(base.native_effect_areas[901])
        source_area.update(effect_uid=902, effect_reference=123)
        base.native_owned_area_effects.clear()
        base.native_effect_areas.clear()
        base.native_retained_tracking = True
        base.native_retained_records, base.native_retained_order = {}, []
        base.publisher_marks, base.trace = [], []
        effect = dict(
            effect_class=315,
            variant=0,
            minimum_level=0,
            maximum_level=1,
            parameters=[1546, 0, 1, 0, 1, 0],
            native_execution_mode=0,
        )
        metadata = dict(
            effects={
                "123": dict(effect, definition_type=0, definition_dispellable=True)
            },
            states={},
        )
        invocation = EffectInvocation(
            123, 1, 7, None, (2, -3, 4), native_retained_container={"present": False}
        )

        def operation(fight, *, fail=False):
            retention = NativeRetainedRuntime(
                fight,
                [],
                plan={"native_retained_container": {"present": False}},
                state_catalog={},
                action_id=3,
                timing=None,
                metadata=metadata,
            )
            test = self

            class AreaHandler:
                def __call__(self, definition, values, call):
                    fight.native_owned_area_effects[902] = deepcopy(source_row)
                    fight.native_effect_areas[901] = deepcopy(source_area)
                    fight.trace.append("native_created")
                    # This reproduces the actual early10006 failure without
                    # weakening the strict complete-population view guard.
                    with test.assertRaisesRegex(
                        ValueError, "Unregistered native retained"
                    ):
                        retention.view()
                    return True

                def on_post_retention_registration(self, row):
                    test.assertEqual(row["uid"], 901)
                    test.assertEqual(
                        {entry.uid for entry in retention.view().entries}, {902}
                    )
                    fight.trace.append("complete_parent315")
                    fight.publisher_marks.append([row["uid"], 7])
                    if fail:
                        raise ValueError("injected publisher child failure")

            self.assertTrue(retention.wrap(AreaHandler())(effect, {}, invocation))
            self.assertEqual(fight.trace, ["native_created", "complete_parent315"])
            self.assertEqual(fight.publisher_marks, [[901, 7]])
            self.assertEqual(set(retention._live()), {902})
            self.assertEqual(set(fight.native_retained_records), {902})

        failed = deepcopy(base)
        with self.assertRaisesRegex(ValueError, "injected publisher"):
            operation(failed, fail=True)
        self.assertEqual(base.publisher_marks, [])
        self.assertEqual(base.native_owned_area_effects, {})
        self.assertEqual(base.native_retained_records, {})
        retried = deepcopy(base)
        operation(retried)
