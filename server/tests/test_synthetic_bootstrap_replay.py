"""Every selected replay frame must adapt a real fresh owned character."""
import base64
from copy import deepcopy
import gzip
import json
from pathlib import Path
import struct
import sys
from unittest.mock import patch

from postgres_case import PostgresCase
from wakfu_server import health_store, wire

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "server/tools"))
from build_synthetic_bootstrap import build


class SyntheticBootstrapReplayTests(PostgresCase):
    def test_all_selected_frames_adapt_fresh_owned_character_and_restore_legacy_authority(
        self,
    ):
        from test_legacy_bootstrap_compatibility import (
            LegacyBootstrapCompatibilityTests,
        )

        # The real durable sheet supplies level, HP, inventory and build fields;
        # no missing-level shortcut can suppress strict entity fingerprint checks.
        account = self.store.register("synthetic-replay-owner", "test-password")["id"]
        character = self.store.create_character(account, "Replay Owner")
        generation = self.store.begin_session(account)
        self.store.select_character(account, generation, character["id"])
        character = health_store.initialize(
            self.store, account, generation, character["id"]
        )
        self.assertEqual(character["level"], 1)
        self.assertTrue(character["inventory_containers"])
        defaults = json.loads(
            (
                ROOT
                / "server/data/installation/source/native-fresh-entity-defaults.json"
            ).read_text()
        )
        frames = build(defaults)
        artifact = (
            ROOT / "server/data/installation/artifacts/bootstrap.synthetic.jsonl.gz"
        )
        installed_frames = [
            json.loads(line)
            for line in gzip.decompress(artifact.read_bytes()).splitlines()
        ]
        self.assertEqual(
            installed_frames,
            frames,
            "Distributed artifact must match the fixed generator",
        )
        metadata = frames[0]["synthetic_template"]
        self.assertEqual(
            {row["format"] for row in metadata["layouts"]}, {4, 5, 10, 11, 22, 28}
        )
        before = deepcopy(wire.ENTITY_LAYOUTS)
        identity = (
            wire.TEMPLATE_ACCOUNT,
            wire.TEMPLATE_CHARACTER,
            wire.TEMPLATE_NAME,
            wire.SYNTHETIC_BOOTSTRAP,
        )
        packets = []
        with patch.multiple(
            wire,
            TEMPLATE_ACCOUNT=wire.TEMPLATE_ACCOUNT,
            TEMPLATE_CHARACTER=wire.TEMPLATE_CHARACTER,
            TEMPLATE_NAME=wire.TEMPLATE_NAME,
            SYNTHETIC_BOOTSTRAP=wire.SYNTHETIC_BOOTSTRAP,
        ), patch.dict(wire.ENTITY_LAYOUTS, deepcopy(wire.ENTITY_LAYOUTS), clear=True):
            wire.register_synthetic_bootstrap(metadata)
            for index, frame in enumerate(frames[45:114], 45):
                if frame["direction"] != "in":
                    continue
                body = base64.b64decode(frame["body_base64"])
                try:
                    adapted = wire.adapt(frame["opcode"], body, account, character)
                except Exception as error:
                    raise AssertionError(
                        f"Selected replay slot{index}/opcode{frame['opcode']} failed"
                    ) from error
                self.assertIsInstance(adapted, bytes)
                self.assertEqual(frame["body_base64"], base64.b64encode(body).decode())
                packets.append((index, frame["opcode"], adapted))
            self.assertGreater(len(packets), 20)
            self.assertTrue(
                {13713, 12666, 13974, 12608, 15548, 12436}
                <= {op for _, op, _ in packets}
            )
            bag = next(body for _, opcode, body in packets if opcode == 13713)
            self.assertEqual(struct.unpack_from(">qB", bag), (character["id"], 4))
            # The exact synthetic bag body is registered independently of the
            # larger legacy snapshot: no hash bypass or unknown-format fallback.
            source_bag = base64.b64decode(
                next(
                    frame["body_base64"]
                    for frame in frames[45:114]
                    if frame["direction"] == "in" and frame["opcode"] == 13713
                )
            )[8:]
            self.assertNotEqual(
                before[4]["template_sha256"], wire.ENTITY_LAYOUTS[4]["template_sha256"]
            )
            with self.assertRaisesRegex(ValueError, "verified section boundaries"):
                wire.minimal_entity(source_bag + b"\0", character)
        self.assertEqual(wire.ENTITY_LAYOUTS, before)
        self.assertEqual(
            (
                wire.TEMPLATE_ACCOUNT,
                wire.TEMPLATE_CHARACTER,
                wire.TEMPLATE_NAME,
                wire.SYNTHETIC_BOOTSTRAP,
            ),
            identity,
        )
        LegacyBootstrapCompatibilityTests(
            "test_legacy_registration_gate_auth_header_and_character_filter_keep_exact_bytes"
        ).test_legacy_registration_gate_auth_header_and_character_filter_keep_exact_bytes()
