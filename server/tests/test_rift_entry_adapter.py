"""Native portal isolation and admission transaction regression tests."""
import contextlib
import struct
import unittest
from unittest.mock import Mock, patch

from wakfu_server import rift_entry_adapter as adapter


class RiftEntryAdapterTests(unittest.TestCase):
    def setUp(self):
        self.portal = {
            "wave_id": 3,
            "map_id": 1314,
            "level": 21,
            "entrances": [{"map_id": 527, "object_id": 33010}],
        }
        self.body = struct.pack(">qHH", 33010, 11, 0)

    def test_native_exact_action_layout(self):
        self.assertEqual(adapter.decode_action(self.body), (33010, 11))
        for body in (
            b"",
            self.body[:-1],
            self.body + b"\0",
            struct.pack(">qHH", 33010, 11, 1),
            "not bytes",
        ):
            with self.assertRaises(ValueError):
                adapter.decode_action(body)

    def test_portal_is_bound_to_source_map_and_action(self):
        catalog = {"3": self.portal}
        self.assertEqual(
            adapter.resolve_portal(catalog, 527, self.body),
            (self.portal, self.portal["entrances"][0]),
        )
        self.assertIsNone(adapter.resolve_portal(catalog, 528, self.body))
        self.assertIsNone(
            adapter.resolve_portal(catalog, 527, struct.pack(">qHH", 33010, 0, 0))
        )

    def test_ambiguous_catalog_fails_closed(self):
        with self.assertRaises(ValueError):
            adapter.resolve_portal({"3": self.portal, "4": self.portal}, 527, self.body)

    def test_lore_action_never_starts_fight_or_reads_database(self):
        db = Mock()
        self.assertIsNone(
            adapter.authorize_start(
                db,
                Mock(),
                1,
                "session",
                1,
                struct.pack(">qHH", 33012, 1, 0),
                source_allowed=lambda *a: True,
            )
        )
        db.execute.assert_not_called()

    def _entry(self, *, destination=None, source_allowed=lambda *a: True):
        db = Mock()
        db.execute.return_value.fetchone.return_value = {"value": {"3": self.portal}}
        store = Mock()
        store.connection = lambda: contextlib.nullcontext(db)
        row = {
            "id": 1,
            "account_id": 2,
            "generation": "session",
            "map_id": 527,
            "instance_id": 0,
            "level": 21,
            "x": 0,
            "y": 0,
            "z": 0,
        }
        run = {"instance_id": 99}
        resolver = Mock(
            return_value=destination or {"map_id": 1314, "x": 0, "y": 1, "z": 0}
        )
        with patch.object(adapter, "_roster", return_value=[row]), patch.object(
            adapter.rift_runtime, "enter", return_value=run
        ) as enter:
            result = adapter.enter(
                store,
                2,
                "session",
                1,
                527,
                self.body,
                source_allowed=source_allowed,
                resolve_destination=resolver,
                seed="stable",
            )
        return result, db, enter

    def test_atomic_transition_uses_only_server_minted_instance(self):
        result, db, enter = self._entry()
        self.assertEqual(result["destination"]["instance_id"], 99)
        self.assertEqual(db.execute.call_args.args[1], (1314, 99, 0, 1, 0, 1))
        self.assertEqual(enter.call_args.kwargs["seed"], "stable")

    def test_party_entry_freezes_and_moves_every_member_without_solo_fallback(self):
        db, store = Mock(), Mock()
        db.execute.return_value.fetchone.return_value = {"value": {"3": self.portal}}
        store.connection = lambda: contextlib.nullcontext(db)
        rows = [
            dict(
                id=i,
                account_id=i,
                generation="session",
                map_id=527,
                instance_id=0,
                level=21,
                x=0,
                y=0,
                z=0,
            )
            for i in (1, 2)
        ]
        with patch.object(adapter, "_roster", return_value=rows), patch.object(
            adapter.rift_runtime, "enter", return_value={"instance_id": 99}
        ) as create:
            result = adapter.enter(
                store,
                1,
                "session",
                1,
                527,
                self.body,
                source_allowed=lambda *args: True,
                resolve_destination=lambda *args: {
                    "map_id": 1314,
                    "x": 0,
                    "y": 1,
                    "z": 0,
                },
            )
        self.assertEqual([1, 2], create.call_args.args[3])
        self.assertEqual(rows, list(result["members"]))
        updates = [
            call.args[1][-1]
            for call in db.execute.call_args_list
            if call.args[0].startswith("UPDATE characters")
        ]
        self.assertEqual([1, 2], updates)

    def test_invalid_native_arrival_rejects_before_any_position_update(self):
        with self.assertRaisesRegex(ValueError, "arrival"):
            self._entry(destination={"map_id": 527, "x": 0, "y": 1, "z": 0})

    def test_denied_source_never_creates_run(self):
        with self.assertRaisesRegex(ValueError, "eligible"):
            self._entry(source_allowed=lambda *a: False)


if __name__ == "__main__":
    unittest.main()
