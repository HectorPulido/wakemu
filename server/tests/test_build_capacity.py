import ast
from pathlib import Path
import unittest
from wakfu_server import health_policy
from wakfu_server.builds import capacity_message, valid_index, validate
from wakfu_server.wire import proto_field
from postgres_case import PostgresCase


def sheet(index, permanent=0):
    return b"".join(
        proto_field(k, v)
        for k, v in [(8, index), (18, b"Build"), (24, 100), (56, 1), (64, permanent)]
    )


def blobs(index, permanent=0):
    return dict(sheet=sheet(index, permanent), equipment=b"", deck=b"", aptitudes=b"")


def real_blobs(index):
    return dict(
        blobs(index),
        sheet=b"".join(
            proto_field(k, v)
            for k, v in [
                (8, index),
                (18, b"Owned"),
                (24, (1 << 64) - 1),
                (56, 1),
                (64, 0),
            ]
        ),
    )


class BuildCapacityTests(PostgresCase):
    def test_native_capacity_carrier_is_exact_for_one_and_default_twenty_four(self):
        key = b"non.permanent.build.limit"
        for limit, expected_hex in (
            (1, "00000019" + key.hex() + "0000000131"),
            (24, "00000019" + key.hex() + "000000023234"),
        ):
            with self.subTest(limit=limit):
                opcode, body = capacity_message({"non_permanent_build_limit": limit})
                self.assertEqual(opcode, 22318)
                self.assertEqual(body.hex(), expected_hex)

    def test_native_capacity_carrier_rejects_invalid_types_and_bounds(self):
        for value in (None, True, False, 0, -1, 25, 1.0, "1"):
            with self.subTest(value=value):
                with self.assertRaisesRegex(ValueError, "capacity"):
                    capacity_message({"non_permanent_build_limit": value})

    @staticmethod
    def deletion_handler_branch():
        """Compile and run the production 13169 branch without world bootstrap."""
        source = Path("/app/local_game_server.py").read_text()
        tree = ast.parse(source)
        branches = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.If)
            and isinstance(node.test, ast.BoolOp)
            and any(
                isinstance(value, ast.Compare)
                and isinstance(value.left, ast.Name)
                and value.left.id == "opcode"
                and any(
                    isinstance(part, ast.Constant) and part.value == 13169
                    for part in value.comparators
                )
                for value in node.test.values
            )
        ]
        if len(branches) != 1:
            raise AssertionError(
                f"expected one 13169 handler branch, found {len(branches)}"
            )
        branches[0].orelse = []
        names = (
            "opcode",
            "loaded",
            "body",
            "character",
            "account_id",
            "generation",
            "fight",
            "connection",
            "service",
            "bag_session",
            "STORE",
            "builds",
            "send",
            "record",
            "COMBAT_TEST_WP",
        )
        function = ast.FunctionDef(
            name="handle_deletion",
            args=ast.arguments(
                posonlyargs=[],
                args=[ast.arg(arg=name) for name in names],
                kwonlyargs=[],
                kw_defaults=[],
                defaults=[],
            ),
            body=[
                branches[0],
                ast.Return(value=ast.Name(id="character", ctx=ast.Load())),
            ],
            decorator_list=[],
        )
        module = ast.fix_missing_locations(ast.Module(body=[function], type_ignores=[]))
        namespace = {"builds": __import__("wakfu_server.builds", fromlist=["*"])}
        exec(compile(module, "server/local_game_server.py", "exec"), namespace)
        return namespace["handle_deletion"]

    @staticmethod
    def activation_handler_branch():
        """Compile and run the production 13776 branch without server startup."""
        source = Path("/app/local_game_server.py").read_text()
        tree = ast.parse(source)
        branches = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.If)
            and isinstance(node.test, ast.BoolOp)
            and any(
                isinstance(value, ast.Compare)
                and isinstance(value.left, ast.Name)
                and value.left.id == "opcode"
                and any(
                    isinstance(part, ast.Constant) and part.value == 13776
                    for part in value.comparators
                )
                for value in node.test.values
            )
        ]
        if len(branches) != 1:
            raise AssertionError(
                f"expected one 13776 handler branch, found {len(branches)}"
            )
        branches[0].orelse = []
        names = (
            "opcode",
            "loaded",
            "body",
            "character",
            "account_id",
            "generation",
            "fight",
            "connection",
            "service",
            "bag_session",
            "STORE",
            "builds",
            "send",
            "record",
            "COMBAT_TEST_WP",
        )
        function = ast.FunctionDef(
            name="handle_activation",
            args=ast.arguments(
                posonlyargs=[],
                args=[ast.arg(arg=name) for name in names],
                kwonlyargs=[],
                kw_defaults=[],
                defaults=[],
            ),
            body=[
                branches[0],
                ast.Return(value=ast.Name(id="character", ctx=ast.Load())),
            ],
            decorator_list=[],
        )
        module = ast.fix_missing_locations(ast.Module(body=[function], type_ignores=[]))
        namespace = {"builds": __import__("wakfu_server.builds", fromlist=["*"])}
        exec(compile(module, "server/local_game_server.py", "exec"), namespace)
        return namespace["handle_activation"]

    def dispatch_activation(self, body, *, fight=None, generation=None, character=None):
        sent, records = [], []
        handler = self.activation_handler_branch()
        character = handler(
            13776,
            True,
            body,
            self.char if character is None else character,
            self.account,
            self.generation if generation is None else generation,
            fight,
            object(),
            object(),
            None,
            self.store,
            __import__("wakfu_server.builds", fromlist=["*"]),
            lambda connection, service, opcode, payload: sent.append((opcode, payload)),
            lambda **event: records.append(event),
            6,
        )
        return character, sent, records

    def dispatch_deletion(self, body, *, fight=None, generation=None):
        sent, records = [], []
        handler = self.deletion_handler_branch()
        character = handler(
            13169,
            True,
            body,
            self.char,
            self.account,
            self.generation if generation is None else generation,
            fight,
            object(),
            object(),
            None,
            self.store,
            __import__("wakfu_server.builds", fromlist=["*"]),
            lambda connection, service, opcode, payload: sent.append((opcode, payload)),
            lambda **event: records.append(event),
            6,
        )
        return character, sent, records

    def setUp(self):
        super().setUp()
        self.account = self.store.register("handler-delete", "test-password")["id"]
        self.char = self.store.create_character(self.account, "Handler Delete")
        self.generation = self.store.begin_session(self.account)
        self.store.select_character(self.account, self.generation, self.char["id"])

    def test_sql_deletion_rolls_back_after_delete_and_selection_update(self):
        store = self.store
        account = store.register("delete-rollback", "test-password")["id"]
        char = store.create_character(account, "Delete Rollback")
        generation = store.begin_session(account)
        store.select_character(account, generation, char["id"])
        store.save_build(account, generation, char["id"], 1, real_blobs(1))
        before = store.activate_build(
            account, generation, char["id"], 1, in_fight=False
        )
        with store.connection() as db:
            db.execute(
                "CREATE FUNCTION fail_delete_health() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'Injected health write failure'; END $$"
            )
            db.execute(
                "CREATE TRIGGER fail_delete_health BEFORE UPDATE OF hp,max_hp ON characters FOR EACH ROW EXECUTE FUNCTION fail_delete_health()"
            )
        from psycopg.errors import RaiseException

        with self.assertRaisesRegex(RaiseException, "Injected"):
            store.delete_build(account, generation, char["id"], 1, in_fight=False)
        after = self.reopen().character(account, char["id"])
        for key in (
            "builds",
            "active_build_index",
            "build_selection_revision",
            "hp",
            "max_hp",
            "inventory_items",
        ):
            self.assertEqual(after[key], before[key])
        store.begin_session(account)
        with self.assertRaises(ValueError):
            store.delete_build(account, generation, char["id"], 1, in_fight=False)

    def test_sql_deletion_rejects_permanent_owned_sheet(self):
        store = self.store
        account = store.register("delete-permanent", "test-password")["id"]
        char = store.create_character(account, "Delete Permanent")
        generation = store.begin_session(account)
        store.select_character(account, generation, char["id"])
        # Permanent classification is provisioned by the server, not a client edit.
        data = real_blobs(3)
        data["sheet"] = b"".join(
            proto_field(k, v)
            for k, v in [
                (8, 3),
                (18, b"Permanent"),
                (24, (1 << 64) - 1),
                (56, 1),
                (64, 1),
            ]
        )
        with store.connection() as db:
            db.execute(
                "INSERT INTO character_builds VALUES(%s,%s,%s,%s,%s,%s)",
                (
                    char["id"],
                    3,
                    *(data[k] for k in ("sheet", "equipment", "deck", "aptitudes")),
                ),
            )
        with self.assertRaisesRegex(ValueError, "Permanent"):
            store.delete_build(account, generation, char["id"], 3, in_fight=False)
        self.assertIn(3, self.reopen().character(account, char["id"])["builds"])

    def test_sql_deletion_preserves_units_falls_back_and_rejects_replay(self):
        store = self.store
        account = store.register("delete-owner", "test-password")["id"]
        char = store.create_character(account, "Delete Owner")
        generation = store.begin_session(account)
        store.select_character(account, generation, char["id"])
        store.save_build(account, generation, char["id"], 1, real_blobs(1))
        store.activate_build(account, generation, char["id"], 1, in_fight=False)
        with store.connection() as db:
            current = store.character(account, char["id"], db)
            health_policy.apply(db, current, 7)
        before = store.character(account, char["id"])
        for index, combat in ((0, False), (1, True), (127, False)):
            with self.assertRaises(ValueError):
                store.delete_build(
                    account, generation, char["id"], index, in_fight=combat
                )
        after = store.delete_build(account, generation, char["id"], 1, in_fight=False)
        self.assertEqual((after["active_build_index"], after["hp"]), (0, 7))
        self.assertNotIn(1, after["builds"])
        self.assertEqual(after["inventory_items"], before["inventory_items"])
        self.assertEqual(
            after["build_selection_revision"], before["build_selection_revision"] + 1
        )
        restored = self.reopen().character(account, char["id"])
        self.assertEqual(restored["builds"], after["builds"])
        with self.assertRaises(ValueError):
            store.delete_build(account, generation, char["id"], 1, in_fight=False)

    def test_deleting_inactive_build_keeps_selection_health_and_wire_ack(self):
        import struct
        from wakfu_server import builds

        store = self.store
        account = store.register("delete-inactive", "test-password")["id"]
        char = store.create_character(account, "Delete Inactive")
        generation = store.begin_session(account)
        store.select_character(account, generation, char["id"])
        store.save_build(account, generation, char["id"], 1, real_blobs(1))
        store.save_build(account, generation, char["id"], 2, real_blobs(2))
        selected = store.activate_build(
            account, generation, char["id"], 2, in_fight=False
        )

        deleted = store.delete_build(account, generation, char["id"], 1, in_fight=False)
        self.assertNotIn(1, deleted["builds"])
        self.assertIn(2, deleted["builds"])
        self.assertEqual(
            (
                deleted["active_build_index"],
                deleted["build_selection_revision"],
                deleted["hp"],
                deleted["max_hp"],
            ),
            (
                2,
                selected["build_selection_revision"],
                selected["hp"],
                selected["max_hp"],
            ),
        )
        self.assertEqual(
            builds.deletion_message(char["id"], 1, failed=False),
            (12837, struct.pack(">qbB", char["id"], 1, 0)),
        )
        self.assertEqual(
            builds.selection_message(deleted),
            (13811, struct.pack(">qb", char["id"], 2)),
        )
        reopened = self.reopen().character(account, char["id"])
        self.assertEqual(reopened["builds"], deleted["builds"])
        self.assertEqual(reopened["active_build_index"], 2)

    def test_foreign_and_malformed_deletion_requests_get_failure_response_only(self):
        import struct
        from wakfu_server import builds

        account = self.store.register("delete-request", "test-password")["id"]
        char = self.store.create_character(account, "Delete Request")
        generation = self.store.begin_session(account)
        self.store.select_character(account, generation, char["id"])
        self.store.save_build(account, generation, char["id"], 1, real_blobs(1))
        before = self.store.character(account, char["id"])

        foreign = self.store.register("foreign-delete", "test-password")["id"]
        foreign_char = self.store.create_character(foreign, "Foreign Delete")
        foreign_generation = self.store.begin_session(foreign)
        self.store.select_character(foreign, foreign_generation, foreign_char["id"])
        self.store.save_build(
            foreign, foreign_generation, foreign_char["id"], 1, real_blobs(1)
        )

        foreign_body = struct.pack(">qb", foreign_char["id"], 1)
        actor, index = builds.decode_deletion(foreign_body)
        self.assertNotEqual(actor, char["id"])
        with self.assertRaises(ValueError):
            self.store.delete_build(account, generation, actor, index, in_fight=False)
        malformed_body = struct.pack(">qb", char["id"], 1) + b"extra"
        with self.assertRaises(ValueError):
            builds.decode_deletion(malformed_body)

        failure = builds.deletion_message(char["id"], 1, failed=True)
        self.assertEqual(failure[0], 12837)
        self.assertEqual(failure[1][-1], 1)
        current = self.store.character(account, char["id"])
        self.assertEqual(current["builds"], before["builds"])
        self.assertEqual(current["active_build_index"], before["active_build_index"])
        foreign_current = self.store.character(foreign, foreign_char["id"])
        self.assertEqual(foreign_current["builds"], {1: foreign_current["builds"][1]})

    def test_production_handler_success_ack_precedes_selection_and_stats(self):
        import struct
        from wakfu_server import builds
        from wakfu_server.inventory_items import grant
        from wakfu_server.progression import level_xp
        from wakfu_server.wire import proto_field

        with self.store.connection() as db:
            db.execute("UPDATE characters SET level=20 WHERE id=%s", (self.char["id"],))
            db.execute(
                "UPDATE character_progression SET xp=%s WHERE character_id=%s",
                (level_xp(20), self.char["id"]),
            )
        current = self.store.character(self.account, self.char["id"])
        item = grant(
            self.store,
            self.account,
            self.generation,
            self.char["id"],
            reference=2022,
            quantity=1,
            container=current["inventory_containers"][0]["uid"],
            slot=0,
            allowed_references={2022},
        )
        data = real_blobs(1)
        data["equipment"] = proto_field(
            10, proto_field(8, item["uid"]) + proto_field(16, 7)
        )
        self.store.save_build(self.account, self.generation, self.char["id"], 1, data)
        selected = self.store.activate_build(
            self.account, self.generation, self.char["id"], 1, in_fight=False
        )
        self.char = self.store.character(self.account, self.char["id"])
        character, sent, records = self.dispatch_deletion(
            struct.pack(">qb", self.char["id"], 1)
        )
        self.assertEqual([opcode for opcode, _ in sent[:2]], [12837, 13811])
        self.assertEqual(
            sent[0], builds.deletion_message(self.char["id"], 1, failed=False)
        )
        self.assertEqual(sent[1], builds.selection_message(character))
        self.assertEqual(character["active_build_index"], 0)
        self.assertEqual(
            character["build_selection_revision"],
            selected["build_selection_revision"] + 1,
        )
        self.assertEqual(sent[-1][0], 13046)
        self.assertEqual(character["inventory_items"], [item])
        self.assertEqual(records[-1]["event"], "build_deleted")

    def test_production_handler_rejects_bad_requests_and_replays_with_owned_failure_ack(
        self,
    ):
        import struct
        from wakfu_server import builds

        self.store.save_build(
            self.account, self.generation, self.char["id"], 1, real_blobs(1)
        )
        foreign = self.store.register("foreign-handler", "test-password")["id"]
        foreign_char = self.store.create_character(foreign, "Foreign Handler")
        foreign_generation = self.store.begin_session(foreign)
        self.store.select_character(foreign, foreign_generation, foreign_char["id"])
        self.store.save_build(
            foreign, foreign_generation, foreign_char["id"], 1, real_blobs(1)
        )
        permanent = real_blobs(3)
        permanent["sheet"] = b"".join(
            proto_field(tag, value)
            for tag, value in [
                (8, 3),
                (18, b"Permanent"),
                (24, (1 << 64) - 1),
                (56, 1),
                (64, 1),
            ]
        )
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO character_builds VALUES(%s,%s,%s,%s,%s,%s)",
                (
                    self.char["id"],
                    3,
                    *(
                        permanent[key]
                        for key in ("sheet", "equipment", "deck", "aptitudes")
                    ),
                ),
            )
        self.char = self.store.character(self.account, self.char["id"])
        expected = self.store.character(self.account, self.char["id"])
        active_wire = struct.pack(">qb", self.char["id"], 1)
        foreign_wire = struct.pack(">qb", foreign_char["id"], 1)
        malformed_wire = active_wire + b"!"
        default_wire = struct.pack(">qb", self.char["id"], 0)
        permanent_wire = struct.pack(">qb", self.char["id"], 3)
        absent_wire = struct.pack(">qb", self.char["id"], 127)

        for request, requested_index in (
            (foreign_wire, 1),
            (malformed_wire, 0),
            (default_wire, 0),
            (permanent_wire, 3),
            (absent_wire, 127),
        ):
            with self.subTest(request=request):
                character, sent, records = self.dispatch_deletion(request)
                self.assertEqual(
                    sent,
                    [
                        builds.deletion_message(
                            self.char["id"], requested_index, failed=True
                        )
                    ],
                )
                self.assertEqual(character["builds"], expected["builds"])
                self.assertEqual(records[-1]["event"], "build_deletion_rejected")

        first_character, first_sent, _ = self.dispatch_deletion(active_wire)
        self.assertEqual(first_sent[0][1][-1], 0)
        self.assertNotIn(1, first_character["builds"])
        self.char = first_character
        replay_character, replay_sent, replay_records = self.dispatch_deletion(
            active_wire
        )
        self.assertEqual(
            replay_sent, [builds.deletion_message(self.char["id"], 1, failed=True)]
        )
        self.assertEqual(replay_character["builds"], first_character["builds"])
        self.assertEqual(replay_records[-1]["event"], "build_deletion_rejected")

    def test_production_handler_combat_and_replaced_lease_fail_without_mutation(self):
        import struct
        from wakfu_server import builds

        self.store.save_build(
            self.account, self.generation, self.char["id"], 1, real_blobs(1)
        )
        self.char = self.store.character(self.account, self.char["id"])
        body = struct.pack(">qb", self.char["id"], 1)
        before = self.store.character(self.account, self.char["id"])
        character, sent, records = self.dispatch_deletion(body, fight=object())
        self.assertEqual(
            sent, [builds.deletion_message(self.char["id"], 1, failed=True)]
        )
        self.assertEqual(character["builds"], before["builds"])
        self.assertEqual(records[-1]["event"], "build_deletion_rejected")

    def test_production_activation_handler_persists_ack_snapshot_and_replay(self):
        import struct
        from wakfu_server import builds
        from wakfu_server.wire import proto_fields

        self.store.save_build(
            self.account, self.generation, self.char["id"], 1, real_blobs(1)
        )
        with self.store.connection() as db:
            current = self.store.character(self.account, self.char["id"], db)
            health_policy.apply(db, current, 7)
        self.char = self.store.character(self.account, self.char["id"])
        request = struct.pack(">qb", self.char["id"], 1)

        selected, sent, records = self.dispatch_activation(request)
        self.assertEqual(sent[0], builds.selection_message(selected))
        self.assertEqual(sent[0][0], 13811)
        self.assertEqual([opcode for opcode, _ in sent[1:]], [13046])
        self.assertEqual(
            (
                selected["active_build_index"],
                selected["build_selection_revision"],
                selected["hp"],
            ),
            (1, 1, 7),
        )
        self.assertEqual(records[-1]["event"], "build_activated")
        self.assertEqual(records[-1]["revision"], 1)

        self.char = selected
        repeated, repeated_packets, repeated_records = self.dispatch_activation(request)
        self.assertEqual(repeated["build_selection_revision"], 1)
        self.assertEqual(repeated_packets[0], builds.selection_message(repeated))
        self.assertEqual(repeated_packets[0][0], 13811)
        self.assertEqual([opcode for opcode, _ in repeated_packets[1:]], [13046])
        self.assertEqual(repeated_records[-1]["revision"], 1)

        reopened = self.reopen().character(self.account, self.char["id"])
        self.assertEqual(
            (
                reopened["active_build_index"],
                reopened["build_selection_revision"],
                reopened["hp"],
            ),
            (1, 1, 7),
        )
        self.assertEqual(dict(proto_fields(builds.build_set(reopened, b"")))[8], 1)

    def test_production_activation_handler_rejections_preserve_selection_and_hp(self):
        import struct
        from wakfu_server import builds

        self.store.save_build(
            self.account, self.generation, self.char["id"], 1, real_blobs(1)
        )
        with self.store.connection() as db:
            current = self.store.character(self.account, self.char["id"], db)
            health_policy.apply(db, current, 7)
        self.char = self.store.character(self.account, self.char["id"])
        before = self.store.character(self.account, self.char["id"])
        foreign = self.store.register("foreign-activation", "test-password")["id"]
        foreign_char = self.store.create_character(foreign, "Foreign Activation")

        rejected = (
            (struct.pack(">qb", foreign_char["id"], 1), None, self.generation),
            (struct.pack(">qb", self.char["id"], 127), None, self.generation),
            (struct.pack(">qb", self.char["id"], 1), object(), self.generation),
            (struct.pack(">qb", self.char["id"], 1), None, "stale-generation"),
        )
        for body, fight, generation in rejected:
            with self.subTest(body=body, in_fight=fight is not None):
                character, sent, records = self.dispatch_activation(
                    body, fight=fight, generation=generation
                )
                self.assertEqual(sent, [builds.selection_message(before)])
                self.assertEqual(
                    character["active_build_index"], before["active_build_index"]
                )
                self.assertEqual(
                    character["build_selection_revision"],
                    before["build_selection_revision"],
                )
                self.assertEqual(character["hp"], before["hp"])
                self.assertEqual(records[-1]["event"], "build_activation_rejected")

        reopened = self.reopen().character(self.account, self.char["id"])
        self.assertEqual(
            (
                reopened["active_build_index"],
                reopened["build_selection_revision"],
                reopened["hp"],
            ),
            (
                before["active_build_index"],
                before["build_selection_revision"],
                before["hp"],
            ),
        )

        stale_generation = self.generation
        self.generation = self.store.begin_session(self.account)
        self.store.select_character(self.account, self.generation, self.char["id"])
        character, sent, records = self.dispatch_deletion(
            body, generation=stale_generation
        )
        self.assertEqual(
            sent, [builds.deletion_message(self.char["id"], 1, failed=True)]
        )
        self.assertEqual(character["builds"], before["builds"])
        self.assertEqual(records[-1]["event"], "build_deletion_rejected")

    def test_sparse_index_and_native_byte_boundaries(self):
        for index in (3, 24, 127):
            validate({"level": 100, "builds": {}}, index, blobs(index))
        for index in (-1, 128, True, 1.0):
            self.assertFalse(valid_index(index))

    def test_capacity_is_count_not_max_index(self):
        saved = {i: {k: v.hex() for k, v in blobs(i).items()} for i in range(1, 25)}
        character = {"level": 100, "builds": saved}
        validate(character, 24, blobs(24))
        with self.assertRaisesRegex(ValueError, "capacity"):
            validate(character, 127, blobs(127))
        with self.assertRaisesRegex(ValueError, "permanent"):
            validate(character, 127, blobs(127, 1))

    def test_permanent_classification_cannot_be_removed(self):
        saved = {3: {k: v.hex() for k, v in blobs(3, 1).items()}}
        character = {"level": 100, "builds": saved}
        validate(character, 3, blobs(3, 1))
        with self.assertRaisesRegex(ValueError, "classification"):
            validate(character, 3, blobs(3, 0))

    def test_database_capacity_controls_validation_and_reopen(self):
        store = self.store
        account = store.register("capacity-owner", "test-password")["id"]
        character = store.create_character(account, "Capacity Owner")
        with store.connection() as db:
            db.execute(
                "UPDATE settings SET value='1' WHERE name='non_permanent_build_limit'"
            )
        current = self.reopen().character(account, character["id"])
        self.assertEqual(current["non_permanent_build_limit"], 1)
        validate(dict(current, level=100), 1, blobs(1))
        with self.assertRaisesRegex(ValueError, "capacity"):
            validate(
                dict(
                    current,
                    level=100,
                    builds={1: {k: v.hex() for k, v in blobs(1).items()}},
                ),
                3,
                blobs(3),
            )
        with store.connection() as db:
            db.execute(
                "UPDATE settings SET value='25' WHERE name='non_permanent_build_limit'"
            )
        with self.assertRaisesRegex(ValueError, "capacity"):
            store.character(account, character["id"])

    def test_database_capacity_rejects_save_without_partial_insert(self):
        account = self.account
        character = self.char
        with self.store.connection() as db:
            db.execute(
                "UPDATE settings SET value='1' WHERE name='non_permanent_build_limit'"
            )
        self.store.save_build(
            account, self.generation, character["id"], 1, real_blobs(1)
        )
        with self.assertRaisesRegex(ValueError, "capacity"):
            self.store.save_build(
                account, self.generation, character["id"], 2, real_blobs(2)
            )
        reopened = self.reopen().character(account, character["id"])
        self.assertEqual(set(reopened["builds"]), {1})

    def test_high_index_save_reopen_and_effective_stats(self):
        from wakfu_server.equipment_stats import bonuses

        store = self.store
        account = store.register("sparse-build-owner", "test-password")["id"]
        character = store.create_character(account, "Sparse Build Owner")
        generation = store.begin_session(account)
        store.select_character(account, generation, character["id"])
        data = blobs(127)
        data["sheet"] = b"".join(
            proto_field(k, v)
            for k, v in [(8, 127), (18, b"Sparse"), (24, 1), (56, 1), (64, 0)]
        )
        saved = store.save_build(account, generation, character["id"], 127, data)
        reopened = self.reopen().character(account, character["id"])
        self.assertEqual(saved["builds"], reopened["builds"])
        bonuses(reopened, build_index=127)
        with self.assertRaises(ValueError):
            bonuses(reopened, build_index=128)

    def test_metadata_equipment_and_aptitudes_share_catalog(self):
        from wakfu_server import builds
        from wakfu_server.wire import proto_fields

        character = {
            "id": 7,
            "level": 100,
            "builds": {127: {k: v.hex() for k, v in blobs(127).items()}},
        }
        metadata = [
            dict(proto_fields(v))[8]
            for t, v in proto_fields(builds.build_set(character, b""))
            if t == 18
        ]
        equipment = [
            dict(proto_fields(v))[8]
            for t, v in proto_fields(builds.equipment_registry(character))
            if t == 10
        ]
        aptitudes = [
            dict(proto_fields(v))[8]
            for t, v in proto_fields(builds.aptitude_registry(character))
            if t == 18
        ]
        self.assertEqual(metadata, [0, 127])
        self.assertEqual(equipment, metadata)
        self.assertEqual(aptitudes, metadata)
        with self.assertRaises(ValueError):
            builds.catalog_indices(dict(character, builds={128: {}}))

    def test_save_response_publishes_new_owned_registry_entries(self):
        import struct
        from wakfu_server import builds
        from wakfu_server.wire import proto_fields

        character = {
            "id": 7,
            "account_id": 9,
            "map_id": 1134,
            "instance_id": 0,
            "direction": 3,
            "x": 0,
            "y": 0,
            "z": 0,
            "name": "Registry Owner",
            "level": 100,
            "breed": 8,
            "hp": 500,
            "max_hp": 500,
            "builds": {127: {k: v.hex() for k, v in blobs(127).items()}},
        }
        packets = builds.response_messages(character, 127, wp=6)
        self.assertEqual([op for op, _ in packets], [12284, 12393, 12103, 13046])
        registry = packets[1][1]
        self.assertEqual(struct.unpack(">I", registry[:4])[0], len(registry) - 4)
        entries = list(proto_fields(dict(proto_fields(registry[4:]))[10]))
        self.assertEqual(dict(entries)[16], 7)
        self.assertEqual(
            [dict(proto_fields(v))[8] for t, v in entries if t == 10], [0, 127]
        )
        aptitudes = packets[2][1]
        self.assertEqual(struct.unpack(">qI", aptitudes[:12]), (7, len(aptitudes) - 12))

    def test_persisted_selection_is_encoded_on_reconnect(self):
        from wakfu_server import builds
        from wakfu_server.wire import proto_fields

        store = self.store
        account = store.register("selected-owner", "test-password")["id"]
        character = store.create_character(account, "Selected Owner")
        self.assertEqual(character["active_build_index"], 0)
        generation = store.begin_session(account)
        store.select_character(account, generation, character["id"])
        store.save_build(account, generation, character["id"], 1, real_blobs(1))
        with store.connection() as db:
            db.execute(
                "UPDATE character_build_selection SET active_index=1,revision=1 WHERE character_id=%s",
                (character["id"],),
            )
        reopened = self.reopen().character(account, character["id"])
        self.assertEqual(
            (reopened["active_build_index"], reopened["build_selection_revision"]),
            (1, 1),
        )
        self.assertEqual(dict(proto_fields(builds.build_set(reopened, b"")))[8], 1)
        with store.connection() as db:
            db.execute(
                "UPDATE character_build_selection SET active_index=127 WHERE character_id=%s",
                (character["id"],),
            )
        with self.assertRaisesRegex(ValueError, "missing"):
            store.character(account, character["id"])

    def test_activation_is_lease_checked_idempotent_and_never_heals(self):
        store = self.store
        account = store.register("activate-owner", "test-password")["id"]
        char = store.create_character(account, "Activate Owner")
        generation = store.begin_session(account)
        store.select_character(account, generation, char["id"])
        with store.connection() as db:
            current = store.character(account, char["id"], db)
            health_policy.apply(db, current, 7)
        store.save_build(account, generation, char["id"], 1, real_blobs(1))
        first = store.activate_build(account, generation, char["id"], 1, in_fight=False)
        self.assertEqual(
            (
                first["active_build_index"],
                first["build_selection_revision"],
                first["hp"],
            ),
            (1, 1, 7),
        )
        repeat = store.activate_build(
            account, generation, char["id"], 1, in_fight=False
        )
        self.assertEqual(repeat["build_selection_revision"], 1)
        for index, combat in [(127, False), (0, True)]:
            with self.assertRaises(ValueError):
                store.activate_build(
                    account, generation, char["id"], index, in_fight=combat
                )
        store.begin_session(account)
        with self.assertRaises(ValueError):
            store.activate_build(account, generation, char["id"], 0, in_fight=False)
        reopened = self.reopen().character(account, char["id"])
        self.assertEqual((reopened["active_build_index"], reopened["hp"]), (1, 7))

    def test_activation_wire_and_authoritative_selection(self):
        import struct
        from wakfu_server import builds

        self.assertEqual(builds.decode_activation(struct.pack(">qb", 7, 127)), (7, 127))
        for body in (
            b"",
            struct.pack(">qb", 7, -1),
            struct.pack(">qb", 0, 1),
            struct.pack(">qb", 7, 1) + b"x",
        ):
            with self.assertRaises(ValueError):
                builds.decode_activation(body)
        self.assertEqual(
            builds.selection_message(
                {
                    "id": 7,
                    "active_build_index": 1,
                    "builds": {1: {k: v.hex() for k, v in real_blobs(1).items()}},
                }
            ),
            (13811, struct.pack(">qb", 7, 1)),
        )

    def test_deletion_wire_error_flag_and_strict_request(self):
        import struct
        from wakfu_server import builds

        self.assertEqual(builds.decode_deletion(struct.pack(">qb", 7, 127)), (7, 127))
        for body in (b"", struct.pack(">qb", 7, -1), struct.pack(">qb", 7, 1) + b"x"):
            with self.assertRaises(ValueError):
                builds.decode_deletion(body)
        self.assertEqual(
            builds.deletion_message(7, 127, failed=False),
            (12837, struct.pack(">qbB", 7, 127, 0)),
        )
        self.assertEqual(builds.deletion_message(7, 127, failed=True)[1][-1], 1)
        with self.assertRaises(ValueError):
            builds.deletion_message(7, 127, failed=1)

    def test_effective_sheet_level_preserves_modulation_on_level_up(self):
        from wakfu_server import builds

        saved = {3: {k: v.hex() for k, v in blobs(3).items()}}
        saved[3]["sheet"] = b"".join(
            proto_field(k, v)
            for k, v in [(8, 3), (18, b"Fixed49"), (24, 49), (56, 1), (64, 0)]
        ).hex()
        character = {"level": 50, "builds": saved}
        self.assertEqual(builds.effective_sheet_level(character, 3), 49)
        self.assertEqual(builds.effective_sheet_level(character, 0), 50)
        saved[3]["sheet"] = proto_field(24, (1 << 64) - 1).hex()
        self.assertEqual(builds.effective_sheet_level(character, 3), 50)
        saved[3]["sheet"] = proto_field(24, 51).hex()
        with self.assertRaises(ValueError):
            builds.effective_sheet_level(character, 3)
