import copy
import unittest
from types import SimpleNamespace

from wakfu_server.combat_copied_pa import (
    SOURCE,
    install_copied_pa_pool,
    copied_raw_current,
    copied_shift_result,
    shift_copied_current,
    set_copied_current,
    copied_current_stat_result,
    set_copied_maximum,
)
from wakfu_server.combat_character_copy_metadata import native_copy_characteristics
from wakfu_server.combat_character_copy_codec import CopyCharacteristic


class CopiedPATests(unittest.TestCase):
    def fixture(self, hp_maximum=82):
        metadata = native_copy_characteristics()
        rows = []
        for stat in metadata["native_characteristic_order"]:
            definition = metadata["fresh_characteristics"][str(stat)]
            rows.append(
                CopyCharacteristic(
                    stat,
                    125 if stat == 1 else definition["current"],
                    definition["minimum"],
                    hp_maximum if stat == 1 else definition["maximum"],
                    definition["percentage"],
                )
            )
        rows = tuple(rows)
        source = dict(
            producer=SOURCE,
            actor_id=7,
            effect_reference=1002,
            source_actor_id=9,
            profile=2382,
            copied_raw_characteristics=[
                [row.identifier, row.current, row.minimum, row.maximum, row.percentage]
                for row in rows
            ],
        )
        actor = SimpleNamespace(id=7, effect_frozen=frozenset())
        install_copied_pa_pool(actor, rows, metadata=metadata, source_record=source)
        return SimpleNamespace(actors={7: actor}), actor, rows, source

    def test_hidden_hp_raw125_and_effective82_survive_damage_then_collapse_on_heal(
        self,
    ):
        fight, actor, _, _ = self.fixture()
        self.assertEqual(
            (actor.hp, actor.max_hp, copied_raw_current(actor, 1)), (82, 82, 125)
        )
        self.assertEqual(shift_copied_current(fight, actor, 1, 10, subtract=True), 10)
        self.assertEqual((actor.hp, copied_raw_current(actor, 1)), (82, 115))
        self.assertEqual(shift_copied_current(fight, actor, 1, 1), -33)
        self.assertEqual((actor.hp, copied_raw_current(actor, 1)), (82, 82))

    def test_oo_boundary_uses_effective_capacity_and_returns_raw_delta(self):
        _, actor, _, _ = self.fixture()
        self.assertEqual(copied_shift_result(actor, 1, 82, subtract=True), (43, 43, 82))
        self.assertEqual(copied_shift_result(actor, 1, 83, subtract=True), (0, 0, 125))
        _, actor50, _, _ = self.fixture(125)
        self.assertEqual(
            copied_shift_result(actor50, 1, 10, subtract=True), (115, 115, 10)
        )

    def test_frozen_hp_does_not_change_raw_or_report_an_actual_delta(self):
        fight, actor, _, _ = self.fixture()
        actor.effect_frozen = frozenset({1})
        self.assertEqual(shift_copied_current(fight, actor, 1, 200, subtract=True), 0)
        set_copied_current(fight, actor, 1, 0)
        self.assertEqual((actor.hp, copied_raw_current(actor, 1)), (82, 125))

    def test_current_stat_reports_raw_return_and_percent_uses_effective_current(self):
        _, actor, _, _ = self.fixture()
        result = copied_current_stat_result(actor, 1, 10, family="eWQ", percent=False)
        self.assertEqual(
            (result["current"], result["raw_current"], result["actual"]), (82, 82, -43)
        )
        result = copied_current_stat_result(actor, 1, 50, family="eWR", percent=True)
        self.assertEqual((result["raw_current"], result["actual"]), (84, 41))

    def test_actual_wp_forced_setter_keeps_full_pool_and_wire_consistent(self):
        from wakfu_server.combat_force_characteristic import (
            NativeForcedCharacteristicHandler,
        )
        from wakfu_server.combat_effect_dispatch import EffectInvocation
        from wakfu_server.combat_stat_handler import StatExecutionContext
        from wakfu_server.combat_snapshot_wire import snapshot_characteristics

        fight, actor, _, _ = self.fixture()
        fight.id, fight.phase, fight.owned_stat_effects = 8, "active", {}
        fight._event = lambda *args, **kwargs: None
        set_copied_current(fight, actor, 4, 5)
        packets = []
        handler = NativeForcedCharacteristicHandler(
            fight,
            packets,
            {"effects": {"952": {"runner": "eYO", "fixed_stat_id": 4}}},
            action_id=1,
            allocate_uid=lambda: 101,
            context=lambda *args: StatExecutionContext(True, True, None, False, None),
            rng=lambda: 0.0,
        )
        self.assertTrue(
            handler(
                {"effect_class": 952, "parameters": [6.0, 0.0, 1.0, 0.0]},
                [],
                EffectInvocation(413083, 200, actor.id, actor.id, (0, 0, 0)),
            )
        )
        self.assertEqual(
            (
                copied_raw_current(actor, 4),
                actor.effect_stats[4],
                actor.effect_maxima[4],
            ),
            (6, 6, 6),
        )
        before = copy.deepcopy(actor.__dict__)
        wire = snapshot_characteristics(actor)
        self.assertEqual(snapshot_characteristics(actor), wire)
        self.assertEqual(actor.__dict__, before)

    def test_generic_maximum_preserves_fzb_and_frozen_raw_but_clamps_mutable_wp(self):
        fight, actor, _, _ = self.fixture()
        set_copied_maximum(fight, actor, 1, 60)
        self.assertEqual((copied_raw_current(actor, 1), actor.hp), (125, 60))
        set_copied_current(fight, actor, 4, 5)
        set_copied_maximum(fight, actor, 4, 2)
        self.assertEqual((copied_raw_current(actor, 4), actor.effect_stats[4]), (2, 2))
        set_copied_maximum(fight, actor, 4, 6)
        set_copied_current(fight, actor, 4, 5)
        actor.effect_frozen = frozenset({4})
        set_copied_maximum(fight, actor, 4, 2)
        self.assertEqual((copied_raw_current(actor, 4), actor.effect_stats[4]), (5, 2))
        set_copied_current(fight, actor, 4, 0)
        self.assertEqual((copied_raw_current(actor, 4), actor.effect_stats[4]), (5, 2))

    def test_source_record_and_pool_must_correspond_before_installing_any_field(self):
        _, _, rows, source = self.fixture()
        actor = SimpleNamespace(id=7, effect_frozen=frozenset())
        before = copy.deepcopy(actor.__dict__)
        source["copied_raw_characteristics"][0][1] += 1
        with self.assertRaises(ValueError):
            install_copied_pa_pool(
                actor,
                rows,
                metadata=native_copy_characteristics(),
                source_record=source,
            )
        self.assertEqual(actor.__dict__, before)

    def test_repeated_wire_uses_actual_raw_hp_and_does_not_modify_actor(self):
        import struct
        from wakfu_server.combat_snapshot_wire import snapshot_characteristics

        _, actor, _, _ = self.fixture()
        before = copy.deepcopy(actor.__dict__)
        first = snapshot_characteristics(actor)
        self.assertEqual(first, snapshot_characteristics(actor))
        count = struct.unpack_from(">H", first)[0]
        rows = [
            struct.unpack_from(">Biiii", first, 2 + index * 17)
            for index in range(count)
        ]
        self.assertEqual(next(row for row in rows if row[0] == 1), (1, 125, 0, 82, 0))
        self.assertEqual(actor.__dict__, before)
