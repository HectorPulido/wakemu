"""Public state(False) projection preserves final-retired native carriers."""
from contextlib import nullcontext
from dataclasses import asdict
import sys
import unittest
from unittest.mock import patch

from test_combat_range_selection_projection import RangeSelectionProjectionTests
from test_combat_qi_death_lifecycle import NativeQIDeathLifecycleTests
from test_retained_local_query import payload
from wakfu_server import combat_range_native_population as population
from wakfu_server.combat_global_pv_collections import initialize_global_pv_collections
from wakfu_server.combat_qi_fight import (
    prepare_fresh_actor_slots,
    install_fresh_actor_slots,
)
from wakfu_server.combat_ordinary_qi_retirement import (
    complete_ordinary_qi_death,
    retired_ordinary_qi_actor,
)
from wakfu_server.combat_native_death_status import (
    initialize_fresh_bje_death_status,
    apply_native_fighter_state_transition,
)
from wakfu_server.combat_ordinary_authority import OrdinaryActorAuthority
from wakfu_server.combat_state import Fight
from wakfu_server.combat_state_ledger import RunningState
from wakfu_server.combat_retained_effects import RetainedEffect


class StateRangePrefilterTests(unittest.TestCase):
    def fixture(self):
        fixture = RangeSelectionProjectionTests()
        # Delay this fixture's ready transition until its actual QI placement
        # has been installed; never fabricate an active-to-placement rollback.
        with patch.object(Fight, "ready", return_value=None):
            fixture.setUp()
        fight = fixture.fight
        dead = fight.actors[-7]
        # Use the actual ordinary death and QI retirement producers, not an HP
        # or OUT flag standing in for the irreversible retirement lifecycle.
        initialize_global_pv_collections(fight, tuple(fight.actors))
        fight.native_qi_snapshot = dict(x=0, y=0, width=2, height=2, cell_masks=[0] * 4)
        for actor in fight.actors.values():
            actor.native_fight_property_counts = {}
        install_fresh_actor_slots(
            fight,
            prepare_fresh_actor_slots(
                fight, physical_radii={identity: 0 for identity in fight.actors}
            ),
        )
        fight.ready(3)
        native_lifecycle, *_ = NativeQIDeathLifecycleTests().fight()
        fight.native_rail_movement_authority = (
            native_lifecycle.native_rail_movement_authority
        )
        dead.native_world_properties = frozenset()
        initialize_fresh_bje_death_status(dead)
        fight.apply_effect_damage(7, dead.id, dead.hp)
        self.assertTrue(complete_ordinary_qi_death(fight, dead))
        apply_native_fighter_state_transition(dead, 2)
        self.assertTrue(retired_ordinary_qi_actor(fight, dead.id))
        # Actual Qf registration and ledger, including two different casters.
        for identity, entries in (
            (7, ((9001, 1, 7),)),
            (-7, ((9002, 2, 7), (9003, 1, 8))),
        ):
            actor = fight.actors[identity]
            actor.state_ledger._entries = tuple(
                RunningState(
                    uid,
                    3442,
                    level,
                    caster,
                    identity,
                    -1,
                    "target",
                    False,
                    (),
                    0,
                    True,
                    None,
                )
                for uid, level, caster in entries
            )
            for uid, _, _ in entries:
                fight.state_wire_payloads[uid] = payload(uid, identity, 103)
                fight.native_retained_records[uid] = asdict(
                    RetainedEffect(uid, identity, 310, 103, manager_id=identity)
                )
                fight.native_retained_order.append(uid)

        return fixture

    def test_ledger_negative_prefilter_preserves_public_results_and_fallbacks(self):
        fixture = self.fixture()
        fight = fixture.fight
        dead = fight.actors[-7]
        from wakfu_server.combat_condition_selection_scope import (
            condition_actor_selection_scope,
            current_condition_actor_cache,
        )

        def run(enabled, reference=3442):
            snapshots, creations = [], []
            creation_code = OrdinaryActorAuthority._creation_facts.__code__
            previous = sys.getprofile()

            def observe(frame, event, arg):
                if event != "call":
                    return
                actor = frame.f_locals.get("actor")
                if actor is None:
                    return
                if frame.f_code.co_name == "_snapshot":
                    snapshots.append(actor.id)
                if frame.f_code is creation_code:
                    creations.append(actor.id)

            with (
                nullcontext()
                if enabled
                else patch.object(
                    population, "native_state_no_match", return_value=False
                )
            ):
                sys.setprofile(observe)
                try:
                    context = fixture.context()
                    values = [
                        context.state_range_query(
                            99, "caster", reference, level, flag, owner
                        )
                        for level, flag, owner in (
                            (-1, False, ""),
                            (-1, True, ""),
                            (2, False, "caster"),
                            (1, False, "caster"),
                        )
                    ]
                    values.append(
                        context.own_team_state_range_query(
                            99, "caster", reference, -1, False, ""
                        )
                    )
                finally:
                    sys.setprofile(previous)
            return values, snapshots, creations

        baseline, old_snapshots, _ = run(False)
        actual, snapshots, _ = run(True)
        self.assertEqual(actual, baseline)
        self.assertEqual(actual, [2, 1, 1, 1, 2])
        self.assertIn(8, old_snapshots)
        self.assertNotIn(8, snapshots)
        self.assertIn(
            7, snapshots, "The invocation source still has ordinary authority"
        )
        absent, _, old_creations = run(False, 999999)
        absent_fast, _, creations = run(True, 999999)
        self.assertEqual(absent_fast, absent)
        self.assertEqual(absent, [0] * 5)
        self.assertIn(dead.id, old_creations)
        self.assertNotIn(dead.id, creations)
        print(
            "state_negative_prefilter_counts",
            dict(
                unmatched_live_snapshots_before=old_snapshots.count(8),
                unmatched_live_snapshots_after=snapshots.count(8),
                unmatched_retired_facts_before=old_creations.count(dead.id),
                unmatched_retired_facts_after=creations.count(dead.id),
            ),
        )
        # A ledger match is not proof of a registered Qf carrier: the original
        # reader remains responsible for orphan/malformed registration cases.
        actor = fight.actors[8]
        original_entries = actor.state_ledger.entries
        actor.state_ledger._entries = (
            RunningState(9010, 3442, 1, 7, 8, -1, "target", False, (), 0, True, None),
        )
        try:
            self.assertFalse(
                population.native_state_no_match(
                    fight, fixture.native, actor, 3442, -1, None
                )
            )

            def outcome(enabled):
                try:
                    return ("result", run(enabled)[0])
                except ValueError as error:
                    return ("error", str(error))

            self.assertEqual(outcome(True), outcome(False))
        finally:
            actor.state_ledger._entries = original_entries
        # Custom authority hooks retain the legacy full read/callback order.
        reads = []
        original_properties = fixture.native.properties

        def custom_properties(current, candidate):
            reads.append(candidate.id)
            return original_properties(current, candidate)

        with patch.object(fixture.native, "properties", custom_properties):
            self.assertFalse(
                population.native_state_no_match(
                    fight, fixture.native, actor, 3442, -1, None
                )
            )
            old = run(False)[0]
            old_reads = list(reads)
            reads.clear()
            new = run(True)[0]
            self.assertEqual(new, old)
            self.assertEqual(reads, old_reads)
        # Native method identities do not certify a replaced downstream life
        # hook. Its observable call sequence must remain exactly legacy.
        from wakfu_server import combat_ordinary_death

        lifecycle_reads = []
        original_guards = combat_ordinary_death.owned_fighter_guards

        def custom_guards(current, candidate):
            lifecycle_reads.append(candidate.id)
            return original_guards(current, candidate)

        with patch.object(combat_ordinary_death, "owned_fighter_guards", custom_guards):
            self.assertFalse(
                population.native_state_no_match(
                    fight, fixture.native, actor, 3442, -1, None
                )
            )
            self.assertEqual(lifecycle_reads, [])
            old = run(False)[0]
            old_reads = list(lifecycle_reads)
            lifecycle_reads.clear()
            new = run(True)[0]
            self.assertEqual(new, old)
            self.assertEqual(lifecycle_reads, old_reads)
            self.assertIn(actor.id, lifecycle_reads)
        # A custom selected constructor source is likewise observable even
        # though the containing authority uses the original native methods.
        source_reads = []

        class ObservedSource(dict):
            def get(self, key, default=None):
                source_reads.append(key)
                return super().get(key, default)

        source = fixture.ordinary.monsters[actor.id]
        fixture.ordinary.monsters[actor.id] = ObservedSource(source)
        try:
            self.assertFalse(
                population.native_state_no_match(
                    fight, fixture.native, actor, 3442, -1, None
                )
            )
            self.assertEqual(
                source_reads, [], "Eligibility must not invoke the custom source getter"
            )
            old = run(False)[0]
            old_reads = list(source_reads)
            self.assertTrue(old_reads)
            source_reads.clear()
            new = run(True)[0]
            self.assertEqual(new, old)
            self.assertEqual(source_reads, old_reads)
        finally:
            fixture.ordinary.monsters[actor.id] = source
        from wakfu_server.combat_state_ledger import StateLedger

        class CustomLedger(StateLedger):
            pass

        ledger = actor.state_ledger
        actor.state_ledger = CustomLedger(actor.id)
        try:
            self.assertFalse(
                population.native_state_no_match(
                    fight, fixture.native, actor, 3442, -1, None
                )
            )
        finally:
            actor.state_ledger = ledger
        # Existing memo-based range selection remains complete and anchored.
        with condition_actor_selection_scope(), patch.object(
            population,
            "native_state_no_match",
            side_effect=AssertionError("memo path changed"),
        ):
            context = fixture.context()
            first = context.state_range_query(99, "caster", 3442, -1, False, "")
            memo = current_condition_actor_cache(fixture.adapter, fight)
            anchor = memo[("authority", 7)]
            retired_anchor = memo[("authority", dead.id)]
            second = fixture.context().state_range_query(
                99, "caster", 3442, -1, False, ""
            )
            self.assertEqual((first, second), (baseline[0], baseline[0]))
            self.assertIs(memo[("authority", 7)], anchor)
            self.assertIs(memo[("authority", dead.id)], retired_anchor)
