"""Authenticated terminal returns remain behind native encounter receipts."""

import json
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from wakfu_server import owned_story_terminal_returns as returns

ROOT = Path(__file__).resolve().parents[1]
SCHOOL = json.loads(
    (
        ROOT / "wakfu_server/maps/owned_story_profiles/huppermage-platform-1030.json"
    ).read_text()
)


class OwnedStoryTerminalReturnTests(unittest.TestCase):
    def test_actual_temple_private_return_waits_for_corridor_escape_receipt(self):
        root = ROOT / "wakfu_server/maps/owned_story_profiles"
        selected = json.loads((root / "wild-temple-718.json").read_text())
        declaration = returns.policy(selected)
        self.assertEqual(declaration["after_steps"], ["corridor-escaped"])
        self.assertEqual(
            (
                declaration["source_map_id"],
                declaration["source_id"],
                declaration["destination_id"],
            ),
            (718, 20685, 1445),
        )
        target = returns._step_destination(selected, declaration)
        self.assertEqual(target["map_id"], 711)
        self.assertEqual(
            tuple(target[key] for key in ("x", "y", "z")), (-36, -138, -80)
        )

        character = dict(id=7, account_id=2, instance_id=123, map_id=718)
        db = Mock()
        store = Mock()
        with patch(
            "wakfu_server.owned_story_controller.recognizes_instance", return_value=True
        ), patch(
            "wakfu_server.owned_story_controller._scope", return_value=(selected, set())
        ):
            self.assertIsNone(returns.pending(db, store, character))
            db.execute.assert_not_called()
            with patch(
                "wakfu_server.owned_story_controller._scope",
                return_value=(selected, {"corridor-escaped"}),
            ):
                self.assertEqual(returns.pending(db, store, character), target)
        db.execute.assert_not_called()

    def fixture(self, *, victory=True, phase="finished", roster=None, marker=True):
        selected = dict(SCHOOL)
        if not marker:
            selected.pop("terminal_returns")
        original = [dict(id=-11, ref=3927, instance_id=123)]
        fight = SimpleNamespace(
            id=71,
            phase=phase,
            winner=0 if victory else 1,
            actors={
                7: SimpleNamespace(team=0, controlled=True, owner_id=2, hp=80),
                -11: SimpleNamespace(team=1, controlled=False, hp=0 if victory else 15),
            },
            events=[dict(kind="death", actor_id=-11)] if victory else [],
        )
        participant = dict(character_id=7, account_id=2)
        encounter = dict(
            fight_status="finished",
            encounter_scope="main",
            room_order=1,
            team=0,
            player_team=0,
            status="victory" if victory else "defeat",
            result={"victory": victory},
        )
        members = roster if roster is not None else [dict(id=-11, ref=3927)]

        class Cursor:
            def __init__(self, row):
                self.row = row

            def fetchone(self):
                return self.row

        class DB:
            def __init__(self):
                self.calls = []

            def execute(self, query, args=()):
                self.calls.append((query, args))
                if "SELECT map_id,instance_id FROM characters" in query:
                    return Cursor(dict(map_id=1030, instance_id=123))
                if "FROM dungeon_room_encounters e" in query:
                    return Cursor(encounter)
                if "FROM dungeon_room_spawn_receipts r" in query:
                    return Cursor(dict(members=members, asset_map_id=1030))
                raise AssertionError(query)

        db = DB()
        store = Mock()
        store.character.return_value = dict(
            id=7, account_id=2, map_id=1030, instance_id=123, x=127, y=-18, z=0
        )
        configuration = dict(
            compiled_plan={
                "rooms": [dict(order=1, monsters=[dict(ref_id=3927, count=1)])]
            }
        )
        return db, store, fight, [participant], original, selected, configuration

    def stage(self, db, store, fight, participants, original, selected, configuration):
        with patch(
            "wakfu_server.dungeon_runtime.configuration_for_instance",
            return_value=(None, configuration),
        ), patch(
            "wakfu_server.owned_story_controller.recognizes_instance",
            return_value=True,
        ), patch(
            "wakfu_server.owned_story_controller.policy", return_value=selected
        ), patch(
            "wakfu_server.owned_story_controller._scope", return_value=(selected, set())
        ):
            return returns.stage(db, store, fight, participants, original)

    def test_native_school_terminal_policy_pins_actual_approach_and_rejects_changes(
        self,
    ):
        declaration = returns.policy(SCHOOL)
        self.assertEqual(declaration["room_order"], 1)
        self.assertEqual(declaration["victory"]["position"], [0, -59, -44])
        with self.assertRaisesRegex(ValueError, "native exterior approach"):
            returns.policy(
                dict(
                    SCHOOL,
                    terminal_returns=dict(
                        SCHOOL["terminal_returns"],
                        victory=dict(
                            SCHOOL["terminal_returns"]["victory"],
                            source_sha256="0" * 64,
                        ),
                    ),
                )
            )
        with self.assertRaisesRegex(ValueError, "native exterior approach"):
            returns.policy(
                dict(
                    SCHOOL,
                    terminal_returns=dict(
                        SCHOOL["terminal_returns"],
                        victory=dict(
                            SCHOOL["terminal_returns"]["victory"],
                            position=[1, -59, -44],
                        ),
                    ),
                )
            )

    def test_genuine_win_and_defeat_stage_once_from_original_room_receipt(self):
        for victory in (True, False):
            with self.subTest(victory=victory):
                (
                    db,
                    store,
                    fight,
                    participants,
                    original,
                    selected,
                    configuration,
                ) = self.fixture(victory=victory)
                with patch(
                    "wakfu_server.achievements.storage.record_event", return_value=True
                ) as record:
                    self.stage(
                        db,
                        store,
                        fight,
                        participants,
                        original,
                        selected,
                        configuration,
                    )
                    self.stage(
                        db,
                        store,
                        fight,
                        participants,
                        original,
                        selected,
                        configuration,
                    )
                self.assertEqual(record.call_count, 2)
                args = record.call_args.args
                self.assertEqual(args[0:2], (db, 7))
                self.assertEqual(args[2], "owned-story-terminal-return:123:71")
                self.assertEqual(args[3]["victory"], victory)
                self.assertEqual(args[3]["original_actor_ids"], [-11])

    def test_marked_operator_win_stages_without_fabricated_deaths_and_rejects_foreign_marker(
        self,
    ):
        (
            db,
            store,
            fight,
            participants,
            original,
            selected,
            configuration,
        ) = self.fixture()
        fight.actors[7].owner_id = 2
        # The real operator terminal can set the losing side to zero HP without
        # manufacturing native death events for that administration command.
        fight.actors[-11].hp = 0
        fight.events = [
            dict(
                kind="administrative_outcome",
                command="!winfight",
                account_id=2,
                character_id=7,
                winner=0,
            ),
            dict(kind="finished", winner=0),
        ]
        with patch(
            "wakfu_server.achievements.storage.record_event", return_value=True
        ) as record:
            self.stage(
                db, store, fight, participants, original, selected, configuration
            )
        self.assertEqual(record.call_count, 1)
        payload = record.call_args.args[3]
        self.assertTrue(payload["victory"])
        self.assertEqual(payload["original_actor_ids"], [-11])
        self.assertFalse(any(event.get("kind") == "death" for event in fight.events))

        for marker in (
            dict(
                kind="administrative_outcome",
                command="!winfight",
                account_id=99,
                character_id=7,
                winner=0,
            ),
            dict(
                kind="administrative_outcome",
                command="!winfight",
                account_id=2,
                character_id=99,
                winner=0,
            ),
        ):
            rejected = self.fixture()
            db, store, fight, participants, original, selected, configuration = rejected
            fight.actors[7].owner_id = 2
            fight.actors[-11].hp = 0
            fight.events = [marker, dict(kind="finished", winner=0)]
            with patch(
                "wakfu_server.achievements.storage.record_event"
            ) as record, self.assertRaisesRegex(ValueError, "native deaths"):
                self.stage(
                    db, store, fight, participants, original, selected, configuration
                )
            record.assert_not_called()

        # A valid marker does not bypass the original-formation HP invariant.
        (
            db,
            store,
            fight,
            participants,
            original,
            selected,
            configuration,
        ) = self.fixture()
        fight.actors[7].owner_id = 2
        fight.actors[-11].hp = 15
        fight.events = [
            dict(
                kind="administrative_outcome",
                command="!winfight",
                account_id=2,
                character_id=7,
                winner=0,
            ),
            dict(kind="finished", winner=0),
        ]
        with patch(
            "wakfu_server.achievements.storage.record_event"
        ) as record, self.assertRaisesRegex(ValueError, "native deaths"):
            self.stage(
                db, store, fight, participants, original, selected, configuration
            )
        record.assert_not_called()

    def test_wrong_roster_and_unfinished_fight_fail_without_receipt(self):
        for options in (
            dict(roster=[dict(id=-12, ref=3927)]),
            dict(phase="turn"),
        ):
            with self.subTest(options=options):
                (
                    db,
                    store,
                    fight,
                    participants,
                    original,
                    selected,
                    configuration,
                ) = self.fixture(**options)
                with patch(
                    "wakfu_server.achievements.storage.record_event"
                ) as record, self.assertRaises(ValueError):
                    self.stage(
                        db,
                        store,
                        fight,
                        participants,
                        original,
                        selected,
                        configuration,
                    )
                record.assert_not_called()

    def test_unmarked_owned_story_and_public_combat_do_not_stage_returns(self):
        (
            db,
            store,
            fight,
            participants,
            original,
            selected,
            configuration,
        ) = self.fixture(marker=False)
        with patch("wakfu_server.achievements.storage.record_event") as record:
            self.stage(
                db, store, fight, participants, original, selected, configuration
            )
        record.assert_not_called()
        public_original = [dict(original[0], instance_id=0)]
        public_db = Mock()
        with patch("wakfu_server.achievements.storage.record_event") as record:
            returns.stage(public_db, store, fight, participants, public_original)
        public_db.execute.assert_not_called()
        record.assert_not_called()

    def test_pending_win_uses_school_gate_and_defeat_uses_recorded_entry(self):
        selected = SCHOOL
        store = Mock()
        store.character.return_value = dict(id=7, instance_id=123)
        with patch(
            "wakfu_server.owned_story_controller.recognizes_instance", return_value=True
        ), patch(
            "wakfu_server.owned_story_controller._scope", return_value=(selected, set())
        ), patch.object(
            returns, "policy", return_value=selected["terminal_returns"]
        ):
            db = Mock()
            db.execute.return_value.fetchone.return_value = {
                "payload": {
                    "kind": returns.SCHEMA,
                    "instance_id": 123,
                    "profile_sha256": "unused",
                    "victory": True,
                }
            }
            with patch(
                "wakfu_server.owned_story_controller._digest", return_value="unused"
            ):
                self.assertEqual(
                    returns.pending(db, store, dict(id=7, instance_id=123)),
                    dict(map_id=1017, x=0, y=-59, z=-44),
                )

            new_run = Mock()
            new_run.execute.return_value.fetchone.return_value = None
            with patch(
                "wakfu_server.owned_story_controller._digest", return_value="unused"
            ):
                self.assertIsNone(
                    returns.pending(new_run, store, dict(id=7, instance_id=124))
                )
            self.assertEqual(new_run.execute.call_args.args[1], (7, 124, 1))

            db.execute.reset_mock()
            db.execute.return_value.fetchone.side_effect = [
                {
                    "payload": {
                        "kind": returns.SCHEMA,
                        "instance_id": 123,
                        "profile_sha256": "unused",
                        "victory": False,
                    }
                },
                {
                    "instance_id": 123,
                    "entry_map_id": 527,
                    "entry_object_id": 23621,
                    "entry_destination_id": 4029,
                },
            ]
            with patch(
                "wakfu_server.owned_story_controller._digest", return_value="unused"
            ), patch(
                "wakfu_server.dungeon_recovery._recorded_exterior",
                return_value=dict(map_id=527, instance_id=0, x=44, y=-54, z=8),
            ) as exterior:
                self.assertEqual(
                    returns.pending(
                        db, store, dict(id=7, account_id=2, instance_id=123)
                    ),
                    dict(map_id=527, instance_id=0, x=44, y=-54, z=8),
                )
                exterior.assert_called_once()

    def test_poll_flushes_then_uses_normal_exit_and_rebinds_before_delivery(self):
        order = []
        destination = dict(map_id=1017, x=0, y=-59, z=-44)
        character = dict(id=7, account_id=2, map_id=1030, instance_id=123)
        db = object()
        store = Mock()

        @contextmanager
        def connection():
            order.append("connection")
            yield db

        store.connection.side_effect = connection

        @contextmanager
        def account_barrier(account):
            self.assertEqual(account, 2)
            order.append("barrier-enter")
            yield
            order.append("barrier-exit")

        positions = SimpleNamespace(
            account_barrier=account_barrier,
            rebind_selected=lambda *args: order.append("rebind"),
        )
        runtime = SimpleNamespace(
            STORE=store,
            POSITIONS=positions,
            flush_positions=lambda **kwargs: order.append("flush"),
            COMBAT_SESSIONS=SimpleNamespace(lookup_character=lambda _identity: None),
        )
        session = SimpleNamespace(
            state=SimpleNamespace(
                character=character,
                loaded=True,
                fight=None,
                combat_session=None,
                spectator_session=None,
                account_id=2,
                generation="lease",
            ),
            runtime=runtime,
            account_id=2,
            generation="lease",
            deliver_dungeon_transitions=lambda **kwargs: order.append("deliver"),
        )

        def normal_exit(
            _store,
            account_id,
            generation,
            character_id,
            *,
            in_fight,
            destination_for,
        ):
            self.assertEqual((account_id, generation, character_id), (2, "lease", 7))
            self.assertIs(in_fight(7), False)
            order.append("leave")
            result = destination_for(
                db, character, dict(instance_id=123, entry_map_id=527)
            )
            self.assertEqual(result, destination)

        with patch.object(
            returns, "pending", side_effect=[destination, destination]
        ) as pending, patch(
            "wakfu_server.owned_story_controller._scope",
            return_value=(SCHOOL, {}),
        ), patch(
            "wakfu_server.dungeon_exit._leave", side_effect=normal_exit
        ):
            self.assertTrue(returns.poll(session))
        self.assertEqual(pending.call_count, 2)
        self.assertLess(order.index("flush"), order.index("leave"))
        self.assertLess(order.index("leave"), order.index("rebind"))
        self.assertLess(order.index("rebind"), order.index("deliver"))
        self.assertIn("barrier-enter", order)
        self.assertIn("barrier-exit", order)


if __name__ == "__main__":
    unittest.main()
