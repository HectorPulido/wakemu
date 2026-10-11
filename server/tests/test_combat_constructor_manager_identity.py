"""Detached constructor Qf identities stay local and retain ordinary guards."""
from dataclasses import replace
from types import SimpleNamespace
import unittest

import test_combat_disabled_spell_level as disabled_fixture
import test_combat_retained_cell_groups as retained_fixture
from wakfu_server.combat_runtime_adapter import NativeActorAuthority
from wakfu_server.combat_summon_initialization import detached_summon_scope
from wakfu_server.combat_state_ledger import StateLedger
from wakfu_server.combat_retained_effects import (
    NativeRetainedEffectView,
    RetainedEffect,
)


def construction_actor(identity):
    actor = SimpleNamespace(id=identity, team=-1, state_ledger=StateLedger(identity))
    authority = NativeActorAuthority(
        targeting={"dpu_id": identity, "dpr_id": identity, "bcN": -1},
        is_player=False,
        deck_spell_ids=frozenset(),
        excluded_deck_spell_ids=frozenset(),
        is_carried=False,
        breed_id=1345,
        summon_count=0,
        summon_counts_by_breed={},
        occupant_blocks=True,
        native_controller_id=identity,
    )
    return actor, authority


class ConstructorManagerIdentityTests(unittest.TestCase):
    def test_actual_detached_cell_manager_accepts_only_scoped_owned_identity(self):
        fight, _ = retained_fixture.RetainedCellGroupTests().fixture()
        actor, authority = construction_actor(7)
        fight.actors.clear()
        record = RetainedEffect(**fight.native_retained_records[901])
        with self.assertRaisesRegex(ValueError, "cell group manager"):
            NativeRetainedEffectView(fight, [record], population_verified_complete=True)
        with detached_summon_scope(fight, actor, authority):
            NativeRetainedEffectView(fight, [record], population_verified_complete=True)
            self.assertEqual(fight.actors, {})
            with self.assertRaisesRegex(ValueError, "cell group manager"):
                NativeRetainedEffectView(
                    fight,
                    [replace(record, manager_id=999)],
                    population_verified_complete=True,
                )
            foreign, _ = retained_fixture.RetainedCellGroupTests().fixture()
            foreign.actors.clear()
            with self.assertRaisesRegex(ValueError, "cell group manager"):
                NativeRetainedEffectView(
                    foreign, [record], population_verified_complete=True
                )
        with self.assertRaisesRegex(ValueError, "cell group manager"):
            NativeRetainedEffectView(fight, [record], population_verified_complete=True)

    def test_disabled_level_placement_constructor_self_delivers_without_actor_registration(
        self,
    ):
        (
            _,
            fight,
            packets,
            _,
            handler,
            effect,
            invocation,
        ) = disabled_fixture.DisabledSpellLevelTests().fixture(retained=False)
        actor, authority = construction_actor(1)
        fight.phase = "placement"
        fight.actors.clear()
        with detached_summon_scope(fight, actor, authority):
            self.assertTrue(
                handler(effect, {}, handler.prepare(effect, {}, invocation))
            )
            self.assertEqual(fight.actors, {})
            self.assertEqual(len(packets), 1)
            foreign, _ = construction_actor(2)
            fight.actors[2] = foreign
            for delivery in (
                replace(invocation, target_id=2),
                replace(invocation, caster_id=2),
            ):
                with self.assertRaisesRegex(ValueError, "requires SELF"):
                    handler._context(effect, delivery)
        with self.assertRaisesRegex(ValueError, "fight/caster"):
            handler._context(effect, invocation)
        self.assertFalse(handler.prepared)
        self.assertFalse(handler.runners)

    def test_registered_placement_actor_cannot_use_constructor_exemption(self):
        (
            _,
            fight,
            packets,
            _,
            handler,
            effect,
            invocation,
        ) = disabled_fixture.DisabledSpellLevelTests().fixture()
        fight.phase = "placement"
        with self.assertRaisesRegex(ValueError, "fight/caster"):
            handler._context(effect, invocation)
        self.assertEqual(packets, [])

    def test_detached_fighter_is_not_misclassified_as_unregistered_area(self):
        from unittest.mock import patch
        from wakfu_server.combat_state_handler import NativeStateHandler
        from wakfu_server.combat_effect_dispatch import EffectInvocation

        fight = SimpleNamespace(actors={})
        actor, authority = construction_actor(91)
        handler = object.__new__(NativeStateHandler)
        handler.fight = fight
        invocation = EffectInvocation(1, 1, 91, 91, (0, 0, 0))
        with detached_summon_scope(fight, actor, authority), patch(
            "wakfu_server.combat_area_authority.area_guards",
            side_effect=AssertionError("A real detached fighter is not an area"),
        ):
            self.assertFalse(handler._area_target_blocked({}, invocation))
            self.assertEqual(fight.actors, {})
        with patch(
            "wakfu_server.combat_area_authority.area_guards",
            side_effect=ValueError("Missing registered native area PV"),
        ):
            with self.assertRaisesRegex(
                ValueError, "Missing registered native area PV"
            ):
                handler._area_target_blocked({}, invocation)
