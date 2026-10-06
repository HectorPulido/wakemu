import unittest
from postgres_case import PostgresCase
from wakfu_server.haven_bag_store import save
from wakfu_server.haven_bag import own_bag, validate_leave_request


class HavenBagPersistenceTests(PostgresCase):
    def test_owned_minimal_state_and_saved_layout_survive_reopen(self):
        store = self.store
        store.clock = lambda: 1000
        account = store.register("owner", "local-password")["id"]
        first = store.create_character(account, "First")
        second = store.create_character(account, "Second")
        self.assertNotEqual(
            first["haven_bag"]["rooms"][0]["primary_uid"],
            second["haven_bag"]["rooms"][0]["primary_uid"],
        )
        self.assertEqual(first["haven_bag"]["furniture"], [])
        self.assertEqual(
            first["haven_bag"]["access"],
            {"groups": [{"group": 0, "rights": 1}], "characters": []},
        )
        generation = store.begin_session(account)
        store.select_character(account, generation, first["id"])
        rooms = [
            first["haven_bag"]["rooms"][0],
            {
                **first["haven_bag"]["rooms"][0],
                "index": 1,
                "enabled": False,
                "primary_uid": first["id"] * 256 + 2,
            },
        ]
        saved = save(store, account, generation, first["id"], rooms=rooms, locked=True)
        reopened = self.reopen()
        self.assertEqual(
            reopened.character(account, first["id"])["haven_bag"],
            saved["haven_bag"],
        )
        self.assertEqual(
            reopened.character(account, second["id"])["haven_bag"],
            second["haven_bag"],
        )
        self.assertNotEqual(own_bag(first), own_bag(saved))
        with self.assertRaises(ValueError):
            save(store, account, generation, second["id"], locked=True)
        store.begin_session(account)
        with self.assertRaises(ValueError):
            save(store, account, generation, first["id"], locked=False)

    def test_captured_exit_byte_is_accepted_and_bad_payload_rejected(self):
        validate_leave_request(bytes.fromhex("00"))
        validate_leave_request(b"")
        for body in (b"\x01", b"\x00\x00", b"\xff"):
            with self.assertRaises(ValueError):
                validate_leave_request(body)

    def test_move_owned_secondary_to_new_room_conserves_unique_items(self):
        from wakfu_server.haven_bag_store import rearrange_rooms

        config = {
            "rooms": [
                dict(
                    index=0,
                    enabled=True,
                    primary_ref=4262,
                    primary_uid=257,
                    secondary_ref=4262,
                    secondary_uid=258,
                )
            ]
        }
        rooms = rearrange_rooms(config, bytes((0, 1, 0, 1)))
        self.assertEqual(rooms[0]["secondary_ref"], -1)
        self.assertEqual(
            (rooms[1]["primary_ref"], rooms[1]["primary_uid"]), (4262, 258)
        )
        self.assertEqual(config["rooms"][0]["secondary_uid"], 258)
        with self.assertRaises(ValueError):
            rearrange_rooms(config, bytes((1, 1, 0, 1)))
        with self.assertRaises(ValueError):
            rearrange_rooms(config, bytes((0, 1, 0, 9)))

    def test_invalid_model_is_rejected_before_database_mutation(self):
        store = self.store
        store.clock = lambda: 1000
        account = store.register("owner", "local-password")["id"]
        char = store.create_character(account, "First")
        generation = store.begin_session(account)
        store.select_character(account, generation, char["id"])
        with self.assertRaises(ValueError):
            save(store, account, generation, char["id"], appearance_id=2147483647)
        self.assertEqual(
            store.character(account, char["id"])["haven_bag"]["appearance_id"], 408
        )

    def test_permission_wire_roundtrip_and_postgres_ownership(self):
        import struct
        from wakfu_server.haven_bag import permission_payload, decode_permissions

        store = self.store
        store.clock = lambda: 1000
        account = store.register("owner", "local-password")["id"]
        char = store.create_character(account, "First")
        other = store.create_character(account, "Second")
        access = {
            "groups": [{"group": 0, "rights": 1}],
            "characters": [{"id": other["id"], "name": other["name"], "rights": 3}],
        }
        payload = permission_payload({"locked": True, "access": access})
        self.assertEqual(
            decode_permissions(struct.pack(">I", len(payload)) + payload),
            (True, access),
        )
        generation = store.begin_session(account)
        store.select_character(account, generation, char["id"])
        saved = save(store, account, generation, char["id"], locked=True, access=access)
        reopened = self.reopen()
        self.assertEqual(
            reopened.character(account, char["id"])["haven_bag"]["access"], access
        )
        self.assertIn(payload, own_bag(saved))
        access["characters"][0]["name"] = "Captured official player"
        with self.assertRaises(ValueError):
            save(store, account, generation, char["id"], access=access)
        with self.assertRaises(ValueError):
            decode_permissions(struct.pack(">I", len(payload) + 1) + payload)

    def test_furniture_is_owned_persistent_and_deployment_cannot_create_items(self):
        import struct
        from wakfu_server.haven_bag_store import deploy_furniture
        from wakfu_server.haven_bag_furniture import encode_vf

        store = self.store
        store.clock = lambda: 1000
        account = store.register("owner", "local-password")["id"]
        char = store.create_character(account, "First")
        generation = store.begin_session(account)
        store.select_character(account, generation, char["id"])
        # An explicit local grant, never copied from captured account data.
        item = dict(
            template_id=21327,
            item_uid=123456,
            item_ref=456,
            x=0,
            y=0,
            z=0,
            direction=0,
            virtual=False,
            quantity=1,
            deployed=False,
            room=0,
        )
        saved = save(store, account, generation, char["id"], furniture=[item])
        request = struct.pack(">iqiihi", 456, 123456, 2, 2, 0, 3)
        furniture = deploy_furniture(saved["haven_bag"], request)
        self.assertFalse(saved["haven_bag"]["furniture"][0]["deployed"])
        saved = save(store, account, generation, char["id"], furniture=furniture)
        reopened = self.reopen()
        self.assertEqual(
            reopened.character(account, char["id"])["haven_bag"]["furniture"],
            furniture,
        )
        form = {k: v for k, v in furniture[0].items() if k not in ("room", "deployed")}
        self.assertIn(encode_vf(**form), own_bag(saved))
        with self.assertRaises(ValueError):
            deploy_furniture(saved["haven_bag"], request)
        with self.assertRaises(ValueError):
            deploy_furniture(char["haven_bag"], request)
        with self.assertRaises(ValueError):
            save(store, account, generation, char["id"], furniture=[item, item])
        with self.assertRaises(ValueError):
            save(
                store,
                account,
                generation,
                char["id"],
                furniture=[{**item, "quantity": 2}],
            )

    def test_itemizable_actions_resolve_owned_template_not_item_uid(self):
        import struct
        from wakfu_server.haven_bag_store import edit_furniture, initial_layout

        item = dict(
            template_id=21327,
            item_uid=123456,
            item_ref=456,
            x=1,
            y=1,
            z=0,
            direction=0,
            virtual=False,
            quantity=1,
            deployed=True,
            room=0,
        )
        config = dict(rooms=initial_layout(1), furniture=[item])
        rotated = edit_furniture(config, 12870, struct.pack(">qHxx", 21327, 29))
        self.assertEqual(rotated[0]["direction"], 2)
        self.assertEqual(config["furniture"][0]["direction"], 0)
        moved = edit_furniture(config, 12363, struct.pack(">qiihi", 21327, 2, 3, 0, 4))
        self.assertEqual(
            (moved[0]["x"], moved[0]["y"], moved[0]["direction"]), (2, 3, 4)
        )
        repacked = edit_furniture(config, 12870, struct.pack(">qHxx", 21327, 23))
        self.assertFalse(repacked[0]["deployed"])
        self.assertEqual(repacked[0]["item_uid"], 123456)
        for opcode, body in (
            (12870, struct.pack(">qHxx", 123456, 23)),
            (12870, struct.pack(">qHxx", 21327, 47)),
            (12363, struct.pack(">qiihi", 21327, 9, 9, 0, 0)),
            (12363, struct.pack(">qiihi", 21327, 2, 3, 0, 8)),
        ):
            with self.assertRaises(ValueError):
                edit_furniture(config, opcode, body)
        with self.assertRaises(ValueError):
            edit_furniture(
                {**config, "furniture": [item, item]},
                12870,
                struct.pack(">qHxx", 21327, 23),
            )

    def test_disconnect_or_character_switch_retains_owned_state_and_exterior(self):
        from wakfu_server.haven_bag import HavenBagSession

        store = self.store
        store.clock = lambda: 1000
        account = store.register("owner", "local-password")["id"]
        char = store.create_character(account, "First")
        other = store.create_character(account, "Second")
        generation = store.begin_session(account)
        outside = store.select_character(account, generation, char["id"])
        bag = HavenBagSession(outside)
        inside = bag.move(bag.inside, {"x": 1, "y": -7, "z": 4})
        saved = save(store, account, generation, char["id"], locked=True)
        inside = bag.refresh(inside, saved)
        self.assertEqual(inside["map_id"], 9)
        persisted = store.character(account, char["id"])
        self.assertEqual(
            (persisted["map_id"], persisted["x"], persisted["y"]),
            (outside["map_id"], outside["x"], outside["y"]),
        )
        store.clear_character(account, generation)
        store.select_character(account, generation, other["id"])
        with self.assertRaises(ValueError):
            save(store, account, generation, char["id"], locked=False)
        newer = store.begin_session(account)
        store.end_session(account, generation)
        self.assertTrue(store.current_session(account, newer))
        self.assertTrue(
            store.select_character(account, newer, char["id"])["haven_bag"]["locked"]
        )

    def test_fixed_entrance_layout_cannot_be_removed_disabled_or_given_foreign_gem(
        self,
    ):
        store = self.store
        store.clock = lambda: 1000
        account = store.register("owner", "local-password")["id"]
        char = store.create_character(account, "First")
        generation = store.begin_session(account)
        store.select_character(account, generation, char["id"])
        base = char["haven_bag"]["rooms"][0]
        for rooms in (
            [{**base, "index": 1}],
            [{**base, "enabled": False}],
            [{**base, "primary_ref": -1, "primary_uid": 0}],
            [{**base, "primary_uid": 999999}],
        ):
            with self.assertRaises(ValueError):
                save(store, account, generation, char["id"], rooms=rooms)
        self.assertEqual(
            store.character(account, char["id"])["haven_bag"], char["haven_bag"]
        )

    def test_matching_owned_gem_can_move_to_existing_secondary_slot_without_duplication(
        self,
    ):
        from wakfu_server.haven_bag_store import initial_layout, rearrange_rooms

        config = dict(rooms=initial_layout(1))
        config["rooms"][1].update(primary_ref=4262, primary_uid=258)
        actual = rearrange_rooms(config, bytes((1, 0, 1, 0)))
        self.assertEqual(
            (actual[0]["primary_uid"], actual[0]["secondary_uid"]), (257, 258)
        )
        self.assertEqual((actual[1]["primary_ref"], actual[1]["primary_uid"]), (-1, 0))
        self.assertEqual(config["rooms"][1]["primary_uid"], 258)
        config["rooms"][1].update(primary_ref=4263)
        with self.assertRaises(ValueError):
            rearrange_rooms(config, bytes((1, 0, 1, 0)))

    def test_custom_model_furniture_permissions_stay_per_character_across_accounts_and_reopen(
        self,
    ):
        from wakfu_server.haven_bag_store import MODELS

        store = self.store
        store.clock = lambda: 1000
        first_account = store.register("owner", "local-password")["id"]
        second_account = store.register("other", "local-password")["id"]
        first = store.create_character(first_account, "First")
        sibling = store.create_character(first_account, "Sibling")
        foreign = store.create_character(second_account, "Foreign")
        generation = store.begin_session(first_account)
        store.select_character(first_account, generation, first["id"])
        model = next(model for model in sorted(MODELS) if model != 408)
        furniture = [
            dict(
                template_id=21327,
                item_uid=first["id"] * 256 + 9,
                item_ref=456,
                x=1,
                y=2,
                z=0,
                direction=3,
                virtual=False,
                quantity=1,
                room=0,
                deployed=True,
            )
        ]
        access = {
            "groups": [{"group": 0, "rights": 1}],
            "characters": [{"id": sibling["id"], "name": sibling["name"], "rights": 3}],
        }
        saved = save(
            store,
            first_account,
            generation,
            first["id"],
            appearance_id=model,
            furniture=furniture,
            access=access,
            locked=True,
        )
        reopened = self.reopen()
        self.assertEqual(
            reopened.character(first_account, first["id"])["haven_bag"],
            saved["haven_bag"],
        )
        self.assertEqual(
            reopened.character(first_account, sibling["id"])["haven_bag"],
            sibling["haven_bag"],
        )
        self.assertEqual(
            reopened.character(second_account, foreign["id"])["haven_bag"],
            foreign["haven_bag"],
        )
        self.assertEqual(
            own_bag(reopened.character(first_account, first["id"])), own_bag(saved)
        )
        self.assertNotEqual(own_bag(saved), own_bag(first))
        other_generation = reopened.begin_session(second_account)
        reopened.select_character(second_account, other_generation, foreign["id"])
        with self.assertRaises(ValueError):
            save(
                reopened,
                second_account,
                other_generation,
                first["id"],
                locked=False,
            )
