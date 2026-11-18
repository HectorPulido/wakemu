"""Native eWD207 parameter and actual registered relation regressions."""
import unittest
from types import SimpleNamespace
from unittest.mock import patch
import test_combat_controller_registry as registry_tests
from wakfu_server.combat_controller_transfer import (
    native_controller_selection,
    prepare_controller_transfer,
    apply_controller_transfer,
    remove_controller_transfer,
)
from wakfu_server.combat_controller_registry import (
    current_native_controller,
    current_native_team,
    transfer_native_controller,
)


class NativeControllerTransfer207Tests(unittest.TestCase):
    def setUp(self):
        self.fight = registry_tests.NativeControllerRegistryTests().fight()
        self.caster = self.fight.actors[7]
        self.target = self.fight.actors[-7]
        self.caster.native_controlled_by_ai = True
        self.target.native_controlled_by_ai = False
        self.authority = lambda fight, actor: SimpleNamespace(
            targeting={"is_eGj": True}
        )

    def prepare(self, parameters=(), published=False):
        return prepare_controller_transfer(
            self.fight,
            self.caster,
            self.target,
            self.authority,
            parameters=parameters,
            level=1,
            definitions={},
            effects={},
            published=published,
        )

    def test_native_oracle_first_parameter_exact_one_and_default(self):
        self.assertFalse(native_controller_selection([], 1))
        for value in [-2147483648, -1, 0, 1, 2, 2147483647]:
            self.assertEqual(native_controller_selection([value, 0], 1), value == 1)
            self.assertEqual(
                native_controller_selection([value, 0, 1, 0], 1), value == 1
            )

    def test_actual_transfer_retains_ownership_and_restores_original_not_previous(self):
        transfer_native_controller(self.fight, -7, 7)
        self.target.native_controller_id = -7
        receipt = apply_controller_transfer(self.fight, 7, -7, self.prepare())
        self.assertEqual(current_native_controller(self.fight, -7), 7)
        self.assertTrue(self.target.native_controlled_by_ai)
        self.assertEqual(self.target.native_controller_id, -7)
        remove_controller_transfer(self.fight, receipt)
        self.assertEqual(
            (
                current_native_controller(self.fight, -7),
                current_native_team(self.fight, -7),
            ),
            (-7, 1),
        )
        self.assertFalse(self.target.native_controlled_by_ai)

    def test_unknown_ai_fails_before_relation_changes(self):
        del self.target.native_controlled_by_ai
        with self.assertRaisesRegex(ValueError, "fqL"):
            self.prepare()
        self.assertEqual(current_native_controller(self.fight, -7), -7)

    def test_published_book_requires_real_source_and_does_not_change_ownership(self):
        with patch(
            prepare_controller_transfer.__module__ + ".target_controller_spellbook",
            side_effect=ValueError("missing source"),
        ):
            with self.assertRaisesRegex(ValueError, "missing source"):
                self.prepare(published=True)
        self.assertEqual(current_native_controller(self.fight, -7), -7)

    def test_publication_flag_cannot_be_inferred_from_retention(self):
        with self.assertRaisesRegex(ValueError, "publication flag"):
            self.prepare(published=None)

    def test_current_caster_controller_selected_when_available(self):
        transfer_native_controller(self.fight, 7, -7)
        receipt = apply_controller_transfer(self.fight, 7, -7, self.prepare([1, 0]))
        self.assertEqual(receipt.applied_controller, -7)
        self.assertEqual(receipt.applied_team, 1)


class ControllerTransferRunner207Tests(unittest.TestCase):
    def fixture(self, retained=False):
        from wakfu_server.combat_controller_transfer import (
            NativeControllerTransferHandler,
        )
        from wakfu_server.combat_effect_dispatch import EffectInvocation
        from wakfu_server.combat_stat_handler import StatExecutionContext
        from wakfu_server.combat_character_copy_book import CopyBookAction

        fight = registry_tests.NativeControllerRegistryTests().fight()
        fight.id = 8
        fight.owned_stat_effects = {}
        fight.actors[7].native_controlled_by_ai = True
        fight.actors[-7].native_controlled_by_ai = False
        packets = []
        handler = NativeControllerTransferHandler(
            fight,
            packets,
            allocate_uid=lambda: 91,
            action_id=5,
            context=lambda e, i: StatExecutionContext(True, True, None, retained, b""),
            authority=lambda f, a: SimpleNamespace(targeting={"is_eGj": True}),
            rng=lambda: 0.5,
            definitions={},
            effects={},
        )
        effect = dict(effect_class=207, parameters=[], target_masks=[None] * 7)
        invocation = EffectInvocation(
            22,
            1,
            7,
            -7,
            (2, 0, 0),
            native_context_hex="0800100020ffffffffffffffffff0128013000380040004800",
        )
        book = (CopyBookAction(1001, 549, 1, False, True, False),)
        return handler, fight, packets, effect, invocation, book

    def test_runner_native_wire_phases_and_book_do_not_grant_ownership(self):
        handler, fight, packets, effect, invocation, book = self.fixture()
        phases = []
        handler.event_lifecycle = SimpleNamespace(
            phase=lambda e, i, **k: phases.append(
                (k["channel"], current_native_controller(fight, -7))
            )
        )
        with patch(
            prepare_controller_transfer.__module__ + ".target_controller_spellbook",
            return_value=(book, "owned.actual.fixture"),
        ):
            self.assertTrue(handler(effect, {}, invocation))
        self.assertEqual(phases, [(1, -7), (2, -7), (3, 7), (4, 7)])
        self.assertEqual(packets[0][0], 12613)
        self.assertEqual(fight.native_controller_action_books[-7]["actions"], book)
        self.assertFalse(hasattr(fight.actors[-7], "native_summon_action_book"))
        self.assertEqual(handler.runners, {})

    def test_actual_point_selector_registered_glyph_noops_after_phase_two(self):
        import json
        from pathlib import Path
        from dataclasses import replace
        from wakfu_server.combat_global_pv_collections import register_global_area
        from wakfu_server.combat_state_managers import registered_area_pv

        records = json.loads(
            (
                Path(__file__).resolve().parents[2]
                / ".runtime/quest-archetypes/bworkball/native-source.json"
            ).read_text()
        )
        effect = records["effects"]["105633"]
        glyph = records["areas"]["635"]
        self.assertEqual(effect["effect_class"], 207)
        self.assertEqual(effect["native_target_selector"], {"class": "fcE", "mask": 1})
        self.assertTrue(glyph["raw_bcR"])

        handler, fight, packets, _unused_effect, invocation, _book = self.fixture()
        uid = -901
        row = dict(
            uid=uid,
            reference=635,
            owner_id=7,
            cell=(3, 0, 0),
            direction=0,
            native_cells_xy=((3, 0),),
            native_area_contract="faY",
            native_fight_affiliation=-1,
            native_running_effect_manager=False,
            state_ledger=None,
        )
        fight.native_effect_areas = {uid: row}
        register_global_area(fight, uid)
        phases = []
        handler.event_lifecycle = SimpleNamespace(
            phase=lambda e, i, **kw: phases.append(kw["channel"])
        )
        with patch(
            "wakfu_server.combat_effect_area.native_effect_areas",
            return_value={"635": glyph},
        ):
            selected_area = registered_area_pv(fight, uid)
            self.assertTrue(selected_area.native_is_area)
            self.assertEqual(selected_area.native_entry_masks, frozenset())
            self.assertIsNone(selected_area.state_ledger)
            self.assertTrue(handler(effect, {}, replace(invocation, target_id=uid)))
            self.assertEqual(phases, [1, 2, 3, 4])
            self.assertEqual(packets, [])
            self.assertEqual(current_native_controller(fight, -7), -7)
            self.assertFalse(hasattr(fight, "native_controller_action_books"))

            unknown = replace(invocation, target_id=-902)
            with self.assertRaisesRegex(ValueError, "Missing actual eWD fighters"):
                handler(effect, {}, unknown)

            forged = dict(row, uid=-902, native_area_contract="faW")
            fight.native_effect_areas[-902] = forged
            register_global_area(fight, -902)
            with self.assertRaisesRegex(
                ValueError, "Incomplete registered area PV authority"
            ):
                handler(effect, {}, replace(invocation, target_id=-902))

    def test_ordered_native_307_207_325_uses_real_ally_and_null_qf_glyph(self):
        import json
        from pathlib import Path
        from random import Random
        from dataclasses import replace
        from types import SimpleNamespace
        from unittest.mock import patch
        from wakfu_server import combat_ai_control, monsters
        from wakfu_server.combat_effect_dispatch import EffectInvocation
        from wakfu_server.combat_global_pv_collections import register_global_area
        from wakfu_server.combat_state_managers import registered_area_pv
        from wakfu_server.combat_stat_handler import StatExecutionContext
        from test_combat_summon_effect_phases import FreshSummonPhaseTests

        records = json.loads(
            (
                Path(__file__).resolve().parents[2]
                / ".runtime/quest-archetypes/bworkball/native-source.json"
            ).read_text()
        )
        effects = records["effects"]
        glyph = records["areas"]["635"]
        fresh = FreshSummonPhaseTests()
        (
            fight,
            summon,
            builder,
            _old_effect,
            _old_values,
            old_invocation,
            _observations,
            _allocated,
        ) = fresh.make_handler()
        for candidate_actor in fight.actors.values():
            candidate_actor.physical_radius = 0
        from wakfu_server.combat_global_pv_collections import (
            initialize_global_pv_collections,
        )

        fight.actors[7].native_controlled_by_ai = True
        fight.actors[-7].native_controlled_by_ai = False
        initialize_global_pv_collections(
            fight, tuple(sorted(fight.actors)), controller_registration=True
        )
        actual307 = effects["105627"]
        actual_values = {"parameters": [2791, 20, 0, 3, 0, 0, 1]}
        actual_invocation = EffectInvocation(
            105627,
            1,
            7,
            None,
            old_invocation.cell,
            native_context_hex=old_invocation.native_context_hex,
        )
        dependencies = fresh._native_dependencies()
        with patch(
            "wakfu_server.combat_summon_handler.native_actor_catalog",
            return_value={"npc_profiles": {"2791": {}}},
        ), patch("wakfu_server.monsters.reference", return_value={"min_level": 1}):
            prepared = summon.prepare(actual307, actual_values, actual_invocation)
            self.assertTrue(summon(actual307, actual_values, prepared))
        ally = builder.created[0][0]
        self.assertEqual(builder.created[0][1].reference, 2791)
        self.assertIs(fight.actors[ally.id], ally)

        area_uid = -901
        area_row = dict(
            uid=area_uid,
            reference=635,
            owner_id=7,
            cell=tuple(ally.position),
            direction=0,
            native_cells_xy=(tuple(ally.position[:2]),),
            native_area_contract="faY",
            native_fight_affiliation=-1,
            native_running_effect_manager=False,
            state_ledger=None,
        )
        fight.native_effect_areas = {area_uid: area_row}
        register_global_area(fight, area_uid)
        packets = []
        from wakfu_server.combat_controller_transfer import (
            NativeControllerTransferHandler,
        )
        from wakfu_server.combat_character_copy_book import CopyBookAction

        book = (CopyBookAction(1001, 549, 1, False, True, False),)
        transfer = NativeControllerTransferHandler(
            fight,
            packets,
            allocate_uid=lambda: 990,
            action_id=9,
            context=lambda e, i: StatExecutionContext(True, True, None, False, b""),
            authority=lambda f, a: SimpleNamespace(targeting={"is_eGj": True}),
            rng=Random(1).random,
            definitions={},
            effects=effects,
        )
        actual207 = effects["105633"]
        execution_context = "0800100020ffffffffffffffffff0128013000380040004800"
        invocation207 = EffectInvocation(
            105633,
            1,
            7,
            ally.id,
            ally.position,
            native_context_hex=execution_context,
        )
        with patch(
            "wakfu_server.combat_effect_area.native_effect_areas",
            return_value={"635": glyph},
        ), patch(
            transfer.__module__ + ".target_controller_spellbook",
            return_value=(book, "actual.2791.book"),
        ):
            from wakfu_server.combat_effect_resolver import (
                EffectResolutionContext,
                NativeEffectResolver,
            )

            selected_area = registered_area_pv(fight, area_uid)
            selected_area.team = 0
            selected_area.physical_radius = 0
            resolver = NativeEffectResolver(
                actors=lambda e, i: (fight.actors[7], ally, selected_area),
                native_context=lambda e, i: {
                    7: {"bEe": True, "is_Qq": False, "is_eGj": True},
                    ally.id: {
                        "bEe": True,
                        "is_Qq": False,
                        "is_eGj": True,
                        "UNTARGETTABLE_BY_OTHER": False,
                        "is_eHH": False,
                    },
                    area_uid: {
                        "bEe": True,
                        "is_Qq": True,
                        "is_eGj": False,
                        "bcR": True,
                        "UNTARGETTABLE_BY_OTHER": False,
                        "is_eHH": False,
                    },
                },
                context=lambda e, i: EffectResolutionContext(
                    "ALL",
                    "immediate",
                    "actors",
                    True,
                ),
            )
            live_candidates = resolver(actual207, invocation207)
            self.assertEqual(
                [candidate.target_id for candidate in live_candidates],
                [ally.id, area_uid],
            )
            self.assertTrue(transfer(actual207, {}, invocation207))
            before_area = (
                (len(packets), current_native_controller(fight, area_uid))
                if area_uid in fight.actors
                else len(packets)
            )
            self.assertTrue(
                transfer(actual207, {}, replace(invocation207, target_id=area_uid))
            )
            self.assertEqual(len(packets), before_area)
            self.assertTrue(registered_area_pv(fight, area_uid).native_is_area)
            self.assertEqual(current_native_controller(fight, ally.id), 7)
            self.assertNotIn(
                area_uid,
                getattr(fight, "native_controller_registry", {}).get("actors", {}),
            )

        fight.owned_stat_effects = {}
        control = combat_ai_control.NativeAIControlHandler(
            fight,
            packets,
            allocate_uid=lambda: 991,
            context=lambda e, i: StatExecutionContext(
                True, True, None, True, b"timing"
            ),
            authority=lambda f, a: SimpleNamespace(
                targeting={"is_eGj": True},
                native_ai_control_baseline=True,
            ),
            rng=Random(2).random,
            delivery=lambda e, i, **kw: combat_ai_control.ai_control_delivery(
                fight.id, 9, e, i, **kw
            ),
        )
        actual325 = effects["105634"]
        invoke325 = EffectInvocation(
            105634,
            1,
            7,
            ally.id,
            ally.position,
            native_context_hex=execution_context,
        )
        with patch(
            "wakfu_server.combat_effect_area.native_effect_areas",
            return_value={"635": glyph},
        ):
            self.assertTrue(control(actual325, {}, invoke325))
            self.assertIs(ally.native_controlled_by_ai, False)
            self.assertIs(
                fight.owned_stat_effects[991]["native_ai_control_baseline"], True
            )
            before_control_area = len(packets)
            self.assertTrue(
                control(actual325, {}, replace(invoke325, target_id=area_uid))
            )
            self.assertEqual(len(packets), before_control_area + 1)
            self.assertNotIn(992, fight.owned_stat_effects)
            with self.assertRaisesRegex(
                ValueError, "Missing actual native AI-control recipient"
            ):
                control(actual325, {}, replace(invoke325, target_id=-902))

    def test_player_ai_without_real_class_executor_rejects_before_any_mutation(self):
        import pickle

        handler, fight, packets, effect, invocation, book = self.fixture()
        target = fight.actors[-7]
        target.controlled = True
        target.owner_id = 101
        handler.authority = lambda f, a: SimpleNamespace(
            targeting={"is_eGj": True}, is_player=a is target
        )
        allocations = []
        phases = []
        handler.allocate_uid = lambda: allocations.append(91) or 91
        handler.event_lifecycle = SimpleNamespace(
            phase=lambda *a, **k: phases.append(k)
        )
        before = pickle.dumps(fight)
        with self.assertRaisesRegex(ValueError, "player AI capability producer"):
            handler(effect, {}, invocation)
        self.assertEqual(pickle.dumps(fight), before)
        self.assertEqual(packets, [])
        self.assertEqual(allocations, [])
        self.assertEqual(phases, [])
        self.assertEqual(handler.runners, {})

    def test_retained_removal_restores_original_controller_ai_and_retires_ui_book(self):
        from wakfu_server.combat_controller_transfer import remove_controller_runner

        handler, fight, packets, effect, invocation, book = self.fixture(retained=True)
        with patch(
            prepare_controller_transfer.__module__ + ".target_controller_spellbook",
            return_value=(book, "owned.actual.fixture"),
        ):
            self.assertTrue(handler(effect, {}, invocation))
        self.assertTrue(fight.actors[-7].native_controlled_by_ai)
        remove_controller_runner(
            SimpleNamespace(fight=fight, action_id=6, packets=packets), 91
        )
        self.assertEqual(current_native_controller(fight, -7), -7)
        self.assertFalse(fight.actors[-7].native_controlled_by_ai)
        self.assertNotIn(-7, fight.native_controller_action_books)
        self.assertNotIn(91, fight.owned_stat_effects)
        self.assertEqual(packets[-1][0], 13560)


class ControllerTransferInput207Tests(unittest.TestCase):
    fixture = ControllerTransferRunner207Tests.fixture

    def test_actual_cast_uid_resolver_rejects_old_owner_and_accepts_current_controller(
        self,
    ):
        from wakfu_server.combat_cast import resolve_owned_spell_action

        handler, fight, packets, effect, invocation, book = self.fixture()
        caster, target = fight.actors[7], fight.actors[-7]
        caster.controlled = True
        caster.owner_id = 202
        caster.native_controlled_by_ai = False
        target.controlled = True
        target.owner_id = 101
        fight.phase = "active"
        fight.current = target
        with patch(
            prepare_controller_transfer.__module__ + ".target_controller_spellbook",
            return_value=(book, "owned.actual.fixture"),
        ):
            self.assertTrue(handler(effect, {}, invocation))
        request = {"actor_id": target.id, "spell_uid": 1001}
        with self.assertRaisesRegex(ValueError, "owned active actor"):
            resolve_owned_spell_action(request, {"id": target.id}, fight, 101, b"")
        resolved = resolve_owned_spell_action(
            request, {"id": caster.id}, fight, 202, b""
        )
        self.assertEqual(resolved, (target, 549, 1))
        self.assertEqual(target.owner_id, 101)
        with self.assertRaisesRegex(ValueError, "absent"):
            resolve_owned_spell_action(
                {"actor_id": target.id, "spell_uid": 9999},
                {"id": caster.id},
                fight,
                202,
                b"",
            )


if __name__ == "__main__":
    unittest.main()
