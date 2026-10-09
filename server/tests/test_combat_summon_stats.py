"""Registered summon updates use actual actor identity and native snapshot."""
import struct
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from wakfu_server.combat_summon_stats import registered_summon_stats


class RegisteredSummonStatsTests(unittest.TestCase):
    def test_ordinary_serializers_cannot_clear_registered_summon_recognition(self):
        from wakfu_server.combat_actor import (
            actual_actor_stats,
            actual_monster_actor_stats,
        )

        actor, _ = self.fixture()
        for serialize in (actual_actor_stats, actual_monster_actor_stats):
            with self.subTest(serializer=serialize.__name__), self.assertRaisesRegex(
                ValueError, "current native registration"
            ):
                serialize({"id": actor.id}, actor, 77, wp_current=0, wp_maximum=0)

    def fixture(self):
        source = dict(
            ref=3251,
            level=20,
            caster_id=12,
            controller_id=12,
            native_relation_source="big.new_bje.fdt_initial_registration",
        )
        actor = SimpleNamespace(
            id=901,
            native_summon_source=source,
            native_controller_id=12,
            direction=1,
            native_obstacle_id=5,
            native_controlled_by_ai=False,
            position=(2, 3, 0),
        )
        row = dict(
            actor_id=901,
            caster_id=12,
            controller_id=12,
            authority=dict(
                is_summon=True,
                is_player=False,
                breed_id=3251,
                native_real_level=20,
                native_controller_id=12,
            ),
        )
        return actor, SimpleNamespace(
            id=77, actors={901: actor}, native_summon_registrations={901: row}
        )

    def test_native_fighter_identity_and_snapshot_preserved(self):
        actor, fight = self.fixture()
        snapshot = b"\x00\x00"
        with patch(
            "wakfu_server.combat_summon_stats.snapshot_characteristics",
            return_value=snapshot,
        ) as serialize:
            payload = registered_summon_stats(actor, fight, 1134)
        serialize.assert_called_once_with(actor)
        self.assertEqual(payload[0], 2)
        # Native pW: Ue, Uf, Ug, Uh (eGj.ly/dTE), Ui, Uj, Uk.
        common_offset = 1 + struct.calcsize(">iihqBB")
        self.assertEqual(
            struct.unpack_from(">iBBBBbB", payload, common_offset),
            (77, 0, 0, 1, 0, 5, 0),
        )
        self.assertEqual(struct.unpack_from(">q", payload, len(payload) - 20)[0], 901)
        self.assertIn(struct.pack(">hBhH", 3251, 1, 20, 0), payload)
        from wakfu_server.combat_wire import actor_state, decode_actor_state

        decoded = decode_actor_state(12873, actor_state(12873, 77, 901, payload))
        self.assertEqual((decoded["fight_id"], decoded["actor_id"]), (77, 901))
        self.assertEqual(decoded["state"], payload)
        self.assertEqual(decoded["state"][common_offset + 6], 1)  # pW.Uh / eGj.dTE

    def test_missing_or_stale_registration_rejected_before_serialization(self):
        for change in ("missing", "roster", "controller", "reference"):
            actor, fight = self.fixture()
            if change == "missing":
                fight.native_summon_registrations.clear()
            elif change == "roster":
                fight.actors.clear()
            elif change == "controller":
                actor.native_controller_id = 13
            else:
                actor.native_summon_source["ref"] = 3252
            with self.subTest(change=change), patch(
                "wakfu_server.combat_summon_stats.snapshot_characteristics"
            ) as serialize:
                with self.assertRaises(ValueError):
                    registered_summon_stats(actor, fight, 1134)
                serialize.assert_not_called()
