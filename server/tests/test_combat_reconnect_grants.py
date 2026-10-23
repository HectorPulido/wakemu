"""Reconnect installs native grants exactly once after controller restoration."""
from types import SimpleNamespace
from unittest.mock import patch
import struct
import unittest

from wakfu_server.combat_effects import _integer, _varint
from wakfu_server.combat_stat_effects import owned_effect_payload, owned_effect_delivery
from wakfu_server.combat_remote_effects import (
    RemoteRunningEffect,
    encode_remote_effects,
    decode_remote_effects,
)
from wakfu_server.combat_reconnect_grants import ReconnectGrantProjection
from wakfu_server.combat_reconnect_snapshot import owned_snapshot
from wakfu_server.combat_geometry_snapshot import source_snapshot
from wakfu_server.combat_wire import decode_bootstrap, decode_actor_state
from test_combat_reconnect_summon_timeline import fixture


def grant(actor_id=200, uid=901):
    additional = b"".join(
        _integer(field, value)
        for field, value in ((10, 4604), (14, 1), (19, 2), (20, 3))
    )
    payload = (
        owned_effect_payload(
            uid=uid,
            base_uid=uid,
            generic_effect=313107,
            caster_id=actor_id,
            target_id=actor_id,
            value=0,
            execution_status=0,
            inherit_container=False,
        )
        + b"\x42"
        + _varint(len(additional))
        + additional
    )
    packet = owned_effect_delivery(
        89,
        41,
        native_opcode=12613,
        effect_class=649,
        target_id=actor_id,
        uid=uid,
        running_effect_payload=payload,
    )
    return RemoteRunningEffect(649, payload, 3753), packet


class ReconnectGrantTests(unittest.TestCase):
    def test_bootstrap_defers_exact_grant_without_changing_other_effects(self):
        record, packet = grant()
        other = RemoteRunningEffect(310, b"unchanged-state", 77)
        projection = ReconnectGrantProjection([packet])
        encoded = encode_remote_effects((other, record))
        self.assertEqual(
            decode_remote_effects(projection.effects(200, encoded)), (other,)
        )
        projection.verify_complete()
        self.assertEqual(projection.other_carriers, [])
        self.assertEqual(decode_remote_effects(encoded)[1], record)

    def test_projection_rejects_missing_mismatched_foreign_and_duplicate_carriers(self):
        record, packet = grant()
        encoded = encode_remote_effects((record,))
        with self.assertRaises(ValueError):
            ReconnectGrantProjection([]).effects(200, encoded)
        with self.assertRaises(ValueError):
            ReconnectGrantProjection([packet, packet])
        with self.assertRaises(ValueError):
            ReconnectGrantProjection([packet]).effects(100, encoded)
        with self.assertRaises(ValueError):
            ReconnectGrantProjection([packet]).effects(
                200, encode_remote_effects((record, record))
            )
        with self.assertRaises(ValueError):
            ReconnectGrantProjection([packet]).verify_complete()
        changed, _ = grant(uid=902)
        with self.assertRaises(ValueError):
            ReconnectGrantProjection([packet]).effects(
                200, encode_remote_effects((changed,))
            )

    def test_complete_owned_reconnect_publishes_full_grant_only_after_action(self):
        for current_summon in (False, True):
            with self.subTest(current_summon=current_summon):
                fight, summon, shared = fixture(current_summon)
                record, packet = grant()
                effects = encode_remote_effects((record,))
                before = source_snapshot(fight)
                session = SimpleNamespace(account_id=1, character_id=100)
                with patch(
                    "wakfu_server.combat_spectator_snapshot._retained_carrier_packets",
                    return_value=(packet,),
                ):
                    packets = owned_snapshot(
                        fight,
                        shared,
                        session,
                        actor_payload=lambda state, actor, _: (
                            b"authoritative-stats",
                            effects if actor.id == 200 else bytes(2),
                        ),
                    )
                boot = decode_bootstrap(packets[0][1])
                self.assertTrue(
                    all(row["myF"] == bytes(2) for row in boot["participants"])
                )
                opcodes = [opcode for opcode, _ in packets]
                self.assertEqual(opcodes.count(12514), 1)
                action = opcodes.index(12514)
                hero_snapshot = next(
                    (index, decode_actor_state(13912, body))
                    for index, (opcode, body) in enumerate(packets)
                    if opcode == 13912
                    and decode_actor_state(13912, body)["actor_id"] == 200
                )
                self.assertGreater(hero_snapshot[0], action)
                self.assertEqual(hero_snapshot[1]["state"], effects)
                self.assertEqual(
                    decode_remote_effects(hero_snapshot[1]["state"]), (record,)
                )
                self.assertEqual(packets[hero_snapshot[0] + 1][0], 12873)
                self.assertNotIn(packet, packets)
                self.assertNotIn(13560, opcodes)
                self.assertNotIn(13482, opcodes)
                self.assertEqual(source_snapshot(fight), before)


if __name__ == "__main__":
    unittest.main()
