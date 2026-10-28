"""Every native travel mist opens without changing unrelated transport policy."""
import copy
import struct
import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from wakfu_server import (
    generic_transports,
    exploration_transport,
    exploration_artifact_actions,
    seasonal_native_gateway as gateway,
    seasonal_transport,
    travel_mists,
    world_scene_sync,
    world_static,
)
from wakfu_server.interactive_publication import (
    InteractivePublication,
    refresh_snapshots,
)


def frame(opcode, body=b""):
    return struct.pack(">IH", len(body) + 6, opcode) + body


def packets(data):
    while data:
        size, opcode = struct.unpack_from(">IH", data)
        yield opcode, data[6:size]
        data = data[size:]


class TravelMistsTests(unittest.TestCase):
    def sources(self):
        return tuple(
            s for s in generic_transports._CATALOG if travel_mists.recognizes(s)
        )

    def row(self, source):
        return next(
            r for r in world_static.objects(source["map_id"]) if r["id"] == source["id"]
        )

    def test_all_native_family_geometry_menu_actions_and_free_destinations(self):
        sources = self.sources()
        self.assertEqual(len(sources), 27)
        self.assertEqual(
            {s["definition_id"] for s in sources}, travel_mists.DEFINITION_IDS
        )
        baseline = copy.deepcopy(sources)
        forbidden = Mock(
            side_effect=AssertionError("Mist must not query mission authority")
        )
        fees = []
        count = 0
        for source in sources:
            with self.subTest(source=source["id"]):
                row = self.row(source)
                actor = dict(id=1, map_id=source["map_id"], instance_id=0, level=1)
                binding = gateway.binding(source["map_id"], source["id"])
                original = gateway._parts(bytes.fromhex(row["payload_hex"]))
                projected = gateway._parts(gateway.appearance(row, binding))
                self.assertEqual(projected[0], original[0])
                marker = source["native_parameters"].encode()
                marker = struct.pack(">H", len(marker)) + marker
                replacement = binding["activation_parameters"]
                self.assertEqual(
                    projected[1],
                    original[1].replace(
                        marker, struct.pack(">H", len(replacement)) + replacement
                    ),
                )
                self.assertEqual(
                    projected[2], gateway._parts(world_static._DUNGEON_ENTRY_STATE)[2]
                )
                self.assertEqual(replacement.count(b"{1;"), len(source["destinations"]))
                for index, destination in enumerate(source["destinations"]):
                    action = travel_mists.ACTION_IDS[index]
                    activation = gateway.activation(
                        actor, struct.pack(">qHH", source["id"], action, 0)
                    )
                    self.assertEqual(
                        struct.unpack(">qiBi", activation["body"]),
                        (source["id"], destination["destination_id"], 0, 2),
                    )
                    route = generic_transports.resolve(
                        actor,
                        activation["body"],
                        source_allowed=lambda *_: True,
                        criterion_evaluator=forbidden,
                    )
                    self.assertEqual(
                        route["destination"],
                        {
                            **{k: destination[k] for k in ("map_id", "x", "y", "z")},
                            "instance_id": 0,
                        },
                    )
                    self.assertEqual(route["criterion"], "")
                    self.assertNotIn("item_payment", route)
                    if destination["cyW"] > 0:
                        fees.append(destination["item_reference"])
                    count += 1
        self.assertEqual(count, 31)
        self.assertEqual(fees, [18722] * 4)
        self.assertEqual(sources, baseline)
        forbidden.assert_not_called()

    def test_real_state_producers_first_replay_unload_and_reload_keep_menu_enabled(
        self,
    ):
        for source in self.sources():
            with self.subTest(source=source["id"]):
                row = self.row(source)
                identity, map_id = source["id"], source["map_id"]
                selected = world_scene_sync.chunk(row)
                all_bodies = world_static.snapshots(map_id)
                chunk_bodies = world_scene_sync.dynamic_snapshots(map_id, (selected,))
                for bodies in (all_bodies, chunk_bodies):
                    records = [
                        record
                        for body in bodies
                        for record in refresh_snapshots(body)
                        if struct.unpack_from(">q", record)[0] == identity
                    ]
                    self.assertEqual(len(records), 1)
                    self.assertEqual(records[0][10:], world_static._DUNGEON_ENTRY_STATE)
                snapshot = b"".join(frame(13984, body) for body in chunk_bodies)
                scope = dict(
                    session_id="qa",
                    generation="lease",
                    account_id=1,
                    character_id=2,
                    map_id=map_id,
                    instance_id=0,
                )
                tracker = InteractivePublication(
                    lambda _: (row,), attachment_projector=gateway.attachment
                )
                loader = frame(12318, struct.pack(">ii", int(row["x"]), int(row["y"])))
                first = tuple(packets(tracker.transform(loader + snapshot, scope)))
                attachments = [body for opcode, body in first if opcode == 13664]
                self.assertEqual(len(attachments), 1)
                self.assertEqual(
                    struct.unpack_from(">hqq", attachments[0]), (1, identity, 19825)
                )
                replay = tuple(packets(tracker.transform(snapshot, scope)))
                updates = [
                    body
                    for opcode, body in replay
                    if opcode == 12344 and struct.unpack_from(">q", body)[0] == identity
                ]
                self.assertEqual(len(updates), 1)
                self.assertEqual(updates[0][10:], world_static._DUNGEON_ENTRY_STATE)
                tracker.transform(frame(12318, struct.pack(">ii", 10000, 10000)), scope)
                for reset in (b"", frame(13256)):
                    again = tuple(
                        packets(tracker.transform(reset + loader + snapshot, scope))
                    )
                    self.assertEqual(
                        [body for opcode, body in again if opcode == 13664], attachments
                    )
                self.assertEqual(tracker.attached, {identity})

    def test_public_source_and_destination_guards_remain_authoritative(self):
        for source in self.sources():
            actor = dict(map_id=source["map_id"], instance_id=0)
            body = struct.pack(
                ">qiBi", source["id"], source["destinations"][0]["destination_id"], 0, 2
            )
            with self.subTest(source=source["id"]):
                with self.assertRaisesRegex(ValueError, "interaction not allowed"):
                    generic_transports.resolve(
                        actor, body, source_allowed=lambda *_: False
                    )
                for changed in (dict(actor, instance_id=99), dict(actor, map_id=-999)):
                    with self.assertRaises(ValueError):
                        generic_transports.resolve(
                            changed, body, source_allowed=lambda *_: True
                        )
                with self.assertRaisesRegex(ValueError, "destination"):
                    generic_transports.resolve(
                        actor,
                        struct.pack(">qiBi", source["id"], -999, 0, 2),
                        source_allowed=lambda *_: True,
                    )
                for action, padding in ((99, 0), (0, 1)):
                    with self.assertRaises(ValueError):
                        gateway.activation(
                            actor, struct.pack(">qHH", source["id"], action, padding)
                        )
                with self.assertRaises(ValueError):
                    gateway.activation(
                        dict(actor, instance_id=99),
                        struct.pack(">qHH", source["id"], 0, 0),
                    )

    def test_unrelated_native_payment_level_calendar_and_dynamic_state_are_preserved(
        self,
    ):
        actor = dict(id=1, map_id=235, instance_id=0, level=51)
        body = struct.pack(">qiBi", 18012, 4810, 0, 2)
        store = SimpleNamespace(clock=lambda: 1893456000)
        allowed = seasonal_transport.evaluator(store, actor)
        route = generic_transports.resolve(
            actor,
            body,
            source_allowed=lambda *_: True,
            criterion_evaluator=allowed,
            allow_item_payment=True,
        )
        self.assertEqual(route["item_payment"], dict(reference=33075, quantity=1))
        with self.assertRaisesRegex(ValueError, "item transaction"):
            generic_transports.resolve(
                actor, body, source_allowed=lambda *_: True, criterion_evaluator=allowed
            )
        with self.assertRaisesRegex(ValueError, "criterion is not met"):
            generic_transports.resolve(
                dict(actor, level=50),
                body,
                source_allowed=lambda *_: True,
                criterion_evaluator=allowed,
                allow_item_payment=True,
            )
        self.assertFalse(allowed(route["criterion"], actor, 147))
        for source in generic_transports._CATALOG:
            if (
                travel_mists.recognizes(source)
                or exploration_transport.recognizes(source)
                or exploration_artifact_actions.projection_required(
                    source["map_id"], source["id"]
                )
            ):
                continue
            self.assertEqual(
                world_static.dynamic_state(source["map_id"], source["id"]),
                world_static._DYNAMIC_STATES[(source["map_id"], source["id"])],
            )
