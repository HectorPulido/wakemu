import struct
import unittest
from types import SimpleNamespace
from wakfu_server.combat_snapshot_wire import snapshot_characteristics
from wakfu_server.combat_actor import actual_actor_stats, actual_monster_actor_stats


class SnapshotWireTests(unittest.TestCase):
    def actor(self, controlled=True):
        values = {1: 80, 2: 8, 3: 2, 4: 3, 20: 125, 35: 10, 92: 15, 97: 50, 100: 5}
        maxima = {k: 2147483647 for k in values}
        maxima.update({1: 120, 2: 9, 3: 3, 4: 6, 20: 50000, 92: 30})
        return SimpleNamespace(
            id=1 if controlled else -1,
            controlled=controlled,
            native_controlled_by_ai=False,
            team=0 if controlled else 1,
            position=(1, 2, 0),
            hp=80,
            max_hp=120,
            ap=8,
            max_ap=9,
            mp=2,
            max_mp=3,
            initiative=10,
            native_obstacle_id=101,
            effect_stats=values,
            effect_minima={k: 0 for k in values},
            effect_base_minima={k: 0 for k in values},
            effect_maxima=maxima,
            effect_percentages={k: 20 if k == 1 else 0 for k in values},
            effect_base_maxima=dict(maxima),
        )

    def decode(self, blob, offset=0):
        count = struct.unpack_from(">H", blob, offset)[0]
        return {
            row[0]: row[1:]
            for row in (
                struct.unpack_from(">Biiii", blob, offset + 2 + n * 17)
                for n in range(count)
            )
        }

    def test_native_raw_max_and_percentage_are_preserved(self):
        actor = self.actor()
        actor.effect_base_maxima[1] = 100
        rows = self.decode(snapshot_characteristics(actor))
        self.assertEqual(rows[1], (80, 0, 100, 20))
        self.assertEqual(rows[20][0], 125)
        self.assertEqual(
            (rows[2][0], rows[4][0], rows[92][0], rows[97][0]), (8, 3, 15, 50)
        )

    def test_expandable_raw_current_is_serialized_without_changing_effective_actor(
        self,
    ):
        from wakfu_server.combat_resource_pa_notifications import RAW_SOURCE

        actor = self.actor()
        actor.effect_base_maxima[1] = 100
        actor.ap = actor.effect_stats[2] = 9
        actor.effect_resource_raw_currents = {2: 12, 3: 2}
        actor.native_resource_raw_current_source = RAW_SOURCE
        rows = self.decode(snapshot_characteristics(actor))
        self.assertEqual(rows[2], (12, 0, 9, 0))
        self.assertEqual(actor.ap, 9)
        actor.effect_resource_raw_currents[2] = 8
        with self.assertRaisesRegex(ValueError, "raw/effective current disagreement"):
            snapshot_characteristics(actor)

    def test_both_player_sections_and_npc_section_use_actual_snapshot(self):
        char = dict(
            id=1,
            account_id=2,
            breed=8,
            level=6,
            map_id=1,
            x=1,
            y=2,
            z=0,
            hp=80,
            max_hp=120,
        )
        actor = self.actor()
        actor.effect_base_maxima[1] = 100
        data = actual_actor_stats(char, actor, 77, wp_current=3, wp_maximum=6)
        first = self.decode(data, 39)
        length = 2 + 17 * len(first)
        second = self.decode(data, 39 + length + 4)
        self.assertEqual(first, second)
        self.assertEqual(first[97][0], 50)
        npc = self.actor(False)
        npc.effect_base_maxima[1] = 100
        monster = dict(id=-1, ref=1, level=8, map_id=1)
        data = actual_monster_actor_stats(monster, npc, 77, wp_current=3, wp_maximum=6)
        self.assertEqual(self.decode(data, 31), first)

    def test_stale_percentage_metadata_rejects_and_plain_maximum_buff_works(self):
        actor = self.actor()
        actor.effect_base_maxima[1] = 100
        actor.max_ap = 10
        actor.effect_maxima[2] = 10
        actor.effect_base_maxima[2] = 10
        self.assertEqual(self.decode(snapshot_characteristics(actor))[2][2], 10)
        actor.max_hp = 130
        actor.effect_maxima[1] = 130
        with self.assertRaises(ValueError):
            snapshot_characteristics(actor)
        actor.effect_percentages = None
        with self.assertRaises(ValueError):
            snapshot_characteristics(actor)

    def test_raw_negative_minimum_survives_refresh(self):
        actor = self.actor()
        actor.effect_base_maxima[1] = 100
        actor.effect_base_minima[3] = -1
        self.assertEqual(self.decode(snapshot_characteristics(actor))[3][1], -1)

    def test_class_resource_updates_reach_both_native_player_sections(self):
        # These are distinct native characteristics, not aliases of WP or a
        # state level. Serializing a refresh must not cache the initial zero.
        from wakfu_server.combat_actor_snapshot import native_actor_catalog

        definitions = native_actor_catalog()["characteristics"]
        for resource, value in ((67, 35), (50, 35), (111, 35), (117, 25), (123, 4)):
            with self.subTest(resource=resource):
                actor = self.actor()
                actor.effect_base_maxima[1] = 100
                row = definitions[str(resource)]
                actor.effect_stats[resource] = 0
                actor.effect_minima[resource] = row["minimum"]
                actor.effect_base_minima[resource] = row["minimum"]
                actor.effect_maxima[resource] = row["maximum"]
                actor.effect_base_maxima[resource] = row["maximum"]
                actor.effect_percentages[resource] = 0
                character = dict(
                    id=1,
                    account_id=2,
                    breed=8,
                    level=20,
                    map_id=1,
                    x=1,
                    y=2,
                    z=0,
                    hp=80,
                    max_hp=120,
                )
                for current in (0, value):
                    actor.effect_stats[resource] = current
                    data = actual_actor_stats(
                        character, actor, 77, wp_current=3, wp_maximum=6
                    )
                    first = self.decode(data, 39)
                    second = self.decode(data, 39 + 2 + 17 * len(first) + 4)
                    self.assertEqual(first[resource][0], current)
                    self.assertEqual(second[resource], first[resource])
                    self.assertEqual(first[4][0], 3)
