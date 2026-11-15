"""Celestial Dojo native path: arrival script, hidden carrier and lesson scene.

Authority is the private official capture of 2026-11-12, decoded in
`agents_docs/reports/quest-reconstruction/dojo-official-contract-20261112.json`:
entering map 1388 publishes scenario 2543 events 22403 (dojo actor identities)
and 22490 (ready, one zero); the client callback completes objective 11542 and
hidden carrier 5592; all seven lesson bootstraps use terrain template 378 and
fight model 14 with the player on team 1 against the sack on team 0.
"""

import struct
from types import SimpleNamespace
import unittest
from contextlib import contextmanager
from unittest.mock import Mock, patch

from wakfu_server import mission_transport
from wakfu_server.achievements import (
    rii_dojo_arrival,
    storage,
    transport_missions,
    wire,
    zone_missions,
)

CARRIER = {
    "d": 5592,
    "native_class": "aJM",
    "aqb": True,
    "isVisible": False,
    "cjI": "",
    "cjJ": [{"d": 11542, "ckc": "", "cke": "", "ckf": [], "ckb": True}],
    "cjK": [],
    "cjL": 0,
    "cjU": 0,
    "getDuration": 0,
}


def _scenario(body):
    mode, event, scenario, count = struct.unpack_from(">BiiB", body, 0)
    return dict(
        mode=mode,
        event=event,
        scenario=scenario,
        arguments=[
            struct.unpack_from(">q", body, 10 + 8 * index)[0] for index in range(count)
        ],
    )


class DojoArrivalTests(unittest.TestCase):
    def setUp(self):
        self.db = object()
        self.source = {"id": 7, "account_id": 1, "map_id": 1385}
        self.saved = {"id": 7, "account_id": 1, "map_id": 1388}

        @contextmanager
        def connection():
            yield self.db

        self.store = Mock()
        self.store.connection.side_effect = connection
        self.store.transition_map_in_transaction.return_value = self.saved

    def test_entering_the_dojo_publishes_the_native_script_bootstrap(self):
        with patch.object(
            rii_dojo_arrival, "scene_uids", return_value=[-42, -77]
        ), patch.object(zone_missions, "enter_rii", return_value=[]):
            _saved, packets = mission_transport.transition(
                self.store,
                1,
                3,
                self.source,
                {"destination": {"map_id": 1388}},
                native_zaap=False,
            )
        self.assertEqual([opcode for opcode, _ in packets], [13411, 13411])
        self.assertEqual(
            [_scenario(body) for _, body in packets],
            [
                dict(mode=0, event=22403, scenario=2543, arguments=[-42, -77]),
                dict(mode=0, event=22490, scenario=2543, arguments=[0]),
            ],
        )

    def test_leaving_rii_does_not_announce_the_dojo_script(self):
        with patch.object(zone_missions, "enter_rii", return_value=[]), patch.object(
            transport_missions, "on_native_transport", return_value=[]
        ):
            _saved, packets = mission_transport.transition(
                self.store,
                1,
                3,
                {"id": 7, "account_id": 1, "map_id": 1388},
                {"destination": {"map_id": 1385}},
                native_zaap=False,
            )
        self.assertNotIn(13411, [opcode for opcode, _ in packets])


class DojoCarrierTests(unittest.TestCase):
    def setUp(self):
        self.db = Mock()
        self.store = Mock()
        self.store.now.return_value.timestamp.return_value = 1.5
        self.character = {"id": 7, "account_id": 1, "map_id": 1388, "instance_id": 0}
        self.state = {
            "variables": {},
            "objectives": [],
            "running": [],
            "completed": [],
            "tracking": [],
            "recent": [],
            "completion_dates": {},
        }

    def test_carrier_validation_requires_the_installed_definition(self):
        self.assertEqual(rii_dojo_arrival.validate_carrier(CARRIER), CARRIER)
        for change in (
            {"aqb": False},
            {"cjJ": [{"d": 11543, "ckc": "", "cke": "", "ckf": []}]},
            {"cjK": [{"d": 1, "aeV": 6, "ckl": [1]}]},
            {"cjU": 86400},
        ):
            tampered = dict(CARRIER, **change)
            with self.subTest(change=list(change)), self.assertRaises(ValueError):
                rii_dojo_arrival.validate_carrier(tampered)

    def test_callback_completes_the_carrier_once_with_journal_packets(self):
        with patch.object(
            storage, "load_locked", return_value=dict(self.state)
        ), patch.object(
            storage, "record_event", return_value=True
        ) as receipt, patch.object(
            storage, "store"
        ) as save, patch.object(
            rii_dojo_arrival, "carrier_definition", return_value=CARRIER
        ):
            packets = rii_dojo_arrival.settle(
                self.db, self.store, self.character, rii_dojo_arrival.READY
            )
        self.assertEqual([opcode for opcode, _ in packets], [13832, 13422])
        self.assertEqual(struct.unpack_from(">i", packets[0][1], 8)[0], 11542)
        self.assertEqual(struct.unpack_from(">i", packets[1][1], 8)[0], 5592)
        self.assertEqual(struct.unpack_from(">q", packets[1][1], 12)[0], 1500)
        receipt.assert_called_once()
        saved = save.call_args[0][2]
        self.assertEqual(saved["objectives"], [11542])
        self.assertEqual(saved["completed"], [5592])
        self.assertEqual(saved["recent"], [{"id": 5592, "date_ms": 1500}])

    def test_replayed_callback_and_other_scenes_produce_nothing(self):
        self.state.update(objectives=[11542], completed=[5592])
        with patch.object(storage, "load_locked", return_value=dict(self.state)):
            self.assertEqual(
                rii_dojo_arrival.settle(
                    self.db, self.store, self.character, rii_dojo_arrival.READY
                ),
                [],
            )
        for event, where in (
            (rii_dojo_arrival.READY, {"map_id": 1385, "id": 7, "account_id": 1}),
            (rii_dojo_arrival.ACTORS, {"map_id": 1388, "id": 7, "account_id": 1}),
        ):
            with self.subTest(event=event), patch.object(
                storage, "load_locked", return_value=dict(self.state)
            ):
                self.assertEqual(
                    rii_dojo_arrival.settle(self.db, self.store, where, event),
                    [],
                )

    def test_delivery_requires_the_unmoved_owner(self):
        moved = dict(self.character, x=1)
        source = dict(self.character, x=0)
        connection = Mock()
        connection.__enter__ = Mock(return_value=self.db)
        connection.__exit__ = Mock(return_value=False)
        self.store.connection.return_value = connection
        self.store.character.return_value = moved
        with self.assertRaises(ValueError):
            rii_dojo_arrival.deliver_callback(self.store, 1, 2, source)
        self.store.lock_character.assert_called_once_with(
            self.db, 1, 2, 7, selected=True
        )


class DojoLessonSceneTests(unittest.TestCase):
    def test_lesson_placement_uses_the_native_terrain_and_fight_model(self):
        from wakfu_server.combat_placement_policy import _arena

        from wakfu_server.combat_geometry import published_geometry

        cells = sorted(published_geometry(1388).cells)[:12]
        edges = [
            [start, end]
            for start in cells
            for end in published_geometry(1388).outgoing.get(tuple(start), ())
            if end in cells
        ]
        layout = {
            "cells": cells,
            "edges": edges,
            "wire_instance_id": 0,
            "placement": {0: [cells[0]], 1: [cells[-1]]},
            "native_rii_lesson_layout": {
                "schema": "rii-observed-lesson-placement-v1",
                "owner": 7,
                "objective": 10574,
            },
            "participant_player_position": [(cells[0], cells[1])],
        }
        arena = _arena(1388, 0, layout)
        self.assertEqual(arena["terrain_effect_id"], 378)
        self.assertEqual(arena["native_fight_model"], 14)
        with self.assertRaises(ValueError):
            _arena(
                527,
                0,
                dict(
                    layout,
                    cells=sorted(published_geometry(527).cells)[:12],
                    edges=[],
                ),
            )


class JournalOrderTests(unittest.TestCase):
    def test_activation_follows_the_active_mission_facts(self):
        before = {
            "variables": {},
            "objectives": [],
            "running": [],
            "completed": [],
            "tracking": [],
            "recent": [],
            "completion_dates": {},
        }
        definition = {
            "d": 5145,
            "native_class": "aJM",
            "aqb": False,
            "cjJ": [{"d": 10597, "ckc": "", "cke": "", "ckf": [{"ckn": [756]}]}],
        }
        after = {
            "variables": {"756": 0},
            "objectives": [10615, 10607],
            "running": [5145],
            "completed": [],
            "tracking": [5145],
            "recent": [],
            "completion_dates": {},
        }
        packets = wire.changes(
            7,
            before,
            after,
            [10615, 10607],
            [],
            1000,
            definitions={5145: definition},
        )
        # Official 19:19:53: parent objectives, the new counters at zero, then
        # ctx/ctq/ctu of the activated mission.
        self.assertEqual(
            [opcode for opcode, _ in packets],
            [13832, 13832, 13295, 13205, 13312, 13371],
        )
        self.assertEqual(struct.unpack_from(">iq", packets[2][1], 8), (756, 0))


if __name__ == "__main__":
    unittest.main()
