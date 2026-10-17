"""Boundary diagnostics report contradictions without repairing combat state."""
import unittest

from wakfu_server.combat_invariants import (
    Boundary,
    CombatInvariantError,
    check_prepared_boundary,
)
from wakfu_server.combat_native_delay_queue import SOURCE as DELAY_SOURCE
from wakfu_server.combat_runtime_messages import RuntimeMessages
from wakfu_server.combat_state import Actor, Fight
from wakfu_server.combat_state_ledger import RunningState


def forbidden(*args, **kwargs):
    raise AssertionError("Invariant diagnostics must not invoke providers or catalogs")


def fight_runtime(*, clock=None):
    player = Actor(7, 0, (0, 0, 0), 60, 6, 3, 100, 1, 3, True)
    npc = Actor(-7, 1, (1, 0, 0), 20, 4, 2, 50, 1)
    fight = Fight(
        902,
        (player, npc),
        {player.position, npc.position},
        {0: {player.position}, 1: {npc.position}},
    )
    fight.phase = "active"
    fight.order = [7, -7]
    fight.turn_index = 0
    runtime = RuntimeMessages(fight, clock=forbidden if clock is None else clock)
    return fight, runtime, player, npc


def install_supported_resource_projection(
    actor,
    *,
    hp=None,
    ap=None,
    mp=None,
    raw_hp=None,
    raw_ap=None,
    raw_mp=None,
    hp_min=1,
    ap_min=0,
    mp_min=0
):
    hp = actor.hp if hp is None else hp
    ap = actor.ap if ap is None else ap
    mp = actor.mp if mp is None else mp
    raw_hp = hp if raw_hp is None else raw_hp
    raw_ap = ap if raw_ap is None else raw_ap
    raw_mp = mp if raw_mp is None else raw_mp
    actor.hp, actor.ap, actor.mp = hp, ap, mp
    actor.effect_stats = {1: hp, 2: ap, 3: mp, 4: 10}
    actor.effect_minima = {1: hp_min, 2: ap_min, 3: mp_min, 4: 0}
    actor.effect_maxima = {1: actor.max_hp, 2: actor.max_ap, 3: actor.max_mp, 4: 10}
    actor.native_hp_raw_current_source = "fresh_initial_tB_HP.on_resource_override"
    actor.effect_hp_raw_current = raw_hp
    actor.native_resource_raw_current_source = (
        "fresh_ffh_AP_MP_mutable_on_within_bounds"
    )
    actor.effect_resource_raw_currents = {2: raw_ap, 3: raw_mp}


class CombatInvariantTests(unittest.TestCase):
    def setUp(self):
        self.fight, self.runtime, self.player, self.npc = fight_runtime()
        self.boundary = Boundary("npc.cast", "prepared")

    def report(self):
        return check_prepared_boundary(self.fight, self.runtime, self.boundary)

    def assert_violation(self, report, invariant, path_fragment=None):
        matches = [row for row in report.violations if row.invariant == invariant]
        self.assertTrue(matches, report.as_dict())
        if path_fragment is not None:
            self.assertTrue(
                any(path_fragment in row.path for row in matches), report.as_dict()
            )

    def test_identity_key_mismatch_raises_operation_specific_error(self):
        del self.fight.actors[7]
        self.fight.actors[700] = self.player
        report = self.report()
        self.assert_violation(report, "actor.identity", "fight.actors[700].id")
        with self.assertRaises(CombatInvariantError) as caught:
            report.raise_if_violated()
        self.assertIn("npc.cast [prepared]", str(caught.exception))
        self.assertIs(caught.exception.report, report)

    def test_scalar_and_raw_clamp_mismatches_are_distinct_violations(self):
        install_supported_resource_projection(self.player)
        self.player.hp -= 1
        report = self.report()
        self.assert_violation(report, "resource.scalar_projection", "effect_stats[1]")

        install_supported_resource_projection(self.player, raw_ap=4)
        report = self.report()
        self.assert_violation(report, "resource.raw_projection", "effect_stats[2]")

    def test_supported_raw_values_clamp_at_expandable_bounds(self):
        install_supported_resource_projection(
            self.player,
            raw_hp=self.player.max_hp + 500,
            raw_ap=self.player.max_ap + 9,
            mp=0,
            raw_mp=-7,
            hp_min=1,
            ap_min=0,
            mp_min=0,
        )
        report = self.report()
        self.assertNotIn(
            "resource.raw_projection",
            {row.invariant for row in report.violations},
            report.as_dict(),
        )
        self.assertNotIn(
            "resource.scalar_projection",
            {row.invariant for row in report.violations},
            report.as_dict(),
        )

    def test_ledger_owner_and_duplicate_state_uid_are_reported(self):
        self.player.state_ledger.actor_id = 999
        shared_uid = 41
        self.player.state_ledger._entries = (
            RunningState(
                shared_uid, 10, 1, 7, 7, 2, "caster", False, (1,), 0, True, None
            ),
        )
        self.npc.state_ledger._entries = (
            RunningState(
                shared_uid, 11, 1, 7, -7, 2, "caster", False, (2,), 0, True, None
            ),
        )
        report = self.report()
        self.assert_violation(report, "state.owner", "state_ledger.actor_id")
        self.assert_violation(report, "state.identity", "entries[0].uid")

    def test_timeline_rejects_missing_actor_but_allows_duplicate_turn_entries(self):
        self.fight.order = [7, 12345]
        report = self.report()
        self.assert_violation(report, "timeline.references", "fight.order")

        self.fight.order = [7, 7, -7]
        self.fight.turn_index = 0
        report = self.report()
        self.assertNotIn(
            "timeline.references",
            {row.invariant for row in report.violations},
            report.as_dict(),
        )

    def test_delay_uid_duplicates_reject_but_dead_clock_and_clock_provider_are_not_used(
        self,
    ):
        self.fight.native_delay_queue = {
            "source": DELAY_SOURCE,
            "next_sequence": 2,
            "entries": [
                dict(
                    sequence=1,
                    uid=91,
                    clock_id=987654,
                    round=3,
                    phase="end",
                    invocation={},
                )
            ],
        }
        report = self.report()
        self.assertNotIn(
            "timer.identity",
            {row.invariant for row in report.violations},
            report.as_dict(),
        )
        self.assertEqual(self.runtime.clock, forbidden)

        self.fight.native_delay_queue = {
            "source": DELAY_SOURCE,
            "next_sequence": 3,
            "entries": [
                dict(
                    sequence=1,
                    uid=91,
                    clock_id=987654,
                    round=3,
                    phase="end",
                    invocation={},
                ),
                dict(
                    sequence=2,
                    uid=91,
                    clock_id=987655,
                    round=4,
                    phase="start",
                    invocation={},
                ),
            ],
        }
        report = self.report()
        self.assert_violation(report, "timer.identity", "native_delay_queue.entries")

    def test_runtime_binding_is_checked_only_for_candidate_boundary(self):
        other_fight, _, _, _ = fight_runtime()
        self.runtime.fight = other_fight
        candidate = self.report()
        self.assert_violation(candidate, "runtime.fight_alias", "runtime.fight")

        source_boundary = Boundary("npc.cast", "pre_adoption", runtime_binding="source")
        source_report = check_prepared_boundary(
            self.fight, self.runtime, source_boundary
        )
        self.assertNotIn(
            "runtime.fight_alias",
            {row.invariant for row in source_report.violations},
            source_report.as_dict(),
        )

    def test_unfinished_resolution_is_a_stability_violation(self):
        self.fight._resolution_depth = 2
        self.assert_violation(self.report(), "boundary.stable", "_resolution_depth")

    def test_analysis_is_read_only_preserves_aliases_and_never_calls_providers(self):
        shared_stats = {1: 60, 2: 6, 3: 3, 4: 10}
        shared_minima = {1: 1, 2: 0, 3: 0, 4: 0}
        shared_maxima = {1: 60, 2: 6, 3: 3, 4: 10}
        for actor in (self.player, self.npc):
            actor.effect_stats = shared_stats
            actor.effect_minima = shared_minima
            actor.effect_maxima = shared_maxima
            actor.native_hp_raw_current_source = (
                "fresh_initial_tB_HP.on_resource_override"
            )
            actor.effect_hp_raw_current = 60
            actor.native_resource_raw_current_source = (
                "fresh_ffh_AP_MP_mutable_on_within_bounds"
            )
            actor.effect_resource_raw_currents = {2: 6, 3: 3}
        self.runtime.stats_serializer = forbidden
        self.runtime.runtime_stats_serializer = forbidden
        self.runtime.turn_end_provider = forbidden
        self.runtime.turn_start_provider = forbidden
        self.fight.native_invariant_catalog = forbidden
        order, actors, pending = (
            self.fight.order,
            self.fight.actors,
            self.runtime.pending,
        )
        before = (
            self.fight._resolution_depth,
            self.player.hp,
            self.player.ap,
            self.runtime.action_id,
            self.runtime.native_action_id,
            self.fight.native_delay_queue["next_sequence"],
        )

        report = self.report()

        after = (
            self.fight._resolution_depth,
            self.player.hp,
            self.player.ap,
            self.runtime.action_id,
            self.runtime.native_action_id,
            self.fight.native_delay_queue["next_sequence"],
        )
        self.assertEqual(after, before)
        self.assertIs(self.fight.order, order)
        self.assertIs(self.fight.actors, actors)
        self.assertIs(self.runtime.pending, pending)
        self.assertIs(self.runtime.fight, self.fight)
        self.assertIs(self.player.effect_stats, self.npc.effect_stats)
        self.assertIs(self.player.effect_minima, self.npc.effect_minima)
        self.assertIs(self.player.effect_maxima, self.npc.effect_maxima)
        self.assertEqual(report.actor_count, 2)

    def test_unavailable_authority_is_explicit_unknown_not_a_pass(self):
        install_supported_resource_projection(self.player)
        install_supported_resource_projection(self.npc)
        # A legacy/containerless graph lacks the fresh retained-population
        # attestation; the newly implemented adapter can certify fresh empties.
        self.fight.native_retained_tracking = False
        report = self.report()
        unknown = {(row.invariant, row.status) for row in report.unknown}
        for name in (
            "resource.hard_bounds",
            "timeline.participation",
            "spatial.authority",
            "retained.completeness",
        ):
            self.assertIn((name, "unknown"), unknown, report.as_dict())
        self.assertNotIn("resource.hard_bounds", report.checked)
        self.assertNotIn("timeline.participation", report.checked)
        self.assertNotIn("spatial.authority", report.checked)
        self.assertNotIn("retained.completeness", report.checked)

    def test_untrusted_fight_runtime_and_boundary_types_reject(self):
        class Spoof:
            pass

        with self.assertRaisesRegex(ValueError, "Trusted Fight"):
            check_prepared_boundary(Spoof(), self.runtime, self.boundary)
        with self.assertRaisesRegex(ValueError, "Trusted Fight"):
            check_prepared_boundary(self.fight, Spoof(), self.boundary)
        with self.assertRaisesRegex(ValueError, "Typed boundary"):
            check_prepared_boundary(self.fight, self.runtime, Spoof())


if __name__ == "__main__":
    unittest.main()
