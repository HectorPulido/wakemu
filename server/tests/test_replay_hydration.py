"""Replay account data is loaded once per invocation, without bootstrap imports."""
import ast
import base64
from copy import deepcopy
import json
import os
from pathlib import Path
import struct
import unittest

from postgres_case import PostgresCase


def _production_replay(globals_update=None):
    test_dir = Path(__file__).resolve().parent
    candidates = (
        test_dir.parent / "local_game_server.py",
        Path("/app/local_game_server.py"),
    )
    source_path = next((path for path in candidates if path.is_file()), None)
    if source_path is None:
        raise AssertionError("could not locate local_game_server.py")
    tree = ast.parse(source_path.read_text())
    functions = [
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "replay"
    ]
    if len(functions) != 1:
        raise AssertionError(f"expected one replay function, found {len(functions)}")
    module = ast.fix_missing_locations(ast.Module(body=functions, type_ignores=[]))
    namespace = {"base64": base64, "struct": struct}
    namespace.update(globals_update or {})
    exec(compile(module, str(source_path), "exec"), namespace)
    return namespace["replay"]


class _Store:
    def __init__(self, characters):
        self.max_characters = 18
        self.rows = list(characters)
        self.calls = []

    def characters(self, account_id):
        self.calls.append(account_id)
        return [dict(row) for row in self.rows]


class _Wire:
    TEMPLATE_CHARACTER = 1

    @staticmethod
    def adapt(opcode, original, account_id, character):
        return f"equipment:{character['id']}".encode()

    @staticmethod
    def character_list(template, account_id, characters):
        return ("list:" + ",".join(str(row["id"]) for row in characters)).encode()

    @staticmethod
    def attribute_sheets(original, characters):
        return ("sheets:" + ",".join(str(row["id"]) for row in characters)).encode()

    @staticmethod
    def without_captured_players(original):
        return b"clean-world"


class _Social:
    @staticmethod
    def adapt(opcode, original, account_id, character, owned, *, cosmetic_record=None):
        if opcode == 13873:
            return b"social-response"
        return None


class ReplayHydrationTests(unittest.TestCase):
    @staticmethod
    def _frame(opcode, body):
        return {
            "direction": "in",
            "opcode": opcode,
            "body_base64": base64.b64encode(body).decode("ascii"),
        }

    def _replay(self, frames, store):
        sent = []
        namespace = {
            "FRAMES": frames,
            "STORE": store,
            "wire": _Wire,
            "social": _Social,
            "CHARACTERS": b"template",
            "send": lambda connection, service, opcode, body: sent.append(
                (opcode, body)
            ),
        }
        # Recompile with the test namespace so production code remains unimported.
        function = _production_replay(namespace)
        function(object(), 0, len(frames), 42)
        return sent

    def test_account_hydration_is_shared_across_social_equipment_and_character_packets(
        self,
    ):
        frames = [
            self._frame(13873, struct.pack(">II", 2, 0)),
            self._frame(13078, struct.pack(">q", _Wire.TEMPLATE_CHARACTER)),
            self._frame(23548, b""),
            self._frame(12393, b"sheets-request"),
        ]
        store = _Store(({"id": 101}, {"id": 202}))

        sent = self._replay(frames, store)

        self.assertEqual(store.calls, [42])
        self.assertEqual(
            sent,
            [
                (13873, b"social-response"),
                (13078, b"equipment:101"),
                (13078, b"equipment:202"),
                (23992, b"\x0d"),
                (23548, b"list:101,202"),
                (12393, b"sheets:101,202"),
            ],
        )

    def test_captured_slot_count_is_replaced_before_current_roster(self):
        frames = [self._frame(23992, b"\x00"), self._frame(23548, b"")]
        store = _Store(({"id": 101},))
        store.max_characters = 24
        self.assertEqual(
            self._replay(frames, store),
            [(23992, b"\x13"), (23992, b"\x13"), (23548, b"list:101")],
        )

    def test_packets_without_account_hydration_do_not_query_store(self):
        frames = [self._frame(12608, b"captured-world")]
        store = _Store(({"id": 101},))

        sent = self._replay(frames, store)

        self.assertEqual(store.calls, [])
        self.assertEqual(sent, [(12608, b"clean-world")])

    def test_hydration_cache_is_invocation_local_and_refreshes_state(self):
        frames = [self._frame(23548, b"")]
        store = _Store(({"id": 101},))

        first = self._replay(frames, store)
        store.rows = [{"id": 303}, {"id": 404}]
        second = self._replay(frames, store)

        self.assertEqual(store.calls, [42, 42])
        self.assertEqual(first, [(23992, b"\x0d"), (23548, b"list:101")])
        self.assertEqual(second, [(23992, b"\x0d"), (23548, b"list:303,404")])


class ReplayHydrationPostgresTests(PostgresCase):
    @staticmethod
    def _native_templates():
        from protocol_codec import Reader
        from wakfu_server import wire

        capture = Path(os.environ.get("WAKFU_CAPTURE_PATH", "/fixtures/frames.jsonl"))
        if not capture.is_file():
            raise AssertionError("captured replay fixture is unavailable")
        wanted = {}
        for index, line in enumerate(capture.read_text().splitlines()):
            frame = json.loads(line)
            opcode = frame.get("opcode")
            if (
                frame.get("direction") != "in"
                or opcode not in {13078, 13873, 23548, 12393}
                or opcode in wanted
            ):
                continue
            body = base64.b64decode(frame["body_base64"], validate=True)
            if opcode == 13078 and (
                len(body) < 8
                or struct.unpack(">q", body[:8])[0] != wire.TEMPLATE_CHARACTER
            ):
                continue
            if opcode == 13873 and body[:8] != struct.pack(">II", 2, 0):
                continue
            wanted[opcode] = (index, frame, body)
        missing = {13078, 13873, 23548, 12393} - set(wanted)
        if missing:
            raise AssertionError(
                f"captured fixture lacks replay opcodes: {sorted(missing)}"
            )

        roster_body = wanted[23548][2]
        reader = Reader(roster_body)
        entries = [reader.take(reader.number("I")) for _ in range(reader.number("B"))]
        pekebu = [blob for blob in entries if b"Pekebu" in blob]
        if len(pekebu) != 1:
            raise AssertionError("captured character-list fixture has no unique Pekebu")
        characters_template = (
            b"\x01"
            + struct.pack(">I", len(pekebu[0]))
            + pekebu[0]
            + roster_body[reader.pos :]
        )
        selected = sorted(wanted.values(), key=lambda item: item[0])
        frames = [item[1] for item in selected]
        bodies = {opcode: item[2] for opcode, item in wanted.items()}
        return frames, bodies, characters_template

    def test_real_coders_preserve_shared_postgres_characters_and_packet_bytes(self):
        from unittest.mock import patch
        from wakfu_server import social, wire

        account_id = self.store.register("replay-hydration", "test-password")["id"]
        first = self.store.create_character(account_id, "Replay Hydration A")
        second = self.store.create_character(account_id, "Replay Hydration B")
        generation = self.store.begin_session(account_id)
        self.store.select_character(account_id, generation, first["id"])
        sheet = b"".join(
            wire.proto_field(tag, value)
            for tag, value in ((8, 1), (18, b"Owned slot"), (24, 1), (56, 0))
        )
        self.store.save_build(
            account_id,
            generation,
            first["id"],
            1,
            {"sheet": sheet, "equipment": b"", "deck": b"", "aptitudes": b""},
        )

        frames, bodies, characters_template = self._native_templates()

        # The reference models each handler doing its own independent SQL
        # hydration, then running the same production serializers.
        expected = []
        reference_collections = []
        for frame in frames:
            opcode = frame["opcode"]
            original = bodies[opcode]
            owned = self.store.characters(account_id)
            before = deepcopy(owned)
            reference_collections.append((owned, before))
            if opcode == 13873:
                expected.append(
                    (opcode, social.adapt(opcode, original, account_id, None, owned))
                )
            elif opcode == 13078:
                expected.extend(
                    (opcode, wire.adapt(opcode, original, account_id, character))
                    for character in owned
                )
            elif opcode == 23548:
                from wakfu_server.characters.selection_capacity import packet

                expected.append(packet(self.store.max_characters))
                expected.append(
                    (
                        opcode,
                        wire.character_list(characters_template, account_id, owned),
                    )
                )
            elif opcode == 12393:
                expected.append((opcode, wire.attribute_sheets(original, owned)))
        for collection, original in reference_collections:
            self.assertEqual(collection, original)

        fixture_frames = [
            {
                "direction": "in",
                "opcode": frame["opcode"],
                "body_base64": frame["body_base64"],
            }
            for frame in frames
        ]
        held_collections = []
        query_characters = self.store.characters

        def tracked_characters(requested_account):
            collection = query_characters(requested_account)
            held_collections.append((collection, deepcopy(collection)))
            return collection

        actual = []
        replay = _production_replay(
            {
                "FRAMES": fixture_frames,
                "STORE": self.store,
                "wire": wire,
                "social": social,
                "CHARACTERS": characters_template,
                "send": lambda connection, service, opcode, body: actual.append(
                    (opcode, body)
                ),
            }
        )
        with patch.object(
            self.store, "characters", side_effect=tracked_characters
        ) as hydration:
            replay(object(), 0, len(fixture_frames), account_id)

        self.assertEqual(hydration.call_count, 1)
        self.assertEqual(len(held_collections), 1)
        self.assertEqual(held_collections[0][0], held_collections[0][1])
        self.assertEqual(actual, expected)

        from protocol_codec import Reader

        attribute_packet = next(body for opcode, body in actual if opcode == 12393)
        reader = Reader(attribute_packet)
        sets = list(wire.proto_fields(reader.take(reader.number("I"))))
        reader.finish()
        registries = [
            list(wire.proto_fields(value)) for tag, value in sets if tag == 10
        ]
        indices = [
            [dict(wire.proto_fields(entry))[8] for tag, entry in registry if tag == 10]
            for registry in registries
        ]
        owner_ids = [dict(registry)[16] for registry in registries]
        self.assertEqual(indices, [[0, 1], [0]])
        self.assertEqual(owner_ids, [first["id"], second["id"]])


if __name__ == "__main__":
    unittest.main()
