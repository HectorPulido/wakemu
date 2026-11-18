"""Shared authentic occupations and original owned encounter loss boundaries."""

from contextlib import nullcontext
import struct
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from wakfu_server import emotes
from wakfu_server.application.session_world import WorldSessionMixin
from wakfu_server.achievements import mission_emote_events as events
from wakfu_server.achievements import mission_toolkit_contract as contract
from wakfu_server.achievements import source_quest_encounters
import test_owned_story_terminal_returns as terminal_fixtures


class MissionEmoteAndDefeatTests(unittest.TestCase):
    def test_lieutenant_actual_source_requires_both_original_preparations(self):
        producer = source_quest_encounters
        document = producer._read_document(
            producer.SOURCE.with_name("whispering-lieutenant-4872.v1.json")
        )
        row = document["bindings"][0]
        self.assertEqual((row["quest_id"], row["objective_id"]), (4872, 10087))
        self.assertEqual(
            (row["source"]["id"], row["source"]["descriptor_id"]), (32826, 1452)
        )
        self.assertEqual(
            row["scenario"],
            dict(id=2462, begin_event=21395, win_event=21397, loss_event=21398),
        )
        criterion = row["action"]["effects"][0]["criterion"]
        for objectives, hero, expected in (
            ([], False, False),
            ([10047], False, False),
            ([10048], False, False),
            ([10047, 10048], False, True),
            ([10047, 10048], True, False),
            ([10047, 10048, 10087], False, False),
        ):
            with self.subTest(objectives=objectives, hero=hero):
                state = dict(running=[4872], completed=[], objectives=objectives)
                self.assertEqual(
                    producer.source_guard(criterion, state, is_hero=hero), expected
                )

    def test_only_authorized_native_emote_emits_and_stale_position_fails(self):
        character = dict(
            id=7, account_id=2, hp=100, map_id=453, instance_id=123, x=0, y=0, z=0
        )
        store = Mock()
        db = Mock()
        db.execute.return_value.fetchone.return_value = None
        store.connection.return_value = nullcontext(db)
        store.character.return_value = dict(character)
        native = dict(packet=(12088, b"native"), duration_ms=4200)
        options = dict(
            resolve_target=Mock(), in_fight=lambda _: False, occupied=lambda _: False
        )
        with patch.object(emotes, "authorize", return_value=(20106, -1)), patch.object(
            emotes, "prepare_authorized_occupation", return_value=native
        ), patch.object(
            events.mission_toolkit, "settle", return_value=[(13832, b"progress")]
        ) as settle:
            result = emotes.prepare_play(
                store, 2, "lease", character, struct.pack(">iq", 20106, -1), **options
            )
            self.assertEqual(result["mission_packets"], [(13832, b"progress")])
            self.assertEqual(settle.call_args.args[-2:], ("emote_performed", 20106))
            settle.reset_mock()
            store.character.return_value = dict(character, x=1)
            with self.assertRaisesRegex(ValueError, "position"):
                emotes.prepare_play(store, 2, "lease", character, b"request", **options)
            settle.assert_not_called()
        with patch.object(
            emotes, "authorize", side_effect=ValueError("locked")
        ), patch.object(events, "performed") as emit:
            with self.assertRaisesRegex(ValueError, "locked"):
                emotes.prepare_play(store, 2, "lease", character, b"bad", **options)
            emit.assert_not_called()

    def test_actual_session_flushes_before_authorization_and_publishes_updates(self):
        order = []
        runtime = SimpleNamespace(
            STORE=Mock(),
            POSITIONS=Mock(),
            flush_positions=Mock(side_effect=lambda **_: order.append("flush")),
            WORLD=Mock(),
            COMBAT_SESSIONS=Mock(),
            HARVESTS=SimpleNamespace(pending={}),
            PLANTINGS=SimpleNamespace(pending={}),
        )
        runtime.POSITIONS.account_barrier.return_value = nullcontext()
        session = SimpleNamespace(
            runtime=runtime,
            state=SimpleNamespace(
                account_id=2,
                generation="lease",
                character={"id": 7},
                body=b"request",
                fight=None,
                combat_session=None,
            ),
            publish_settled_quest_packets=Mock(),
        )
        result = dict(
            packet=(12088, b"native"),
            duration_ms=4200,
            mission_packets=[(13832, b"progress")],
        )

        def prepared(*args, **kwargs):
            order.append("authorized")
            return result

        with patch.object(emotes, "prepare_play", side_effect=prepared):
            WorldSessionMixin.handle_emote(session)
        self.assertEqual(order, ["flush", "authorized"])
        runtime.WORLD.update.assert_called_once_with(
            "lease", session.state.character, 12088, b"native"
        )
        session.publish_settled_quest_packets.assert_called_once_with(
            [(13832, b"progress")]
        )

    def test_defeat_requires_actual_player_death_not_victory_or_withdrawal(self):
        fixture = terminal_fixtures.OwnedStoryTerminalReturnTests()
        for victory, withdrawn, hp, death, expected in (
            (False, False, 0, True, True),
            (False, True, 0, True, False),
            (False, False, 1, True, False),
            (False, False, 0, False, False),
            (True, False, 1, False, False),
        ):
            values = fixture.fixture(victory=victory)
            db, store, fight, participants, original, selected, configuration = values
            participants[0]["withdrawn"] = withdrawn
            fight.actors[7].hp = hp
            if death:
                fight.events.append(dict(kind="death", actor_id=7))
            with self.subTest(
                victory=victory, withdrawn=withdrawn, hp=hp, death=death
            ), patch(
                "wakfu_server.achievements.storage.record_event", return_value=True
            ), patch(
                "wakfu_server.achievements.mission_toolkit.settle",
                return_value=[(13832, b"loss")],
            ) as settle:
                result = fixture.stage(*values)
                self.assertEqual(bool(settle.call_count), expected)
                if expected:
                    self.assertEqual(result, {2: [(13832, b"loss")]})
                    self.assertEqual(
                        settle.call_args.args[-2:], ("owned_room_defeat", 1)
                    )
                else:
                    self.assertEqual(result, {})

    def test_new_events_keep_positive_native_references(self):
        for kind in ("emote_performed", "owned_room_defeat"):
            contract.validate_event(dict(kind=kind, reference=1, quantity=1))
            with self.assertRaises(ValueError):
                contract.validate_event(dict(kind=kind, reference=0, quantity=1))


if __name__ == "__main__":
    unittest.main()
