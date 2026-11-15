"""Scene batches preserve loader order and successful-write boundaries."""

from types import SimpleNamespace
import struct
import unittest
from unittest.mock import patch

from wakfu_server.application.session_world import WorldSessionMixin


class ScenePublicationBatchTests(unittest.TestCase):
    def exercise(self, fail_batch=None):
        events = []
        regions = frozenset({(-1, 0), (0, 0)})
        batches = []

        def write(_connection, _service, packets):
            packets = tuple(packets)
            batches.append(packets)
            events.append("write")
            if len(batches) == fail_batch:
                raise OSError("socket write failed")

        def resources(*args, **kwargs):
            self.assertEqual(args, (527, 0))
            self.assertEqual(kwargs["chunks"], regions)
            events.append("resource_query")
            return [(13135, b"resource")]

        runtime = SimpleNamespace(
            STORE=object(),
            send_batch=write,
            PLANTINGS=SimpleNamespace(snapshots=resources),
            is_dungeon_run=lambda _: False,
            snapshot_ids=lambda _: [7, 8],
            record=lambda **_: events.append("record"),
        )
        subject = SimpleNamespace(
            runtime=runtime,
            state=SimpleNamespace(
                loaded=True,
                fight=None,
                spectator_session=None,
                character=dict(id=99, map_id=527, instance_id=0, x=-1, y=2),
                connection=object(),
                service="world",
                scene_sync=SimpleNamespace(
                    last_regions=regions, poll=lambda *_: (b"first", b"second")
                ),
            ),
            publish_environment_scene=lambda **_: events.append("environment"),
        )
        with patch(
            "wakfu_server.treasure_definition_projections.project_snapshot_bodies",
            side_effect=lambda _store, _map, bodies: bodies,
        ):
            if fail_batch is None:
                WorldSessionMixin.sync_scene_world(subject)
            else:
                with self.assertRaises(OSError):
                    WorldSessionMixin.sync_scene_world(subject)
        return events, batches

    def test_loader_and_static_batch_precede_resource_query_and_publication(self):
        events, batches = self.exercise()
        self.assertEqual(
            events, ["write", "resource_query", "write", "environment", "record"]
        )
        self.assertEqual(
            batches,
            [
                (
                    (12318, struct.pack(">ii", -1, 2)),
                    (13984, b"first"),
                    (13984, b"second"),
                ),
                ((13135, b"resource"),),
            ],
        )

    def test_failed_write_stops_later_queries_and_publications(self):
        for fail_batch, expected in (
            (1, ["write"]),
            (2, ["write", "resource_query", "write"]),
        ):
            with self.subTest(fail_batch=fail_batch):
                events, _ = self.exercise(fail_batch)
                self.assertEqual(events, expected)
