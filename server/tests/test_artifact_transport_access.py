"""Projected exploration powers grant transport access without spending items."""
import copy
import struct
import unittest
from unittest.mock import Mock

from wakfu_server import (
    exploration_secrets,
    exploration_transport,
    generic_transports,
    travel_mists,
    seasonal_native_gateway as gateway,
    world_static,
    world_scene_sync,
)
from wakfu_server.interactive_publication import (
    InteractivePublication,
    refresh_snapshots,
)
from test_travel_mists import frame, packets


class ArtifactTransportAccessTests(unittest.TestCase):
    def test_all_reviewed_artifact_gateways_publish_replay_activate_and_keep_story_guards(
        self,
    ):
        sources = tuple(
            s
            for s in generic_transports._CATALOG
            if exploration_transport.recognizes(s)
        )
        self.assertEqual(
            {s["definition_id"] for s in sources},
            exploration_transport.MISSION_FREE_DEFINITIONS,
        )
        self.assertEqual(len(exploration_transport.MISSION_FREE_DEFINITIONS), 26)
        baseline = copy.deepcopy(sources)
        forbidden = Mock(
            side_effect=AssertionError(
                "Reviewed artifact must not query story progress"
            )
        )
        for source in sources:
            with self.subTest(source=source["id"], definition=source["definition_id"]):
                identity, map_id = source["id"], source["map_id"]
                actor = dict(
                    id=1,
                    account_id=7,
                    map_id=map_id,
                    instance_id=0,
                    level=1,
                    exploration_secrets=dict(
                        account_item_refs=exploration_secrets.ITEM_REFS
                    ),
                )
                row = next(
                    r for r in world_static.objects(map_id) if r["id"] == identity
                )
                binding = gateway.binding(map_id, identity)
                self.assertEqual(binding["route_key"], "exploration_artifact")
                self.assertEqual(
                    binding["activation_parameters"].count(b"{1;"),
                    len(source["destinations"]),
                )
                self.assertEqual(
                    gateway._parts(gateway.appearance(row, binding))[0],
                    gateway._parts(bytes.fromhex(row["payload_hex"]))[0],
                )
                with self.assertRaisesRegex(ValueError, "identity changed"):
                    gateway.appearance(dict(row, x=row["x"] + 1), binding)
                bodies = world_scene_sync.dynamic_snapshots(
                    map_id, (world_scene_sync.chunk(row),)
                )
                for produced in (bodies, world_static.snapshots(map_id)):
                    records = [
                        r
                        for body in produced
                        for r in refresh_snapshots(body)
                        if struct.unpack_from(">q", r)[0] == identity
                    ]
                    self.assertEqual(len(records), 1)
                    self.assertEqual(records[0][10:], world_static._DUNGEON_ENTRY_STATE)
                snapshot = b"".join(frame(13984, b) for b in bodies)
                loader = frame(12318, struct.pack(">ii", int(row["x"]), int(row["y"])))
                scope = dict(
                    actor, character_id=1, session_id="artifact-qa", generation="lease"
                )
                tracker = InteractivePublication(
                    lambda _: (row,), attachment_projector=gateway.attachment
                )
                first = tuple(packets(tracker.transform(loader + snapshot, scope)))
                attachments = [b for op, b in first if op == 13664]
                self.assertEqual(len(attachments), 1)
                self.assertEqual(
                    struct.unpack_from(">hqq", attachments[0]), (1, identity, 19825)
                )
                replay = tuple(packets(tracker.transform(snapshot, scope)))
                updates = [
                    b
                    for op, b in replay
                    if op == 12344 and struct.unpack_from(">q", b)[0] == identity
                ]
                self.assertEqual(len(updates), 1)
                self.assertEqual(updates[0][10:], world_static._DUNGEON_ENTRY_STATE)
                tracker.transform(frame(12318, struct.pack(">ii", 10000, 10000)), scope)
                for reset in (b"", frame(13256)):
                    again = tuple(
                        packets(tracker.transform(reset + loader + snapshot, scope))
                    )
                    self.assertEqual([b for op, b in again if op == 13664], attachments)
                for index, destination in enumerate(source["destinations"]):
                    action = exploration_transport.ACTION_IDS[index]
                    activated = gateway.activation(
                        actor, struct.pack(">qHH", identity, action, 0)
                    )
                    self.assertEqual(
                        struct.unpack(">qiBi", activated["body"]),
                        (identity, destination["destination_id"], 0, 2),
                    )
                    route = generic_transports.resolve(
                        actor,
                        activated["body"],
                        source_allowed=lambda *_: True,
                        criterion_evaluator=forbidden,
                    )
                    self.assertEqual(route["criterion"], "")
                    self.assertNotIn("item_payment", route)
                    self.assertEqual(
                        route["destination"],
                        {
                            **{
                                key: destination[key]
                                for key in ("map_id", "x", "y", "z")
                            },
                            "instance_id": 0,
                        },
                    )
                    with self.assertRaisesRegex(ValueError, "interaction not allowed"):
                        generic_transports.resolve(
                            actor, activated["body"], source_allowed=lambda *_: False
                        )
                    disabled = dict(
                        actor, exploration_secrets=dict(account_item_refs=())
                    )
                    if destination["criterion"].strip():
                        denied = Mock(return_value=False)
                        with self.assertRaisesRegex(ValueError, "criterion is not met"):
                            generic_transports.resolve(
                                disabled,
                                activated["body"],
                                source_allowed=lambda *_: True,
                                criterion_evaluator=denied,
                            )
                        denied.assert_called_once_with(
                            destination["criterion"], disabled, destination["map_id"]
                        )
                first_request = struct.pack(
                    ">qiBi", identity, source["destinations"][0]["destination_id"], 0, 2
                )
                for malformed in ((18591, 18591), (19,), (True,), None):
                    forged = dict(
                        actor, exploration_secrets=dict(account_item_refs=malformed)
                    )
                    with self.assertRaisesRegex(ValueError, "owned exploration"):
                        generic_transports.resolve(
                            forged, first_request, source_allowed=lambda *_: True
                        )
                foreign = dict(
                    actor,
                    account_quest_items=[
                        dict(account_id=8, reference=18591, quantity=1)
                    ],
                )
                with self.assertRaisesRegex(ValueError, "Foreign"):
                    generic_transports.resolve(
                        foreign, first_request, source_allowed=lambda *_: True
                    )
                with self.assertRaisesRegex(ValueError, "destination"):
                    generic_transports.resolve(
                        actor,
                        struct.pack(">qiBi", identity, -999, 0, 2),
                        source_allowed=lambda *_: True,
                    )
                with self.assertRaises(ValueError):
                    gateway.activation(
                        dict(actor, instance_id=99), struct.pack(">qHH", identity, 0, 0)
                    )
                with self.assertRaises(ValueError):
                    gateway.activation(actor, struct.pack(">qHH", identity, 99, 0))
                self.assertIsNone(
                    gateway.activation(
                        dict(actor, map_id=-999), struct.pack(">qHH", identity, 0, 0)
                    )
                )
        forbidden.assert_not_called()
        self.assertEqual(sources, baseline)
        for definition in (1985, 1854, 1855):
            ordinary = [
                s
                for s in generic_transports._CATALOG
                if s.get("definition_id") == definition
            ]
            self.assertTrue(ordinary)
            guarded = 0
            for source in ordinary:
                for destination in source["destinations"]:
                    if not destination["criterion"].strip():
                        continue
                    guarded += 1
                    seen = []

                    def deny(expression, *_):
                        seen.append(expression)
                        return False

                    with self.assertRaisesRegex(ValueError, "criterion is not met"):
                        generic_transports.resolve(
                            dict(map_id=source["map_id"], instance_id=0),
                            struct.pack(
                                ">qiBi",
                                source["id"],
                                destination["destination_id"],
                                0,
                                2,
                            ),
                            source_allowed=lambda *_: True,
                            criterion_evaluator=deny,
                        )
                    self.assertEqual(seen, [destination["criterion"]])
            self.assertGreater(guarded, 0)
        print(
            "Reviewed artifact gateways:",
            len(sources),
            "sources;",
            sum(len(s["destinations"]) for s in sources),
            "destinations; 26 definitions",
        )

    def test_all_artifact_routes_require_owned_projection_and_preserve_other_prices(
        self,
    ):
        catalog = copy.deepcopy(generic_transports._CATALOG)
        artifact_routes = [
            (source, destination)
            for source in generic_transports._CATALOG
            for destination in source["destinations"]
            if destination["cyW"] > 0
            and destination["item_reference"] in exploration_secrets.ITEM_REFS
            and not travel_mists.recognizes(source)
        ]
        self.assertEqual(len(artifact_routes), 60)
        self.assertEqual(
            {
                ref: sum(d["item_reference"] == ref for _, d in artifact_routes)
                for ref in (18591, 19113)
            },
            {18591: 40, 19113: 20},
        )
        forbidden = Mock(
            side_effect=AssertionError("Artifact route unexpectedly queried a mission")
        )

        def actor(source, refs=exploration_secrets.ITEM_REFS):
            return dict(
                id=1,
                account_id=7,
                level=1,
                map_id=source["map_id"],
                instance_id=0,
                inventory_items=[],
                account_quest_items=[],
                exploration_secrets=dict(
                    account_item_refs=refs,
                    world_properties=exploration_secrets.MOVEMENT_PROPERTIES,
                ),
            )

        def request(source, destination):
            return struct.pack(
                ">qiBi", source["id"], destination["destination_id"], 0, 2
            )

        for source, destination in artifact_routes:
            with self.subTest(
                source=source["id"], destination=destination["destination_id"]
            ):
                current = actor(source)
                before = copy.deepcopy(current)
                route = generic_transports.resolve(
                    current,
                    request(source, destination),
                    source_allowed=lambda *_: True,
                    criterion_evaluator=forbidden,
                )
                self.assertNotIn("item_payment", route)
                self.assertEqual(
                    route["destination"],
                    {
                        **{key: destination[key] for key in ("map_id", "x", "y", "z")},
                        "instance_id": 0,
                    },
                )
                self.assertEqual(current, before)
                disabled = actor(source, ())
                with self.assertRaisesRegex(ValueError, "item transaction"):
                    generic_transports.resolve(
                        disabled,
                        request(source, destination),
                        source_allowed=lambda *_: True,
                        criterion_evaluator=forbidden,
                    )
                paid = generic_transports.resolve(
                    disabled,
                    request(source, destination),
                    source_allowed=lambda *_: True,
                    criterion_evaluator=forbidden,
                    allow_item_payment=True,
                )
                self.assertEqual(
                    paid["item_payment"],
                    dict(
                        reference=destination["item_reference"],
                        quantity=destination["cyW"],
                    ),
                )

        source, destination = artifact_routes[0]
        for malformed in ((18591, 18591), (19,), (True,), None):
            with self.subTest(malformed=malformed), self.assertRaisesRegex(
                ValueError, "owned exploration"
            ):
                generic_transports.resolve(
                    actor(source, malformed),
                    request(source, destination),
                    source_allowed=lambda *_: True,
                )
        foreign = actor(source)
        foreign["account_quest_items"] = [
            dict(account_id=8, reference=destination["item_reference"], quantity=1)
        ]
        with self.assertRaisesRegex(ValueError, "Foreign"):
            generic_transports.resolve(
                foreign, request(source, destination), source_allowed=lambda *_: True
            )
        physical_only = actor(source, ())
        physical_only["account_quest_items"] = [
            dict(account_id=7, reference=destination["item_reference"], quantity=1)
        ]
        with self.assertRaisesRegex(ValueError, "item transaction"):
            generic_transports.resolve(
                physical_only,
                request(source, destination),
                source_allowed=lambda *_: True,
            )

        for reference in (33075, 18193):
            source, destination = next(
                (s, d)
                for s in generic_transports._CATALOG
                for d in s["destinations"]
                if d["item_reference"] == reference
                and d["cyW"] > 0
                and d["cyZ"] < 0
                and d["cyX"] == 0
                and d["native_altitude_walkable"]
                and not travel_mists.recognizes(s)
            )
            with self.subTest(unrelated_price=reference):
                with self.assertRaisesRegex(ValueError, "item transaction"):
                    generic_transports.resolve(
                        actor(source),
                        request(source, destination),
                        source_allowed=lambda *_: True,
                        criterion_evaluator=lambda *_: True,
                    )
                paid = generic_transports.resolve(
                    actor(source),
                    request(source, destination),
                    source_allowed=lambda *_: True,
                    criterion_evaluator=lambda *_: True,
                    allow_item_payment=True,
                )
                self.assertEqual(
                    paid["item_payment"],
                    dict(reference=reference, quantity=destination["cyW"]),
                )

        mists = [s for s in generic_transports._CATALOG if travel_mists.recognizes(s)]
        self.assertEqual(len(mists), 27)
        self.assertEqual(sum(len(s["destinations"]) for s in mists), 31)
        for source in mists:
            for destination in source["destinations"]:
                route = generic_transports.resolve(
                    actor(source, ()),
                    request(source, destination),
                    source_allowed=lambda *_: True,
                    criterion_evaluator=forbidden,
                )
                self.assertEqual(route["criterion"], "")
                self.assertNotIn("item_payment", route)
        forbidden.assert_not_called()
        self.assertEqual(generic_transports._CATALOG, catalog)
