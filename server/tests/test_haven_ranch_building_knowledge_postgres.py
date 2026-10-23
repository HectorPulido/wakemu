"""Transactional tests for native bIA Ranch building learning."""
import ast
from copy import deepcopy
from pathlib import Path
import struct
import sys
from types import ModuleType
import uuid
from unittest.mock import patch

from postgres_case import PostgresCase
from wakfu_server.items import haven_ranch_building_knowledge as ranch


class RanchBuildingKnowledgePostgresTests(PostgresCase):
    def setUp(self):
        super().setUp()
        self.account = self.store.register("ranch_learning", "password-test")["id"]
        self.character = self.store.create_character(self.account, "Ranch Learner")
        self.generation = self.store.begin_session(self.account)
        self.store.select_character(self.account, self.generation, self.character["id"])

    def add_item(self, character_id=None, *, quantity=1, reference=33110):
        character_id = character_id or self.character["id"]
        with self.store.connection() as db:
            bag = db.execute(
                "SELECT uid FROM inventory_containers WHERE character_id=%s AND kind=0",
                (character_id,),
            ).fetchone()["uid"]
            slot = db.execute(
                "SELECT COALESCE(max(slot),-1)+1 AS slot FROM inventory_items WHERE container=%s",
                (bag,),
            ).fetchone()["slot"]
            return db.execute(
                "INSERT INTO inventory_items(character_id,reference,quantity,container,slot) "
                "VALUES(%s,%s,%s,%s,%s) RETURNING uid",
                (character_id, reference, quantity, bag, slot),
            ).fetchone()["uid"]

    def learn(
        self, uid, action=15152, *, account_id=None, generation=None, character_id=None
    ):
        from wakfu_server.items.cosmetic_learning import learn_item

        return learn_item(
            self.store,
            self.account if account_id is None else account_id,
            self.generation if generation is None else generation,
            self.character["id"] if character_id is None else character_id,
            struct.pack(">iq", action, uid),
        )

    def quantity(self, uid):
        with self.store.connection() as db:
            row = db.execute(
                "SELECT quantity FROM inventory_items WHERE uid=%s", (uid,)
            ).fetchone()
        return None if row is None else row["quantity"]

    def refs(self, account_id=None):
        with self.store.connection() as db:
            return [
                row["building_ref"]
                for row in db.execute(
                    "SELECT building_ref FROM account_ranch_building_knowledge "
                    "WHERE account_id=%s ORDER BY building_ref",
                    (self.account if account_id is None else account_id,),
                )
            ]

    def test_native_seed_learns_once_replays_and_is_account_isolated(self):
        uid = self.add_item(quantity=2)
        with self.store.connection() as db:
            seed = db.execute(
                "SELECT count(*) AS total, count(*) FILTER (WHERE minimum_level<>0) AS nonzero, "
                "count(*) FILTER (WHERE item_ref=33110 AND action_id=15152 "
                "AND profession_id=82 AND building_refs=ARRAY[16] AND native_class='bIA') AS target "
                "FROM native_ranch_building_learning_actions"
            ).fetchone()
        self.assertEqual((seed["total"], seed["nonzero"], seed["target"]), (119, 0, 1))

        first = self.learn(uid)
        self.assertTrue(first["applied"])
        self.assertEqual([packet[0] for packet in first["packets"]], [12470, 13873])
        self.assertEqual(first["packets"][0][1], struct.pack(">qh", uid, -1))
        self.assertEqual(self.quantity(uid), 1)
        self.assertEqual(self.refs(), [16])

        replay = self.learn(uid)
        self.assertFalse(replay["applied"])
        self.assertEqual([packet[0] for packet in replay["packets"]], [13873])
        self.assertEqual(self.quantity(uid), 1)
        self.assertEqual(self.refs(), [16])
        with self.reopen().connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM ranch_building_learning_receipts "
                    "WHERE account_id=%s AND source_uid=%s",
                    (self.account, uid),
                ).fetchone()["n"],
                1,
            )

        other = self.store.register("ranch_other", "password-test")["id"]
        self.assertEqual(self.refs(other), [])
        packet = ranch.packet(self.store, other)
        self.assertEqual(
            packet, (13873, struct.pack(">II", 1, 18) + ranch.library_payload([]))
        )

    def test_missing_published_target_rejects_learning_without_consuming_source(self):
        # Native records 119 bIA sources whose targets are absent from the
        # installed aMR catalog. Their exact source/action mapping remains
        # authoritative, but it must not consume an item or publish knowledge.
        with self.store.connection() as db:
            native = db.execute(
                "SELECT item_ref,action_id,building_refs FROM "
                "native_ranch_building_learning_actions "
                "WHERE item_ref=33319"
            ).fetchone()
        self.assertIsNotNone(native)
        self.assertEqual(native["building_refs"], [131])
        uid = self.add_item(reference=native["item_ref"])
        with self.assertRaisesRegex(
            ValueError, "no installed native building definition"
        ):
            self.learn(uid, action=native["action_id"])
        self.assertEqual(self.quantity(uid), 1)
        self.assertEqual(self.refs(), [])
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM ranch_building_learning_receipts "
                    "WHERE account_id=%s AND source_uid=%s",
                    (self.account, uid),
                ).fetchone()["n"],
                0,
            )

    def test_changed_published_definition_rejects_learning_atomically(self):
        from psycopg.types.json import Jsonb

        uid = self.add_item(reference=33110)
        with self.store.connection() as db:
            row = db.execute(
                "SELECT descriptor FROM native_ranch_building_definitions "
                "WHERE reference=16"
            ).fetchone()
            self.assertIsNotNone(row)
            altered = deepcopy(row["descriptor"])
            altered["epF"] = altered["epF"] + 1
            db.execute(
                "UPDATE native_ranch_building_definitions SET descriptor=%s "
                "WHERE reference=16",
                (Jsonb(altered),),
            )
        with self.assertRaisesRegex(ValueError, "definition has changed"):
            self.learn(uid)
        self.assertEqual(self.quantity(uid), 1)
        self.assertEqual(self.refs(), [])
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM ranch_building_learning_receipts "
                    "WHERE account_id=%s AND source_uid=%s",
                    (self.account, uid),
                ).fetchone()["n"],
                0,
            )

    def test_native_library_payload_matches_empty_sections_and_known_new_sets(self):
        expected = (
            struct.pack(">I", 8)
            + b"\x00" * 8
            + struct.pack(">I", 2)
            + b"\x00\x00"
            + struct.pack(">I", 16)
            + struct.pack(">IiIi", 1, 16, 1, 16)
        )
        self.assertEqual(ranch.library_payload([16]), expected)
        with self.assertRaises(ValueError):
            ranch.library_payload([16, 16])

    def test_wrong_action_criteria_and_profession_requirement_leave_item_untouched(
        self,
    ):
        uid = self.add_item()
        with self.assertRaisesRegex(ValueError, "Unsupported native Ranch"):
            self.learn(uid, action=15151)
        self.assertEqual(self.quantity(uid), 1)

        from wakfu_server import haven_bag_furniture_knowledge

        native_rules = dict(haven_bag_furniture_knowledge._rules())
        native_rules[33110] = dict(native_rules[33110], use_has_criteria=True)
        with patch.object(
            haven_bag_furniture_knowledge, "_rules", return_value=native_rules
        ):
            with self.assertRaisesRegex(ValueError, "criteria"):
                self.learn(uid)
        self.assertEqual(self.quantity(uid), 1)

        with self.store.connection() as db:
            db.execute(
                "UPDATE native_ranch_building_learning_actions SET minimum_level=1 "
                "WHERE item_ref=33110"
            )
            db.execute(
                "INSERT INTO account_professions(account_id,profession_id,xp) "
                "VALUES(%s,82,0) ON CONFLICT(account_id,profession_id) DO UPDATE SET xp=0",
                (self.account,),
            )
        with self.assertRaisesRegex(ValueError, "Profession level"):
            self.learn(uid)
        self.assertEqual(self.quantity(uid), 1)
        with self.store.connection() as db:
            db.execute(
                "UPDATE account_professions SET xp=75 WHERE account_id=%s AND profession_id=82",
                (self.account,),
            )
        self.assertTrue(self.learn(uid)["applied"])

    def test_foreign_missing_and_inactive_hero_item_uids_are_rejected(self):
        foreign_account = self.store.register("ranch_foreign", "password-test")["id"]
        foreign_character = self.store.create_character(foreign_account, "Foreign")
        foreign_generation = self.store.begin_session(foreign_account)
        self.store.select_character(
            foreign_account, foreign_generation, foreign_character["id"]
        )
        foreign_uid = self.add_item(foreign_character["id"])
        with self.assertRaises(ValueError):
            self.learn(foreign_uid)
        with self.assertRaises(ValueError):
            self.learn(9_999_999_999)
        self.assertEqual(self.quantity(foreign_uid), 1)

        hero = self.store.create_character(self.account, "Inactive Ranch Hero")
        hero_uid = self.add_item(hero["id"])
        with self.assertRaises(ValueError):
            self.learn(hero_uid)
        self.assertEqual(self.quantity(hero_uid), 1)

    def test_chest_custody_uid_is_not_treated_as_a_bag_item(self):
        from psycopg.types.json import Jsonb

        uid = self.add_item()
        with self.store.connection() as db:
            item = dict(
                db.execute(
                    "SELECT * FROM inventory_items WHERE uid=%s", (uid,)
                ).fetchone()
            )
            db.execute(
                "INSERT INTO account_haven_chests(account_id,compartment_id,items) "
                "VALUES(%s,%s,%s)",
                (
                    self.account,
                    uuid.uuid4(),
                    Jsonb([{"slot": 0, "item": item, "metadata": {}}]),
                ),
            )
            db.execute("DELETE FROM inventory_items WHERE uid=%s", (uid,))
        with self.assertRaises(ValueError):
            self.learn(uid)
        self.assertEqual(self.refs(), [])
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM ranch_building_learning_receipts "
                    "WHERE account_id=%s AND source_uid=%s",
                    (self.account, uid),
                ).fetchone()["n"],
                0,
            )

    def test_active_same_account_hero_can_learn_its_owned_item(self):
        from wakfu_server.characters.heroes import add

        hero = self.store.create_character(self.account, "Ranch Hero")
        add(self.store, self.account, self.generation, self.character["id"], hero["id"])
        uid = self.add_item(hero["id"])
        result = self.learn(uid)
        self.assertTrue(result["applied"])
        self.assertEqual(result["character"]["id"], hero["id"])
        self.assertEqual(self.quantity(uid), None)
        with self.store.connection() as db:
            receipt = db.execute(
                "SELECT character_id FROM ranch_building_learning_receipts "
                "WHERE account_id=%s AND source_uid=%s",
                (self.account, uid),
            ).fetchone()
        self.assertEqual(receipt["character_id"], hero["id"])

    def test_equipped_or_specific_data_item_is_not_consumed(self):
        uid = self.add_item()
        from wakfu_server import wire

        equipped = wire.proto_field(10, wire.proto_field(8, uid))
        with self.store.connection() as db:
            db.execute(
                "UPDATE character_builds SET equipment=%s WHERE character_id=%s "
                "AND build_index=0",
                (equipped, self.character["id"]),
            )
        with self.assertRaisesRegex(ValueError, "Unequip"):
            self.learn(uid)
        self.assertEqual(self.quantity(uid), 1)
        with self.store.connection() as db:
            db.execute(
                "UPDATE character_builds SET equipment=%s WHERE character_id=%s "
                "AND build_index=0",
                (b"", self.character["id"]),
            )
            db.execute(
                "INSERT INTO inventory_item_elements(uid,damage_elements,resistance_elements) "
                "VALUES(%s,0,0)",
                (uid,),
            )
        with self.assertRaisesRegex(ValueError, "specific data"):
            self.learn(uid)
        self.assertEqual(self.quantity(uid), 1)
        self.assertEqual(self.refs(), [])

    def test_bootstrap_routes_owned_component_18_after_furniture_and_suppresses_capture(
        self,
    ):
        source = Path(__file__).resolve().parents[1] / "local_game_server.py"
        module = ast.parse(source.read_text())
        nodes = [node for node in ast.walk(module) if isinstance(node, ast.If)]
        furniture = next(
            node
            for node in nodes
            if "original[:8] == struct.pack('>II', 1, 11)" in ast.unparse(node.test)
        )
        captured = next(
            node
            for node in nodes
            if "original[:8] == struct.pack('>II', 1, 18)" in ast.unparse(node.test)
        )
        furniture_code = ast.unparse(furniture)
        self.assertLess(
            furniture_code.index("furniture_account_packet"),
            furniture_code.index("ranch_building_account_packet"),
        )
        self.assertIn(
            "send(connection, 'world', *ranch_building_account_packet(STORE, account_id))",
            furniture_code,
        )
        self.assertIn("continue", ast.unparse(captured))

        learn_branch = next(
            node
            for node in nodes
            if "opcode == 13220" in ast.unparse(node.test)
            and "loaded" in ast.unparse(node.test)
            and "len(body) != 20" in ast.unparse(node.test)
        )
        learn_code = ast.unparse(learn_branch)
        self.assertIn("learn_item", learn_code)
        self.assertIn("result['packets']", learn_code)

        class ContinueAsBreak(ast.NodeTransformer):
            def visit_Continue(self, node):
                return ast.copy_location(ast.Break(), node)

        def execute_branch(branch, namespace):
            branch = ContinueAsBreak().visit(deepcopy(branch))
            wrapper = ast.While(
                test=ast.Constant(True),
                body=[branch, ast.Break()],
                orelse=[],
            )
            tree = ast.fix_missing_locations(
                ast.Module(body=[wrapper], type_ignores=[])
            )
            exec(compile(tree, str(source), "exec"), namespace)

        furniture_module = ModuleType("wakfu_server.haven_bag_furniture_knowledge")
        furniture_module.packet = lambda _store, _account: (13871, b"furniture")
        ranch_module = ModuleType("wakfu_server.haven_ranch_building_knowledge")
        ranch_module.packet = lambda _store, _account: (13873, b"owned-ranch")
        sent = []
        common = {
            "frame": {"opcode": 13873},
            "original": struct.pack(">II", 1, 11),
            "connection": object(),
            "STORE": object(),
            "account_id": 17,
            "send": lambda connection, service, opcode, body: sent.append(
                (service, opcode, body)
            ),
            "struct": struct,
        }
        with patch.dict(
            sys.modules,
            {
                "wakfu_server.haven_bag_furniture_knowledge": furniture_module,
                "wakfu_server.haven_ranch_building_knowledge": ranch_module,
            },
        ):
            execute_branch(furniture, dict(common))
        self.assertEqual(
            [(opcode, body) for _, opcode, body in sent],
            [(13871, b"furniture"), (13873, b"owned-ranch")],
        )

        sent.clear()
        captured_namespace = dict(common, original=struct.pack(">II", 1, 18))
        execute_branch(captured, captured_namespace)
        self.assertEqual(sent, [])

        learn_module = ModuleType("wakfu_server.cosmetic_learning")
        learn_calls = []
        saved = {"id": 41}
        learn_module.learn_item = lambda *args: (
            learn_calls.append(args)
            or {
                "character": saved,
                "packets": [(12470, b"consume"), (13873, b"known")],
                "applied": True,
            }
        )
        sent.clear()
        records = []
        learn_namespace = {
            "opcode": 13220,
            "loaded": True,
            "body": struct.pack(">iq", 15152, 99),
            "fight": None,
            "STORE": common["STORE"],
            "account_id": 17,
            "generation": "generation",
            "character": saved,
            "connection": common["connection"],
            "service": "world",
            "send": common["send"],
            "record": lambda **fields: records.append(fields),
            "refresh_owned_character": lambda value: value,
        }
        with patch.dict(sys.modules, {"wakfu_server.cosmetic_learning": learn_module}):
            learn_dispatch = deepcopy(learn_branch)
            learn_dispatch.orelse = []
            execute_branch(learn_dispatch, learn_namespace)
        self.assertEqual(len(learn_calls), 1)
        self.assertEqual([opcode for _, opcode, _ in sent], [12470, 13873])
        self.assertEqual(records, [{"event": "item_learned", "actor_id": 41}])
