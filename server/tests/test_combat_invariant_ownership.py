"""Source-attested ownership checks preserve native non-HP participation."""
import unittest
from unittest.mock import patch

from wakfu_server.combat_invariant_ownership import (
    LISTENER_SOURCE,
    PV_SOURCE,
    RELATION_SOURCE,
    check_ownership,
)
from wakfu_server.combat_state import Actor
from wakfu_server.combat_state_ledger import RunningState, StateLedger
from wakfu_server.combat_state_timing import StateTimer


def actor(identity, team=0):
    result = Actor(identity, team, (identity, 0, 0), 50, 6, 3, 10, 1)
    result.native_turn_suppression_bits = 0
    result.native_fight_properties = frozenset()
    return result


def fixture():
    actors = {7: actor(7), -7: actor(-7, 1)}
    state = dict(
        actors=actors,
        phase="active",
        order=[7, -7],
        native_global_pv_collections=dict(
            source=PV_SOURCE,
            mode="rRm",
            fighters=dict(keys=[7, -7, 0], states=[1, 1, 0], size=2),
            areas={},
            extras={},
            fighter_status={"7": "IN_PLAY", "-7": "IN_PLAY"},
            retired_fighters=[],
        ),
        native_effect_areas={},
        native_retired_area_managers={},
        native_retained_tracking=True,
        native_retained_records={},
        native_retained_order=[],
        native_owned_state_containers={},
        owned_stat_effects={},
        native_owned_group_effects={},
        native_owned_area_effects={},
        native_owned_spatial_effects={},
        state_wire_payloads={},
        native_delay_queue=dict(
            source="native.eZR.bbS.SU.TC.Tu.v1", next_sequence=1, entries=[]
        ),
    )
    return state, actors


def retained(state, uid, *, target=7, owner=None, family=400):
    row = dict(
        uid=uid,
        target_id=target,
        effect_class=family,
        generic_effect=100,
        owner_uid=owner,
        manager_id=target,
    )
    state["native_retained_records"][uid] = row
    state["native_retained_order"].append(uid)
    state["native_owned_group_effects"][uid] = dict(
        target_id=target,
        state_uid=owner,
        effect_class=family,
        caster_id=7,
        payload="",
        native_delayed=True,
        invocation={},
    )


class OwnershipInvariantTests(unittest.TestCase):
    def setUp(self):
        self.state, self.actors = fixture()
        self.fight = object()

    def inspect(self):
        findings, checked = [], []

        def issue(name, path, reason, status="violation"):
            findings.append((name, path, reason, status))

        def unknown(name, path, reason):
            issue(name, path, reason, "unknown")

        check_ownership(self.fight, self.state, self.actors, issue, unknown, checked)
        return findings, checked

    def violations(self):
        return {row[0] for row in self.inspect()[0] if row[3] == "violation"}

    def test_hp_zero_in_play_extra_activations_and_suppression_remain_valid(self):
        self.actors[7].hp = 0
        self.actors[7].native_turn_suppression_bits = 6
        self.state["order"] = [7, 7, -7]
        self.assertFalse(self.violations())
        self.assertIn("timeline.participation", self.inspect()[1])

    def test_off_play_actor_can_remain_registered_but_cannot_take_turn(self):
        self.state["native_global_pv_collections"]["fighter_status"]["-7"] = "OFF_PLAY"
        self.actors[-7].hp = 0
        self.state["order"] = [7]
        self.assertFalse(self.violations())
        self.state["order"].append(-7)
        self.assertIn("timeline.participation", self.violations())

    def test_property114_and_malformed_suppression_are_distinct(self):
        self.actors[-7].native_fight_properties = frozenset({114})
        self.state["order"] = [7]
        self.assertFalse(self.violations())
        self.state["order"].append(-7)
        self.actors[7].native_turn_suppression_bits = -1
        self.assertIn("timeline.property114", self.violations())
        self.assertIn("timeline.suppression", self.violations())

    def test_native_sy_membership_detects_missing_eligible_activation(self):
        self.state["native_timeline_snapshot_source"] = "owned-tc-sy-v1"
        self.state["native_timeline_member_counters"] = {"7": 0, "-7": 0}
        self.state["order"] = [7, 7, -7]
        self.assertFalse(self.violations())
        self.state["order"] = [7]
        self.assertIn("timeline.membership", self.violations())

    def test_retired_and_registered_is_invalid_without_hp_inference(self):
        self.state["native_global_pv_collections"]["retired_fighters"].append(7)
        self.assertIn("timeline.population", self.violations())

    def test_absent_native_participation_is_unknown_and_never_synthesized(self):
        del self.state["native_global_pv_collections"]
        findings, checked = self.inspect()
        self.assertTrue(
            any(
                row[0] == "timeline.participation" and row[3] == "unknown"
                for row in findings
            )
        )
        self.assertNotIn("timeline.participation", checked)
        self.assertNotIn("native_global_pv_collections", self.state)

    def test_complete_retained_ledger_detects_missing_runner_and_duplicate_order(self):
        retained(self.state, 91)
        self.assertFalse(self.violations())
        self.state["native_retained_order"].append(91)
        self.state["native_owned_group_effects"].pop(91)
        self.assertIn("retained.order", self.violations())
        self.assertIn("retained.completeness", self.violations())

    def test_unattested_population_does_not_claim_completeness(self):
        self.state["native_retained_tracking"] = False
        findings, checked = self.inspect()
        self.assertNotIn("retained.completeness", checked)
        self.assertTrue(
            any(
                row[0] == "retained.completeness" and row[3] == "unknown"
                for row in findings
            )
        )

    def test_removed_area_can_keep_state_manager_without_geometry_refresh(self):
        ledger = StateLedger(300)
        ledger._entries = (
            RunningState(
                92,
                10,
                1,
                7,
                300,
                2,
                "caster",
                False,
                (),
                0,
                True,
                StateTimer(-7, 3, "end"),
            ),
        )
        self.state["native_retired_area_managers"][300] = dict(
            uid=300,
            native_area_contract="faN",
            state_ledger=ledger,
            native_anchor_id=7,
            owner_id=7,
            native_anchor_source="faN.bgZ",
            cell=(999, 0, 0),
            native_cells_xy=((999, 0),),
        )
        self.state["state_wire_payloads"][92] = "00"
        self.state["native_retained_records"][92] = dict(
            uid=92, target_id=300, effect_class=310, generic_effect=100, owner_uid=None
        )
        self.state["native_retained_order"].append(92)
        with patch(
            "wakfu_server.combat_effect_area_geometry.refresh_area_geometry",
            side_effect=AssertionError("refresh"),
        ):
            self.assertFalse(self.violations())
        self.assertEqual(
            self.state["native_retired_area_managers"][300]["cell"], (999, 0, 0)
        )
        self.state["native_retained_records"][92]["target_id"] = 301
        self.assertIn("retained.owner", self.violations())

    def test_state_timer_accepts_native_short_round_but_rejects_invalid_phase(self):
        self.actors[7].state_ledger._entries = (
            RunningState(
                92,
                10,
                1,
                -7,
                7,
                2,
                "caster",
                False,
                (),
                0,
                True,
                StateTimer(-7, -32768, "end"),
            ),
        )
        self.state["state_wire_payloads"][92] = "00"
        self.state["native_retained_records"][92] = dict(
            uid=92, target_id=7, owner_uid=None
        )
        self.state["native_retained_order"].append(92)
        self.assertFalse(self.violations())
        self.actors[7].state_ledger._entries = (
            RunningState(
                92,
                10,
                1,
                -7,
                7,
                2,
                "caster",
                False,
                (),
                0,
                True,
                StateTimer(-7, 0, "active"),
            ),
        )
        self.assertIn("timer.state", self.violations())

    def test_retained_child_may_keep_captured_container_after_carrier_removal(self):
        retained(self.state, 91, owner=80)
        self.state["native_owned_state_containers"][80] = dict(
            uid=80, target_id=7, caster_id=-7
        )
        self.assertFalse(self.violations())
        self.state["native_owned_state_containers"].clear()
        self.assertIn("retained.container", self.violations())

    def test_exact_pending_scope_excludes_unregistered_carrier_only_inside_scope(self):
        from wakfu_server.combat_pending_state import _PENDING

        self.actors[7].state_ledger._entries = (
            RunningState(92, 10, 1, -7, 7, 2, "caster", False, (), 0, True, None),
        )
        self.state["state_wire_payloads"][92] = "00"
        token = _PENDING.set(((self.fight, 92),))
        try:
            self.assertFalse(self.violations())
        finally:
            _PENDING.reset(token)
        self.assertIn("retained.completeness", self.violations())

    def test_exact_detached_constructor_can_keep_a_retained_container(self):
        from wakfu_server.combat_summon_initialization import (
            _construction,
            DetachedSummonConstruction,
        )

        detached = actor(70)
        retained(self.state, 91, owner=80)
        self.state["native_owned_state_containers"][80] = dict(
            uid=80, target_id=7, caster_id=70
        )
        token = _construction.set(
            (DetachedSummonConstruction(self.fight, detached, object()),)
        )
        try:
            self.assertFalse(self.violations())
        finally:
            _construction.reset(token)
        self.assertIn("retained.container", self.violations())

    def test_delayed_owner_is_required_but_dead_clock_needs_no_turn(self):
        retained(self.state, 91)
        self.state["native_delay_queue"]["entries"] = [
            dict(uid=91, sequence=1, clock_id=-7, round=3, phase="end", invocation={})
        ]
        self.actors[-7].hp = 0
        self.state["order"] = [7]
        self.state["native_global_pv_collections"]["fighter_status"]["-7"] = "OFF_PLAY"
        self.assertFalse(self.violations())
        self.state["native_owned_group_effects"].clear()
        self.assertIn("timer.owner", self.violations())

    def test_ap_listener_needs_its_owned_runner_without_notifications(self):
        self.state["native_resource_pa_listeners"] = {
            7: [dict(source=LISTENER_SOURCE, actor_id=7, uid=91, rBe=6, rBf=6, rBg=0)]
        }
        self.state["owned_stat_effects"][91] = dict(target_id=7, state_uid=None)
        self.state["native_retained_records"][91] = dict(
            uid=91, target_id=7, owner_uid=None
        )
        self.state["native_retained_order"].append(91)
        self.assertFalse(self.violations())
        self.state["owned_stat_effects"].clear()
        self.assertIn("subscription.runner", self.violations())

    def test_dummy_owner_summon_preserves_relationships_and_retirement(self):
        summon = actor(70)
        summon.native_master_id = summon.native_controller_id = 7
        summon.native_summon_source = dict(
            native_relation_source=RELATION_SOURCE,
            caster_id=7,
            controller_id=7,
            ref=500,
            level=1,
        )
        self.actors[70] = summon
        self.state["native_summon_registrations"] = {
            70: dict(
                actor_id=70,
                caster_id=7,
                controller_id=7,
                authority=dict(
                    is_summon=True,
                    native_controller_id=7,
                    breed_id=500,
                    native_real_level=1,
                ),
            )
        }
        self.state["native_summon_retirements"] = {
            70: dict(
                source="wakemu.summon_retirement.ko_zero_after_settlement.v1",
                actor_id=70,
            )
        }
        summon.native_obstacle_id = -1
        pv = self.state["native_global_pv_collections"]
        pv["fighters"] = dict(keys=[7, -7, 70], states=[1, 1, 1], size=3)
        pv["fighter_status"]["70"] = "OUT_OF_PLAY"
        self.assertFalse(self.violations())
        summon.native_master_id = -7
        self.assertIn("summon.owner", self.violations())

    def test_inspection_preserves_aliases_and_never_reads_catalog_or_calls_owner_getters(
        self,
    ):
        import wakfu_server.native_catalog as catalog
        from wakfu_server.combat import combat_state_managers, combat_qi_fight

        retained(self.state, 91)
        groups = self.state["native_owned_group_effects"]
        order = self.state["native_retained_order"]
        before = repr(self.state)
        with patch.object(
            catalog, "load", side_effect=AssertionError("catalog")
        ), patch.object(
            combat_state_managers,
            "state_manager",
            side_effect=AssertionError("manager"),
        ), patch.object(
            combat_qi_fight, "current_registry", side_effect=AssertionError("QI")
        ):
            self.assertFalse(self.violations())
        self.assertEqual(repr(self.state), before)
        self.assertIs(self.state["native_owned_group_effects"], groups)
        self.assertIs(self.state["native_retained_order"], order)


if __name__ == "__main__":
    unittest.main()
