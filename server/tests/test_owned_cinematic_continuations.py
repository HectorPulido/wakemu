"""Reviewed endpoint authority and once-only cinematic timeline transitions."""

from copy import deepcopy
from datetime import datetime, timezone, timedelta
import json
from pathlib import Path
import struct
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import wakfu_server
from wakfu_server import owned_cinematic_continuations as module

DOCUMENT = json.loads((module.ROOT / "astrub-ullu-898.json").read_text())


def sources():
    result = {}
    for entry in DOCUMENT["entries"]:
        result[(887, entry["source_id"])] = dict(
            destinations=[
                dict(
                    DOCUMENT["stage"],
                    destination_id=entry["destination_id"],
                    criterion="IsAchievementComplete(2170)",
                    cyZ=-1,
                    cyX=0,
                    cyW=0,
                    native_altitude_walkable=True,
                )
            ]
        )
    result[(887, 23582)]["destinations"].append(
        dict(
            map_id=527,
            x=44,
            y=-54,
            z=8,
            destination_id=2002,
            criterion="!IsAchievementComplete(2170)",
            cyZ=-1,
            cyX=0,
            cyW=0,
            native_altitude_walkable=True,
        )
    )
    return result


class CinematicPolicyTests(unittest.TestCase):
    def test_stage_namespace_reuses_existing_private_scope_and_rejects_foreign_owner(
        self,
    ):
        from wakfu_server.intro_cinematic import private_instance_id

        owner = dict(id=388, map_id=898, instance_id=module.stage_instance_id(388))
        self.assertEqual(owner["instance_id"], private_instance_id(388))
        self.assertTrue(module.owns_stage(owner))
        self.assertFalse(module.owns_stage(dict(owner, id=389)))
        self.assertFalse(module.owns_stage(dict(owner, instance_id=0)))
        self.assertFalse(module.owns_stage(dict(owner, map_id=527)))
        self.assertNotEqual(
            module.stage_instance_id(388), module.stage_instance_id(389)
        )

    def test_classification_preserves_precompletion_exit_and_other_unrelated_routes(
        self,
    ):
        self.assertIn(898, module.stage_maps())
        self.assertNotIn(527, module.stage_maps())
        with patch.object(module, "policy", return_value=DOCUMENT):
            self.assertTrue(
                module.recognizes({}, struct.pack(">qiBi", 23582, 2074, 0, 2))
            )
            for body in (
                struct.pack(">qiBi", 23582, 2002, 0, 2),
                b"bad",
                struct.pack(">qiBi", 23614, 2075, 1, 2),
            ):
                self.assertFalse(module.recognizes({}, body))
        self.assertFalse(module.recognizes({}, b"unrelated"))

    def test_both_actual_native_completed_exits_and_existing_return_anchor_are_required(
        self,
    ):
        native = sources()
        self.assertEqual(
            module.validate(deepcopy(DOCUMENT), lambda *k: native.get(k)), DOCUMENT
        )
        for mutate in (
            lambda d: d["entries"][0].update(destination_id=2002),
            lambda d: d["stage"].update(map_id=527),
            lambda d: d["return_anchor"].update(x=45),
            lambda d: d.update(quest_id=2166),
            lambda d: d["presentation"].update(duration_ms=True),
        ):
            document = deepcopy(DOCUMENT)
            mutate(document)
            with self.subTest(document=document), self.assertRaises(ValueError):
                module.validate(document, lambda *k: native.get(k))

    def test_missing_unwalkable_or_paid_native_destinations_are_not_authorized(self):
        for change in (
            {"native_altitude_walkable": False},
            {"cyZ": 0},
            {"cyX": 1},
            {"cyW": 1},
        ):
            native = sources()
            native[(887, 23582)]["destinations"][0].update(change)
            with self.subTest(change=change), self.assertRaises(ValueError):
                module.validate(DOCUMENT, lambda *k: native.get(k))

    def test_packet_uses_real_owner_and_only_original_presentation_events(self):
        opcode, body = module.packet(DOCUMENT, 14387, 388)
        self.assertEqual(opcode, 13411)
        self.assertEqual(struct.unpack(">BiiBq", body), (0, 14387, 1731, 1, 388))
        self.assertEqual(
            module.packet(DOCUMENT, 14388, 388),
            (13411, struct.pack(">BiiB", 0, 14388, 1731, 0)),
        )
        for event, owner in ((14387, True), (14387, -1), (99999, 388)):
            with self.subTest(event=event, owner=owner), self.assertRaises(ValueError):
                module.packet(DOCUMENT, event, owner)


class CinematicTimelineTests(unittest.TestCase):
    def setUp(self):
        self.db = Mock()
        self.character = dict(
            id=388,
            account_id=314,
            instance_id=module.stage_instance_id(388),
            **DOCUMENT["stage"]
        )
        self.now = datetime(2026, 11, 15, tzinfo=timezone.utc)
        self.store = Mock()
        self.store.now.side_effect = lambda: self.now
        self.store.character.return_value = self.character
        self.arrival = dict(source_instance_id=91)
        self.pending = patch.object(
            module, "pending", return_value=(DOCUMENT, self.arrival)
        )
        self.pending.start()
        self.addCleanup(self.pending.stop)

    def test_ready_starts_once_and_reconnect_preserves_original_deadline(self):
        ledger = {}

        def record(db, owner, key, value):
            self.assertNotIn(key, ledger)
            ledger[key] = value
            return True

        with patch.object(
            module, "_event", side_effect=lambda db, owner, key: ledger.get(key)
        ), patch.object(module.storage, "record_event", side_effect=record):
            first = module.ready(self.db, self.store, 314, "first", 388)
            self.assertEqual(first["packets"], [module.packet(DOCUMENT, 14387, 388)])
            self.assertEqual(first["due_ms"], int(self.now.timestamp() * 1000) + 40700)
            self.now += timedelta(seconds=20)
            replay = module.ready(self.db, self.store, 314, "reconnect", 388)
            self.assertEqual(replay, dict(packets=[], due_ms=first["due_ms"]))
            self.assertEqual(len(ledger), 1)

    def test_no_client_callback_or_early_timer_can_finish_the_stage(self):
        due = int(self.now.timestamp() * 1000) + 40700
        with patch.object(
            module, "_event", return_value=dict(generation="first", due_ms=due)
        ), patch.object(module.storage, "record_event") as record:
            self.assertIsNone(module.finish(self.db, self.store, 314, "first", 388))
            self.db.execute.assert_not_called()
            self.store.transition_map_in_transaction.assert_not_called()
            record.assert_not_called()

    def test_due_return_uses_normal_transition_and_durable_exit_delivery_without_rewards(
        self,
    ):
        due = int(self.now.timestamp() * 1000)
        self.db.execute.side_effect = [
            SimpleNamespace(
                fetchone=lambda: dict(
                    instance_id=91, party_id=52, status="closed", revision=7
                )
            ),
            SimpleNamespace(fetchone=lambda: dict(status="returned")),
            Mock(),
            Mock(),
            Mock(),
            Mock(),
        ]
        saved = dict(self.character, map_id=527, x=44, y=-54, z=8)
        self.store.transition_map_in_transaction.return_value = saved
        with patch.object(
            module, "_event", return_value=dict(generation="first", due_ms=due)
        ), patch.object(module.storage, "record_event", return_value=True) as record:
            result = module.finish(self.db, self.store, 314, "first", 388)
            self.store.transition_map_in_transaction.assert_called_once_with(
                self.db,
                314,
                "first",
                388,
                self.character,
                dict(map_id=527, instance_id=0, x=44, y=-54, z=8),
            )
            self.assertEqual(
                result["before_transition_packets"],
                [module.packet(DOCUMENT, 14388, 388)],
            )
            self.assertEqual(result["transition_kind"], "exit")
            calls = self.db.execute.call_args_list
            self.assertIn("dungeon_transition_outbox", calls[-1].args[0])
            self.assertEqual(
                calls[-1].args[1],
                (
                    91,
                    52,
                    8,
                    388,
                    "first",
                    898,
                    module.stage_instance_id(388),
                    0,
                    0,
                    0,
                    527,
                    44,
                    -54,
                    8,
                ),
            )
            record.assert_called_once()


class CinematicAdmissionTests(unittest.TestCase):
    def test_unfinished_owned_arrival_resumes_same_stage_without_starting_a_new_scene(
        self,
    ):
        db, store = Mock(), Mock()
        character = dict(
            id=388, account_id=314, map_id=887, instance_id=92, x=0, y=-69, z=12
        )
        store.character.return_value = character
        selected = dict(
            cinematic_continuation=dict(path="astrub-ullu-898.json", sha256="a" * 64)
        )
        authority = SimpleNamespace(
            authenticate_exit=Mock(
                return_value=dict(controller=selected, completed_steps=set())
            )
        )
        exits = SimpleNamespace(
            _leave=Mock(
                return_value=dict(
                    map_id=898, instance_id=module.stage_instance_id(388), x=0, y=0, z=0
                )
            )
        )
        arrival = dict(
            schema=module.SCHEMA,
            owner=388,
            account_id=314,
            source_instance_id=91,
            policy_sha256=module._digest(DOCUMENT),
            stage_map_id=898,
            stage_instance_id=module.stage_instance_id(388),
        )
        with patch.object(
            wakfu_server, "owned_story_exits", authority, create=True
        ), patch.object(wakfu_server, "dungeon_exit", exits, create=True), patch.object(
            module, "policy", return_value=DOCUMENT
        ), patch.object(
            module,
            "_event",
            side_effect=lambda db, owner, key: (
                arrival if key == module._key(DOCUMENT, "arrival") else None
            ),
        ), patch.object(
            module.storage, "load_locked", return_value=dict(completed=[2170])
        ), patch.object(
            module.storage, "record_event", return_value=True
        ) as record:
            module.begin(
                db,
                store,
                314,
                "current",
                388,
                struct.pack(">qiBi", 23582, 2074, 0, 2),
                source_allowed=lambda *_: True,
                in_fight=lambda _: False,
            )
            self.assertEqual(
                exits._leave.call_args.kwargs["destination_for"](),
                dict(DOCUMENT["stage"], instance_id=module.stage_instance_id(388)),
            )
            record.assert_called_once()
            self.assertEqual(
                record.call_args.args[2], module._key(DOCUMENT, "resume") + ":92"
            )
            exits._leave.reset_mock()
            record.reset_mock()
            arrival["owner"] = 389
            with self.assertRaisesRegex(ValueError, "original owner"):
                module.begin(
                    db,
                    store,
                    314,
                    "current",
                    388,
                    struct.pack(">qiBi", 23582, 2074, 0, 2),
                    source_allowed=lambda *_: True,
                    in_fight=lambda _: False,
                )
            exits._leave.assert_not_called()
            record.assert_not_called()

    def test_only_earned_owned_controller_exit_can_start_the_stage_in_same_transaction(
        self,
    ):
        db, store = Mock(), Mock()
        character = dict(
            id=388, account_id=314, map_id=887, instance_id=91, x=0, y=-69, z=12
        )
        store.character.return_value = character
        controller = SimpleNamespace(
            _scope=Mock(
                return_value=(
                    dict(
                        cinematic_continuation=dict(
                            path="astrub-ullu-898.json", sha256="a" * 64
                        )
                    ),
                    {"boss-victory", "boss-exit-scene-done"},
                )
            )
        )
        exits = SimpleNamespace(
            _leave=Mock(
                return_value=dict(
                    map_id=898, instance_id=module.stage_instance_id(388), x=0, y=0, z=0
                )
            )
        )
        authority = SimpleNamespace(
            authenticate_exit=Mock(
                side_effect=lambda *a, **k: dict(
                    controller=controller._scope.return_value[0],
                    completed_steps=controller._scope.return_value[1],
                )
            )
        )
        with patch.object(
            wakfu_server, "owned_story_exits", authority, create=True
        ), patch.object(wakfu_server, "dungeon_exit", exits, create=True), patch.object(
            module, "policy", return_value=DOCUMENT
        ), patch.object(
            module, "_event", return_value=None
        ), patch.object(
            module.storage, "load_locked", return_value=dict(completed=[2170])
        ), patch.object(
            module.storage, "record_event", return_value=True
        ) as record:
            allowed, combat = Mock(return_value=True), Mock(return_value=False)
            request = struct.pack(">qiBi", 23582, 2074, 0, 2)
            result = module.begin(
                db,
                store,
                314,
                "lease",
                388,
                request,
                source_allowed=allowed,
                in_fight=combat,
            )
            self.assertEqual(result["map_id"], 898)
            authority.authenticate_exit.assert_called_once_with(
                db, store, character, request, source_allowed=allowed
            )
            call = exits._leave.call_args
            self.assertIs(call.kwargs["_db"], db)
            self.assertEqual(
                call.kwargs["destination_for"](),
                dict(DOCUMENT["stage"], instance_id=module.stage_instance_id(388)),
            )
            record.assert_called_once()
            exits._leave.reset_mock()
            record.reset_mock()
            for quest, completed, body in (
                ([], {"boss-victory", "boss-exit-scene-done"}, request),
                ([2170], {"boss-victory"}, request),
                (
                    [2170],
                    {"boss-victory", "boss-exit-scene-done"},
                    struct.pack(">qiBi", 23582, 2002, 0, 2),
                ),
                ([2170], {"boss-victory", "boss-exit-scene-done"}, b"bad"),
            ):
                controller._scope.return_value = (
                    dict(cinematic_continuation={}),
                    completed,
                )
                with patch.object(
                    module.storage, "load_locked", return_value=dict(completed=quest)
                ), self.assertRaises(ValueError):
                    module.begin(
                        db,
                        store,
                        314,
                        "lease",
                        388,
                        body,
                        source_allowed=allowed,
                        in_fight=combat,
                    )
            exits._leave.assert_not_called()
            record.assert_not_called()


if __name__ == "__main__":
    unittest.main()
