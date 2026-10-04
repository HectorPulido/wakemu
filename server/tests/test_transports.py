import struct
import tempfile
from pathlib import Path
import unittest
from protocol_codec import Reader
from wakfu_server import transports, wire
from wakfu_server.store import Store


class TransportTests(unittest.TestCase):
    def request(self, route):
        return struct.pack(
            ">qiBi", route["interactive_element_id"], route["destination_id"], 0, 2
        )

    def test_verified_route_requires_actual_source_map_and_proximity(self):
        route = transports.CATALOG["routes"][0]
        char = {
            "map_id": route["source_map"],
            "instance_id": 0,
            **route["source_position"],
        }
        self.assertEqual(transports.resolve(char, self.request(route)), route)
        for wrong in [
            {**char, "map_id": 1134},
            {**char, "x": char["x"] + 20},
            {**char, "instance_id": 3},
        ]:
            with self.assertRaises(ValueError):
                transports.resolve(wrong, self.request(route))

    def test_tutorial_detour_has_verified_return_and_rejects_invalid_requests(self):
        outward = next(
            r
            for r in transports.CATALOG["routes"]
            if r["destination"]["map_id"] == 1387
        )
        backward = next(
            r for r in transports.CATALOG["routes"] if r["source_map"] == 1387
        )
        self.assertEqual(
            backward["destination"],
            {"map_id": 1385, "instance_id": 0, **outward["source_position"]},
        )
        self.assertEqual(
            (backward["interactive_element_id"], backward["destination_id"]),
            (34618, 4563),
        )
        for route in (outward, backward):
            char = {
                "map_id": route["source_map"],
                "instance_id": 0,
                **route["source_position"],
            }
            self.assertIs(transports.resolve(char, self.request(route)), route)
            for invalid in (
                {**char, "z": char["z"] + 2},
                {**char, "instance_id": 9},
                {**char, "x": char["x"] + 4},
            ):
                with self.assertRaises(ValueError):
                    transports.resolve(invalid, self.request(route))
            for flag, mode in ((1, 2), (0, 1), (0, 3)):
                with self.assertRaises(ValueError):
                    transports.resolve(
                        char,
                        struct.pack(
                            ">qiBi",
                            route["interactive_element_id"],
                            route["destination_id"],
                            flag,
                            mode,
                        ),
                    )

    def test_transition_bootstrap_has_destination_world_and_local_identity(self):
        for route in transports.CATALOG["routes"]:
            char = {"id": 7, "account_id": 9, **route["destination"]}
            packets = list(transports.bootstrap(char, route))
            raw = next(body for opcode, body in packets if opcode == 13974)
            r = Reader(raw)
            block = r.take(r.number("H"))
            self.assertEqual(struct.unpack_from(">q", block, 1)[0], 7)
            self.assertEqual(struct.unpack_from(">q", block, 10)[0], 9)
            self.assertEqual(struct.unpack_from(">q", block, 28)[0], char["map_id"])
            self.assertEqual(
                struct.unpack_from(">iih", block, 18), (char["x"], char["y"], char["z"])
            )
            self.assertTrue(
                all(
                    struct.pack(">q", wire.TEMPLATE_CHARACTER) not in body
                    for _, body in packets
                )
            )

    def test_persisted_transition_is_generation_and_origin_safe(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "db"
            st = Store(path)
            a = st.register("traveler", "local-test-password")["id"]
            c = st.create_character(a, "Traveler")
            g = st.begin_session(a)
            st.select_character(a, g, c["id"])
            destination = transports.CATALOG["routes"][0]["destination"]
            changed = st.transition_map(a, g, c["id"], c, destination)
            reopened = Store(path).character(a, c["id"])
            self.assertTrue(
                all(reopened[key] == value for key, value in destination.items())
            )
            with self.assertRaises(ValueError):
                st.transition_map(a, g, c["id"], c, destination)
            st.begin_session(a)
            with self.assertRaises(ValueError):
                st.transition_map(
                    a, g, c["id"], changed, {**destination, "map_id": 1385}
                )
