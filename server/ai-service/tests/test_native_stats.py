from types import SimpleNamespace
import unittest
from unittest.mock import patch
import struct

from wakfu_ai.native.native_stats import NativeStats


class NativeStatsTests(unittest.TestCase):
    def test_summon_without_owned_map_rejects_before_encoding(self):
        actor = SimpleNamespace(id=901, effect_stats={4: 0}, effect_maxima={4: 0})
        registration = {"actor_id": 901}
        fight = SimpleNamespace(id=41, native_summon_registrations={901: registration})
        serializer = NativeStats(
            characters={}, monsters={}, fight_id=41, registrations={901: registration}
        )
        with patch(
            "wakfu_server.combat_summon_stats.registered_summon_stats"
        ) as encode:
            with self.assertRaisesRegex(ValueError, "owned encounter map"):
                serializer(actor, fight)
            encode.assert_not_called()

    def test_registered_positive_summon_preserves_native_flag_on_bulk_refresh(self):
        source = dict(
            ref=3791,
            level=20,
            direction=3,
            caster_id=7,
            controller_id=7,
            native_relation_source="big.new_bje.fdt_initial_registration",
        )
        actor = SimpleNamespace(
            id=901,
            controlled=False,
            effective_level=20,
            team=1,
            position=(2, 3, 0),
            direction=3,
            native_obstacle_id=1,
            native_controller_id=7,
            native_controlled_by_ai=False,
            owner_id=19,
            turn_count=2,
            native_summon_source=source,
            native_fight_property_counts={},
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
                native_controller_id=7,
            ),
        )
        fight = SimpleNamespace(
            id=41,
            actors={901: actor},
            native_summon_registrations={901: registration},
        )
        serializer = NativeStats(
            characters={},
            monsters={},
            fight_id=41,
            registrations={901: registration},
            map_id=1134,
        )
        with patch(
            "wakfu_server.combat_summon_stats.snapshot_characteristics",
            return_value=b"\x00\x00",
        ):
            actual = serializer(actor, fight)
            repeated = serializer.for_fight(fight)(actor, fight)
        self.assertEqual(actual, repeated)
        offset = 1 + struct.calcsize(">iihqBB")
        self.assertEqual(struct.unpack_from(">iBBBBbB", actual, offset)[3], 1)
        self.assertEqual(struct.unpack_from(">q", actual, len(actual) - 20)[0], 901)
        self.assertEqual(actor.native_summon_source, source)
        self.assertEqual(
            (actor.owner_id, actor.native_controller_id, actor.turn_count), (19, 7, 2)
        )
        self.assertTrue(
            fight.native_summon_registrations[901]["authority"]["is_summon"]
        )
        with self.assertRaisesRegex(ValueError, "current fight"):
            serializer(actor)

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
        with self.assertRaisesRegex(ValueError, "Registered summon"):
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
