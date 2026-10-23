"""Public bootstrap callers and native wire registration, no World startup."""
import ast
import base64
from copy import deepcopy
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import struct
import sys
import unittest
from unittest.mock import patch

from protocol_codec import Reader
from wakfu_server import wire

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "server/tools"))
from build_synthetic_bootstrap import build
from synthetic_bootstrap_entities import build_entities


class SyntheticBootstrapTests(unittest.TestCase):
    def test_fresh_defaults_cover_real_fixture_callers_realm_filter_and_owned_wire_adaptation(
        self,
    ):
        path = Path(
            os.environ.get(
                "WAKFU_PUBLIC_BOOTSTRAP_DEFAULTS",
                ROOT
                / "server/data/installation/source/native-fresh-entity-defaults.json",
            )
        )
        self.assertTrue(
            path.is_file(),
            "Fresh native serializer defaults are required for this oracle",
        )
        defaults = json.loads(path.read_text())
        frames = build(defaults)
        self.assertEqual(len(frames), 132)
        self.assertEqual(frames, build(defaults))
        metadata = frames[0]["synthetic_template"]
        source = ast.parse((ROOT / "server/local_game_server.py").read_text())
        required = {
            node.args[0].value
            for node in ast.walk(source)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "fixture"
            and node.args
            and isinstance(node.args[0], ast.Constant)
            and type(node.args[0].value) is int
        }
        bodies = {
            row["opcode"]: base64.b64decode(row["body_base64"])
            for row in frames
            if row["direction"] == "in"
        }
        self.assertFalse(required - set(bodies))
        functions = [
            node
            for node in source.body
            if isinstance(node, ast.FunctionDef)
            and node.name in ("pack_text", "realms_local")
        ]
        namespace = {
            "Reader": Reader,
            "struct": struct,
            "ipaddress": ipaddress,
            "os": os,
        }
        exec(
            compile(
                ast.fix_missing_locations(ast.Module(body=functions, type_ignores=[])),
                "<actual-production-realm-caller>",
                "exec",
            ),
            namespace,
        )
        with patch.dict(
            os.environ,
            {
                "WAKFU_ADVERTISE_HOST": "127.0.0.1",
                "WAKFU_ADVERTISE_WORLD_PORT": "15556",
            },
        ):
            self.assertEqual(namespace["realms_local"](bodies[453]), bodies[453])
        entities, layouts = build_entities(
            defaults, metadata["account_id"], metadata["character_id"], metadata["name"]
        )
        self.assertEqual({row["format"] for row in layouts}, {5, 10, 11, 22, 28})
        for layout in layouts:
            self.assertEqual(
                hashlib.sha256(entities[layout["format"]]).hexdigest(),
                layout["template_sha256"],
            )
        # Real registration runs only inside a restored module-state scope.
        with patch.multiple(
            wire,
            TEMPLATE_ACCOUNT=wire.TEMPLATE_ACCOUNT,
            TEMPLATE_CHARACTER=wire.TEMPLATE_CHARACTER,
            TEMPLATE_NAME=wire.TEMPLATE_NAME,
            SYNTHETIC_BOOTSTRAP=wire.SYNTHETIC_BOOTSTRAP,
        ), patch.dict(wire.ENTITY_LAYOUTS, deepcopy(wire.ENTITY_LAYOUTS), clear=True):
            wire.register_synthetic_bootstrap(metadata)
            self.assertTrue(wire.SYNTHETIC_BOOTSTRAP)
            for kind in (10, 11, 28):
                self.assertEqual(entities[kind].count(wire.INITIAL_POSITION), 1)
            actual_account = 1900000991
            actual_character = dict(
                id=1900000992,
                name="Fresh Native",
                map_id=527,
                instance_id=0,
                x=0,
                y=32,
                z=0,
            )
            adapted_auth = wire.adapt(472, bodies[472], actual_account)
            self.assertEqual(
                struct.unpack(">qq", adapted_auth[2:18]),
                (actual_account, actual_account),
            )
            self.assertEqual(
                adapted_auth[:2] + adapted_auth[18:], bodies[472][:2] + bodies[472][18:]
            )
            original = bodies[12666]
            adapted = wire.adapt(12666, original, actual_account, actual_character)
            reader = Reader(adapted)
            reader.take(reader.number("H") * 8)
            blocks = [reader.take(reader.number("I")) for _ in range(3)]
            reader.finish()
            header = Reader(blocks[0])
            self.assertEqual(header.number("B"), 10)
            self.assertEqual(header.number("q"), actual_character["id"])
            header.take(1)
            self.assertEqual(header.number("q"), actual_account)
            self.assertEqual(header.text("H"), actual_character["name"])
            self.assertEqual(bodies[12666], original)
            # The existing static catalog has independent native entity28
            # templates; generated fixture identities must remain compatible.
            from wakfu_server.transports import CATALOG
            from wakfu_server.haven_bag import map_transition

            catalog_template = next(
                bytes.fromhex(packet["body_hex"])
                for route in CATALOG["routes"]
                for packet in route["packets"]
                if packet["opcode"] == 13974
            )
            moved = map_transition(
                catalog_template,
                dict(actual_character, account_id=actual_account, x=3, y=4, z=0),
                9,
            )
            transition = Reader(moved)
            entity28 = transition.take(transition.number("H"))
            self.assertEqual(
                struct.unpack(">q", entity28[1:9])[0], actual_character["id"]
            )
            self.assertEqual(struct.unpack(">q", entity28[10:18])[0], actual_account)
            self.assertEqual(struct.unpack(">iihq", entity28[18:36]), (3, 4, 0, 9))
            self.assertNotIn(struct.pack(">q", 83668792), moved)
            self.assertNotIn(struct.pack(">q", 2409354), moved)
            malformed = deepcopy(metadata)
            malformed["layouts"][0]["sections"][0]["start"] += 1
            with self.assertRaisesRegex(ValueError, "Noncontiguous"):
                wire.register_synthetic_bootstrap(malformed)
