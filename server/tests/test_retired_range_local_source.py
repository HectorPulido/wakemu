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


class RetiredRangeLocalSourceTests(unittest.TestCase):
    def test_registered_summon_population_uses_local_retired_source(self):
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
        from test_recipient_projection import EventRecipientProjectionTests
        from wakfu_server.combat_controller_registry import (
            initialize_controller_registry,
            register_native_controller,
        )
        from wakfu_server.combat_carrying import carry_population_scope
        from wakfu_server.combat_summon import RegisteredSummonAuthority
        from types import SimpleNamespace

        initialize_controller_registry(fight)
        for identity, actor in fight.actors.items():
            register_native_controller(
                fight, identity, team=actor.team, controller_id=identity
            )
        registration = EventRecipientProjectionTests()
        registration.fight = fight
        summon = registration._register_summon()
        self.assertIn(summon.id, fight.native_summon_registrations)

        def old_projection():
            with patch.object(
                population, "_local_retired_population", return_value=False
            ):
                return population.retired_range_facts(fight, fixture.native, dead)

        def observed(callback):
            calls = []
            code = RegisteredSummonAuthority._ordinary_view.__code__
            prior = sys.getprofile()

            def observe(frame, event, arg):
                if event == "call" and frame.f_code is code:
                    calls.append(True)

            sys.setprofile(observe)
            try:
                result = callback()
            finally:
                sys.setprofile(prior)
            return result, len(calls)

        old, old_calls = observed(old_projection)
        new, new_calls = observed(
            lambda: population.retired_range_facts(fight, fixture.native, dead)
        )
        self.assertIsNotNone(new)
        self.assertEqual((vars(new[0]), new[1]), (vars(old[0]), old[1]))
        self.assertEqual((old_calls, new_calls), (1, 0))
        print(
            "retired_range_ordinary_view_calls",
            dict(baseline=old_calls, candidate=new_calls),
        )
        # The selected source remains freshly validated for carry/controller.
        dead.native_carrier_id = 7
        for callback in (
            old_projection,
            lambda: population.retired_range_facts(fight, fixture.native, dead),
        ):
            with self.assertRaises(ValueError):
                callback()
        dead.native_carrier_id = None
        controller = fight.native_controller_registry["fighters"][str(dead.id)]
        original_controller = controller["current_controller"]
        controller["current_controller"] = "UNKNOWN"
        try:
            for callback in (
                old_projection,
                lambda: population.retired_range_facts(fight, fixture.native, dead),
            ):
                with self.assertRaises(ValueError):
                    callback()
        finally:
            controller["current_controller"] = original_controller
        self.assertIsNone(population.retired_range_facts(fight, fixture.native, summon))

        class CustomRecords(dict):
            pass

        records = fight.native_summon_registrations
        fight.native_summon_registrations = CustomRecords(records)
        try:
            custom, custom_calls = observed(
                lambda: population.retired_range_facts(fight, fixture.native, dead)
            )
            self.assertEqual((vars(custom[0]), custom[1]), (vars(old[0]), old[1]))
            self.assertEqual(custom_calls, 1)
        finally:
            fight.native_summon_registrations = records
        with patch.object(
            fixture.native, "_ordinary_view", wraps=fixture.native._ordinary_view
        ):
            self.assertIsNone(
                population.retired_range_facts(fight, fixture.native, dead)
            )
