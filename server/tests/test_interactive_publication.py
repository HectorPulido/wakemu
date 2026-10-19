import struct
import unittest

from wakfu_server.maps.interactive_publication import (
    InteractivePublication,
    resource_cell,
)


def frame(opcode, body=b""):
    return struct.pack(">IH", 6 + len(body), opcode) + body


def snapshot(*records):
    return frame(
        13984,
        struct.pack(">h", len(records))
        + b"".join(
            struct.pack(">qH", identity, len(payload)) + payload
            for identity, payload in records
        ),
    )


def decode(data):
    result = []
    while data:
        size, opcode = struct.unpack_from(">IH", data)
        result.append((opcode, data[6:size]))
        data = data[size:]
    return result


class InteractivePublicationTests(unittest.TestCase):
    def setUp(self):
        self.rows = [
            dict(id=1, x=0, y=0, auto=False),
            dict(id=2, x=1, y=1, auto=True),
            dict(id=3, x=90, y=0, auto=False),
        ]
        self.scope = dict(
            session_id="peer",
            generation=1,
            account_id=7,
            character_id=8,
            map_id=1385,
            instance_id=0,
        )
        self.events = []
        self.publisher = InteractivePublication(
            lambda map_id: self.rows, self.events.append
        )
        self.loader = frame(12318, struct.pack(">ii", 0, 0))
        self.publish(self.loader)

    def publish(self, data, **scope):
        return self.publisher.transform(data, dict(self.scope, **scope))

    def test_first_attachment_then_changed_state_updates_in_place(self):
        self.assertEqual(self.publish(snapshot((1, b"a"))), snapshot((1, b"a")))
        result = decode(self.publish(snapshot((1, b"changed"))))
        self.assertEqual(result, [(12344, struct.pack(">qH", 1, 7) + b"changed")])

    def test_automatic_asset_never_receives_attachment(self):
        for _ in range(2):
            self.assertEqual(decode(self.publish(snapshot((2, b"a"))))[0][0], 12344)

    def test_loaded_neighborhood_filters_distant_known_objects(self):
        result = self.publish(
            frame(12318, struct.pack(">ii", 0, 0)) + snapshot((3, b"a"))
        )
        self.assertEqual([opcode for opcode, _ in decode(result)], [12318])
        self.assertNotIn(3, self.publisher.attached)

    def test_unload_then_return_allows_new_attachment(self):
        self.publish(frame(12318, struct.pack(">ii", 0, 0)) + snapshot((1, b"a")))
        self.publish(frame(12318, struct.pack(">ii", 90, 0)))
        self.assertNotIn(1, self.publisher.attached)
        result = self.publish(
            frame(12318, struct.pack(">ii", 0, 0)) + snapshot((1, b"a"))
        )
        self.assertEqual([opcode for opcode, _ in decode(result)], [12318, 13984])
        self.assertTrue(any(event["operation"] == "unload" for event in self.events))

    def test_overlapping_neighborhood_retains_attachment(self):
        self.publish(frame(12318, struct.pack(">ii", 0, 0)) + snapshot((1, b"a")))
        result = self.publish(
            frame(12318, struct.pack(">ii", 18, 0)) + snapshot((1, b"b"))
        )
        self.assertEqual([opcode for opcode, _ in decode(result)], [12318, 12344])

    def test_scope_change_and_reconnect_require_new_attachment(self):
        for field, value in (
            ("instance_id", 42),
            ("map_id", 9),
            ("generation", 2),
            ("session_id", "new"),
            ("account_id", 9),
        ):
            with self.subTest(field=field):
                self.publisher.clear()
                self.publish(self.loader)
                self.publish(snapshot((1, b"a")))
                self.assertEqual(
                    decode(
                        self.publish(
                            self.loader + snapshot((1, b"a")), **{field: value}
                        )
                    )[-1][0],
                    13984,
                )

    def test_independent_publishers_do_not_share_membership(self):
        self.publish(snapshot((1, b"a")))
        other = InteractivePublication(lambda map_id: self.rows)
        self.assertEqual(
            other.transform(self.loader + snapshot((1, b"a")), self.scope),
            self.loader + snapshot((1, b"a")),
        )

    def test_scene_reset_allows_new_attachment(self):
        for opcode in (13256, 13974):
            self.publish(snapshot((1, b"a")))
            result = self.publish(
                frame(opcode, b"scene") + self.loader + snapshot((1, b"b"))
            )
            self.assertEqual(
                [code for code, _ in decode(result)], [opcode, 12318, 13984]
            )

    def test_malformed_batch_does_not_commit_partial_state(self):
        malformed = frame(13984, struct.pack(">hqH", 1, 2, 5) + b"a")
        with self.assertRaises(ValueError):
            self.publish(snapshot((1, b"a")) + malformed)
        self.assertEqual(self.publisher.attached, set())
        self.assertEqual(self.events, [])
        self.assertEqual(self.publish(snapshot((1, b"a"))), snapshot((1, b"a")))

    def test_malformed_tcp_and_loader_frames_are_atomic(self):
        for malformed in (b"abc", frame(12318, b"bad"), struct.pack(">IH", 90, 1)):
            with self.subTest(malformed=malformed), self.assertRaises(ValueError):
                self.publish(snapshot((1, b"a")) + malformed)
            self.assertEqual(self.publisher.attached, set())

    def test_unrelated_combat_and_resource_frames_are_byte_identical(self):
        data = (
            frame(12608, bytes(range(70)))
            + frame(13852, b"path")
            + frame(13579, b"fight")
        )
        self.assertEqual(self.publish(data), data)

    def test_unknown_ids_passthrough_and_legitimate_updates_not_suppressed(self):
        unknown = snapshot((999, b"unknown"))
        self.assertEqual(self.publish(unknown), unknown)
        self.assertEqual(self.publish(unknown), unknown)
        update = frame(12344, struct.pack(">qH", 1, 1) + b"x")
        self.assertEqual(self.publish(update + update), update + update)

    def test_clear_after_socket_failure_allows_retry(self):
        self.publish(snapshot((1, b"a")))
        self.publisher.clear()
        self.publish(self.loader)
        self.assertEqual(self.publish(snapshot((1, b"a"))), snapshot((1, b"a")))

    def test_hero_change_preserves_same_native_loader_membership(self):
        self.publish(snapshot((1, b"a")))
        result = self.publish(snapshot((1, b"b")), character_id=12)
        self.assertEqual([opcode for opcode, _ in decode(result)], [12344])
        self.assertEqual(self.events[-1]["character_id"], 12)

    def test_same_world_ready_rebuilds_native_partition_membership(self):
        self.publish(snapshot((1, b"a")))
        # Original ciu 13974 unconditionally clears cdE before rebuilding it.
        result = self.publish(frame(13974, b"ready") + snapshot((1, b"b")))
        self.assertEqual([opcode for opcode, _ in decode(result)], [13974])
        self.assertEqual(self.publisher.attached, set())
        result = self.publish(self.loader + snapshot((1, b"b")))
        self.assertEqual([opcode for opcode, _ in decode(result)], [12318, 13984])
        self.assertEqual(
            [opcode for opcode, _ in decode(self.publish(snapshot((1, b"c"))))],
            [12344],
        )

    def test_before_loader_does_not_poison_first_attachment(self):
        self.publisher.clear()
        self.assertEqual(self.publish(snapshot((1, b"a"))), b"")
        self.assertEqual(self.publisher.attached, set())
        self.assertEqual(
            self.publish(self.loader + snapshot((1, b"a"))),
            self.loader + snapshot((1, b"a")),
        )

    def test_unrelated_frames_do_not_load_catalog(self):
        publisher = InteractivePublication(
            lambda _: self.fail("Unexpected catalog lookup")
        )
        self.assertEqual(
            publisher.transform(frame(13579, b"combat"), self.scope),
            frame(13579, b"combat"),
        )
        self.assertEqual(publisher.transform(b"unframed", None), b"unframed")

    def test_resource_updates_respect_visibility_without_deduplication(self):
        near = frame(12782, struct.pack(">iihhqi", 1, 2, 3, 4, 0, 0))
        changed = frame(12782, struct.pack(">iihhqi", 1, 2, 3, 5, 0, 0))
        far = frame(12782, struct.pack(">iihhqi", 90, 2, 3, 4, 0, 0))
        self.assertEqual(
            self.publish(near + changed + near + far), near + changed + near
        )

    def test_resource_initial_defer_and_partition_reentry(self):
        resource = frame(13135, b"\x08\x01\x10\x01\x18\x02\x28\x01")
        self.publisher.clear()
        self.assertEqual(self.publish(resource), b"")
        self.assertEqual(self.publish(self.loader + resource), self.loader + resource)
        self.publish(frame(12318, struct.pack(">ii", 90, 0)))
        self.assertEqual(self.publish(resource), b"")
        self.assertEqual(self.publish(self.loader + resource), self.loader + resource)

    def test_resource_negative_coordinates_use_floor_partition(self):
        negative = b"\xff" * 9 + b"\x01"
        resource = frame(13135, b"\x10" + negative + b"\x18" + negative)
        self.assertEqual(resource_cell(13135, resource[6:]), (-1, -1))
        self.assertEqual(self.publish(resource), resource)
        loader = frame(12318, struct.pack(">ii", 18, 18))
        self.assertEqual(self.publish(loader + resource), loader)

    def test_resource_proto_unknown_fields_are_skipped(self):
        body = (
            b"\x10\x01\x18\x02"
            + b"\x49"
            + b"a" * 8
            + b"\x52\x03abc"
            + b"\x5d"
            + b"b" * 4
            + b"\x60\x01"
        )
        self.assertEqual(resource_cell(13135, body), (1, 2))
        resource = frame(13135, body)
        self.assertEqual(self.publish(resource + resource), resource + resource)

    def test_unqualified_resource_layouts_passthrough(self):
        bodies = (
            b"",
            b"\x10\x80",
            b"\x10" + b"\xff" * 11,
            b"\x10\x01\x18\x02\x52\x09x",
            b"\x14",
            b"\x12\x01x\x18\x02",
            b"\x10\x01",
            b"\x00",
        )
        for body in bodies:
            with self.subTest(body=body):
                self.assertIsNone(resource_cell(13135, body))
                resource = frame(13135, body)
                self.assertEqual(self.publish(resource), resource)
        invalid_fixed = frame(12782, b"unknown-layout")
        self.assertEqual(self.publish(invalid_fixed), invalid_fixed)

    def test_trace_filter_and_bound_do_not_change_delivery(self):
        events = []
        publisher = InteractivePublication(
            lambda map_id: self.rows,
            events.append,
            trace_ids={1},
            trace_account_id=7,
            trace_limit=1,
        )
        publisher.transform(self.loader + snapshot((1, b"a"), (2, b"b")), self.scope)
        publisher.transform(snapshot((1, b"a")), self.scope)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["id"], 1)
        self.assertEqual(events[0]["operation"], "attach")
        self.assertEqual(events[0]["account_id"], 7)


if __name__ == "__main__":
    unittest.main()
