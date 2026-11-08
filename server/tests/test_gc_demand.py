"""Demand traversal retains the complete planner's observable root contract."""
from copy import deepcopy
import sys
import unittest
from test_retained_gc_graph import fixture, wire
from wakfu_server import combat_retained_gc as gc_plan


class DemandRetainedGCTests(unittest.TestCase):
    def test_reference_plan_parity_roots_opaque_data_and_native_retirement(self):
        scenarios = []

        def case(name, modify=lambda snapshot: None, pending=()):
            snapshot = fixture()
            modify(snapshot)
            scenarios.append((name, snapshot, pending))

        case("terminal_carrier_value_only")
        case(
            "live_caster",
            lambda s: s["state_wire_payloads"].__setitem__("10", wire(10, -100, 1)),
        )
        case(
            "wire_related_uid",
            lambda s: s["state_wire_payloads"].__setitem__(
                "10", wire(10, 1, 1, related=21)
            ),
        )

        def cross_manager(snapshot):
            snapshot["native_retained_records"]["11"] = dict(
                uid=11, manager_id=1, target_id=1, effect_class=949, owner_uid=20
            )
            snapshot["native_owned_group_effects"]["11"] = dict(
                uid=11, target_id=1, state_uid=20, payload=wire(11, 1, 1), timer=None
            )
            snapshot["native_retained_order"].append(11)

        case("cross_manager_parent", cross_manager)
        case(
            "source_provenance",
            lambda s: s["native_state_source_provenance"].update(
                entries={
                    "10": dict(uid=10, caster_id=1, target_id=1, parent_state_uid=19),
                    "19": dict(
                        uid=19, caster_id=-100, target_id=-100, parent_state_uid=20
                    ),
                    "20": dict(
                        uid=20, caster_id=-100, target_id=-100, parent_state_uid=None
                    ),
                }
            ),
        )
        case("pending_cross_manager", pending={"future_runner": 20})
        case(
            "active_area",
            lambda s: s.update(
                native_effect_areas={"900": {"uid": 900, "effect_uid": 20}}
            ),
        )

        def retired_source(snapshot):
            snapshot["actors"]["1"]["area_uid"] = 900
            snapshot["native_retired_area_managers"] = {
                "900": dict(
                    uid=900,
                    effect_uid=10,
                    native_area_contract="faM",
                    native_running_effect_manager=False,
                    executing=False,
                    removing=False,
                    child_effect_uids={"-100": [21]},
                )
            }

        case("dormant_area_source", retired_source)
        case("pending_area_execution", retired_source, {"area": 900})
        case(
            "timer",
            lambda s: s["native_owned_group_effects"]["21"].update(
                timer={"remaining": 1}
            ),
        )
        case(
            "actual_delay",
            lambda s: s.update(
                native_delay_queue=dict(
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
            ),
        )
        case(
            "opaque_wire_unreachable",
            lambda s: s["native_owned_group_effects"]["31"].update(payload="ff"),
        )
        case(
            "opaque_context_unreachable",
            lambda s: s["native_owned_group_effects"]["31"].update(
                native_context_hex="ff"
            ),
        )
        case(
            "opaque_child_registry",
            lambda s: s.update(
                native_retired_area_managers={
                    "900": dict(uid=900, child_effect_uids={"-100": object()})
                }
            ),
        )
        counts = []
        for name, snapshot, pending in scenarios:
            with self.subTest(name=name):
                # The opaque object is intentionally shared, not compared by copied identity.
                before = repr(snapshot)
                known = gc_plan.reference_schemas_known(snapshot)
                plans = []
                for enabled in (False, True):
                    calls = []

                    def profile(frame, event, arg):
                        if (
                            event == "call"
                            and frame.f_code.co_name == "walk"
                            and frame.f_code.co_filename == gc_plan.__file__
                        ):
                            calls.append(1)

                    old = sys.getprofile()
                    try:
                        sys.setprofile(profile)
                        plans.append(
                            gc_plan.plan_retired_effects(
                                snapshot,
                                {-100, -200},
                                pending_roots=pending,
                                _reference_schemas_valid=known if enabled else False,
                            )
                        )
                    finally:
                        sys.setprofile(old)
                    if name == "terminal_carrier_value_only":
                        counts.append(len(calls))
                self.assertEqual(*plans)
                self.assertEqual(repr(snapshot), before)
                if name.startswith("opaque_"):
                    self.assertFalse(plans[1].effect_uids)
                    self.assertTrue(plans[1].opaque_sources)
                if name == "terminal_carrier_value_only":
                    self.assertEqual(plans[1].effect_uids, {21, 22, 31})
                    self.assertTrue(known)
        self.assertLess(counts[1], counts[0])
        # Actual native terminal receipt is the boundary authority, never HP zero.
        from test_gc_owned_collections import OwnedCollectionGCTests
        from wakfu_server import combat_retained_gc_boundary as boundary

        for field in ("native_context_hex", "child_effect_uids"):
            cycle = []
            cycle.append(cycle)
            self.assertFalse(gc_plan.reference_schemas_known({field: cycle}))
            _, graph, _, dead, _ = OwnedCollectionGCTests().fixture()
            setattr(graph.actors[dead], field, cycle)
            self.assertFalse(boundary._canonical_graph(graph, reference_schemas=[]))
        # Native storage wrappers project to dictionaries. An already visited
        # alias must still be checked under its new contextual field name.
        _, graph, _, dead, _ = OwnedCollectionGCTests().fixture()
        graph.actors[dead].child_effect_uids = graph.native_owned_group_effects
        schemas = []
        self.assertTrue(boundary._canonical_graph(graph, reference_schemas=schemas))
        self.assertEqual(schemas, [False])
        projected, projected_roots = boundary._project_snapshot(graph, ())
        reference = gc_plan.plan_retired_effects(projected, {dead}, pending_roots=())
        guarded = gc_plan.plan_retired_effects(
            projected,
            {dead},
            pending_roots=(),
            _reference_schemas_valid=schemas == [True],
        )
        self.assertEqual(reference, guarded)
        self.assertFalse(guarded.effect_uids)
        self.assertTrue(guarded.opaque_sources)
        previous, fight, runtime, dead, uid = OwnedCollectionGCTests().fixture()
        self.assertIn(dead, boundary._terminal_retired_ids(fight))
        boundary.prepare_retired_gc(previous, fight, runtime, ())
        self.assertNotIn(uid, fight.native_retained_records)
        self.assertIn(dead, fight.actors)
        self.assertIn(uid, previous.native_retained_records)
        for opaque_callback in (False, True):
            previous, fight, runtime, dead, uid = OwnedCollectionGCTests().fixture()
            if opaque_callback:
                runtime.turn_start_provider = lambda *args, **kwargs: None
            else:
                fight.native_ordinary_qi_retirements.clear()
                self.assertEqual(fight.actors[dead].hp, 0)
                self.assertNotIn(dead, boundary._terminal_retired_ids(fight))
            boundary.prepare_retired_gc(previous, fight, runtime, ())
            self.assertIn(uid, fight.native_retained_records)


if __name__ == "__main__":
    unittest.main()
