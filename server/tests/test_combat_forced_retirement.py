"""Native eXl934 dispatch transcript and owned retirement regression tests."""
import unittest
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import patch

from wakfu_server.combat_forced_retirement import (
    NativeForcedRetirementCleanup,
    cleanup_runner_order,
    force_retire_fighter,
    retired_forced_fighter_ids,
    linked_fighter_order,
)
from wakfu_server.combat_qi_fight import current_registry
from wakfu_server.combat_global_pv_collections import (
    global_fighter_registered,
    global_fighter_guards,
)


class ForcedRetirementTests(unittest.TestCase):
    def fixture(self):
        from test_combat_qi_death_lifecycle import NativeQIDeathLifecycleTests
        from wakfu_server.combat_controller_registry import (
            initialize_controller_registry,
            register_native_controller,
        )
        from wakfu_server.combat_retained_runtime import NativeRetainedRuntime
        from wakfu_server.combat_stat_handler import (
            NativeStatHandler,
            StatExecutionContext,
        )

        fight, pc, target, survivor = NativeQIDeathLifecycleTests().fight()
        initialize_controller_registry(fight)
        for actor in fight.actors.values():
            register_native_controller(
                fight, actor.id, team=actor.team, controller_id=actor.id
            )
        packets = []
        retention = NativeRetainedRuntime(
            fight,
            packets,
            plan={
                "native_retained_container": {
                    "present": True,
                    "type": 11,
                    "id": 123,
                    "is_spell": True,
                    "protected": False,
                }
            },
            state_catalog={},
            action_id=1,
            timing=None,
            metadata={},
        )
        context = lambda *args: StatExecutionContext(True, True, None, False, b"")
        retention.stat_handler = NativeStatHandler(
            fight,
            packets,
            {"effects": {}},
            action_id=1,
            allocate_uid=lambda: 900,
            context=context,
            rng=lambda: 0,
        )
        return fight, pc, target, survivor, retention, packets, context

    def retire(self, fight, actor, retention, uid=900):
        return force_retire_fighter(
            fight, actor, uid=uid, cleanup=NativeForcedRetirementCleanup(retention)
        )

    def test_positive_hp_fdt_identity_and_native_transcript(self):
        fight, _, target, _, retention, _, _ = self.fixture()
        hp, identity, slot = target.hp, id(target), target.native_obstacle_id
        with fight.effect_resolution():
            receipt = self.retire(fight, target, retention)
        # Actual installed eXl.c/eGj.dnu transcript, both boolean flag values.
        self.assertEqual(
            receipt["trace"],
            [
                "OFF_PLAY",
                "Qs.k",
                "SU.eT",
                "OUT_OF_PLAY",
                "restore_controller",
                "SU.eu",
                "QI.g",
                "removed_history",
            ],
        )
        self.assertEqual((target.hp, id(fight.actors[target.id])), (hp, identity))
        self.assertTrue(global_fighter_registered(fight, target.id))
        self.assertEqual(
            global_fighter_guards(fight, target.id),
            dict(baF=False, baG=False, baK=True),
        )
        self.assertEqual(target.native_obstacle_id, -1)
        self.assertEqual(retired_forced_fighter_ids(fight), {target.id})
        self.assertIsNone(current_registry(fight).slots[slot])
        self.assertNotIn(target.id, fight.order)
        self.assertFalse(
            any(event["kind"] in ("damage", "death") for event in fight.events)
        )

    def test_fem_permanent_removal_keeps_other_saved_entries_and_shifts_positions(self):
        fight, _, target, _, retention, _, _ = self.fixture()
        target_index = fight.order.index(target.id)
        fight.native_timeline_removed.append(
            dict(actor_id=88, progress=3, position=target_index + 2, modifications=[])
        )
        self.retire(fight, target, retention)
        self.assertNotIn(str(target.id), fight.native_timeline_member_counters)
        self.assertEqual(
            fight.native_timeline_removed,
            [
                dict(
                    actor_id=88, progress=3, position=target_index + 1, modifications=[]
                )
            ],
        )

    def test_multiple_removals_use_live_tc_positions_before_order_reconciliation(self):
        fight, pc, target, survivor, retention, _, _ = self.fixture()
        fight.order[:] = [pc.id, target.id, survivor.id]
        fight.turn_index = 0
        fight.native_timeline_removed.append(
            dict(actor_id=88, progress=3, position=3, modifications=[])
        )
        self.retire(fight, target, retention)
        self.retire(fight, survivor, retention, uid=901)
        self.assertEqual(fight.native_timeline_removed[0]["position"], 1)

    def test_not_present_in_timeline_skips_native_fem_bookkeeping(self):
        fight, _, target, _, retention, _, _ = self.fixture()
        target.native_fight_property_counts[114] = 1
        # fcb.be/bd both return before consulting SU when sfE is present.
        before = deepcopy(fight.native_timeline_member_counters)
        saved = dict(actor_id=target.id, progress=3, position=1, modifications=[])
        fight.native_timeline_removed.append(saved)
        self.retire(fight, target, retention)
        self.assertEqual(fight.native_timeline_member_counters, before)
        self.assertEqual(fight.native_timeline_removed, [saved])

    def test_constructor_controller_and_team_restored(self):
        from wakfu_server.combat_controller_registry import (
            transfer_native_controller,
            current_native_controller,
            current_native_team,
        )

        fight, pc, target, _, retention, _, _ = self.fixture()
        transfer_native_controller(fight, target.id, pc.id)
        self.retire(fight, target, retention)
        self.assertEqual(current_native_controller(fight, target.id), target.id)
        self.assertEqual(current_native_team(fight, target.id), target.team)
        self.assertTrue(global_fighter_registered(fight, target.id))

    def ordinary_authority(self, fight, pc):
        from wakfu_server.combat_ordinary_authority import OrdinaryActorAuthority
        from wakfu_server.combat_spell_level import NativeSpellBook

        return OrdinaryActorAuthority(
            characters={
                pc.id: dict(
                    id=pc.id,
                    breed=15,
                    level=1,
                    native_spellbook=NativeSpellBook({}, True, {}, None),
                )
            },
            monsters={
                identity: dict(id=identity, ref=5525)
                for identity in fight.actors
                if identity != pc.id
            },
            decks={pc.id: []},
            excluded_decks={pc.id: []},
        )

    def test_registered_ordinary_player_constructor_pb_binds_before_retirement(self):
        from wakfu_server.combat_effect_dispatch import EffectInvocation
        from wakfu_server.combat_execution_context import constructed_execution_context

        fight, pc, caster, _, retention, packets, context = self.fixture()
        del pc.native_fight_property_counts
        authority = self.ordinary_authority(fight, pc)
        expected = authority.property_counts(fight, pc)
        self.assertFalse(hasattr(pc, "native_fight_property_counts"))
        handler = self.handler(fight, retention, packets, context)
        handler.actor_authority = authority
        invocation = EffectInvocation(
            101,
            1,
            caster.id,
            pc.id,
            pc.position,
            native_context_hex=constructed_execution_context().payload().hex(),
        )
        self.assertTrue(
            handler(
                dict(
                    effect_class=934, parameters=[], target_masks=[[] for _ in range(7)]
                ),
                {},
                invocation,
            )
        )
        self.assertEqual(pc.native_fight_property_counts, expected)
        self.assertIsNot(pc.native_fight_property_counts, expected)
        self.assertEqual(pc.native_obstacle_id, -1)
        self.assertGreater(pc.hp, 0)

    def test_registered_pb_rejects_live_set_without_counters_before_mutation(self):
        from wakfu_server.fight_checkpoint_store import snapshot

        fight, pc, _, _, retention, _, _ = self.fixture()
        del pc.native_fight_property_counts
        pc.native_fight_properties = frozenset({114})
        authority = self.ordinary_authority(fight, pc)
        before = snapshot(fight)
        with self.assertRaisesRegex(ValueError, "set lacks counter"):
            force_retire_fighter(
                fight,
                pc,
                uid=900,
                cleanup=NativeForcedRetirementCleanup(retention),
                property_counts=authority.property_counts,
            )
        self.assertEqual(snapshot(fight), before)

    def test_missing_registered_pb_authority_rejects_without_empty_default(self):
        fight, pc, _, _, retention, _, _ = self.fixture()
        del pc.native_fight_property_counts
        with self.assertRaisesRegex(ValueError, "registered.*PB counter authority"):
            self.retire(fight, pc, retention)
        self.assertFalse(hasattr(pc, "native_fight_property_counts"))
        self.assertEqual(global_fighter_guards(fight, pc.id)["baF"], True)

    def test_live_pb_multiplicity_survives_retirement_without_constructor_reset(self):
        fight, _, target, _, retention, _, _ = self.fixture()
        target.native_fight_property_counts = {66: 3, 114: -2}
        self.retire(fight, target, retention)
        self.assertEqual(target.native_fight_property_counts, {66: 3, 114: -2})

    def test_constructor_pb_binding_rolls_back_with_detached_transaction(self):
        from wakfu_server.combat_effect_dispatch import run_effect_transaction
        from wakfu_server.fight_checkpoint_store import snapshot

        fight, pc, _, _, _, _, _ = self.fixture()
        del pc.native_fight_property_counts
        before = snapshot(fight)

        def factory(preview):
            retention = self.fixture()[4]
            retention.fight = preview
            retention.stat_handler.fight = preview
            authority = self.ordinary_authority(preview, preview.actors[pc.id])

            def execute(invocation):
                actor = preview.actors[pc.id]
                force_retire_fighter(
                    preview,
                    actor,
                    uid=900,
                    cleanup=NativeForcedRetirementCleanup(retention),
                    property_counts=authority.property_counts,
                )
                self.assertIsInstance(actor.native_fight_property_counts, dict)
                raise ValueError("failure after constructor PB binding")

            return SimpleNamespace(execute=execute)

        with self.assertRaisesRegex(ValueError, "after constructor PB binding"):
            run_effect_transaction(fight, [None], factory)
        self.assertEqual(snapshot(fight), before)
        self.assertIs(fight.actors[pc.id], pc)
        self.assertFalse(hasattr(pc, "native_fight_property_counts"))

    def test_retiring_carried_fighter_releases_reciprocal_pair_before_qi_removal(self):
        from wakfu_server.combat_carrying import carry_registered, carrying_relations

        fight, pc, target, _, retention, _, _ = self.fixture()
        pc.native_los_height = 0
        carry_registered(fight, pc, target, source_uid=123)
        self.assertTrue(carrying_relations(fight, target)["is_carried"])
        hp, direction = target.hp, target.direction
        self.retire(fight, target, retention)
        self.assertEqual((target.hp, target.direction), (hp, direction))
        self.assertEqual(target.position, pc.position)
        self.assertEqual(fight.native_carry_pairs, {})
        self.assertIsNone(pc.native_carried_actor_id)
        self.assertIsNone(target.native_carrier_id)
        current_registry(fight)

    def test_repeated_dnu_appends_history_without_inventing_idempotence(self):
        fight, _, target, _, retention, _, _ = self.fixture()
        self.retire(fight, target, retention)
        self.retire(fight, target, retention, uid=901)
        self.assertEqual(fight.native_forced_retirement_order, [target.id, target.id])
        self.assertEqual(target.native_obstacle_id, -1)
        current_registry(fight)

    def test_missing_controller_authority_rejects_before_mutation(self):
        from wakfu_server.combat_geometry_snapshot import source_snapshot

        fight, _, target, _, retention, _, _ = self.fixture()
        del fight.native_controller_registry
        before = source_snapshot(fight)
        with self.assertRaisesRegex(ValueError, "controller"):
            self.retire(fight, target, retention)
        self.assertEqual(source_snapshot(fight), before)

    def test_forged_actor_receipt_rejected(self):
        fight, _, target, _, retention, _, _ = self.fixture()
        self.retire(fight, target, retention)
        target.native_forced_retirement = dict(target.native_forced_retirement, uid=1)
        with self.assertRaisesRegex(ValueError, "retirement authority"):
            current_registry(fight)

    def test_native_dly_excludes_out_of_play_even_when_hp_positive(self):
        from wakfu_server.combat_global_pv_collections import set_global_fighter_status

        fight, pc, target, survivor, _, _, _ = self.fixture()
        set_global_fighter_status(fight, survivor.id, "OUT_OF_PLAY")
        self.assertEqual(set(linked_fighter_order(fight, target.id)), {pc.id})

    def test_linked_cleanup_order_and_exemptions(self):
        from wakfu_server.combat_retained_effects import RetainedEffect

        entries = [
            RetainedEffect(
                uid,
                target,
                family,
                100 + uid,
                manager_id=manager,
                container_present=True,
                container_type=container,
            )
            for uid, target, family, manager, container in (
                (1, -7, 1, -7, 11),
                (2, -7, 1, -7, 11),
                (3, -7, 310, -7, 11),
                (4, -7, 1, -7, 1),
                (5, -7, 1, 7, 11),
                (6, 7, 1, -7, 11),
            )
        ]
        pairs = {1: (8, -7), 2: (-7, -7), 6: (-7, 7)}
        selected = cleanup_runner_order(
            SimpleNamespace(entries=entries), (7, 8), -7, lambda entry: pairs[entry.uid]
        )
        self.assertEqual(selected, (6, 1))

    def handler(self, fight, retention, packets, context):
        from wakfu_server.combat_forced_retirement_handler import (
            NativeForcedRetirementHandler,
        )

        return NativeForcedRetirementHandler(
            fight,
            packets,
            action_id=1,
            allocate_uid=lambda: 900,
            context=context,
            retention=retention,
            rng=lambda: 0,
        )

    def test_real_handler_packet_and_null_target(self):
        from wakfu_server.combat_effect_dispatch import EffectInvocation
        from wakfu_server.combat_execution_context import constructed_execution_context

        fight, pc, target, _, retention, packets, context = self.fixture()
        handler = self.handler(fight, retention, packets, context)
        effect = dict(
            effect_class=934, parameters=[], target_masks=[[] for _ in range(7)]
        )
        invocation = EffectInvocation(
            101,
            1,
            pc.id,
            None,
            target.position,
            native_context_hex=constructed_execution_context().payload().hex(),
        )
        self.assertFalse(handler(effect, {}, invocation))
        self.assertEqual(packets, [])
        from dataclasses import replace

        self.assertTrue(handler(effect, {}, replace(invocation, target_id=target.id)))
        self.assertEqual(packets[-1][0], 13497)
        self.assertGreater(len(packets[-1][1]), 18)
        self.assertEqual(target.native_obstacle_id, -1)

    def test_real_retained_callback_removes_runner_without_resurrecting_fighter(self):
        from wakfu_server.combat_effect_dispatch import EffectInvocation
        from wakfu_server.combat_execution_context import constructed_execution_context
        from wakfu_server.combat_stat_handler import StatExecutionContext

        fight, pc, target, _, retention, packets, _ = self.fixture()
        effect = dict(
            effect_class=934,
            parameters=[],
            target_masks=[[] for _ in range(7)],
            variant=0,
            minimum_level=1,
            maximum_level=100,
            native_execution_mode=2,
        )
        retention.metadata = {
            "effects": {
                "101": dict(
                    effect,
                    definition_type=2,
                    definition_dispellable=True,
                    owner_on_caster=False,
                )
            }
        }
        handler = self.handler(
            fight,
            retention,
            packets,
            lambda *args: StatExecutionContext(True, True, None, True, b""),
        )
        invocation = EffectInvocation(
            101,
            1,
            pc.id,
            target.id,
            target.position,
            native_context_hex=constructed_execution_context().payload().hex(),
        )
        self.assertTrue(handler(effect, {}, invocation))
        self.assertIn(900, fight.owned_stat_effects)
        self.retire(fight, target, retention, uid=901)
        self.assertNotIn(900, fight.owned_stat_effects)
        self.assertEqual([packet[0] for packet in packets], [13497, 13560])
        self.assertEqual(target.hp, 30)
        self.assertTrue(global_fighter_guards(fight, target.id)["baK"])
        current_registry(fight)

    def test_qs_owner_snapshot_callback_identity_and_off_play_order(self):
        from wakfu_server.combat_effect_area_events import NativeAreaEventRuntime
        from wakfu_server.combat_global_pv_collections import (
            register_global_area,
            global_area_order,
        )

        fight, pc, target, _, retention, _, _ = self.fixture()
        for uid, owner in ((901, target.id), (902, pc.id), (903, target.id)):
            fight.native_effect_areas[uid] = dict(
                uid=uid,
                reference=1474,
                owner_id=owner,
                cell=(0, 0, 0),
                native_cells_xy=((0, 0),),
                native_area_contract="faY",
                child_effect_uids={},
                native_running_effect_manager=False,
                native_fight_affiliation=1,
                native_fight_affiliation_source="faV.j(PV).bcM",
            )
            register_global_area(fight, uid)
        events = NativeAreaEventRuntime(
            fight,
            SimpleNamespace(),
            definitions={
                "1474": {
                    "type": "GLYPH",
                    "native_removal_masks": [],
                    "entry_masks": [],
                    "exit_masks": [],
                }
            },
        )
        retention.area_events = events
        expected = [uid for uid in global_area_order(fight) if uid != 902]
        observed = []
        original = events.removed

        def removed(row):
            observed.append(row["uid"])
            self.assertNotIn(row["uid"], fight.native_effect_areas)
            self.assertTrue(global_fighter_guards(fight, target.id)["baG"])
            self.assertNotEqual(target.native_obstacle_id, -1)
            return original(row)

        with patch.object(events, "removed", side_effect=removed):
            self.retire(fight, target, retention)
        self.assertEqual(observed, expected)
        self.assertEqual(set(fight.native_effect_areas), {902})
        current_registry(fight)

    def test_actual_preview_failure_preserves_source_and_dynamic_checkpoint_state(self):
        from wakfu_server.combat_effect_dispatch import run_effect_transaction
        from wakfu_server.fight_checkpoint_store import snapshot

        fight, _, target, _, _, _, _ = self.fixture()
        before = snapshot(fight)
        identity = id(target)

        def factory(preview):
            # Actual production cleanup provider on the detached transaction.
            template = self.fixture()
            retention = template[4]
            retention.fight = preview
            retention.stat_handler.fight = preview

            def execute(invocation):
                self.retire(preview, preview.actors[target.id], retention)
                self.assertIn("native_forced_retirements", snapshot(preview))
                raise ValueError("injected serializer failure")

            return SimpleNamespace(execute=execute)

        with self.assertRaisesRegex(ValueError, "injected serializer"):
            run_effect_transaction(fight, [None], factory)
        self.assertEqual(snapshot(fight), before)
        self.assertEqual(id(fight.actors[target.id]), identity)
