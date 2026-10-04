import struct
import unittest
from wakfu_server import generic_transports as g


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
