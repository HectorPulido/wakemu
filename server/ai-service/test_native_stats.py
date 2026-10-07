from types import SimpleNamespace
import unittest
from unittest.mock import patch
import struct

from native_stats import NativeStats


class NativeStatsTests(unittest.TestCase):
    def test_registered_positive_summon_reuses_native_body_and_preserves_identity(self):
        source = dict(ref=3791, level=20, direction=3, caster_id=7, controller_id=7)
        actor = SimpleNamespace(
            id=901,
            controlled=False,
            effective_level=20,
            team=1,
            position=(2, 3, 0),
            native_obstacle_id=1,
            native_summon_source=source,
            effect_stats={4: 3},
            effect_maxima={4: 6},
        )
        registration = dict(
            actor_id=901,
            caster_id=7,
            controller_id=7,
            authority=dict(
                is_summon=True,
                is_player=False,
                breed_id=3791,
                native_real_level=20,
                native_instance_id=1134,
            ),
        )
        serializer = NativeStats(
            characters={}, monsters={}, fight_id=41, registrations={901: registration}
        )
        from wakfu_server.combat_actor import monster_actor_stats

        descriptor = dict(source, id=-901, team=1, x=2, y=3, z=0, map_id=1134)
        expected = monster_actor_stats(
            descriptor,
            41,
            direction=3,
            obstacle_id=1,
            characteristics_payload=b"\x00\x00",
        )
        with patch(
            "wakfu_server.combat_snapshot_wire.snapshot_characteristics",
            return_value=b"\x00\x00",
        ):
            actual = serializer(actor)
        self.assertEqual(actual[:-20], expected[:-20])
        self.assertEqual(actual[-12:], expected[-12:])
        self.assertEqual(struct.unpack_from(">q", actual, len(actual) - 20)[0], 901)
        self.assertEqual(actor.id, 901)
        self.assertEqual(actor.native_summon_source, source)

    def test_summon_registration_mismatch_is_rejected(self):
        actor = SimpleNamespace(
            id=901,
            controlled=False,
            effect_stats={4: 3},
            effect_maxima={4: 6},
            native_summon_source=dict(
                ref=3791, level=20, direction=3, caster_id=7, controller_id=7
            ),
        )
        registration = dict(
            actor_id=901,
            caster_id=7,
            controller_id=7,
            authority=dict(
                is_summon=True,
                breed_id=9999,
                native_real_level=20,
                native_instance_id=1134,
            ),
        )
        serializer = NativeStats(
            characters={}, monsters={}, fight_id=41, registrations={901: registration}
        )
        with self.assertRaisesRegex(ValueError, "registered summon"):
            serializer(actor)

    def test_multiple_players_use_their_own_complete_authority(self):
        characters = {
            7: {"id": 7, "future": b"first"},
            8: {"id": 8, "future": b"second"},
        }
        stats = NativeStats(characters=characters, monsters={}, fight_id=41)
        with patch(
            "wakfu_server.combat_actor.actual_actor_stats", return_value=b"native"
        ) as encoder:
            for identity in (7, 8):
                actor = SimpleNamespace(
                    id=identity,
                    controlled=True,
                    effect_stats={4: identity},
                    effect_maxima={4: 12},
                )
                self.assertEqual(stats(actor, SimpleNamespace(id=41)), b"native")
                self.assertEqual(encoder.call_args.args[0], characters[identity])
                self.assertEqual(
                    encoder.call_args.kwargs, {"wp_current": identity, "wp_maximum": 12}
                )

    def test_unknown_actor_missing_resources_and_foreign_encounter_rejected(self):
        stats = NativeStats(characters={7: {"id": 7}}, monsters={}, fight_id=41)
        actor = SimpleNamespace(
            id=8, controlled=True, effect_stats={4: 2}, effect_maxima={4: 6}
        )
        with self.assertRaisesRegex(ValueError, "Missing owned"):
            stats(actor)
        actor.id = 7
        with self.assertRaisesRegex(ValueError, "another native encounter"):
            stats(actor, SimpleNamespace(id=42))
        actor.effect_stats = {}
        with self.assertRaisesRegex(ValueError, "WP snapshot"):
            stats(actor)


if __name__ == "__main__":
    unittest.main()
