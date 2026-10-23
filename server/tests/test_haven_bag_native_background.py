"""Real native background furniture through learning, placement and packing."""
import struct

from postgres_case import PostgresCase


class HavenBagNativeBackgroundTests(PostgresCase):
    def test_native_background_learns_places_reloads_rotates_and_packs(self):
        from wakfu_server.haven_bag_furniture_catalog import resolve_item
        from wakfu_server.haven_bag_furniture_knowledge import learn
        from wakfu_server.haven_bag_furniture_transfer import deploy, edit
        from wakfu_server.haven_bag_furniture_world import packets
        from wakfu_server.haven_bag_store import FURNITURE_TEMPLATES
        from wakfu_server.inventory_items import grant

        account = self.store.register("native-background-owner", "local-password")["id"]
        character = self.store.create_character(account, "Background Owner")
        generation = self.store.begin_session(account)
        self.store.select_character(account, generation, character["id"])
        location = {"map_id": 9, "instance_id": character["id"]}
        definition = resolve_item(9280)
        self.assertEqual(definition["kind"], "DimensionalBagBackgroundDisplay")
        self.assertEqual(definition["template_id"], 6938)
        source = grant(
            self.store,
            account,
            generation,
            character["id"],
            reference=9280,
            quantity=1,
            container=character["inventory_containers"][0]["uid"],
            slot=0,
            allowed_references={9280},
        )
        learned = learn(
            self.store,
            account,
            generation,
            character["id"],
            struct.pack(">iq", 782, source["uid"]),
        )
        self.assertTrue(learned["applied"])
        self.assertFalse(learned["character"]["inventory_items"])
        request = struct.pack(">iqiihi", 9280, 6938, 1, 1, 0, 0)
        placed = deploy(
            self.store,
            account,
            generation,
            character["id"],
            request,
            location=location,
        )["character"]
        unit = placed["haven_bag"]["furniture"][0]
        self.assertTrue(unit["virtual"] and unit["deployed"])
        self.assertEqual([opcode for opcode, _ in packets(placed)], [13664])
        self.assertIn(6938, FURNITURE_TEMPLATES)
        reopened = self.reopen()
        hydrated = reopened.character(account, character["id"])
        self.assertEqual(
            hydrated["haven_bag"]["furniture"], placed["haven_bag"]["furniture"]
        )
        rotated = edit(
            reopened,
            account,
            generation,
            character["id"],
            12870,
            struct.pack(">qH", 6938, 29) + b"\x00\x00",
            location=location,
        )["character"]
        self.assertEqual(rotated["haven_bag"]["furniture"][0]["direction"], 2)
        packed = edit(
            reopened,
            account,
            generation,
            character["id"],
            12870,
            struct.pack(">qH", 6938, 23) + b"\x00\x00",
            location=location,
        )["character"]
        self.assertFalse(packed["haven_bag"]["furniture"])
        self.assertFalse(packed["inventory_items"])
        replaced = deploy(
            reopened,
            account,
            generation,
            character["id"],
            request,
            location=location,
        )["character"]
        self.assertTrue(replaced["haven_bag"]["furniture"][0]["virtual"])
        self.assertFalse(replaced["inventory_items"])
