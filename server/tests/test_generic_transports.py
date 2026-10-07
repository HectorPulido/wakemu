import struct
import unittest
from wakfu_server import dungeon_instances, generic_transports as g


class GenericTransportTests(unittest.TestCase):
    def test_native_free_destinations_preserve_exact_map_layer(self):
        count = 0
        for source in g._CATALOG:
            for dest in source["destinations"]:
                if (
                    dest["criterion"].strip()
                    or (dest["cyW"] > 0 and dest["item_reference"] > 0)
                    or dest["cyX"]
                    or dest["cyZ"] >= 0
                    or not dest["native_altitude_walkable"]
                ):
                    continue
                character = {"map_id": source["map_id"], "instance_id": 0}
                route = g.resolve(
                    character,
                    struct.pack(">qiBi", source["id"], dest["destination_id"], 0, 2),
                    source_allowed=lambda c, s: True,
                )
                self.assertEqual(
                    route["destination"],
                    {
                        **{k: dest[k] for k in ("map_id", "x", "y", "z")},
                        "instance_id": 0,
                    },
                )
                count += 1
        self.assertEqual(count, 2987)

    def test_authoritative_source_callback_and_unknown_reject(self):
        source = next(
            s
            for s in g._CATALOG
            if s["destinations"] and not s["destinations"][0]["criterion"].strip()
        )
        body = struct.pack(
            ">qiBi", source["id"], source["destinations"][0]["destination_id"], 0, 2
        )
        with self.assertRaisesRegex(ValueError, "interaction not allowed"):
            g.resolve(
                {"map_id": source["map_id"], "instance_id": 0},
                body,
                source_allowed=lambda c, s: False,
            )
        with self.assertRaisesRegex(ValueError, "Unknown native teleporter"):
            g.resolve(
                {"map_id": -1, "instance_id": 0}, body, source_allowed=lambda c, s: True
            )

    def test_native_condition_is_never_silently_waived(self):
        source, dest = next(
            (s, d)
            for s in g._CATALOG
            for d in s["destinations"]
            if d["criterion"].strip()
        )
        with self.assertRaisesRegex(ValueError, "access criterion"):
            g.resolve(
                {"map_id": source["map_id"], "instance_id": 0},
                struct.pack(">qiBi", source["id"], dest["destination_id"], 0, 2),
                source_allowed=lambda c, s: True,
            )

    def test_jalato_dungeon_template_is_not_a_live_instance_transport(self):
        route = dungeon_instances.route("jalato_normal")
        source = g.source(route.entry_map_id, route.entry_object_id)
        self.assertIsNotNone(source)
        destination = next(
            item
            for item in source["destinations"]
            if item["destination_id"] == route.destination_id
        )
        self.assertEqual(destination["cyZ"], route.template_id)
        self.assertEqual(destination["map_id"], route.start_map_id)
        self.assertNotEqual(destination["cyZ"], 0)

        # cpJ12296 supplies the native destination choice, but not a live
        # dungeon-instance ID. The generic-world transport must keep rejecting
        # this special route until the party-owned dungeon authority is wired.
        character = {"map_id": route.entry_map_id, "instance_id": 0}
        body = struct.pack(">qiBi", route.entry_object_id, route.destination_id, 0, 2)
        with self.assertRaisesRegex(ValueError, "access criterion"):
            g.resolve(character, body, source_allowed=lambda _c, _s: True)
        self.assertEqual(character, {"map_id": route.entry_map_id, "instance_id": 0})
