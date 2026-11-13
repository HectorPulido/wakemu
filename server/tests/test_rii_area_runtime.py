"""Server-observed area impacts are committed only as one complete cast."""
import unittest
import struct
from contextlib import nullcontext
from types import SimpleNamespace
from unittest.mock import patch

from wakfu_server.achievements import rii_area_runtime as runtime


class Fight:
    def __init__(self, hits=0):
        self.id = 4
        self.walkable = {(x, 0, 0) for x in range(20)}
        self.actors = {1: SimpleNamespace(position=(0, 0, 0), team=0, direction=0)}
        self.actors.update(
            {
                -i: SimpleNamespace(
                    id=-i, position=(i, 0, 0), team=1, direction=0, hp=100
                )
                for i in range(1, 5)
            }
        )
        self.rii_area_lesson_contract = {
            "owner": 1,
            "targets": [-1, -2, -3, -4],
            "initialized": True,
            "hits": hits,
            "actions": list(range(100, 100 + hits)),
        }
        self._next_uid = 1

    def allocate_effect_uid(self):
        uid = self._next_uid
        self._next_uid += 1
        return uid

    def effect_resolution(self):
        return nullcontext()

    def apply_damage(self, owner, target, amount):
        self.actors[target].hp -= amount
        return amount


class AreaRuntimeTests(unittest.TestCase):
    def record(self, fight, targets, *, effect=367103, damage=25):
        self.assertTrue(runtime.begin(fight, source_id=1, action_id=7, spell_id=7969))
        for target in targets:
            self.assertTrue(
                runtime.defer(
                    fight,
                    action_id=7,
                    source_id=1,
                    target_id=target,
                    effect_reference=effect,
                    damage=damage,
                    uid=1000 - target,
                    element=1,
                    cell=None,
                    base_uid=None,
                )
            )

    def test_partial_cast_does_not_damage_or_advance(self):
        fight, packets = Fight(), []
        self.record(fight, [-1, -2, -3])
        self.assertFalse(runtime.finish(fight, packets))
        self.assertEqual([fight.actors[-i].hp for i in range(1, 5)], [100] * 4)
        self.assertEqual(fight.rii_area_lesson_contract["hits"], 0)
        self.assertEqual(packets, [])

    def test_final_qualified_cast_damages_each_sack_once(self):
        fight, packets = Fight(hits=3), []
        self.record(fight, [-1, -2, -3, -4])
        with patch("wakfu_server.combat_effects.direct_damage", return_value=b"damage"):
            self.assertTrue(runtime.finish(fight, packets))
        self.assertEqual([fight.actors[-i].hp for i in range(1, 5)], [75] * 4)
        self.assertEqual(fight.rii_area_lesson_contract["hits"], 4)
        self.assertEqual(packets, [(12613, b"damage")] * 4)

    def test_qualified_cast_relocates_all_sacks_and_emits_movement(self):
        fight, packets = Fight(), []
        self.record(fight, [-1, -2, -3, -4])
        cells = tuple((x, 0, 0) for x in range(10, 14))
        with patch(
            "wakfu_server.combat_effects.direct_damage", return_value=b"damage"
        ), patch(
            "wakfu_server.rii_lesson_spell_catalog.catalog",
            return_value={"effects": {}},
        ), patch.object(
            runtime, "formation", return_value=((9, 0, 0), cells)
        ):
            self.assertTrue(runtime.finish(fight, packets))
        self.assertEqual([fight.actors[-i].position for i in range(1, 5)], list(cells))
        self.assertEqual([opcode for opcode, _ in packets], [12613] * 8)
        self.assertTrue(
            all(
                struct.unpack_from(">i", payload, 13)[0] == 302
                for _, payload in packets[4:]
            )
        )

    def test_duplicate_or_zero_damage_never_counts(self):
        for targets, damage in (([-1, -1, -2, -3], 25), ([-1, -2, -3, -4], 0)):
            fight = Fight()
            self.record(fight, targets, damage=damage)
            self.assertFalse(runtime.finish(fight, []))
            self.assertEqual(fight.rii_area_lesson_contract["hits"], 0)

    def test_sacks_are_protected_from_other_sources_without_a_pending_cast(self):
        fight = Fight()
        self.assertTrue(
            runtime.defer(
                fight,
                action_id=9,
                source_id=2,
                target_id=-1,
                effect_reference=123,
                damage=100,
                uid=1,
                element=1,
                cell=None,
                base_uid=None,
            )
        )
        self.assertFalse(
            runtime.defer(
                fight,
                action_id=9,
                source_id=2,
                target_id=-8,
                effect_reference=123,
                damage=100,
                uid=1,
                element=1,
                cell=None,
                base_uid=None,
            )
        )
        self.assertEqual(fight.actors[-1].hp, 100)


if __name__ == "__main__":
    unittest.main()
