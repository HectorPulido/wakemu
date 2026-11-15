"""Captured Rii fall, owned grandmother handshake and legacy route recovery."""

import copy
from contextlib import ExitStack, contextmanager
from datetime import datetime, timezone
import struct
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

from wakfu_server import astrub_arrival_scene as arrival, rii_zaap_scene

GRANDMOTHER = -1776810787923716


def definition(identity, objective):
    return {
        "d": identity,
        "native_class": "aJM",
        "aqb": False,
        "cjI": "",
        "cjJ": [{"d": objective, "ckc": "", "cke": "", "ckd": [], "ckf": []}],
        "cjK": [],
    }


def progress(*, departed=False):
    return {
        "variables": {},
        "objectives": [10967, *([10624] if departed else [])],
        "running": [] if departed else [5161],
        "completed": [5278, *([5161] if departed else [])],
        "tracking": [] if departed else [5161],
        "recent": [],
        "completion_dates": {},
    }


class ArrivalFixture:
    """Rollback-capable transaction fixture; actual mission planning stays live."""

    def __init__(self, *, legacy=False, started=False):
        self.character = {
            "id": 7,
            "account_id": 2,
            "map_id": 527 if legacy else 1385,
            "instance_id": 0,
            "x": 3,
            "y": -18,
            "z": 4,
        }
        self.state = progress(departed=legacy)
        self.receipts = {
            rii_zaap_scene.START_EVENT_KEY: rii_zaap_scene._start_payload(7),
        }
        if legacy:
            self.receipts[rii_zaap_scene.CALLBACK_EVENT_KEY] = {
                "kind": "rii_zaap_scene_callback",
                "character_id": 7,
                "scenario_event": 22534,
            }
        if started:
            self.character.update(arrival.route()["destination"])
            self.state["running"] = [5568]
            self.receipts[arrival.START_EVENT_KEY] = arrival._start_payload(7)
        self.definitions = {
            5161: definition(5161, 10624),
            5568: definition(5568, 11508),
        }
        self.grandmother_ids = [GRANDMOTHER]
        self.transactions = 0
        self.db = MagicMock()
        self.db.execute.side_effect = self.execute
        self.store = MagicMock()
        self.store.connection.side_effect = self.connection
        self.store.character.side_effect = lambda *_: dict(self.character)
        self.store.transition_map_in_transaction.side_effect = self.transition
        self.store.now.return_value = datetime(2026, 11, 14, tzinfo=timezone.utc)

    @contextmanager
    def connection(self):
        self.transactions += 1
        saved = copy.deepcopy((self.character, self.state, self.receipts))
        try:
            yield self.db
        except BaseException:
            self.character, self.state, self.receipts = saved
            raise

    def execute(self, sql, params=()):
        row, rows = None, []
        if "native_quest_metadata_definitions" in sql:
            native = self.definitions.get(params[0])
            row = None if native is None else {"data": {"native": native}}
        elif "character_achievement_events" in sql:
            payload = self.receipts.get(params[-1])
            row = None if payload is None else {"payload": copy.deepcopy(payload)}
        elif "SELECT actor_id FROM world_dialogue_npcs" in sql:
            rows = [{"actor_id": identity} for identity in self.grandmother_ids]
        elif "UPDATE characters SET x=" in sql:
            self.character.update(zip(("x", "y", "z"), params[:3]))
        return SimpleNamespace(fetchone=lambda: row, fetchall=lambda: rows, rowcount=1)

    def transition(self, db, account_id, generation, identity, source, destination):
        if db is not self.db or (account_id, identity) != (2, 7):
            raise AssertionError("Transition escaped its owned transaction")
        self.character.update(destination)
        return dict(self.character)

    def record(self, _db, identity, key, payload):
        if identity != 7:
            raise AssertionError("Foreign receipt")
        if key in self.receipts:
            return False
        self.receipts[key] = copy.deepcopy(payload)
        return True

    @contextmanager
    def patched(self):
        with ExitStack() as stack:
            stack.enter_context(
                patch(
                    "wakfu_server.achievements.storage.load_locked",
                    side_effect=lambda *_: copy.deepcopy(self.state),
                )
            )
            stack.enter_context(
                patch(
                    "wakfu_server.achievements.storage.store",
                    side_effect=lambda _db, _identity, value: setattr(
                        self, "state", copy.deepcopy(value)
                    ),
                )
            )
            stack.enter_context(
                patch(
                    "wakfu_server.achievements.storage.record_event",
                    side_effect=self.record,
                )
            )
            stack.enter_context(patch("wakfu_server.achievements.service._owner"))
            stack.enter_context(
                patch(
                    "wakfu_server.achievements.service.drain_rewards", return_value=[]
                )
            )
            yield self

    def callback(self, event, **overrides):
        return arrival.callback(
            self.store,
            2,
            3,
            dict(self.character),
            struct.pack(">i", event),
            pending_character_id=overrides.pop("pending_character_id", 7),
            **overrides,
        )


class AstrubArrivalSceneTests(unittest.TestCase):
    def test_native_route_and_exact_captured_presentation_encodings(self):
        self.assertEqual(
            arrival.route()["destination"],
            {
                "map_id": 895,
                "instance_id": 0,
                "x": -8,
                "y": -1,
                "z": 18,
            },
        )
        self.assertEqual(
            arrival.packet(17029), (13411, bytes.fromhex("00000042850000084800"))
        )
        self.assertEqual(
            arrival.packet(23936), (13411, struct.pack(">BiiB", 0, 23936, 2120, 0))
        )
        self.assertEqual(
            arrival.packet(17022, GRANDMOTHER),
            (13411, bytes.fromhex("000000427e0000084801fff9b000002718fc")),
        )
        for event, args in (
            (17021, ()),
            (17029, (1,)),
            (17022, ()),
            (17022, (0,)),
            (17022, (True,)),
            (17022, (-(2**63) - 1,)),
        ):
            with self.subTest(event=event, args=args), self.assertRaises(ValueError):
                arrival.packet(event, *args)

    def test_normal_fall_transition_completes_departure_and_starts_next_mission_atomically(
        self,
    ):
        fixture = ArrivalFixture()
        with fixture.patched():
            saved, packets, route = rii_zaap_scene.finish(
                fixture.store,
                2,
                3,
                dict(fixture.character),
                struct.pack(">i", 22534),
                pending_character_id=7,
            )
        self.assertEqual(fixture.transactions, 1)
        self.assertEqual(saved["map_id"], 895)
        self.assertEqual(route, arrival.route())
        self.assertIn(5161, fixture.state["completed"])
        self.assertIn(10624, fixture.state["objectives"])
        self.assertIn(5568, fixture.state["running"])
        self.assertNotIn(11508, fixture.state["objectives"])
        self.assertEqual(packets[-1], arrival.packet(17029))
        self.assertEqual(
            fixture.receipts[arrival.START_EVENT_KEY], arrival._start_payload(7)
        )

    def test_portal_fall_starts_arrival_without_manufacturing_absent_5161(self):
        fixture = ArrivalFixture()
        fixture.state["running"] = []
        fixture.state["tracking"] = []
        before = copy.deepcopy(fixture.state)
        with fixture.patched():
            saved, packets, _route = rii_zaap_scene.finish(
                fixture.store,
                2,
                3,
                dict(fixture.character),
                struct.pack(">i", 22534),
                pending_character_id=7,
            )
        self.assertEqual(saved["map_id"], 895)
        self.assertEqual(fixture.state["running"], [5568])
        self.assertNotIn(5161, fixture.state["running"])
        self.assertNotIn(5161, fixture.state["completed"])
        self.assertNotIn(10624, fixture.state["objectives"])
        self.assertEqual(fixture.state["completed"], before["completed"])
        self.assertIn(10967, fixture.state["objectives"])
        self.assertEqual(packets[-1], arrival.packet(17029))

    def test_arrival_requires_owned_rii_receipts_and_both_native_qualification_facts(
        self,
    ):
        variants = (
            (
                "portal start",
                lambda fixture: fixture.receipts.pop(rii_zaap_scene.START_EVENT_KEY),
            ),
            (
                "complete hidden fact",
                lambda fixture: fixture.state["completed"].remove(5278),
            ),
            (
                "portal objective fact",
                lambda fixture: fixture.state["objectives"].remove(10967),
            ),
        )
        for label, mutate in variants:
            with self.subTest(label=label):
                fixture = ArrivalFixture()
                mutate(fixture)
                before = copy.deepcopy(
                    (fixture.character, fixture.state, fixture.receipts)
                )
                with fixture.patched(), self.assertRaises(ValueError):
                    rii_zaap_scene.finish(
                        fixture.store,
                        2,
                        3,
                        dict(fixture.character),
                        struct.pack(">i", 22534),
                        pending_character_id=7,
                    )
                self.assertEqual(
                    (fixture.character, fixture.state, fixture.receipts), before
                )

        fixture = ArrivalFixture()
        before = copy.deepcopy((fixture.character, fixture.state, fixture.receipts))
        with fixture.patched(), fixture.connection() as db, self.assertRaises(
            ValueError
        ):
            arrival.enter(
                db,
                fixture.store,
                dict(fixture.character),
                arrival.route()["destination"],
            )
        self.assertEqual((fixture.character, fixture.state, fixture.receipts), before)

    def test_failed_arrival_definition_rolls_back_transition_and_callback_receipt(self):
        fixture = ArrivalFixture()
        fixture.definitions.pop(5568)
        before = copy.deepcopy((fixture.character, fixture.state, fixture.receipts))
        with fixture.patched(), self.assertRaisesRegex(
            ValueError, "mission definition"
        ):
            rii_zaap_scene.finish(
                fixture.store,
                2,
                3,
                dict(fixture.character),
                struct.pack(">i", 22534),
                pending_character_id=7,
            )
        self.assertEqual((fixture.character, fixture.state, fixture.receipts), before)

    def test_owned_stage_chain_replays_safely_and_finishes_at_captured_position(self):
        fixture = ArrivalFixture(started=True)
        with fixture.patched():
            self.assertEqual(
                arrival.login_packets(fixture.db, fixture.character),
                (arrival.packet(17029),),
            )
            self.assertEqual(
                fixture.callback(17029)["packets"], (arrival.packet(23936),)
            )
            self.assertEqual(
                fixture.callback(17029)["packets"], (arrival.packet(23936),)
            )
            self.assertEqual(
                fixture.callback(23936)["packets"],
                (arrival.packet(17022, GRANDMOTHER),),
            )
            self.assertEqual(
                fixture.callback(17029)["packets"],
                (arrival.packet(17022, GRANDMOTHER),),
            )
            result = fixture.callback(17022)
            self.assertTrue(result["finished"])
            self.assertEqual(
                result["packets"],
                ((13259, struct.pack(">qiihBB", 7, -3, -4, 0, 0, 0)),),
            )
            self.assertEqual(fixture.callback(17022)["packets"], ())
            self.assertEqual(arrival.login_packets(fixture.db, fixture.character), ())
        self.assertEqual(
            tuple(fixture.character[k] for k in ("x", "y", "z")), (-3, -4, 0)
        )

    def test_wrong_owner_order_map_and_malformed_callbacks_do_not_advance(self):
        fixture = ArrivalFixture(started=True)
        with fixture.patched():
            for event in (23936, 17022):
                with self.subTest(event=event), self.assertRaisesRegex(
                    ValueError, "out of order"
                ):
                    fixture.callback(event)
            for overrides in ({"pending_character_id": 8}, {"in_combat": True}):
                with self.subTest(overrides=overrides), self.assertRaises(ValueError):
                    fixture.callback(17029, **overrides)
            with self.assertRaises(ValueError):
                arrival.callback(
                    fixture.store,
                    2,
                    3,
                    fixture.character,
                    b"bad",
                    pending_character_id=7,
                )
            fixture.character["map_id"] = 527
            with self.assertRaises(ValueError):
                fixture.callback(17029)
        self.assertFalse(
            any(key.startswith(arrival.CALLBACK_PREFIX) for key in fixture.receipts)
        )

    def test_connection_phase_gate_rejects_replay_before_database_access_and_allows_expected_next(
        self,
    ):
        for event, expected in ((17029, 23936), (23936, 17022), (17022, 17029)):
            with self.subTest(event=event, expected=expected):
                fixture = ArrivalFixture(started=True)
                before = copy.deepcopy(fixture.receipts)
                with fixture.patched(), self.assertRaisesRegex(
                    ValueError, "phase is not pending"
                ):
                    fixture.callback(event, expected_event=expected)
                fixture.store.connection.assert_not_called()
                fixture.db.execute.assert_not_called()
                self.assertEqual(fixture.receipts, before)

        fixture = ArrivalFixture(started=True)
        with fixture.patched():
            self.assertEqual(
                fixture.callback(17029, expected_event=17029)["packets"],
                (arrival.packet(23936),),
            )
            self.assertEqual(
                fixture.callback(23936, expected_event=23936)["packets"],
                (arrival.packet(17022, GRANDMOTHER),),
            )
            # A new connection begins at LOAD while durable VIDEO progress is
            # retained; it resumes the cinematic instead of repeating video.
            self.assertEqual(
                fixture.callback(17029, expected_event=17029)["packets"],
                (arrival.packet(17022, GRANDMOTHER),),
            )
            self.assertTrue(fixture.callback(17022, expected_event=17022)["finished"])

    def test_missing_or_ambiguous_grandmother_rejects_video_callback_without_receipt(
        self,
    ):
        for identities in ([], [GRANDMOTHER, GRANDMOTHER - 1]):
            with self.subTest(identities=identities):
                fixture = ArrivalFixture(started=True)
                fixture.grandmother_ids = identities
                with fixture.patched():
                    fixture.callback(17029)
                    with self.assertRaisesRegex(ValueError, "uniquely published"):
                        fixture.callback(23936)
                self.assertNotIn(arrival.CALLBACK_PREFIX + "23936", fixture.receipts)

    def test_legacy_authenticated_route_recovery_preserves_progress_and_runs_once(self):
        fixture = ArrivalFixture(legacy=True)
        fixture.state["variables"] = {"756": 3}
        fixture.state["objectives"].append(777)
        fixture.state["completion_dates"] = {"5161": 1234}
        with fixture.patched():
            saved, packets = arrival.recover_login(
                fixture.store, 2, 3, dict(fixture.character)
            )
            self.assertIsNone(arrival.recover_login(fixture.store, 2, 3, saved))
        self.assertEqual(saved["map_id"], 895)
        self.assertEqual(fixture.state["variables"], {"756": 3})
        self.assertIn(777, fixture.state["objectives"])
        self.assertEqual(fixture.state["completion_dates"]["5161"], 1234)
        self.assertEqual(packets[-1], arrival.packet(17029))
        self.assertIn(5568, fixture.state["running"])

    def test_recovery_requires_every_owned_legacy_fact_and_never_resets_existing_next_quest(
        self,
    ):
        variants = (
            ("map", lambda f: f.character.update(map_id=1385)),
            ("private", lambda f: f.character.update(instance_id=7)),
            ("starter", lambda f: f.receipts.pop(rii_zaap_scene.START_EVENT_KEY)),
            ("callback", lambda f: f.receipts.pop(rii_zaap_scene.CALLBACK_EVENT_KEY)),
            ("hidden quest", lambda f: f.state["completed"].remove(5278)),
            ("hidden objective", lambda f: f.state["objectives"].remove(10967)),
            ("running", lambda f: f.state["running"].append(5568)),
            ("completed", lambda f: f.state["completed"].append(5568)),
            (
                "already arrived",
                lambda f: f.receipts.update(
                    {arrival.START_EVENT_KEY: arrival._start_payload(7)}
                ),
            ),
        )
        for name, mutate in variants:
            with self.subTest(name=name):
                fixture = ArrivalFixture(legacy=True)
                mutate(fixture)
                before = copy.deepcopy(
                    (fixture.character, fixture.state, fixture.receipts)
                )
                with fixture.patched():
                    self.assertIsNone(
                        arrival.recover_login(
                            fixture.store, 2, 3, dict(fixture.character)
                        )
                    )
                self.assertEqual(
                    (fixture.character, fixture.state, fixture.receipts), before
                )
                fixture.store.transition_map_in_transaction.assert_not_called()


if __name__ == "__main__":
    unittest.main()
