"""Synthetic reducer and native occupation checks for reusable object trials."""

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import sys
import struct
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import wakfu_server
from wakfu_server import owned_object_trials as trials


def synthetic_profile(duration_ms=0):
    payload = b"native-source-payload"
    return dict(
        schema=trials.SCHEMA,
        id="synthetic-object-trial",
        map_id=2698,
        maximum_members=1,
        sources=[
            dict(
                id=101,
                position=[1, 1, 0],
                descriptor_id=401,
                action=0,
                duration_ms=duration_ms,
                payload_sha256=sha256(payload).hexdigest(),
                approaches=[[0, 0, 0]],
            ),
            dict(
                id=102,
                position=[2, 1, 0],
                descriptor_id=402,
                action=0,
                duration_ms=0,
                payload_sha256=sha256(payload).hexdigest(),
                approaches=[[0, 1, 0]],
            ),
            dict(
                id=103,
                position=[3, 1, 0],
                descriptor_id=403,
                action=0,
                duration_ms=0,
                payload_sha256=sha256(payload).hexdigest(),
                approaches=[[1, 0, 0]],
            ),
            dict(
                id=104,
                position=[4, 1, 0],
                descriptor_id=404,
                action=0,
                duration_ms=0,
                payload_sha256=sha256(payload).hexdigest(),
                approaches=[[1, 1, 0]],
            ),
        ],
        trials=[
            dict(
                id="ordered",
                kind="ordered_objects",
                requires=[],
                sources=[101, 102],
                effects={
                    "begin": [],
                    "success": ["ordered-done"],
                    "failure": ["order-reset"],
                },
            ),
            dict(
                id="distinct",
                kind="distinct_discoveries",
                requires=["ordered"],
                sources=[102, 103],
                effects={"begin": [], "success": ["discoveries-done"], "failure": []},
            ),
            dict(
                id="ordered-after-discovery",
                kind="ordered_objects",
                requires=["distinct"],
                sources=[103],
                effects={"begin": [], "success": ["third-done"], "failure": []},
            ),
            dict(
                id="fragile-carry",
                kind="fragile_carry",
                requires=["ordered-after-discovery"],
                pickup_source=104,
                destination_cells=[[5, 0, 0]],
                hazard_cells=[[3, 0, 0]],
                failure_policy="return_to_pickup",
                effects={
                    "begin": ["carry-started"],
                    "success": ["carry-done"],
                    "failure": ["carry-lost"],
                },
            ),
        ],
    )


def event(kind, **values):
    return dict(kind=kind, **values)


class MemoryDB:
    """Minimal synthetic event table for occupation protocol transitions."""

    def __init__(self):
        self.events = {}

    def execute(self, sql, params):
        if "SELECT event_key FROM character_achievement_events e" in sql:
            character_id, prefix_length, prefix = params
            rows = [
                {"event_key": key}
                for (owner, key) in self.events
                if owner == character_id
                and key.startswith(prefix)
                and not (owner, "owned-object-trial-done:" + key) in self.events
            ]
            return SimpleNamespace(fetchall=lambda: deepcopy(rows))
        if "AND left(event_key,%s)=%s" in sql:
            return SimpleNamespace(fetchone=lambda: None)
        if "WHERE character_id=%s AND event_key=%s" in sql:
            character_id, key = params
            payload = self.events.get((character_id, key))
            return SimpleNamespace(
                fetchone=lambda: None if payload is None else {"payload": payload}
            )
        raise AssertionError("Unexpected synthetic trial SQL: " + sql)


class OwnedObjectTrialsTests(unittest.TestCase):
    def test_exact_raw_native_payload_authenticates_without_authoring_descriptor_metadata(
        self,
    ):
        selected = synthetic_profile()
        source = selected["sources"][0]
        current = dict(x=0, y=0, z=0)
        raw = dict(
            id=101,
            x=1,
            y=1,
            z=0,
            type="GenericActivableInteractiveElement",
            payload_hex=b"native-source-payload".hex(),
        )
        fake_world = SimpleNamespace(objects=Mock(return_value=[raw]))
        with patch.dict(
            sys.modules, {"wakfu_server.world_static": fake_world}
        ), patch.object(wakfu_server, "world_static", fake_world, create=True):
            trials._native_source(selected, current, source, 0)
            for changed in (
                dict(raw, descriptor_id=999),
                dict(raw, payload_hex=b"changed".hex()),
            ):
                fake_world.objects.return_value = [changed]
                with self.assertRaisesRegex(ValueError, "native authority"):
                    trials._native_source(selected, current, source, 0)

    def test_order_distinct_discovery_hazards_and_stage_boundaries(self):
        selected = synthetic_profile()
        state = trials.initial_state(selected)

        def apply(fact):
            nonlocal state
            result = trials.reduce(selected, state, fact)
            state = result["state"]
            return result

        wrong = apply(event("interact", source_id=102))
        self.assertEqual(wrong["effects"], ["order-reset"])
        self.assertEqual(state["trials"]["ordered"]["index"], 0)
        apply(event("interact", source_id=101))
        first_order_finish = apply(event("interact", source_id=102))
        self.assertEqual(first_order_finish["effects"], ["ordered-done"])
        self.assertNotIn("distinct", state["trials"])

        first_discovery = apply(event("interact", source_id=102))
        self.assertTrue(first_discovery["changed"])
        self.assertEqual(state["trials"]["distinct"]["discovered"], [102])
        duplicate = apply(event("interact", source_id=102))
        self.assertFalse(duplicate["changed"])
        second_discovery = apply(event("interact", source_id=103))
        self.assertEqual(second_discovery["effects"], ["discoveries-done"])
        self.assertNotIn("ordered-after-discovery", state["trials"])
        third_order = apply(event("interact", source_id=103))
        self.assertEqual(third_order["effects"], ["third-done"])

        started = apply(event("interact", source_id=104))
        self.assertEqual(started["effects"], ["carry-started"])
        hazard_in_path = apply(
            event("movement", cells=[[2, 0, 0], [3, 0, 0], [4, 0, 0]])
        )
        self.assertEqual(hazard_in_path["effects"], ["carry-lost"])
        carry = state["trials"]["fragile-carry"]
        self.assertFalse(carry["carrying"])
        self.assertEqual(carry["failures"], 1)
        apply(event("interact", source_id=104))
        delivered = apply(event("movement", cells=[[4, 0, 0], [5, 0, 0]]))
        self.assertEqual(delivered["effects"], ["carry-done"])
        completed = deepcopy(state)
        replay = apply(event("movement", cells=[[3, 0, 0], [5, 0, 0]]))
        self.assertFalse(replay["changed"])
        self.assertEqual(replay["effects"], [])
        self.assertEqual(state, completed)

    def test_profile_hash_mismatch_and_effect_exception_never_commit_receipt(self):
        selected = synthetic_profile()
        with self.assertRaisesRegex(ValueError, "another pinned profile"):
            trials.reduce(
                selected,
                trials.initial_state(dict(selected, id="other-profile")),
                event("interact", source_id=101),
            )

        character = dict(
            id=17, account_id=9, instance_id=33, map_id=2698, x=0, y=0, z=0
        )
        db = MemoryDB()
        store = SimpleNamespace(now=lambda: datetime(2026, 11, 15, tzinfo=timezone.utc))
        failed = Mock(side_effect=RuntimeError("mechanical effect failed"))
        with patch.object(trials.storage, "record_event") as record:
            with self.assertRaisesRegex(RuntimeError, "mechanical effect"):
                trials._settle(
                    db,
                    store,
                    character,
                    selected,
                    event("interact", source_id=101),
                    "synthetic-failed-step",
                    failed,
                )
        record.assert_not_called()

    def test_source_accept_effects_resolve_only_declared_server_facts(self):
        selected = synthetic_profile()
        selected["trials"][0]["source_effects"] = {
            "101": {"accept": [{"fact": "previous_index"}]},
            "102": {"accept": [{"fact": "index"}]},
        }
        state = trials.initial_state(selected)
        first = trials.reduce(selected, state, event("interact", source_id=101))
        self.assertEqual(first["effects"], [0])
        second = trials.reduce(
            selected, first["state"], event("interact", source_id=102)
        )
        self.assertEqual(second["effects"], [2, "ordered-done"])

        selected["trials"][0]["source_effects"]["101"]["accept"] = [
            {"fact": "client_progress_value"}
        ]
        with self.assertRaisesRegex(ValueError, "unknown server fact"):
            trials.reduce(
                selected,
                trials.initial_state(selected),
                event("interact", source_id=101),
            )

    def test_native_timed_occupation_checks_lease_due_stationarity_and_retry(self):
        selected = synthetic_profile(duration_ms=1000)
        character = dict(
            id=17, account_id=9, instance_id=33, map_id=2698, x=0, y=0, z=0
        )
        clock = [datetime(2026, 11, 15, tzinfo=timezone.utc)]
        store = SimpleNamespace(now=lambda: clock[0])
        payload_hex = b"native-source-payload".hex()
        native = dict(
            id=101,
            descriptor_id=401,
            x=1,
            y=1,
            z=0,
            payload_hex=payload_hex,
        )
        db = MemoryDB()
        token = "timed-source"
        ticket = None

        def record(_db, _owner, _key, payload):
            nonlocal ticket
            _db.events[(_owner, _key)] = deepcopy(payload)
            if payload.get("schema") == trials.SCHEMA and "due_ms" in payload:
                ticket = deepcopy(payload)
            return True

        fake_world = SimpleNamespace(objects=Mock(return_value=[native]))
        with patch.dict(
            sys.modules, {"wakfu_server.world_static": fake_world}
        ), patch.object(wakfu_server, "world_static", fake_world, create=True), patch(
            "wakfu_server.inventory_items._lease"
        ), patch.object(
            trials, "_scope", return_value=(selected, character)
        ), patch.object(
            trials.storage, "record_event", side_effect=record
        ):
            pending = trials.interact(
                db,
                store,
                character,
                struct.pack(">qHH", 101, 0, 0),
                token=token,
                generation="session-a",
                apply_effects=Mock(),
            )
            self.assertFalse(pending["changed"])
            self.assertEqual(
                pending["pending"]["due_ms"], int(clock[0].timestamp() * 1000) + 1000
            )
            self.assertEqual(ticket["generation"], "session-a")

            with self.assertRaisesRegex(ValueError, "not qualified or elapsed"):
                trials.complete_interaction(
                    db,
                    store,
                    character,
                    token,
                    generation="session-b",
                    apply_effects=Mock(),
                )
            with self.assertRaisesRegex(ValueError, "not qualified or elapsed"):
                trials.complete_interaction(
                    db,
                    store,
                    character,
                    token,
                    generation="session-a",
                    apply_effects=Mock(),
                )

            clock[0] += timedelta(seconds=1)
            before_effect_failure = len(db.events)
            effect_failure = Mock(side_effect=RuntimeError("effect rollback"))
            with self.assertRaisesRegex(RuntimeError, "effect rollback"):
                trials.complete_interaction(
                    db,
                    store,
                    character,
                    token,
                    generation="session-a",
                    apply_effects=effect_failure,
                )
            self.assertEqual(len(db.events), before_effect_failure)

            applied = Mock(return_value=[(13832, b"objective")])
            completed = trials.complete_interaction(
                db,
                store,
                character,
                token,
                generation="session-a",
                apply_effects=applied,
            )
        self.assertTrue(completed["changed"])
        applied.assert_called_once()

    def test_timed_occupation_cancels_after_character_moves(self):
        selected = synthetic_profile(duration_ms=1000)
        character = dict(
            id=17, account_id=9, instance_id=33, map_id=2698, x=0, y=0, z=0
        )
        clock = [datetime(2026, 11, 15, tzinfo=timezone.utc)]
        store = SimpleNamespace(now=lambda: clock[0])
        native = dict(
            id=101,
            descriptor_id=401,
            x=1,
            y=1,
            z=0,
            payload_hex=b"native-source-payload".hex(),
        )
        ticket = dict(
            schema=trials.SCHEMA,
            owner=17,
            instance_id=33,
            profile_sha256=trials.digest(selected),
            source_id=101,
            generation="session-a",
            position=[0, 0, 0],
            due_ms=int(clock[0].timestamp() * 1000) + 1000,
        )
        db = MemoryDB()

        def record(_db, _owner, key, payload):
            _db.events[(_owner, key)] = deepcopy(payload)
            return True

        fake_world = SimpleNamespace(objects=Mock(return_value=[native]))
        with patch.dict(
            sys.modules, {"wakfu_server.world_static": fake_world}
        ), patch.object(wakfu_server, "world_static", fake_world, create=True), patch(
            "wakfu_server.inventory_items._lease"
        ), patch.object(
            trials, "_scope", return_value=(selected, character)
        ), patch.object(
            trials.storage, "record_event", side_effect=record
        ):
            trials.interact(
                db,
                store,
                character,
                struct.pack(">qHH", 101, 0, 0),
                token="moving-source",
                generation="session-a",
                apply_effects=Mock(),
            )
            clock[0] += timedelta(seconds=1)
            moved = dict(character, x=1)
            with patch.object(trials, "_scope", return_value=(selected, moved)):
                outcome = trials.complete_interaction(
                    db,
                    store,
                    moved,
                    "moving-source",
                    generation="session-a",
                    apply_effects=Mock(),
                )
        self.assertTrue(outcome["cancelled"])
        self.assertFalse(outcome["changed"])

    def test_accepted_move_away_and_back_cancels_pending_timed_occupation(self):
        selected = synthetic_profile(duration_ms=1000)
        character = dict(
            id=17, account_id=9, instance_id=33, map_id=2698, x=0, y=0, z=0
        )
        clock = [datetime(2026, 11, 15, tzinfo=timezone.utc)]
        store = SimpleNamespace(now=lambda: clock[0])
        native = dict(
            id=101,
            descriptor_id=401,
            x=1,
            y=1,
            z=0,
            payload_hex=b"native-source-payload".hex(),
        )
        db = MemoryDB()

        def record(_db, owner, key, payload):
            _db.events[(owner, key)] = deepcopy(payload)
            return True

        fake_world = SimpleNamespace(objects=Mock(return_value=[native]))
        apply = Mock(return_value=[(13832, b"must-not-award")])
        with patch.dict(
            sys.modules, {"wakfu_server.world_static": fake_world}
        ), patch.object(wakfu_server, "world_static", fake_world, create=True), patch(
            "wakfu_server.inventory_items._lease"
        ), patch.object(
            trials, "_scope", return_value=(selected, character)
        ), patch.object(
            trials.storage, "record_event", side_effect=record
        ):
            trials.interact(
                db,
                store,
                character,
                struct.pack(">qHH", 101, 0, 0),
                token="away-and-back",
                generation="session-a",
                apply_effects=apply,
            )
            clock[0] += timedelta(seconds=1)
            outcome = trials.on_landing(
                db,
                store,
                character,
                [[0, 0, 0], [1, 0, 0], [0, 0, 0]],
                token="loop-path",
                apply_effects=apply,
            )
            finished = trials.complete_interaction(
                db,
                store,
                character,
                "away-and-back",
                generation="session-a",
                apply_effects=apply,
            )

        self.assertTrue(outcome["cancelled_occupation"])
        self.assertFalse(outcome["changed"])
        self.assertFalse(finished["changed"])
        apply.assert_not_called()


if __name__ == "__main__":
    unittest.main()
