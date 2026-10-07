import ast
import copy
from datetime import datetime, timedelta, timezone
import hashlib
import struct
import uuid
from pathlib import Path
from unittest.mock import patch

import unittest
from psycopg.types.json import Jsonb

from postgres_case import PostgresCase
from wakfu_server import mount_codec, mount_inventory, mount_state, wire
from wakfu_server.inventory_items import grant
from wakfu_server.profession_store import ensure_learned
from wakfu_server import resource_collect


class MountPublicationTests(PostgresCase):
    def setUp(self):
        super().setUp()
        self.now = datetime(2034, 2, 3, 4, 5, 6, tzinfo=timezone.utc)
        self.store.clock = lambda: self.now.timestamp()
        self.account = self.store.register(
            "mountpub_" + uuid.uuid4().hex[:12], "test-password"
        )["id"]
        self.character = self.store.create_character(self.account, "Mount Publisher")
        self.generation = self.store.begin_session(self.account)
        self.store.select_character(self.account, self.generation, self.character["id"])
        with self.store.connection() as db:
            db.execute(
                "UPDATE characters SET level=35 WHERE id=%s",
                (self.character["id"],),
            )

    def _grant_mount(self, reference=18682, slot=0):
        character = self.store.character(self.account, self.character["id"])
        return grant(
            self.store,
            self.account,
            self.generation,
            self.character["id"],
            reference=reference,
            quantity=1,
            container=character["inventory_containers"][0]["uid"],
            slot=slot,
            allowed_references={18682, 18704, 18705, 18706},
        )

    @staticmethod
    def _build(index, uid=None, name=None):
        sheet = b"".join(
            wire.proto_field(tag, value)
            for tag, value in (
                (8, index),
                (18, (name or f"Mount build {index}").encode()),
                (24, 35),
                (56, 0),
            )
        )
        equipment = (
            wire.proto_field(10, wire.proto_field(8, uid) + wire.proto_field(16, 24))
            if uid is not None
            # save_build treats an empty payload as an omitted section, so use
            # the verified level-only equipment sheet to explicitly clear it.
            else wire.proto_field(424, 35)
        )
        return {"sheet": sheet, "equipment": equipment, "deck": b"", "aptitudes": b""}

    def _save_build(self, index, uid=None, name=None):
        return self.store.save_build(
            self.account,
            self.generation,
            self.character["id"],
            index,
            self._build(index, uid, name),
        )

    def _ride(self):
        code, character = mount_state.toggle(
            self.store,
            self.account,
            self.generation,
            self.character["id"],
            mounted=True,
            in_fight=False,
            location_allowed=True,
            occupation_cancelable=True,
        )
        self.assertEqual(code, 0)
        self.assertTrue(character["mount_state"]["mounted"])
        return character

    @staticmethod
    def _template_layout():
        template = (
            struct.pack(">BqBq", 10, wire.TEMPLATE_CHARACTER, 0, wire.TEMPLATE_ACCOUNT)
            + struct.pack(">H", 6)
            + b"Pekebu"
            + b"\x00\x00"
            + wire.INITIAL_POSITION
            # Captured rE continues through map id and direction; the minimal
            # synthetic template needs room for wire.position's direction byte.
            + bytes(9)
        )
        return template, {
            "template_sha256": hashlib.sha256(template).hexdigest(),
            "sections": [{"name": "PET", "start": 26, "end": 28}],
        }

    def _assert_refresh_then_dismount(self, previous, current):
        from wakfu_server.mount_publication import equipment_changes

        template, layout = self._template_layout()
        with patch.dict(wire.ENTITY_LAYOUTS, {10: layout}):
            packets = equipment_changes(template, previous, current)
        self.assertEqual([opcode for opcode, _ in packets], [15548, 13928])
        refresh_id, refresh_body = packets[0]
        self.assertEqual(refresh_id, 15548)
        self.assertEqual(struct.unpack_from(">q", refresh_body)[0], current["id"])
        pet = mount_inventory.actor_pet(current)
        self.assertIn(pet, refresh_body[10:])
        self.assertEqual(packets[1], (13928, struct.pack(">q", current["id"])))

    def test_same_mount_unrelated_build_edit_publishes_no_world_packets(self):
        from wakfu_server.mount_publication import equipment_changes

        item = self._grant_mount()
        self._save_build(0, item["uid"])
        previous = self._ride()

        self._save_build(0, item["uid"], name="Renamed, same mount")
        current = self.store.character(self.account, self.character["id"])
        self.assertEqual(previous["mount_state"], current["mount_state"])
        self.assertEqual(
            previous["builds"][0]["equipment"], current["builds"][0]["equipment"]
        )
        self.assertEqual(equipment_changes(b"unused", previous, current), [])

    def test_changed_pet_refresh_precedes_riding_result_for_same_mounted_uid(self):
        from wakfu_server.mount_publication import equipment_changes

        item = self._grant_mount()
        self._save_build(0, item["uid"])
        previous = self._ride()
        with self.store.connection() as db:
            db.execute(
                "UPDATE inventory_mounts SET health=health-1,xp=xp+25 WHERE uid=%s",
                (item["uid"],),
            )
        current = self.store.character(self.account, self.character["id"])
        template, layout = self._template_layout()
        expected_pet = mount_codec.pet_section(
            mount_inventory.equipped(current)["mount"]
        )
        with patch.dict(wire.ENTITY_LAYOUTS, {10: layout}):
            packets = equipment_changes(template, previous, current)

        self.assertEqual([opcode for opcode, _ in packets], [15548, 12634])
        self.assertIn(expected_pet, packets[0][1][10:])
        self.assertEqual(struct.unpack(">qi", packets[1][1]), (current["id"], 0))

    def test_removing_active_mount_refreshes_empty_pet_before_dismount(self):
        item = self._grant_mount()
        self._save_build(0, item["uid"])
        previous = self._ride()
        self._save_build(0, None, name="Mount removed")
        current = self.store.character(self.account, self.character["id"])
        self.assertFalse(current["mount_state"]["mounted"])
        self.assertIsNone(mount_inventory.equipped(current))
        self._assert_refresh_then_dismount(previous, current)

    def test_changing_active_mount_uid_refreshes_new_pet_before_dismount(self):
        first = self._grant_mount(slot=0)
        second = self._grant_mount(reference=18704, slot=1)
        self._save_build(0, first["uid"])
        previous = self._ride()
        self._save_build(0, second["uid"], name="Changed mount UID")
        current = self.store.character(self.account, self.character["id"])
        self.assertFalse(current["mount_state"]["mounted"])
        self.assertEqual(mount_inventory.equipped(current)["uid"], second["uid"])
        self._assert_refresh_then_dismount(previous, current)

    def test_switching_build_reconciles_mount_before_refresh_and_dismount(self):
        first = self._grant_mount(slot=0)
        second = self._grant_mount(reference=18704, slot=1)
        self._save_build(0, first["uid"])
        self._save_build(1, second["uid"])
        previous = self._ride()

        current = self.store.activate_build(
            self.account,
            self.generation,
            self.character["id"],
            1,
            in_fight=False,
        )
        self.assertEqual(current["active_build_index"], 1)
        self.assertEqual(mount_inventory.equipped(current)["uid"], second["uid"])
        self.assertFalse(current["mount_state"]["mounted"])
        self._assert_refresh_then_dismount(previous, current)

    def test_invalid_actor_identity_or_nonboolean_riding_state_is_rejected(self):
        from wakfu_server.mount_publication import equipment_changes

        item = self._grant_mount()
        self._save_build(0, item["uid"])
        previous = self.store.character(self.account, self.character["id"])
        current = self.store.character(self.account, self.character["id"])
        with self.assertRaisesRegex(ValueError, "another actor"):
            equipment_changes(b"unused", previous, dict(current, id=current["id"] + 1))
        with self.assertRaisesRegex(ValueError, "another actor"):
            equipment_changes(
                b"unused", previous, dict(current, account_id=current["account_id"] + 1)
            )
        malformed = dict(current, mount_state=dict(current["mount_state"], mounted=1))
        with self.assertRaisesRegex(ValueError, "riding state"):
            equipment_changes(b"unused", previous, malformed)

    def test_postgres_bootstrap_snapshot_replays_current_mount_after_actor_spawn(self):
        from wakfu_server.mount_publication import snapshot
        from wakfu_server.maps.world import World

        item = self._grant_mount()
        self._save_build(0, item["uid"])
        mounted = self._ride()
        packets = snapshot(mounted)
        self.assertEqual(packets, [mount_codec.ride_result(self.character["id"], 0)])

        sent = []
        world = World(
            lambda character: b"spawn",
            lambda character_id: b"",
            lambda peer, opcode, body: sent.append((peer, opcode, body)),
            state_packets=snapshot,
        )
        world.join(self.generation, "mount-peer", mounted)
        self.assertEqual([opcode for _, opcode, _ in sent], [12634])
        self.assertEqual(sent[0], ("mount-peer", *packets[0]))
        self.assertEqual(world.snapshot()[0]["mount_state"]["mounted"], True)

        dismounted = dict(
            mounted, mount_state=dict(mounted["mount_state"], mounted=False)
        )
        self.assertEqual(snapshot(dismounted), [])

    def test_bootstrap_snapshot_rejects_mounted_character_without_equipped_mount(self):
        from wakfu_server.mount_publication import snapshot

        character = self.store.character(self.account, self.character["id"])
        malformed = dict(character, mount_state={"mounted": True})
        with self.assertRaisesRegex(ValueError, "equipped mount"):
            snapshot(malformed)

    def test_live_harvest_occupation_blocks_mount_without_mutation_but_not_dismount(
        self,
    ):
        item = self._grant_mount()
        self._save_build(0, item["uid"])
        ensure_learned(
            self.store, self.account, self.generation, self.character["id"], [72]
        )
        resource = {
            "resource_uid": 910001,
            "map_id": self.character["map_id"],
            "instance_id": self.character["instance_id"],
            "x": self.character["x"],
            "y": self.character["y"],
            "z": self.character["z"],
            "resource_reference": 60,
            "stage": 3,
            "creation_time": 100,
        }
        with self.store.connection() as db:
            db.execute(
                "UPDATE settings SET value=%s WHERE name='mount_toggle_cooldown_ms'",
                (Jsonb(0),),
            )
            db.execute(
                "INSERT INTO planted_resources(resource_uid,map_id,instance_id,x,y,z,"
                "resource_reference,stage,creation_time) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                tuple(resource.values()),
            )

        def request():
            def signed(value):
                return value if value >= 0 else value + (1 << 64)

            return (
                wire.proto_field(8, 100)
                + wire.proto_field(16, signed(resource["x"]))
                + wire.proto_field(24, signed(resource["y"]))
            )

        prepared = resource_collect.prepare(
            self.store,
            self.account,
            self.generation,
            self.character["id"],
            request(),
            reachable=lambda _character, _resource: True,
        )
        ticket = resource_collect.reserve(
            self.store, self.account, self.generation, prepared
        )
        with self.store.connection() as db:
            before = mount_state.load(db, self.character["id"])

        code, rejected = mount_state.toggle(
            self.store,
            self.account,
            self.generation,
            self.character["id"],
            mounted=True,
            in_fight=False,
            location_allowed=True,
            occupation_cancelable=True,
        )
        self.assertEqual(code, 5)
        with self.store.connection() as db:
            after = mount_state.load(db, self.character["id"])
            rows = db.execute(
                "SELECT count(*) AS count FROM character_mount_state WHERE character_id=%s",
                (self.character["id"],),
            ).fetchone()["count"]
        self.assertEqual(after, before)
        self.assertEqual(rows, 0)
        self.assertFalse(rejected["mount_state"]["mounted"])
        self.assertIsNotNone(
            resource_collect.pending(
                self.store, self.account, self.generation, self.character["id"]
            )
        )

        self.assertTrue(resource_collect.cancel(self.store, ticket))
        code, mounted = mount_state.toggle(
            self.store,
            self.account,
            self.generation,
            self.character["id"],
            mounted=True,
            in_fight=False,
            location_allowed=True,
            occupation_cancelable=True,
        )
        self.assertEqual(code, 0)
        self.assertTrue(mounted["mount_state"]["mounted"])

        prepared_again = resource_collect.prepare(
            self.store,
            self.account,
            self.generation,
            self.character["id"],
            request(),
            reachable=lambda _character, _resource: True,
        )
        expiring_ticket = resource_collect.reserve(
            self.store, self.account, self.generation, prepared_again
        )
        code, dismounted = mount_state.toggle(
            self.store,
            self.account,
            self.generation,
            self.character["id"],
            mounted=False,
            in_fight=False,
            location_allowed=True,
            occupation_cancelable=True,
        )
        self.assertEqual(code, 0)
        self.assertFalse(dismounted["mount_state"]["mounted"])

        self.now = expiring_ticket["expires_at"] + timedelta(seconds=1)
        code, mounted_after_expiry = mount_state.toggle(
            self.store,
            self.account,
            self.generation,
            self.character["id"],
            mounted=True,
            in_fight=False,
            location_allowed=True,
            occupation_cancelable=True,
        )
        self.assertEqual(code, 0)
        self.assertTrue(mounted_after_expiry["mount_state"]["mounted"])
        self.assertIsNotNone(
            resource_collect.pending(
                self.store, self.account, self.generation, self.character["id"]
            )
        )

    def _equip_for_location_tests(self):
        item = self._grant_mount()
        self._save_build(0, item["uid"])
        return item

    def _set_position(self, map_id, position):
        with self.store.connection() as db:
            db.execute(
                "UPDATE characters SET map_id=%s,x=%s,y=%s,z=%s WHERE id=%s",
                (map_id, *position, self.character["id"]),
            )

    def test_native_water_cell_rejects_mount_without_state_mutation(self):
        self._equip_for_location_tests()
        # Verified swimming cell in map 1134; toggle reads this position from PG.
        self._set_position(1134, (-18, 116, -4))
        with self.store.connection() as db:
            before = mount_state.load(db, self.character["id"])
        code, character = mount_state.toggle(
            self.store,
            self.account,
            self.generation,
            self.character["id"],
            mounted=True,
            in_fight=False,
            location_allowed=True,
            occupation_cancelable=True,
        )
        with self.store.connection() as db:
            after = mount_state.load(db, self.character["id"])
            rows = db.execute(
                "SELECT count(*) AS count FROM character_mount_state WHERE character_id=%s",
                (self.character["id"],),
            ).fetchone()["count"]
        self.assertEqual(code, 4)
        self.assertEqual(before, after)
        self.assertEqual(rows, 0)
        self.assertFalse(character["mount_state"]["mounted"])

    def test_native_dry_cell_allows_mount_from_authoritative_position(self):
        self._equip_for_location_tests()
        # Verified dry XYZ in the same native-validated map 1134.
        self._set_position(1134, (0, 116, 21))
        code, character = mount_state.toggle(
            self.store,
            self.account,
            self.generation,
            self.character["id"],
            mounted=True,
            in_fight=False,
            location_allowed=True,
            occupation_cancelable=True,
        )
        self.assertEqual(code, 0)
        self.assertTrue(character["mount_state"]["mounted"])

    def test_unknown_map_topology_fails_closed_without_state_mutation(self):
        self._equip_for_location_tests()
        self._set_position(999999, (0, 116, 21))
        with self.store.connection() as db:
            before = mount_state.load(db, self.character["id"])
        code, character = mount_state.toggle(
            self.store,
            self.account,
            self.generation,
            self.character["id"],
            mounted=True,
            in_fight=False,
            location_allowed=True,
            occupation_cancelable=True,
        )
        with self.store.connection() as db:
            after = mount_state.load(db, self.character["id"])
        self.assertEqual(code, 4)
        self.assertEqual(before, after)
        self.assertFalse(character["mount_state"]["mounted"])

    @staticmethod
    def _mount_handler_branch():
        source_path = Path(__file__).resolve().parents[1] / "local_game_server.py"
        tree = ast.parse(source_path.read_text(), filename=str(source_path))

        def is_handler(node):
            if not isinstance(node, ast.If) or not isinstance(node.test, ast.BoolOp):
                return False
            return any(
                isinstance(value, ast.Compare)
                and isinstance(value.left, ast.Name)
                and value.left.id == "opcode"
                and isinstance(value.ops[0], ast.In)
                and isinstance(value.comparators[0], (ast.Tuple, ast.List))
                and {
                    item.value
                    for item in value.comparators[0].elts
                    if isinstance(item, ast.Constant)
                }
                == {12634, 13928}
                for value in node.test.values
            )

        branches = [node for node in ast.walk(tree) if is_handler(node)]
        if len(branches) != 1:
            raise AssertionError(f"expected one mount handler, found {len(branches)}")
        branch = copy.deepcopy(branches[0])
        branch.orelse = []

        class ReplaceContinue(ast.NodeTransformer):
            def visit_Continue(self, node):
                return ast.copy_location(ast.Break(), node)

        branch = ReplaceContinue().visit(branch)
        names = (
            "connection",
            "opcode",
            "loaded",
            "body",
            "fight",
            "bag_session",
            "generation",
            "character",
            "account_id",
            "STORE",
            "WORLD",
            "PLANTINGS",
            "HARVESTS",
            "cancel_flora",
            "send",
            "service",
            "record",
        )
        function = ast.FunctionDef(
            name="handle_mount",
            args=ast.arguments(
                posonlyargs=[],
                args=[ast.arg(arg=name) for name in names],
                kwonlyargs=[],
                kw_defaults=[],
                defaults=[],
            ),
            body=[
                ast.While(
                    test=ast.Constant(True),
                    body=[branch, ast.Break()],
                    orelse=[],
                ),
                ast.Return(value=ast.Name(id="character", ctx=ast.Load())),
            ],
            decorator_list=[],
        )
        module = ast.fix_missing_locations(ast.Module(body=[function], type_ignores=[]))
        namespace = {}
        exec(compile(module, str(source_path), "exec"), namespace)
        return namespace["handle_mount"]

    def _dispatch_mount(
        self,
        opcode,
        *,
        body=b"",
        fight=None,
        bag_session=None,
        result=0,
        toggle_error=None,
    ):
        events, sent, records = [], [], []
        current = self.store.character(self.account, self.character["id"])
        saved = dict(
            current, mount_state=dict(current["mount_state"], mounted=opcode == 12634)
        )

        class World:
            def update(_self, generation, character, message_id, payload):
                events.append(("world", generation, character, message_id, payload))

        class PlantingsFake:
            def cancel(_self, character_id, generation):
                events.append(("planting_cancel", character_id, generation))

        class HarvestsFake:
            def cancel(_self, character_id, *, generation):
                events.append(("monster_harvest_cancel", character_id, generation))

        def cancel_flora():
            events.append(("flora_cancel",))

        def fake_toggle(store, account_id, generation, character_id, **kwargs):
            events.append(("toggle", kwargs))
            if toggle_error is not None:
                raise toggle_error
            return result, saved

        handler = self._mount_handler_branch()
        with patch("wakfu_server.mount_state.toggle", side_effect=fake_toggle):
            actual = handler(
                object(),
                opcode,
                True,
                body,
                fight,
                bag_session,
                self.generation,
                current,
                self.account,
                self.store,
                World(),
                PlantingsFake(),
                HarvestsFake(),
                cancel_flora,
                lambda connection, service, message_id, payload: sent.append(
                    (message_id, payload)
                ),
                object(),
                lambda **event: records.append(event),
            )
        return actual, events, sent, records

    def test_mount_handler_requires_empty_body_and_fight_or_bag_rejects_without_cancelling(
        self,
    ):
        _, events, sent, records = self._dispatch_mount(12634, body=b"\x00")
        self.assertEqual(events, [])
        self.assertEqual(len(sent), 1)
        self.assertEqual(struct.unpack(">qi", sent[0][1]), (self.character["id"], 7))
        self.assertEqual(records[-1]["event"], "mount_request_rejected")
        for context in ("fight", "bag_session"):
            with self.subTest(context=context):
                kwargs = {context: object()}
                _, events, sent, _ = self._dispatch_mount(12634, **kwargs)
                self.assertEqual(events, [])
                self.assertEqual(len(sent), 1)
                self.assertEqual(sent[0][0], 12634)
                self.assertEqual(
                    struct.unpack(">qi", sent[0][1]), (self.character["id"], 3)
                )

    def test_mount_handler_cancels_all_occupations_before_toggle_then_updates_on_success(
        self,
    ):
        current, events, sent, records = self._dispatch_mount(12634)
        self.assertEqual(
            [event[0] for event in events],
            [
                "flora_cancel",
                "planting_cancel",
                "monster_harvest_cancel",
                "toggle",
                "world",
            ],
        )
        self.assertEqual(
            events[1], ("planting_cancel", self.character["id"], self.generation)
        )
        self.assertEqual(
            events[2], ("monster_harvest_cancel", self.character["id"], self.generation)
        )
        self.assertEqual(
            events[3][1],
            dict(
                mounted=True,
                in_fight=False,
                location_allowed=True,
                occupation_cancelable=True,
            ),
        )
        self.assertEqual(events[4][1:4], (self.generation, current, 12634))
        self.assertEqual(struct.unpack(">qi", events[4][4]), (self.character["id"], 0))
        self.assertEqual(sent, [])
        self.assertEqual(records[-1]["result"], 0)

    def test_mount_handler_rejection_sends_code_without_world_update_and_dismount_skips_cancels(
        self,
    ):
        _, events, sent, _ = self._dispatch_mount(12634, result=4)
        self.assertEqual(
            [event[0] for event in events],
            ["flora_cancel", "planting_cancel", "monster_harvest_cancel", "toggle"],
        )
        self.assertEqual(len(sent), 1)
        self.assertEqual(struct.unpack(">qi", sent[0][1]), (self.character["id"], 4))

        _, dismount_events, dismount_sent, _ = self._dispatch_mount(13928)
        self.assertEqual([event[0] for event in dismount_events], ["toggle", "world"])
        self.assertEqual(dismount_events[1][3], 13928)
        self.assertEqual(dismount_events[1][4], struct.pack(">q", self.character["id"]))
        self.assertEqual(dismount_sent, [])

    def test_mount_handler_maps_toggle_validation_error_to_native_rejection(self):
        _, events, sent, records = self._dispatch_mount(
            12634, toggle_error=ValueError("swimming topology unavailable")
        )
        self.assertEqual(
            [event[0] for event in events],
            ["flora_cancel", "planting_cancel", "monster_harvest_cancel", "toggle"],
        )
        self.assertEqual(len(sent), 1)
        self.assertEqual(struct.unpack(">qi", sent[0][1]), (self.character["id"], 7))
        self.assertEqual(records[-1]["event"], "mount_request_rejected")

    def test_session_publication_helper_skips_fights_and_preserves_packet_order(self):
        source_path = Path(__file__).resolve().parents[1] / "local_game_server.py"
        module = ast.parse(source_path.read_text(), filename=str(source_path))
        helper = next(
            node
            for node in ast.walk(module)
            if isinstance(node, ast.FunctionDef)
            and node.name == "publish_mount_equipment"
        )
        fake_world = type("FakeWorld", (), {"sent": []})()
        fake_world.update = lambda generation, current, *packet: fake_world.sent.append(
            (generation, current, *packet)
        )
        wrapper = ast.FunctionDef(
            name="make_publisher",
            args=ast.arguments(
                posonlyargs=[],
                args=[ast.arg(arg="fight"), ast.arg(arg="generation")],
                kwonlyargs=[],
                kw_defaults=[],
                defaults=[],
            ),
            body=[
                helper,
                ast.Return(
                    value=ast.Name(id="publish_mount_equipment", ctx=ast.Load())
                ),
            ],
            decorator_list=[],
        )
        tree = ast.fix_missing_locations(ast.Module(body=[wrapper], type_ignores=[]))
        namespace = {"WORLD": fake_world, "PLAYER_TEMPLATE": b"template"}
        exec(compile(tree, str(source_path), "exec"), namespace)
        generation = object()
        publisher = namespace["make_publisher"](object(), generation)
        publisher({"id": 1}, {"id": 1})
        self.assertEqual(fake_world.sent, [])

        publisher = namespace["make_publisher"](None, generation)
        fake_packets = [(15548, b"refresh"), (13928, b"dismount")]
        with patch(
            "wakfu_server.mount_publication.equipment_changes",
            return_value=fake_packets,
        ):
            current = {"id": 7, "map_id": 11, "instance_id": 3}
            publisher(
                {"id": 7},
                current,
            )
        self.assertEqual(
            fake_world.sent,
            [
                (generation, current, 15548, b"refresh"),
                (generation, current, 13928, b"dismount"),
            ],
        )

    def test_build_handlers_publish_only_from_success_branch_after_store_commit(self):
        source_path = Path(__file__).resolve().parents[1] / "local_game_server.py"
        tree = ast.parse(source_path.read_text(), filename=str(source_path))
        for opcode, store_method in (
            (13169, "delete_build"),
            (13776, "activate_build"),
            (12772, "save_build"),
        ):
            with self.subTest(opcode=opcode):
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
                            isinstance(part, ast.Constant) and part.value == opcode
                            for part in value.comparators
                        )
                        for value in node.test.values
                    )
                ]
                self.assertEqual(len(branches), 1)
                branch = branches[0]
                branch_body = ast.Module(body=branch.body, type_ignores=[])
                publication = [
                    node
                    for node in ast.walk(branch_body)
                    if isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Name)
                    and node.func.id == "publish_mount_equipment"
                ]
                self.assertEqual(len(publication), 1)
                call = publication[0]
                parent_map = {
                    child: parent
                    for parent in ast.walk(branch_body)
                    for child in ast.iter_child_nodes(parent)
                }
                ancestor = call
                while ancestor in parent_map and not isinstance(
                    parent_map[ancestor], ast.Try
                ):
                    ancestor = parent_map[ancestor]
                self.assertIn(ancestor, parent_map)
                try_node = parent_map[ancestor]
                self.assertIn(ancestor, try_node.orelse)
                self.assertFalse(
                    any(
                        call in list(ast.walk(handler)) for handler in try_node.handlers
                    )
                )
                database_calls = [
                    node
                    for node in ast.walk(try_node)
                    if isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                    and node.func.attr == store_method
                ]
                self.assertEqual(len(database_calls), 1)
                self.assertLess(database_calls[0].lineno, call.lineno)


if __name__ == "__main__":
    unittest.main()
