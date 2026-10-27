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
        self.assertEqual(projection.grant_carriers, [packet])
        self.assertEqual(
            decode_remote_effects(projection.effects(200, encoded, final=True)),
            (other,),
        )
        projection.verify_complete(final=True)
        with self.assertRaises(ValueError):
            projection.effects(200, encoded, final=True)
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

    def test_changed_final_snapshot_still_resets_nonbirth_actor(self):
        fight, summon, shared = fixture(False)
        changed = encode_remote_effects(
            (RemoteRunningEffect(310, b"changed-effect", 77),)
        )
        original = ReconnectGrantProjection.effects

        def projection(projector, actor_id, effects, *, final=False):
            result = original(projector, actor_id, effects, final=final)
            return changed if final and actor_id == 100 else result

        with patch.object(ReconnectGrantProjection, "effects", projection):
            packets = owned_snapshot(
                fight,
                shared,
                SimpleNamespace(account_id=1, character_id=100),
                actor_payload=lambda *args: (b"owned-stats", bytes(2)),
            )
        continuation = packets.presentation.resume_packets
        resets = {
            decode_actor_state(op, body)["actor_id"]: decode_actor_state(op, body)[
                "state"
            ]
            for op, body in continuation
            if op == 13912
        }
        self.assertEqual(resets, {100: changed, summon.id: bytes(2)})

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
                # Birth creation must complete on this recipient before any
                # effect-manager reset or temporary class grant is published.
                self.assertTrue(hasattr(packets, "presentation"))
                self.assertNotIn(13912, [opcode for opcode, _ in packets])
                self.assertNotIn(packet, packets)
                packets = tuple(packets) + packets.presentation.resume_packets
                boot = decode_bootstrap(packets[0][1])
                self.assertTrue(
                    all(row["myF"] == bytes(2) for row in boot["participants"])
                )
                opcodes = [opcode for opcode, _ in packets]
                self.assertEqual(opcodes.count(12514), 1)
                action = opcodes.index(12514)
                self.assertFalse(
                    any(
                        opcode == 13912
                        and decode_actor_state(opcode, body)["actor_id"] == 200
                        for opcode, body in packets
                    )
                )
                hero_stats = next(
                    index
                    for index, (opcode, body) in enumerate(packets)
                    if opcode == 12873
                    and decode_actor_state(opcode, body)["actor_id"] == 200
                )
                self.assertGreater(hero_stats, action)
                self.assertEqual(packets.count(packet), 1)
                self.assertGreater(
                    packets.index(packet),
                    max(
                        index
                        for index, (opcode, _) in enumerate(packets)
                        if opcode == 13912
                    ),
                )
                self.assertNotIn(13560, opcodes)
                self.assertNotIn(13482, opcodes)
                self.assertEqual(source_snapshot(fight), before)


if __name__ == "__main__":
    unittest.main()
