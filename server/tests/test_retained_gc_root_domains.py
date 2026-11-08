"""Root-domain regressions for the public retained-GC planner."""
from copy import deepcopy
import unittest

from test_retained_gc_graph import fixture
from wakfu_server.combat_retained_gc import plan_retired_effects


class RootDomainTests(unittest.TestCase):
    def plan(self, snapshot):
        return plan_retired_effects(snapshot, {-100, -200}, pending_roots=[])

    def test_empty_queue_counter_collision_does_not_root_carrier_owner(self):
        snap = fixture()
        snap["native_delay_queue"] = dict(
            source="native.eZR.bbS.SU.TC.Tu.v1", next_sequence=20, entries=[]
        )
        before = deepcopy(snap)
        self.assertEqual(self.plan(snap).effect_uids, {21, 22, 31})
        self.assertEqual(before, snap)

    def test_actual_delayed_uid_keeps_operative_owner(self):
        snap = fixture()
        snap["native_delay_queue"] = dict(
            source="native.eZR.bbS.SU.TC.Tu.v1",
            next_sequence=2,
            entries=[
                dict(
                    sequence=1,
                    uid=20,
                    clock_id=1,
                    round=1,
                    phase="start",
                    invocation={},
                )
            ],
        )
        self.assertEqual(self.plan(snap).effect_uids, {31})
        snap["native_delay_queue"]["entries"][0]["invocation"] = {"effect_uid": 30}
        self.assertEqual(self.plan(snap).effect_uids, set())

    def test_actor_key_collision_is_not_runner_reference_but_values_are(self):
        from wakfu_server.combat_retained_gc import _ACTOR_KEYED_ROOTS

        for name in _ACTOR_KEYED_ROOTS:
            with self.subTest(name=name):
                snap = fixture()
                snap["actors"]["21"] = {"id": 21, "state_ledger": {"entries": []}}
                snap[name] = {"21": {}}
                self.assertEqual(self.plan(snap).effect_uids, {21, 22, 31})
                snap[name]["21"] = {"effect_uid": 20}
                self.assertEqual(self.plan(snap).effect_uids, {31})

    def test_terminal_actor_key_still_preserves_actor_manager(self):
        snap = fixture()
        snap["native_social_contexts"] = {"-100": {}}
        self.assertEqual(self.plan(snap).effect_uids, {31})

    def test_unknown_map_keeps_conservative_uid_edges(self):
        snap = fixture()
        snap["unknown_extension"] = {"21": {}}
        self.assertEqual(self.plan(snap).effect_uids, {31})

    def test_unknown_queue_and_actor_key_schema_fail_closed(self):
        queue = dict(source="native.eZR.bbS.SU.TC.Tu.v1", next_sequence=2, entries=[])
        for bad in (
            {**queue, "extension": 20},
            {**queue, "source": "unknown"},
            {**queue, "next_sequence": True},
            {**queue, "entries": [{"uid": 20}]},
        ):
            with self.subTest(queue=bad):
                snap = fixture()
                snap["native_delay_queue"] = bad
                plan = self.plan(snap)
                self.assertEqual(plan.effect_uids, set())
                self.assertTrue(plan.opaque_sources)
        for bad in ({True: {}}, {"01": {}}, {"999": {}}, []):
            snap = fixture()
            snap["native_social_contexts"] = bad
            plan = self.plan(snap)
            self.assertEqual(plan.effect_uids, set())
            self.assertTrue(plan.opaque_sources)
