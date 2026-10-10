"""Physical inventory ownership for haven-bag furniture deployment."""
import struct
import json
import unittest
from contextlib import contextmanager
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

from postgres_case import PostgresCase


class _FakeResult:
    def __init__(self, rows=()):
        self.rows = list(rows)

    def fetchone(self):
        return self.rows[0] if self.rows else None

    def __iter__(self):
        return iter(self.rows)


class _TransactionalFurnitureStore:
    """Small transactional adapter for exercising transfer logic offline."""

    def __init__(self, *, quantity=3, capacity=4):
        self.account_id = 7
        self.generation = 11
        self.character_id = 42
        self.container_uid = 80
        self.item_uid = 120
        self.next_uid = 200
        self.state = {
            "rooms": [
                {"index": 0, "enabled": True, "primary_ref": 4262},
                {"index": 1, "enabled": True, "primary_ref": 4262},
            ],
            "furniture": [],
            "items": {
                self.item_uid: {
                    "uid": self.item_uid,
                    "character_id": self.character_id,
                    "reference": 5001,
                    "quantity": quantity,
                    "container": self.container_uid,
                    "slot": 0,
                }
            },
            "containers": [{"uid": self.container_uid, "capacity": capacity}],
            "garden_plants": set(),
        }

    @contextmanager
    def connection(self):
        before = deepcopy(self.state)
        next_uid = self.next_uid
        db = _TransactionalFurnitureDB(self)
        try:
            yield db
        except Exception:
            self.state = before
            self.next_uid = next_uid
            raise

    def now(self):
        return 1000

    def lock_character(self, db, account_id, generation, character_id):
        if (account_id, generation, character_id) != (
            self.account_id,
            self.generation,
            self.character_id,
        ):
            raise ValueError("Invalid fake owner session")
        if (
            db.execute(
                "SELECT id FROM characters WHERE id=%s AND account_id=%s",
                (character_id, account_id),
            ).fetchone()
            is None
        ):
            raise ValueError("Invalid fake owner")

    def character(self, account_id, character_id, db=None):
        if (account_id, character_id) != (self.account_id, self.character_id):
            raise ValueError("Invalid fake owner")
        return {
            "id": self.character_id,
            "haven_bag": {
                "rooms": deepcopy(self.state["rooms"]),
                "furniture": deepcopy(self.state["furniture"]),
            },
            "inventory_items": deepcopy(list(self.state["items"].values())),
            "inventory_containers": deepcopy(self.state["containers"]),
        }


class _TransactionalFurnitureDB:
    def __init__(self, store):
        self.store = store

    def execute(self, sql, params=()):
        statement = " ".join(sql.lower().split())
        state = self.store.state
        if statement.startswith("select b.character_id from account_haven_bags"):
            return _FakeResult([{"character_id": self.store.character_id}])
        if statement.startswith("select character_id from sessions"):
            account_id, generation, _expires = params
            if (account_id, generation) == (
                self.store.account_id,
                self.store.generation,
            ):
                return _FakeResult([{"character_id": self.store.character_id}])
            return _FakeResult()
        if statement.startswith("select id from characters"):
            character_id, account_id = params[:2]
            if (character_id, account_id) == (
                self.store.character_id,
                self.store.account_id,
            ):
                return _FakeResult([{"id": character_id}])
            return _FakeResult()
        if statement.startswith("select layout,furniture from haven_bags"):
            return _FakeResult(
                [{"layout": state["rooms"], "furniture": state["furniture"]}]
            )
        if statement.startswith("select 1 from account_furniture_knowledge"):
            return _FakeResult()
        if statement.startswith("select 1 from planted_resources"):
            instance_id, x, y = params
            return _FakeResult(
                [{"exists": 1}]
                if instance_id == self.store.character_id
                and (x, y) in state["garden_plants"]
                else []
            )
        if statement.startswith(
            "select * from inventory_items where uid=%s and character_id=%s"
        ):
            uid, character_id = params
            item = state["items"].get(uid)
            return _FakeResult(
                [deepcopy(item)]
                if item and item["character_id"] == character_id
                else []
            )
        if statement.startswith(
            "select * from inventory_items where character_id=%s and reference=%s"
        ):
            character_id, reference = params
            rows = sorted(
                (
                    deepcopy(item)
                    for item in state["items"].values()
                    if item["character_id"] == character_id
                    and item["reference"] == reference
                ),
                key=lambda item: item["uid"],
            )
            return _FakeResult(rows[:1])
        if statement.startswith(
            "select 1 from inventory_item_"
        ) or statement.startswith("select 1 from inventory_mounts"):
            return _FakeResult()
        if statement.startswith("select nextval('inventory_uid')"):
            uid = self.store.next_uid
            self.store.next_uid += 1
            return _FakeResult([{"uid": uid}])
        if statement.startswith("update inventory_items set quantity=quantity-1"):
            (uid,) = params
            state["items"][uid]["quantity"] -= 1
            return _FakeResult()
        if statement.startswith("delete from inventory_items where uid=%s"):
            (uid,) = params
            state["items"].pop(uid, None)
            return _FakeResult()
        if statement.startswith("update haven_bags set furniture="):
            furniture, character_id = params
            if character_id != self.store.character_id:
                raise ValueError("Invalid fake bag owner")
            state["furniture"] = deepcopy(furniture.obj)
            return _FakeResult()
        if statement.startswith("select uid,capacity from inventory_containers"):
            (character_id,) = params
            if character_id != self.store.character_id:
                return _FakeResult()
            return _FakeResult(deepcopy(state["containers"]))
        if statement.startswith("select container,slot from inventory_items"):
            (character_id,) = params
            return _FakeResult(
                [
                    {"container": item["container"], "slot": item["slot"]}
                    for item in state["items"].values()
                    if item["character_id"] == character_id
                ]
            )
        if statement.startswith("insert into inventory_items"):
            uid, character_id, reference, container, slot = params
            if any(
                item["container"] == container and item["slot"] == slot
                for item in state["items"].values()
            ):
                raise ValueError("Fake inventory position occupied")
            state["items"][uid] = {
                "uid": uid,
                "character_id": character_id,
                "reference": reference,
                "quantity": 1,
                "container": container,
                "slot": slot,
            }
            return _FakeResult()
        raise AssertionError(f"Unhandled fake SQL: {sql}")


class HavenBagFurnitureTransferTests(PostgresCase):
    """Exercise furniture ownership in isolated PostgreSQL schemas only."""

    DECORATION_REF = 5001
    SECOND_DECORATION_REF = 5002
    DECORATION_TEMPLATE = 21327
    SECOND_DECORATION_TEMPLATE = 21328

    def setUp(self):
        # The allowlist is normally read from the versioned native catalog.
        # These tests use a small deterministic fixture so they remain offline.
        import wakfu_server.native_catalog as native_catalog

        real_catalog_load = native_catalog.load

        def catalog_document(path):
            name = str(path).rsplit("/", 1)[-1]
            if name == "haven-bag-models.json":
                return {"models": [{"id": 408}]}
            if name == "haven-bag-furniture-templates.json":
                return {
                    "templates": [
                        {
                            "template_id": self.DECORATION_TEMPLATE,
                            "java_type": "Decoration:Furniture",
                            "kind": "Decoration",
                        },
                        {
                            "template_id": self.SECOND_DECORATION_TEMPLATE,
                            "java_type": "Decoration:Furniture",
                            "kind": "Decoration",
                        },
                    ]
                }
            if name == "spells.json":
                return {"spells": []}
            if name == "level-xp.json":
                return {"xp_by_level": {"1": 0, "2": 1}}
            if name == "entity-layouts.json":
                return []
            if name == "entity-defaults.json":
                return {}
            return real_catalog_load(path)

        self.catalog_patch = patch.object(
            native_catalog, "load", side_effect=catalog_document
        )
        self.catalog_patch.start()
        self.addCleanup(self.catalog_patch.stop)
        super().setUp()

        self.account = self.store.register("furniture-owner", "local-password")["id"]
        self.character = self.store.create_character(self.account, "Furniture Owner")
        self.generation = self.store.begin_session(self.account)
        self.store.select_character(self.account, self.generation, self.character["id"])
        self.container = self.character["inventory_containers"][0]["uid"]

        from wakfu_server.haven_bag_furniture_transfer import deploy, edit

        self.deploy_furniture = deploy
        self.edit_furniture = edit

    def _item(self, reference=None, quantity=1, *, slot=0):
        from wakfu_server.inventory_items import grant

        if reference is None:
            reference = self.DECORATION_REF
        return grant(
            self.store,
            self.account,
            self.generation,
            self.character["id"],
            reference=reference,
            quantity=quantity,
            container=self.container,
            slot=slot,
            allowed_references={
                self.DECORATION_REF,
                self.SECOND_DECORATION_REF,
                100,
            },
        )

    def _deploy_body(self, item, *, x=1, y=1, direction=0):
        return struct.pack(
            ">iqiihi", item["reference"], item["uid"], x, y, 0, direction
        )

    def _deploy(self, item, *, x=1, y=1):
        return self.deploy_furniture(
            self.store,
            self.account,
            self.generation,
            self.character["id"],
            self._deploy_body(item, x=x, y=y),
            location={"map_id": 9, "instance_id": self.character["id"]},
            resolver=lambda reference: {
                "template_id": (
                    self.DECORATION_TEMPLATE
                    if reference == self.DECORATION_REF
                    else self.SECOND_DECORATION_TEMPLATE
                ),
                "kind": "Decoration",
            },
        )

    def _pack_body(self, template_id=None):
        if template_id is None:
            template_id = self.DECORATION_TEMPLATE
        return struct.pack(">qH", template_id, 23) + b"\x00\x00"

    def test_stack_unit_deploys_packs_and_survives_reopen(self):
        item = self._item(quantity=3)
        deployed = self._deploy(item)
        self.assertEqual(
            deployed["packets"], [(12470, struct.pack(">qh", item["uid"], -1))]
        )

        state = deployed["character"]
        furniture = state["haven_bag"]["furniture"]
        self.assertEqual(len(furniture), 1)
        unit = furniture[0]
        self.assertTrue(unit["deployed"])
        self.assertEqual(unit["item_ref"], self.DECORATION_REF)
        self.assertEqual(unit["template_id"], self.DECORATION_TEMPLATE)
        self.assertEqual(unit["quantity"], 1)
        self.assertNotEqual(unit["item_uid"], item["uid"])
        self.assertEqual(
            [(row["uid"], row["quantity"]) for row in state["inventory_items"]],
            [(item["uid"], 2)],
        )

        reopened = self.reopen()
        persistent = reopened.character(self.account, self.character["id"])
        self.assertEqual(persistent["haven_bag"]["furniture"], furniture)
        packed = self.edit_furniture(
            reopened,
            self.account,
            self.generation,
            self.character["id"],
            12870,
            self._pack_body(),
            location={"map_id": 9, "instance_id": self.character["id"]},
        )
        self.assertEqual(len(packed["character"]["haven_bag"]["furniture"]), 0)
        items = packed["character"]["inventory_items"]
        self.assertEqual(
            sorted((row["uid"], row["reference"], row["quantity"]) for row in items),
            sorted(
                [
                    (item["uid"], self.DECORATION_REF, 2),
                    (unit["item_uid"], self.DECORATION_REF, 1),
                ]
            ),
        )
        persisted = self.reopen().character(self.account, self.character["id"])
        self.assertEqual(persisted["haven_bag"]["furniture"], [])

    def test_foreign_character_cannot_deploy_another_owners_uid(self):
        item = self._item()
        foreign_account = self.store.register(
            "foreign-furniture-owner", "local-password"
        )["id"]
        foreign_character = self.store.create_character(
            foreign_account, "Foreign Owner"
        )
        foreign_generation = self.store.begin_session(foreign_account)
        self.store.select_character(
            foreign_account, foreign_generation, foreign_character["id"]
        )

        with self.assertRaisesRegex(
            ValueError, "unavailable or belongs to another owner"
        ):
            self.deploy_furniture(
                self.store,
                foreign_account,
                foreign_generation,
                foreign_character["id"],
                struct.pack(">iqiihi", self.DECORATION_REF, item["uid"], 1, 1, 0, 0),
                location={"map_id": 9, "instance_id": foreign_character["id"]},
                resolver=lambda _reference: {
                    "template_id": self.DECORATION_TEMPLATE,
                    "kind": "Decoration",
                },
            )

        owner = self.store.character(self.account, self.character["id"])
        self.assertEqual(owner["inventory_items"][0]["uid"], item["uid"])
        self.assertEqual(owner["inventory_items"][0]["quantity"], 1)
        self.assertEqual(owner["haven_bag"]["furniture"], [])

    def test_deployment_rejects_occupied_cell_without_consuming_second_item(self):
        first = self._item(slot=0)
        second = self._item(self.SECOND_DECORATION_REF, slot=1)
        self._deploy(first, x=2, y=3)

        with self.assertRaisesRegex(ValueError, "occupied"):
            self._deploy(second, x=2, y=3)

        state = self.store.character(self.account, self.character["id"])
        self.assertEqual(
            [(row["uid"], row["quantity"]) for row in state["inventory_items"]],
            [(second["uid"], 1)],
        )
        furniture = state["haven_bag"]["furniture"]
        self.assertEqual(len(furniture), 1)
        self.assertEqual(furniture[0]["item_uid"], first["uid"])
        self.assertTrue(furniture[0]["deployed"])

    def test_pack_with_full_inventory_rolls_back_furniture_state(self):
        item = self._item()
        deployed = self._deploy(item)
        unit = deployed["character"]["haven_bag"]["furniture"][0]
        from wakfu_server.inventory_items import grant

        with self.store.connection() as db:
            containers = list(
                db.execute(
                    "SELECT uid,capacity FROM inventory_containers "
                    "WHERE character_id=%s ORDER BY uid",
                    (self.character["id"],),
                )
            )
        for container in containers:
            for slot in range(container["capacity"]):
                try:
                    grant(
                        self.store,
                        self.account,
                        self.generation,
                        self.character["id"],
                        reference=100,
                        quantity=1,
                        container=container["uid"],
                        slot=slot,
                        allowed_references={100},
                    )
                except ValueError as error:
                    if "occupied" not in str(error).lower():
                        raise

        with self.assertRaisesRegex(ValueError, "free inventory slot"):
            self.edit_furniture(
                self.store,
                self.account,
                self.generation,
                self.character["id"],
                12870,
                self._pack_body(),
                location={"map_id": 9, "instance_id": self.character["id"]},
            )

        persisted = self.store.character(self.account, self.character["id"])
        furniture = persisted["haven_bag"]["furniture"]
        self.assertEqual(len(furniture), 1)
        self.assertEqual(furniture[0]["item_uid"], unit["item_uid"])
        self.assertTrue(furniture[0]["deployed"])
        self.assertNotIn(
            unit["item_uid"], {row["uid"] for row in persisted["inventory_items"]}
        )


class HavenBagFurnitureKnowledgeIntegrationTests(PostgresCase):
    """Use the published native item rules and isolated schema end-to-end."""

    def setUp(self):
        super().setUp()
        from wakfu_server.haven_bag_furniture_knowledge import known, learn
        from wakfu_server.haven_bag_furniture_transfer import deploy, edit
        from wakfu_server.inventory_items import grant

        self.known_furniture = known
        self.learn_furniture = learn
        self.deploy_furniture = deploy
        self.edit_furniture = edit
        self.grant_item = grant

        self.account = self.store.register("furniture-library-owner", "local-password")[
            "id"
        ]
        self.character = self.store.create_character(self.account, "Library Owner")
        self.generation = self.store.begin_session(self.account)
        self.store.select_character(self.account, self.generation, self.character["id"])
        self.container = self.character["inventory_containers"][0]["uid"]
        self.location = {"map_id": 9, "instance_id": self.character["id"]}

    def test_learn_place_pack_reconnect_and_replace_uses_library_without_refund(self):
        source = self.grant_item(
            self.store,
            self.account,
            self.generation,
            self.character["id"],
            reference=6293,
            quantity=2,
            container=self.container,
            slot=0,
            allowed_references={6293},
        )
        correct = struct.pack(">iq", 466, source["uid"])

        with self.assertRaisesRegex(ValueError, "action or native criteria"):
            self.learn_furniture(
                self.store,
                self.account,
                self.generation,
                self.character["id"],
                struct.pack(">iq", 4543, source["uid"]),
            )
        self.assertEqual(
            next(
                row
                for row in self.store.character(self.account, self.character["id"])[
                    "inventory_items"
                ]
                if row["uid"] == source["uid"]
            )["quantity"],
            2,
        )

        foreign_account = self.store.register(
            "foreign-library-owner", "local-password"
        )["id"]
        foreign_character = self.store.create_character(
            foreign_account, "Foreign Library"
        )
        foreign_generation = self.store.begin_session(foreign_account)
        self.store.select_character(
            foreign_account, foreign_generation, foreign_character["id"]
        )
        foreign_source = self.grant_item(
            self.store,
            foreign_account,
            foreign_generation,
            foreign_character["id"],
            reference=6293,
            quantity=1,
            container=foreign_character["inventory_containers"][0]["uid"],
            slot=0,
            allowed_references={6293},
        )
        with self.assertRaisesRegex(ValueError, "unavailable or foreign"):
            self.learn_furniture(
                self.store,
                self.account,
                self.generation,
                self.character["id"],
                struct.pack(">iq", 466, foreign_source["uid"]),
            )
        self.assertEqual(
            self.store.character(foreign_account, foreign_character["id"])[
                "inventory_items"
            ][0]["quantity"],
            1,
        )

        learned = self.learn_furniture(
            self.store,
            self.account,
            self.generation,
            self.character["id"],
            correct,
        )
        self.assertTrue(learned["applied"])
        self.assertEqual(
            [opcode for opcode, _ in learned["packets"]], [12470, 13873, 13247]
        )
        self.assertEqual(learned["packets"][2][1], struct.pack(">II?", 1, 6293, True))
        owner_items = self.store.character(self.account, self.character["id"])[
            "inventory_items"
        ]
        self.assertEqual(
            next(row for row in owner_items if row["uid"] == source["uid"])["quantity"],
            1,
        )

        request = struct.pack(">iqiihi", 6293, 2770, 1, 1, 0, 0)
        first = self.deploy_furniture(
            self.store,
            self.account,
            self.generation,
            self.character["id"],
            request,
            location=self.location,
        )
        placed = first["character"]["haven_bag"]["furniture"][0]
        self.assertTrue(placed["virtual"] and placed["deployed"])
        self.assertNotEqual(placed["item_uid"], source["uid"])

        pack = struct.pack(">qH", 2770, 23) + b"\x00\x00"
        packed = self.edit_furniture(
            self.store,
            self.account,
            self.generation,
            self.character["id"],
            12870,
            pack,
            location=self.location,
        )
        self.assertEqual(packed["packets"], [])
        self.assertEqual(packed["character"]["haven_bag"]["furniture"], [])
        self.assertEqual(
            next(
                row
                for row in packed["character"]["inventory_items"]
                if row["uid"] == source["uid"]
            )["quantity"],
            1,
        )

        reopened = self.reopen()
        with reopened.connection() as db:
            self.assertTrue(self.known_furniture(db, self.account, 6293))
        replacement = self.deploy_furniture(
            reopened,
            self.account,
            self.generation,
            self.character["id"],
            request,
            location=self.location,
        )
        replacement_furniture = replacement["character"]["haven_bag"]["furniture"][0]
        self.assertTrue(
            replacement_furniture["virtual"] and replacement_furniture["deployed"]
        )
        self.assertEqual(
            next(
                row
                for row in replacement["character"]["inventory_items"]
                if row["uid"] == source["uid"]
            )["quantity"],
            1,
        )


class HavenBagFurnitureTransferOfflineTests(unittest.TestCase):
    """Run the real transfer functions against a rollback-capable fake DB."""

    def setUp(self):
        import wakfu_server.native_catalog as native_catalog

        real_catalog_load = native_catalog.load

        def catalog_document(path):
            name = str(path).rsplit("/", 1)[-1]
            if name == "haven-bag-models.json":
                return {"models": [{"id": 408}]}
            if name == "haven-bag-furniture-templates.json":
                return {
                    "templates": [
                        {
                            "template_id": HavenBagFurnitureTransferTests.DECORATION_TEMPLATE,
                            "java_type": "Decoration:Furniture",
                            "kind": "Decoration",
                        }
                    ]
                }
            if name == "spells.json":
                return {"spells": []}
            if name == "level-xp.json":
                return {"xp_by_level": {"1": 0, "2": 1}}
            if name == "entity-layouts.json":
                return []
            if name == "entity-defaults.json":
                return {}
            return real_catalog_load(path)

        self.catalog_patch = patch.object(
            native_catalog, "load", side_effect=catalog_document
        )
        self.catalog_patch.start()
        self.addCleanup(self.catalog_patch.stop)
        from wakfu_server.haven_bag_furniture_transfer import deploy, edit

        self.deploy_furniture = deploy
        self.edit_furniture = edit
        self.store = _TransactionalFurnitureStore()

    def _deploy(self, *, native_template_request=False):
        store = self.store
        item_selector = (
            HavenBagFurnitureTransferTests.DECORATION_TEMPLATE
            if native_template_request
            else store.item_uid
        )
        return self.deploy_furniture(
            store,
            store.account_id,
            store.generation,
            store.character_id,
            struct.pack(">iqiihi", 5001, item_selector, 1, 1, 0, 0),
            location={"map_id": 9, "instance_id": store.character_id},
            resolver=lambda _reference: {
                "template_id": HavenBagFurnitureTransferTests.DECORATION_TEMPLATE,
                "kind": "Decoration",
            },
        )

    def _pack(self):
        store = self.store
        return self.edit_furniture(
            store,
            store.account_id,
            store.generation,
            store.character_id,
            12870,
            struct.pack(">qH", HavenBagFurnitureTransferTests.DECORATION_TEMPLATE, 23)
            + b"\x00\x00",
            location={"map_id": 9, "instance_id": store.character_id},
        )

    def test_stack_deploy_pack_conserves_units_through_real_transfer_functions(self):
        deployed = self._deploy()
        store = self.store
        furniture = deployed["character"]["haven_bag"]["furniture"]
        self.assertEqual(len(furniture), 1)
        unit_uid = furniture[0]["item_uid"]
        self.assertTrue(furniture[0]["deployed"])
        self.assertEqual(store.state["items"][store.item_uid]["quantity"], 2)
        self.assertNotIn(unit_uid, store.state["items"])

        packed = self._pack()["character"]
        self.assertEqual(packed["haven_bag"]["furniture"], [])
        self.assertEqual(store.state["items"][store.item_uid]["quantity"], 2)
        self.assertEqual(store.state["items"][unit_uid]["reference"], 5001)
        self.assertEqual(store.state["items"][unit_uid]["quantity"], 1)

    def test_native_template_selector_resolves_owned_item_deterministically(self):
        store = self.store
        second_uid = store.item_uid + 5
        store.state["items"][second_uid] = {
            "uid": second_uid,
            "character_id": store.character_id,
            "reference": 5001,
            "quantity": 1,
            "container": store.container_uid,
            "slot": 1,
        }
        result = self._deploy(native_template_request=True)
        self.assertEqual(
            result["packets"], [(12470, struct.pack(">qh", store.item_uid, -1))]
        )
        self.assertEqual(store.state["items"][store.item_uid]["quantity"], 2)
        self.assertEqual(store.state["items"][second_uid]["quantity"], 1)
        furniture = result["character"]["haven_bag"]["furniture"]
        self.assertEqual(furniture[0]["item_uid"], store.next_uid - 1)

    def test_full_inventory_pack_failure_rolls_back_transfer_transaction(self):
        self.store = _TransactionalFurnitureStore(quantity=2, capacity=1)
        self._deploy()
        before = deepcopy(self.store.state)

        with self.assertRaisesRegex(ValueError, "free inventory slot"):
            self._pack()

        self.assertEqual(self.store.state, before)


if __name__ == "__main__":
    unittest.main()
