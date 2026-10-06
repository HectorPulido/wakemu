import unittest
from types import SimpleNamespace
from wakfu_server.breed_resources import base_resources, live_wp
from wakfu_server.equipment_stats import combat_resources, effective_character
from wakfu_server.wire import proto_field


class BreedResourceTests(unittest.TestCase):
    def bare(self, breed):
        return dict(id=1, breed=breed, level=6, hp=80, builds={}, inventory_items=[])

    def test_native_breed_exceptions_and_no_universal_fallback(self):
        for breed in range(1, 20):
            if breed == 17:
                continue
            c = self.bare(breed)
            r = combat_resources(c)
            self.assertEqual(
                (r["ap"], r["mp"], r["wp"]),
                (6, 4 if breed == 8 else 3, 12 if breed == 5 else 6),
            )
        with self.assertRaises(ValueError):
            base_resources(self.bare(999))

    def test_explicit_override_and_owned_equipment_counted_once(self):
        c = self.bare(5)
        c["inventory_items"] = [
            dict(uid=1000, character_id=1, reference=2021, quantity=1)
        ]
        c["builds"] = {
            0: dict(
                sheet=proto_field(24, (1 << 64) - 1).hex(),
                equipment=proto_field(
                    10, proto_field(8, 1000) + proto_field(16, 4)
                ).hex(),
            )
        }
        self.assertEqual(combat_resources(c)["ap"], 7)
        self.assertEqual(combat_resources(effective_character(c))["ap"], 7)
        self.assertEqual(combat_resources(c, wp=2)["wp"], 2)
        self.assertEqual(combat_resources(c, base_mp=9)["mp"], 9)

    def test_live_snapshot_never_resets_spent_or_modified_wp(self):
        a = SimpleNamespace(effect_stats={4: 7}, effect_maxima={4: 14})
        f = SimpleNamespace(actors={1: a})
        self.assertEqual(live_wp(f, 1), (7, 14))
        a.effect_stats[4] = 2
        self.assertEqual(live_wp(f, 1), (2, 14))
        a.effect_stats = None
        with self.assertRaises(ValueError):
            live_wp(f, 1)

    def test_native_player_snapshot_installs_breed_resources_and_gear_once(self):
        from wakfu_server.combat_state import Actor
        from wakfu_server.combat_actor_snapshot import build_player_snapshot

        for breed in (5, 8):
            char = effective_character(self.bare(breed))
            resources = combat_resources(char)
            actor = Actor(
                1,
                0,
                (0, 0, 0),
                char["hp"],
                resources["ap"],
                resources["mp"],
                resources["initiative"],
                6,
                owner_id=1,
                controlled=True,
                max_hp=char["max_hp"],
            )
            snapshot = build_player_snapshot(
                char,
                actor,
                wp_current=resources["wp"],
                wp_maximum=resources["wp"],
                running_effects=(),
            )
            snapshot.install(actor)
            self.assertEqual(
                (actor.effect_stats[2], actor.effect_stats[3], actor.effect_stats[4]),
                (6, 3 if breed == 5 else 4, 12 if breed == 5 else 6),
            )
            self.assertEqual(actor.effect_base_maxima[4], resources["wp"])
