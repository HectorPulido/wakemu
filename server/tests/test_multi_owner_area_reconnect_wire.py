"""Owned reconnect wire after real two-owner trap and rail retirement.

These tests exercise server presentation, not a socket or client renderer.
"""
import os
import struct
import unittest
from types import SimpleNamespace
from unittest.mock import patch


@unittest.skipUnless(
    os.environ.get("WAKFU_TEST_GRANTEDCAST") == "1", "native runtime opt-in"
)
class MultiOwnerAreaReconnectWireTests(unittest.TestCase):
    def _run_and_reconnect(self, module, case_name, method_name):
        from wakfu_server import fight_checkpoint_store, combat_terrain
        from wakfu_server.combat_reconnect_snapshot import owned_snapshot

        original_snapshot = fight_checkpoint_store.snapshot
        original_arena = combat_terrain.local_arena
        observed = {}

        def capture_snapshot(fight, *args, **kwargs):
            observed["fight"] = fight
            return original_snapshot(fight, *args, **kwargs)

        def capture_arena(*args, **kwargs):
            arena = original_arena(*args, **kwargs)
            observed["arena"] = arena
            return arena

        # Reuse the complete legal paid gameplay sequence, including its
        # retirement, owner isolation and resource assertions.
        with patch.object(
            fight_checkpoint_store, "snapshot", capture_snapshot
        ), patch.object(combat_terrain, "local_arena", capture_arena):
            if hasattr(module, "snapshot"):
                with patch.object(module, "snapshot", capture_snapshot):
                    getattr(getattr(module, case_name)(method_name), method_name)()
            else:
                getattr(getattr(module, case_name)(method_name), method_name)()

        fight = observed["fight"]
        before = original_snapshot(fight)
        resources = {
            identity: (actor.hp, actor.ap, actor.mp)
            for identity, actor in fight.actors.items()
        }
        current_records = fight.native_retained_records
        expected = {
            (record["target_id"], uid) for uid, record in current_records.items()
        }
        retired = set(getattr(fight, "native_retired_area_managers", {}))
        self.assertTrue(fight.native_effect_areas)
        self.assertTrue(
            any(row.get("owner_id") == 7 for row in fight.native_effect_areas.values())
        )
        runtime = SimpleNamespace(
            fight=fight,
            turn_deadline=None,
            native_action_id=915,
            awaiting_ack=None,
        )
        shared = SimpleNamespace(
            runtime=runtime,
            map_id=1134,
            join_context={
                "arena": observed["arena"],
                "terrain_effect_id": 99,
                "terrain_instance_id": 0,
                "leaders": {0: 7, 1: -7},
            },
        )
        for account_id in (3, 4):
            packets = owned_snapshot(
                fight,
                shared,
                SimpleNamespace(account_id=account_id),
                actor_payload=lambda *_: (b"", b""),
            )
            carriers = [body for opcode, body in packets if opcode == 12613]
            from wakfu_server.combat_effect_removal import _identity_fields

            actual = []
            for body in carriers:
                fields = _identity_fields(body[19:])
                target = fields.get(7)
                if target is not None and target >= (1 << 63):
                    target -= 1 << 64
                actual.append((target, fields[1]))
            self.assertEqual(set(actual), expected)
            self.assertEqual(len(actual), len(expected))
            for body in carriers:
                self.assertEqual(
                    struct.unpack_from(">iiiB", body), (fight.id, 915, -1, 0)
                )
            # Retired area spatial UIDs must not be restored as active areas;
            # retained runner identity is checked independently above.
            self.assertFalse(retired & set(fight.native_effect_areas))
            self.assertEqual(original_snapshot(fight), before)
            self.assertEqual(
                {
                    identity: (actor.hp, actor.ap, actor.mp)
                    for identity, actor in fight.actors.items()
                },
                resources,
            )

    def test_two_sram_partial_retirement_owned_reconnect(self):
        import test_sram_multi_owner_traps as scenario

        self._run_and_reconnect(
            scenario,
            "SramMultiOwnerTrapTests",
            "test_actual_refund_and_retirement_preserve_other_owners_trap",
        )

    def test_two_steamer_partial_retirement_owned_reconnect(self):
        import test_multi_owner_steamer_rails as scenario

        self._run_and_reconnect(
            scenario,
            "MultiOwnerSteamerRailsTests",
            "test_paid_two_owner_network_partial_retirement_preserves_foreign_checkpoint",
        )

    def test_actual_jamjam_actor_aura_preserves_original_payload(self):
        import test_osamodas_jamjam_action_consequences as scenario
        from wakfu_server import combat_spectator_snapshot as presentation
        from wakfu_server.combat_effect_removal import _identity_fields
        from wakfu_server.fight_checkpoint_store import snapshot

        original = scenario.prepare_server_spell
        observed = {}

        def capture(*args, **kwargs):
            tx = original(*args, **kwargs)
            observed["fight"] = tx.fight
            return tx

        with patch.object(scenario, "prepare_server_spell", capture):
            scenario.JamjamActionConsequencesTests(
                "test_lunar_applies_real_owner_state_and_owned_aura"
            ).test_lunar_applies_real_owner_state_and_owned_aura()
        fight = observed["fight"]
        before = snapshot(fight)
        independent = {
            uid: bytes.fromhex(row["payload"])
            for uid, row in fight.native_owned_area_effects.items()
        }
        self.assertTrue(independent, "Actual Jamjam must supply a retained aura")
        for _ in range(2):
            packets = presentation._retained_carrier_packets(fight, 917)
            seen = {}
            for opcode, body in packets:
                self.assertEqual(opcode, 12613)
                declared = struct.unpack_from(">h", body, 17)[0]
                self.assertEqual(len(body), 19 + declared)
                payload = body[19:]
                fields = _identity_fields(payload)
                if fields[1] in independent:
                    seen[fields[1]] = payload
            self.assertEqual(seen, independent)
            self.assertEqual(snapshot(fight), before)
