"""Historical listener context is not a future native invocation root."""
from copy import deepcopy
import unittest

from test_retained_gc_graph import fixture, wire
from wakfu_server.combat_retained_gc import plan_retired_effects


def listener_fixture():
    snapshot = fixture()
    snapshot["native_retained_records"]["11"] = dict(
        uid=11, manager_id=1, target_id=1, effect_class=330, owner_uid=10
    )
    snapshot["native_retained_order"].append(11)
    snapshot["native_owned_group_effects"]["11"] = dict(
        uid=11,
        effect_class=330,
        target_id=1,
        state_uid=10,
        payload=wire(11, 1, 1),
        timer=None,
        native_subscription_masks=[],
        native_selector=None,
        children=[],
        invocation=dict(
            caster_id=1, target_id=1, native_trigger_context={"target_id": -100}
        ),
    )
    return snapshot


class GroupTriggerHistoryTests(unittest.TestCase):
    def test_actual_replay_consumer_identity_revokes_history_proof(self):
        from importlib import import_module
        from unittest.mock import patch
        from wakfu_server import combat_retained_gc_boundary as boundary

        modules = [
            import_module("wakfu_server." + name)
            for name in (
                "combat_event_replay",
                "combat_retained_runtime",
                "combat_effect_dispatch",
                "combat_encounter_scene_external_participant",
                "combat_encounter_owned_start_binding",
                "combat_encounter_movement_binding",
                "combat_encounter_npc_start_binding",
                "rift_ko_cleanup",
            )
        ]
        self.assertTrue(boundary._native_group_replay_known())
        with patch.object(
            modules[0].NativeEventReplay, "__call__", new=lambda *args, **kwargs: None
        ):
            self.assertFalse(boundary._native_group_replay_known())
        self.assertTrue(boundary._native_group_replay_known())

    def test_history_only_edges_preserve_carriers_and_all_current_references(self):
        def plan(snapshot, *, enabled=True, pending=()):
            return plan_retired_effects(
                snapshot,
                {-100, -200},
                pending_roots=pending,
                _native_group_trigger_history=enabled,
            )

        snapshot = listener_fixture()
        before = deepcopy(snapshot)
        self.assertEqual(plan(snapshot, enabled=False).effect_uids, {31})
        self.assertEqual(plan(snapshot).effect_uids, {21, 22, 31})
        self.assertTrue({10, 20, 30}.isdisjoint(plan(snapshot).effect_uids))
        self.assertEqual(snapshot, before)
        # Pending execution consumes its actual context, independently of the
        # historical context retained by a subscription source.
        self.assertEqual(
            plan(
                snapshot,
                pending={"invocation": {"native_trigger_context": {"target_id": -100}}},
            ).effect_uids,
            {31},
        )
        for field, value in (("caster_id", -100), ("target_id", -100)):
            with self.subTest(current_reference=field):
                changed = deepcopy(snapshot)
                changed["native_owned_group_effects"]["11"]["invocation"][field] = value
                self.assertEqual(plan(changed).effect_uids, {31})
        # A PL/state UID preserves that carrier's value, not all unrelated
        # children of its terminal manager (the planner's source-only edge).
        changed = deepcopy(snapshot)
        row = changed["native_owned_group_effects"]["11"]
        row["invocation"]["state_uid"] = 20
        from wakfu_server.combat_retained_gc import _group_listener_reference_fields

        projected = _group_listener_reference_fields(
            row, changed["native_retained_records"]["11"]
        )
        self.assertEqual(projected["invocation"]["state_uid"], 20)
        self.assertEqual(plan(changed).effect_uids, {21, 22, 31})
        self.assertNotIn(20, plan(changed).effect_uids)
        changed = deepcopy(snapshot)
        changed["native_owned_group_effects"]["11"]["payload"] = wire(11, -100, 1)
        self.assertEqual(plan(changed).effect_uids, {31})

        # The private attestation is not a blanket context omission policy.
        cases = (
            "damage",
            "family307",
            "area",
            "delayed_row",
            "delayed_invocation",
            "unknown_family",
            "mismatched_uid",
            "missing_producer_shape",
            "non_dict_context",
        )
        for case in cases:
            with self.subTest(fallback=case):
                changed = deepcopy(snapshot)
                row = changed["native_owned_group_effects"]["11"]
                record = changed["native_retained_records"]["11"]
                if case in ("damage", "family307", "unknown_family"):
                    row["effect_class"] = record["effect_class"] = {
                        "damage": 1,
                        "family307": 307,
                        "unknown_family": 123456,
                    }[case]
                elif case == "area":
                    changed["native_owned_area_effects"]["11"] = changed[
                        "native_owned_group_effects"
                    ].pop("11")
                elif case == "delayed_row":
                    row["native_delayed_uid"] = 9000
                elif case == "delayed_invocation":
                    row["invocation"]["native_delayed_uid"] = 9000
                elif case == "mismatched_uid":
                    row["uid"] = 9999
                elif case == "missing_producer_shape":
                    del row["native_selector"]
                else:
                    row["invocation"]["native_trigger_context"] = [{"target_id": -100}]
                old = deepcopy(changed)
                self.assertEqual(plan(changed), plan(changed, enabled=False))
                self.assertTrue({21, 22}.isdisjoint(plan(changed).effect_uids))
                self.assertEqual(changed, old)
        self.assertEqual(plan(snapshot, enabled=1), plan(snapshot, enabled=False))


if __name__ == "__main__":
    unittest.main()
