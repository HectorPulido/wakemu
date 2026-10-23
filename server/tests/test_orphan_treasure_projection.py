"""Two native constructor projections and the existing declared reward seam."""
import json
from pathlib import Path
import struct
from postgres_case import PostgresCase


class OrphanTreasureProjectionTests(PostgresCase):
    def test_original_native_envelope_menu_and_two_shared_currency_claims(self):
        from wakfu_server import declared_treasure_rewards as rewards
        from wakfu_server import treasure_chests
        from wakfu_server.treasure_definition_projections import (
            project_snapshot_rows,
            project_snapshot_bodies,
            binding,
        )
        from wakfu_server.native_interactive_components import (
            components,
            parameter_bounds,
            envelope,
            packet,
            rebind_definition,
        )

        oracle = json.loads(
            (
                Path(__file__).parent
                / "fixtures/orphan_treasure_native_projection.json"
            ).read_text()
        )
        self.assertEqual(len(oracle["rows"]), 2)
        account = self.store.register(
            "orphan-projection-native", "local-test-password"
        )["id"]
        actor = self.store.create_character(account, "Projected Chest")
        generation = self.store.begin_session(account)
        self.store.select_character(account, generation, actor["id"])
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT count(*) n FROM declared_treasure_locations"
                ).fetchone()["n"],
                52,
            )
            # 285 source evidence stays unchanged;286 adds a separate attestation.
            self.assertEqual(
                db.execute(
                    "SELECT count(*) n FROM declared_treasure_locations WHERE NOT client_action_available"
                ).fetchone()["n"],
                2,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) n FROM declared_treasure_definition_overrides WHERE sealed"
                ).fetchone()["n"],
                2,
            )
            original_wallet = db.execute(
                "SELECT kamas FROM account_wallets WHERE account_id=%s", (account,)
            ).fetchone()["kamas"]

        def snapshot_state(native):
            states = treasure_chests.snapshots(
                self.store, account, native["map_id"], character_id=actor["id"]
            )
            matches = [
                body
                for opcode, body in states
                if opcode == 12344
                and struct.unpack_from(">q", body)[0] == native["object_id"]
            ]
            self.assertEqual(len(matches), 1)
            return struct.unpack_from(">h", matches[0], 17)[0]

        for native in oracle["rows"]:
            rule = rewards.definition(self.store, native["map_id"], native["object_id"])
            self.assertTrue(rule["client_action_available"])
            self.assertEqual(snapshot_state(native), 1)
            self.assertEqual(
                (rule["reward_kind"], rule["kamas"], rule["wire_action"]),
                ("kamas", 100, 22),
            )
            self.assertEqual(
                rule["definition_override"]["replacement_definition"],
                native["definition"],
            )
            row = {"id": rule["object_id"], "payload_hex": rule["state_payload_hex"]}
            projected = project_snapshot_rows(self.store, rule["map_id"], [row])
            self.assertEqual(row["payload_hex"], rule["state_payload_hex"])
            self.assertEqual(projected[0]["id"], rule["object_id"])
            payload = bytes.fromhex(projected[0]["payload_hex"])
            self.assertEqual(payload.hex(), native["combined_hex"])
            parts = components(payload)
            base = components(bytes.fromhex(rule["payload_hex"]))
            self.assertEqual(parts[0], base[0])
            self.assertEqual(
                parts[2], components(bytes.fromhex(rule["state_payload_hex"]))[2]
            )
            position, start, end = parameter_bounds(parts[1])
            self.assertEqual(parts[1][start:end].decode(), native["native_parameter"])
            self.assertEqual(
                struct.unpack_from(">hiih", parts[1], 0),
                (rule["map_id"], rule["x"], rule["y"], rule["z"]),
            )
            self.assertEqual(
                (native["state"], native["action"], native["menu_count"]), (1, 22, 1)
            )
            opcode, body = packet(rule["object_id"], payload)
            self.assertEqual(
                (opcode, *struct.unpack_from(">hqh", body)),
                (13984, 1, rule["object_id"], len(payload)),
            )
            self.assertEqual(body[12:], payload)
            original_state = bytes.fromhex(rule["state_payload_hex"])
            original_batch = (
                struct.pack(">hqh", 1, rule["object_id"], len(original_state))
                + original_state
            )
            # This is the exact wrapper used by both World13984 publishers.
            self.assertEqual(
                project_snapshot_bodies(self.store, rule["map_id"], (original_batch,)),
                (body,),
            )
            self.assertEqual(envelope(parts), payload)
            with self.assertRaises(ValueError):
                rebind_definition(
                    bytes.fromhex(rule["payload_hex"]),
                    bytes.fromhex(rule["state_payload_hex"]),
                    expected_parameter="wrong",
                    replacement_parameter="353",
                )
            with self.assertRaises(ValueError):
                components(payload[:8])
            with self.store.connection() as db:
                db.execute(
                    "UPDATE characters SET map_id=%s,x=%s,y=%s,z=%s WHERE id=%s",
                    (rule["map_id"], *rule["approaches"][0], actor["id"]),
                )
            actual = self.store.character(account, actor["id"])
            request = struct.pack(">qHH", native["object_id"], native["action"], 0)
            with self.assertRaises(ValueError):
                treasure_chests.claim(
                    self.store,
                    account,
                    generation,
                    actual,
                    request,
                    loaded=True,
                    is_hero=True,
                )
            first = treasure_chests.claim(
                self.store,
                account,
                generation,
                actual,
                request,
                loaded=True,
                is_hero=False,
            )
            self.assertEqual(first["receipt"]["kamas"], 100)
            self.assertFalse(first["replay"])
            second = treasure_chests.claim(
                self.store,
                account,
                generation,
                self.store.character(account, actor["id"]),
                request,
                loaded=True,
                is_hero=False,
            )
            self.assertTrue(second["replay"])
            self.assertEqual(snapshot_state(native), 0)
        # A real replacement session republishes both character-specific
        # depleted states without changing the original missing-action flags.
        reconnected = self.store.begin_session(account)
        self.store.select_character(account, reconnected, actor["id"])
        for native in oracle["rows"]:
            self.assertEqual(snapshot_state(native), 0)
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT count(*) n FROM declared_treasure_locations "
                    "WHERE NOT client_action_available"
                ).fetchone()["n"],
                2,
            )
        with self.assertRaises(ValueError):
            project_snapshot_bodies(self.store, 297, (b"\x00",))
        with self.assertRaises(ValueError):
            project_snapshot_bodies(self.store, 297, (b"\x00\x00x",))
        untouched = [{"id": -123, "payload_hex": "deadbeef"}]
        self.assertEqual(project_snapshot_rows(self.store, 297, untouched), untouched)
        passthrough = struct.pack(">hqh", 1, -123, 4) + bytes.fromhex("deadbeef")
        self.assertEqual(
            project_snapshot_bodies(self.store, 297, (passthrough, b"\x00\x00")),
            (passthrough, b"\x00\x00"),
        )
        with self.store.connection() as db:
            wallet = db.execute(
                "SELECT kamas FROM account_wallets WHERE account_id=%s", (account,)
            ).fetchone()["kamas"]
            self.assertEqual(wallet - original_wallet, 200)
            self.assertEqual(
                db.execute(
                    "SELECT count(*) n FROM declared_treasure_attempts WHERE completed_at IS NOT NULL"
                ).fetchone()["n"],
                2,
            )
        # Validate forged pre-seal records against the full original85-row
        # source and its binary hash, not merely a64-character shape check.
        with self.store.connection() as db:
            original_binding = db.execute(
                "SELECT * FROM declared_treasure_definition_overrides WHERE map_id=297"
            ).fetchone()
            source_rule = rewards.definition(self.store, 297, 13819)

            class Forged:
                def __init__(self, changes):
                    self.changes = changes

                def execute(self, query, args=()):
                    if query.startswith(
                        "SELECT * FROM declared_treasure_definition_overrides"
                    ):
                        fake = dict(original_binding)
                        fake.update(self.changes)
                        return type("Row", (), {"fetchone": lambda self: fake})()
                    return db.execute(query, args)

            for changes in (
                {"definition_source_sha256": "a" * 64},
                {"replacement_definition": 56},
                {"original_definition_missing": False},
                {"required_item": 12324},
            ):
                with self.assertRaises(ValueError):
                    binding(Forged(changes), source_rule)
        with self.assertRaises(Exception):
            with self.store.connection() as db:
                db.execute(
                    "UPDATE declared_treasure_definition_overrides SET replacement_definition=56 WHERE map_id=297"
                )
