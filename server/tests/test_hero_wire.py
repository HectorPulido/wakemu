import struct
import unittest
from wakfu_server.characters import hero_wire
from wakfu_server.characters.hero_wire import (
    add_request,
    switch_request,
    added_success,
    company,
    configuration,
)


class HeroWireTests(unittest.TestCase):
    def test_same_map_native_switch_does_not_reset_master_scene_or_double_activate(
        self,
    ):
        import ast
        from pathlib import Path

        tree = ast.parse(
            Path(__file__)
            .resolve()
            .parents[1]
            .joinpath("local_game_server.py")
            .read_text()
        )
        branch = next(
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.If) and "opcode == 12006" in ast.unparse(node.test)
        )
        calls = [
            node
            for statement in branch.body
            for node in ast.walk(statement)
            if isinstance(node, ast.Call)
        ]
        names = [ast.unparse(call.func) for call in calls]
        self.assertNotIn("join_world", names)
        self.assertEqual(1, names.count("hero_wire.refresh"))
        for forbidden in (
            "owned_native_bootstrap",
            "publish_heroes",
            "mark_static_sync_pending",
        ):
            self.assertNotIn(forbidden, names)
        self.assertIn("heroes.switch_main", names)
        self.assertIn("hero_wire.switched_result", names)
        self.assertIn("hero_wire.statistics", names)
        completion = next(
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.If) and "opcode == 12054" in ast.unparse(node.test)
        )
        completion_calls = [
            node
            for statement in completion.body
            for node in ast.walk(statement)
            if isinstance(node, ast.Call)
        ]
        join = next(
            call for call in completion_calls if ast.unparse(call.func) == "join_world"
        )
        context = next(
            call
            for call in completion_calls
            if ast.unparse(call.func) == "wire.adapt"
            and isinstance(call.args[0], ast.Constant)
            and call.args[0].value == 15548
        )
        self.assertEqual("fixture(15548)", ast.unparse(context.args[1]))
        self.assertEqual("character", ast.unparse(context.args[3]))
        self.assertLess(context.lineno, join.lineno)
        self.assertTrue(
            any(
                keyword.arg == "hydrate_heroes" and keyword.value.value is False
                for keyword in join.keywords
            )
        )
        self.assertTrue(
            any(
                ast.unparse(call.func) == "synchronization" for call in completion_calls
            )
        )

    def test_switch_ack_uses_native_zero_success_and_exact_target(self):
        self.assertEqual(
            (13440, struct.pack(">Bq", 0, 42)), hero_wire.switched_result(42)
        )
        for identity, result in ((0, 0), (-1, 0), (42, -1), (42, 7)):
            with self.assertRaises(ValueError):
                hero_wire.switched_result(identity, result)

    def test_owned_entity_hydrates_each_heroes_spellbook_and_saved_deck(self):
        import hashlib
        from unittest.mock import patch
        from wakfu_server import wire
        from wakfu_server.spells import spell_inventory
        from wakfu_server.builds import deck_collection

        template = b"\x0a" + bytes(12)
        layout = {
            "template_sha256": hashlib.sha256(template).hexdigest(),
            "sections": [
                {"name": "SPELL_INVENTORY", "start": 1, "end": 5},
                {"name": "SPELL_DECK", "start": 5, "end": 9},
                {"name": "NATION_ID", "start": 9, "end": 13},
            ],
        }
        books = []
        for identity, breed in ((41, 1), (42, 8)):
            character = {
                "id": identity,
                "breed": breed,
                "level": 60,
                "builds": {0: {"deck": "0000000000000000ffffffff"}},
            }
            with patch.dict(wire.ENTITY_LAYOUTS, {10: layout}):
                actual = wire.minimal_entity(template, character)
            book = spell_inventory(character)
            self.assertEqual(
                b"\x0a" + book + deck_collection(character) + bytes(4), actual
            )
            self.assertGreater(struct.unpack_from(">H", book)[0], 0)
            self.assertEqual(identity, struct.unpack_from(">q", book, 2)[0] >> 32)
            books.append(book)
        self.assertNotEqual(*books)

    def test_owned_entity_hp_replaces_capture_with_effective_owned_health(self):
        import hashlib
        from unittest.mock import patch
        from wakfu_server import wire

        template = b"\x0a" + struct.pack(">i", 3084)
        layout = {
            "template_sha256": hashlib.sha256(template).hexdigest(),
            "sections": [{"name": "HP", "start": 1, "end": 5}],
        }
        with patch.dict(wire.ENTITY_LAYOUTS, {10: layout}), patch(
            "wakfu_server.equipment_stats.effective_character",
            return_value={"hp": 41},
        ):
            actual = wire.minimal_entity(template, {"level": 60})
        self.assertEqual(b"\x0a" + struct.pack(">i", 41), actual)

    def test_cue_activation_contains_entity_build_and_aptitude_blocks(self):
        import struct
        from unittest.mock import patch

        character = {"id": 42, "account_id": 7}
        refresh_body = struct.pack(">qh", 42, 6) + b"entity"
        with patch.object(
            hero_wire, "refresh", return_value=(13046, refresh_body)
        ), patch("wakfu_server.builds.build_set", return_value=b"build"), patch(
            "wakfu_server.builds.aptitude_registry", return_value=b"aptitude"
        ):
            opcode, body = hero_wire.activate(b"template", character)

        self.assertEqual(12093, opcode)
        blocks = []
        offset = 0
        while offset < len(body):
            size = struct.unpack_from(">I", body, offset)[0]
            offset += 4
            blocks.append(body[offset : offset + size])
            offset += size
        self.assertEqual([b"entity", b"build", b"aptitude"], blocks)
        self.assertEqual(offset, len(body))

    def test_join_and_roster_publication_emit_native_activation(self):
        import ast
        from pathlib import Path

        source = (
            Path(__file__)
            .resolve()
            .parents[1]
            .joinpath("local_game_server.py")
            .read_text()
        )
        tree = ast.parse(source)
        join_world = next(
            node
            for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name == "join_world"
        )
        self.assertTrue(
            any(
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "activate"
                for node in ast.walk(join_world)
            )
        )
        publication = next(
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef) and node.name == "publish_heroes"
        )
        self.assertTrue(
            any(
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "activate"
                for node in ast.walk(publication)
            )
        )
        activations = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "activate"
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "hero_wire"
        ]
        self.assertEqual(2, len(activations))
        for call in activations:
            self.assertIsInstance(call.args[0], ast.Name)
            self.assertEqual("OWNED_HERO_TEMPLATE", call.args[0].id)
        refresh = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "refresh"
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "hero_wire"
        ]
        self.assertEqual(1, len(refresh))
        self.assertEqual("OWNED_HERO_TEMPLATE", refresh[0].args[0].id)
        for owner in (join_world, publication):
            calls = [
                node
                for node in ast.walk(owner)
                if isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "hero_wire"
            ]
            activation = next(call for call in calls if call.func.attr == "activate")
            statistics = next(call for call in calls if call.func.attr == "statistics")
            company = next(call for call in calls if call.func.attr == "company")
            self.assertLess(activation.lineno, statistics.lineno)
            self.assertLess(statistics.lineno, company.lineno)
            self.assertLess(
                activation.lineno,
                company.lineno,
                "Company must refresh rows after replacing active hero objects",
            )

    def test_native_cnY_exact_positive_character_identity(self):
        self.assertEqual(4, add_request(struct.pack(">q", 4)))
        for body in (
            b"",
            b"\0" * 7,
            b"\0" * 9,
            struct.pack(">q", 0),
            struct.pack(">q", -1),
            "invalid",
        ):
            with self.assertRaises(ValueError):
                add_request(body)

    def test_native_switch_ack_and_company_activation(self):
        self.assertEqual(4, switch_request(struct.pack(">q", 4)))
        self.assertEqual((12587, b"\x01"), added_success())
        opcode, body = company(2, 4)
        self.assertEqual(13873, opcode)
        self.assertEqual((1, 1, 2, 4, 0, 0, 0, 1, 1), struct.unpack(">IIqqiqIiB", body))

    def test_configuration_preserves_unrelated_overrides_and_replaces_hero_options(
        self,
    ):
        from protocol_codec import Reader

        payload = struct.pack(">IhI", 1, 99, 5) + b"other"
        opcode, body = configuration(struct.pack(">I", len(payload)) + payload)
        self.assertEqual(23053, opcode)
        outer = Reader(body)
        reader = Reader(outer.take(outer.number("I")))
        outer.finish()
        values = {}
        for _ in range(reader.number("I")):
            key = reader.number("h")
            values[key] = reader.take(reader.number("I")).decode()
        reader.finish()
        self.assertEqual(
            {99: "other", 431: "true", 602: "true", 603: "true", 622: "2"}, values
        )
        for invalid in (
            b"",
            body + b"\0",
            struct.pack(">I", 4) + struct.pack(">I", 4097),
        ):
            with self.assertRaises(ValueError):
                configuration(invalid)
