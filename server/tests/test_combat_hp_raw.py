import struct
import unittest
from types import SimpleNamespace

from wakfu_server.combat_hp_raw import (
    SOURCE,
    hp_raw_current,
    hp_shift_result,
    set_hp_raw_maximum,
    shift_hp_raw_current,
)


class HPRawTests(unittest.TestCase):
    def test_actual_fresh_snapshot_records_setter_operand_before_maximum_changes(self):
        from test_combat_actor_snapshot import ActorSnapshotTests
        from wakfu_server.combat_actor_snapshot import build_player_snapshot
        from wakfu_server.combat_snapshot_wire import snapshot_characteristics

        character, actor = ActorSnapshotTests().player()
        snapshot = build_player_snapshot(
            character, actor, wp_current=6, wp_maximum=6, running_effects=()
        )
        self.assertEqual(
            snapshot.native_hp_on_operand,
            dict(producer=SOURCE, actor_id=actor.id, raw_current=41),
        )
        snapshot.install(actor)
        set_hp_raw_maximum(actor, 20)
        self.assertEqual((actor.hp, actor.max_hp, hp_raw_current(actor)), (20, 20, 41))
        self.assertEqual(shift_hp_raw_current(actor, 5, subtract=True), 5)
        self.assertEqual((actor.hp, hp_raw_current(actor)), (20, 36))
        payload = snapshot_characteristics(actor)
        count = struct.unpack_from(">H", payload)[0]
        rows = [
            struct.unpack_from(">Biiii", payload, 2 + index * 17)
            for index in range(count)
        ]
        self.assertEqual(next(row for row in rows if row[0] == 1), (1, 36, 0, 20, 0))
        self.assertEqual(hp_shift_result(actor, 21, subtract=True), (0, 0, 36))

    def test_bounded_effective_hp_is_not_a_raw_source(self):
        actor = SimpleNamespace(
            id=7,
            hp=20,
            effect_stats={1: 20},
            effect_minima={1: 0},
            effect_maxima={1: 20},
        )
        with self.assertRaises(ValueError):
            hp_raw_current(actor)

    def test_copied_source_takes_precedence_over_initial_profile_operand(self):
        from test_combat_copied_pa import CopiedPATests

        _, actor, _, _ = CopiedPATests().fixture()
        actor.native_hp_raw_current_source = SOURCE
        actor.effect_hp_raw_current = 50
        self.assertEqual(hp_raw_current(actor), 125)
        set_hp_raw_maximum(actor, 60)
        self.assertEqual((actor.hp, hp_raw_current(actor)), (60, 125))
