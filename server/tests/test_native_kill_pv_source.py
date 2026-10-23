"""Original eXc accepts a real source PV, while target PA authority stays strict."""
from copy import deepcopy
from dataclasses import replace
from types import SimpleNamespace
import struct
import unittest


class NativeKillPvSourceTests(unittest.TestCase):
    def fixture(self, *, retained=True):
        from test_combat_kill import NativeKillTests
        from wakfu_server.combat_effect_area import native_effect_areas
        from wakfu_server.combat_encounter_glyph_bootstrap import (
            SOURCE,
            point_glyph_row,
            validate_point_prototype,
        )

        (
            fight,
            target,
            packets,
            phases,
            handler,
            effect,
            invocation,
        ) = NativeKillTests().fixture(1, minimum=5)
        definition = native_effect_areas()["910"]
        validate_point_prototype(definition, level=0)
        source = dict(
            uid=901,
            reference=910,
            cell=(2, 3, 0),
            level=0,
            policy="wakemu.unit.kill-source.v1",
            source=SOURCE,
            authority="explicit-unit-native-constructor",
        )
        row = point_glyph_row(source, definition)
        fight.walkable.add(source["cell"])
        fight.native_effect_areas = {901: row}
        original_context = handler.context
        handler.context = lambda *args: replace(
            original_context(*args), retained=retained
        )
        return (
            fight,
            target,
            packets,
            phases,
            handler,
            effect,
            replace(invocation, caster_id=901),
        )

    def apply(self, handler, effect, invocation):
        return handler(effect, {}, handler.prepare(effect, {}, invocation))

    def test_real_neutral_source_changes_only_native_target_and_staging_rollback_preserves_live_fight(
        self,
    ):
        from wakfu_server.combat_geometry_snapshot import source_snapshot
        from wakfu_server.combat_spell_commit import commit_spell_transaction
        from wakfu_server.combat_spell_transaction import SpellTransaction

        fight, target, packets, phases, handler, effect, invocation = self.fixture()
        original = source_snapshot(fight)
        preview = deepcopy(fight)
        handler.fight = preview
        self.assertTrue(self.apply(handler, effect, invocation))
        self.assertEqual(preview.actors[-7].hp, 5)
        self.assertEqual(preview.actors[-7].effect_stats[1], 5)
        self.assertEqual(preview.actors[-7].effect_base_maxima[14], 0)
        self.assertEqual(preview.actors[-7].native_fight_property_counts[65], 1)
        self.assertEqual(preview.owned_stat_effects[101]["caster_id"], 901)
        self.assertEqual(preview.actors[-8].hp, fight.actors[-8].hp)
        row = preview.native_effect_areas[901]
        self.assertNotIn("state_ledger", row)
        self.assertFalse(row["native_running_effect_manager"])
        self.assertNotIn(901, preview.actors)
        runtime = SimpleNamespace(
            fight=fight,
            action_id=4,
            awaiting_ack=None,
            pending=(),
            _flush=lambda: (13420, struct.pack(">i", fight.id)),
        )
        transaction = SpellTransaction(
            preview, {}, 0, (True,), tuple(packets), tuple(preview.events), original, 5
        )

        def reject_serializer(*args):
            raise RuntimeError("post-eXc serialization failure")

        with self.assertRaisesRegex(RuntimeError, "post-eXc"):
            commit_spell_transaction(
                runtime, transaction, stats_serializer=reject_serializer
            )
        self.assertIs(runtime.fight, fight)
        self.assertEqual(source_snapshot(fight), original)
        self.assertEqual(target.hp, 80)

    def test_retired_selected_source_remains_valid_only_during_its_actual_pointer_scope(
        self,
    ):
        from wakfu_server.combat_effect_area import remove_owned_hour_area
        from wakfu_server.combat_state_managers import (
            registered_source_pv,
            selected_area_pv_scope,
        )

        fight, target, packets, phases, handler, effect, invocation = self.fixture(
            retained=False
        )
        with selected_area_pv_scope(fight, (901,)):
            remove_owned_hour_area(fight, 901)
            self.assertNotIn(901, fight.native_effect_areas)
            self.assertIsNotNone(registered_source_pv(fight, 901))
            self.assertTrue(self.apply(handler, effect, invocation))
            self.assertEqual(target.hp, 5)
        self.assertIsNone(registered_source_pv(fight, 901))
        count = len(packets)
        with self.assertRaises(ValueError):
            self.apply(handler, effect, invocation)
        self.assertEqual((target.hp, len(packets)), (5, count))

    def test_foreign_unknown_malformed_sources_and_invalid_hp_targets_cannot_mutate(
        self,
    ):
        from wakfu_server.combat_effect_area import remove_owned_hour_area

        fight, target, packets, phases, handler, effect, invocation = self.fixture()
        _foreign = self.fixture()
        row = fight.native_effect_areas[901]
        remove_owned_hour_area(fight, 901)
        for identity in (901, 99999, None, True, 0, 1 << 63):
            with self.subTest(source=identity), self.assertRaises(ValueError):
                self.apply(handler, effect, replace(invocation, caster_id=identity))
        self.assertEqual((target.hp, len(packets)), (80, 0))
        fight.native_effect_areas[901] = row
        row["native_running_effect_manager"] = True
        with self.assertRaises(ValueError):
            self.apply(handler, effect, invocation)
        row["native_running_effect_manager"] = False
        for identity in (None, 99999):
            with self.subTest(target=identity), self.assertRaises(ValueError):
                self.apply(handler, effect, replace(invocation, target_id=identity))
        target.effect_stats.pop(1)
        with self.assertRaisesRegex(ValueError, "characteristic snapshot"):
            self.apply(handler, effect, invocation)
        self.assertEqual((target.hp, len(packets)), (80, 0))
