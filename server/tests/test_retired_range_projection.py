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


class RetiredRangeProjectionTests(unittest.TestCase):
    def test_native_retirement_state_queries_and_custom_fallback(self):
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

        def run(enabled):
            calls, snapshots = [], []
            code = OrdinaryActorAuthority.__call__.__code__

            def observe(frame, event, arg):
                if event != "call":
                    return
                actor = frame.f_locals.get("actor")
                if frame.f_code is code:
                    calls.append(actor.id)
                elif frame.f_code.co_name == "_snapshot" and actor is not None:
                    snapshots.append(actor.id)

            with (
                nullcontext()
                if enabled
                else patch.object(population, "retired_range_facts", return_value=None)
            ):
                sys.setprofile(observe)
                try:
                    context = fixture.context()
                    values = [
                        context.state_range_query(
                            99, "caster", 3442, level, flag, owner
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
                            99, "caster", 3442, -1, False, ""
                        )
                    )
                finally:
                    sys.setprofile(None)
            return values, calls, snapshots

        self.assertIsNotNone(
            population.retired_range_facts(fight, fixture.native, dead)
        )
        baseline, old_calls, old_snapshots = run(False)
        actual, calls, snapshots = run(True)
        self.assertEqual(actual, baseline)
        self.assertEqual(actual, [2, 1, 1, 1, 2])
        self.assertIn(dead.id, old_calls)
        self.assertIn(dead.id, old_snapshots)
        self.assertNotIn(dead.id, calls)
        self.assertNotIn(dead.id, snapshots)
        self.assertIn(7, calls)
        self.assertIn(8, calls)
        print(
            "retired_snapshot_counts",
            dict(
                baseline=old_snapshots.count(dead.id),
                candidate=snapshots.count(dead.id),
            ),
        )
        # Existing selection memo owns complete authorities and property anchors.
        # The new narrow path must not replace them with partial range facts.
        from wakfu_server.combat_condition_selection_scope import (
            condition_actor_selection_scope,
            current_condition_actor_cache,
        )

        with condition_actor_selection_scope(), patch.object(
            population,
            "retired_range_facts",
            side_effect=AssertionError("memo path bypassed"),
        ):
            context = fixture.context()
            first = context.state_range_query(99, "caster", 3442, -1, False, "")
            memo = current_condition_actor_cache(fixture.adapter, fight)
            source_anchor = memo[("authority", 7)]
            retired_anchor = memo[("authority", dead.id)]
            properties_anchor = memo[("properties", dead.id)]
            second = fixture.context().state_range_query(
                99, "caster", 3442, -1, False, ""
            )
            self.assertEqual((first, second), (baseline[0], baseline[0]))
            self.assertIs(memo[("authority", 7)], source_anchor)
            self.assertIs(memo[("authority", dead.id)], retired_anchor)
            self.assertIs(memo[("properties", dead.id)], properties_anchor)
        # Property 42 still excludes retired carriers; no cached mutable facts.
        dead.native_fight_properties = frozenset({42})
        self.assertEqual(run(True)[0], run(False)[0])
        self.assertEqual(run(True)[0][0], 1)
        dead.native_fight_properties = frozenset()
        # Exact native proof must not suppress user-supplied authority hooks.
        with patch.object(
            fixture.native, "properties", wraps=fixture.native.properties
        ):
            self.assertIsNone(
                population.retired_range_facts(fight, fixture.native, dead)
            )
            values, custom_calls, _ = run(True)
            self.assertEqual(values, baseline)
            self.assertIn(dead.id, custom_calls)
        original = fixture.ordinary.npc_spellbook
        fixture.ordinary.npc_spellbook = lambda *args: ()
        try:
            self.assertIsNone(
                population.retired_range_facts(fight, fixture.native, dead)
            )
        finally:
            fixture.ordinary.npc_spellbook = original
