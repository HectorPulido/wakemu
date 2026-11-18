"""Story overlays compose with the native weekly NPC provider."""
import unittest
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

from wakfu_server import quest_npc
from wakfu_server.maps import weekly_hunter_npc as hunter


class WeeklyHunterStoryOverlayTests(unittest.TestCase):
    def setUp(self):
        self.store = MagicMock()
        self.character = dict(id=41, account_id=7, level=100)
        self.provider = MagicMock(return_value=self.character)

    def begin(self, *, actor=None, action=None):
        return hunter.begin(
            self.store,
            7,
            3,
            self.character,
            hunter.ACTOR if actor is None else actor,
            hunter.ACTION if action is None else action,
            character_provider=self.provider,
        )

    def test_running_published_overlay_precedes_weekly_transaction(self):
        result = (object(), [(12969, b"native-story")])
        with patch.object(
            quest_npc, "try_native_overlay", return_value=result
        ) as overlay:
            self.assertIs(self.begin(), result)
        overlay.assert_called_once_with(
            self.store,
            7,
            3,
            self.character,
            hunter.ACTOR,
            hunter.ACTION,
            character_provider=self.provider,
        )
        self.store.connection.assert_not_called()

    def test_absent_overlay_keeps_weekly_dialogue_and_synchronization(self):
        root, choice = 100, 200
        offer = dict(node_id=root, choice_id=choice, criterion="native")
        node = dict(
            id=root,
            criteria="",
            choices=[
                dict(id=choice, type=5, criteria="native"),
            ],
        )
        self.store.character.return_value = self.character
        session = MagicMock()
        session.open.return_value = (12969, b"weekly")
        with (
            patch.object(quest_npc, "try_native_overlay", return_value=None),
            patch.object(hunter, "_owner"),
            patch.object(hunter, "_actor", return_value={}) as actor,
            patch.object(hunter, "_nearby", return_value=True),
            patch.object(hunter, "_offers", return_value=[offer]),
            patch.object(
                hunter.recurring, "synchronize", return_value=[(1, b"sync")]
            ) as sync,
            patch.object(
                hunter.npc_dialogue,
                "catalog",
                return_value={"node_index": {root: node}},
            ),
            patch.object(hunter.npc_dialogue, "DialogueSession", return_value=session),
        ):
            result = self.begin()
        self.assertEqual(result, (session, [(1, b"sync"), (12969, b"weekly")]))
        self.assertTrue(session.weekly_hunter)
        self.assertEqual(session.weekly_hunter_offers, {choice: offer})
        actor.assert_called_once()
        sync.assert_called_once()

    def test_unknown_actor_or_action_cannot_dispatch_an_overlay(self):
        with patch.object(quest_npc, "try_native_overlay") as overlay:
            for request in (
                dict(actor=hunter.ACTOR + 1),
                dict(action=hunter.ACTION + 1),
            ):
                with self.subTest(request=request), self.assertRaises(ValueError):
                    self.begin(**request)
        overlay.assert_not_called()
        self.store.connection.assert_not_called()


class NativeOverlaySelectorTests(unittest.TestCase):
    def setUp(self):
        self.actor_id = -2251799934992048
        self.source_sha256 = "a" * 64
        self.row = {
            "actor_id": self.actor_id,
            "reference_id": 1,
            "map_id": 507,
            "instance_id": 0,
            "x": 1,
            "y": 1,
            "z": 0,
            "direction": 0,
            "action_ids": [436],
        }
        self.item = {
            "row": self.row,
            "quest_id": 2691,
            "activation_policy": "already_running",
            "existing_native_actor": {
                "source_sha256": self.source_sha256,
                "quest_ids": [2691],
            },
        }
        self.native_actor = dict(
            self.row,
            source_sha256=self.source_sha256,
            name_es="Magnum",
            level=1,
            visual_id=1,
            native_action_ids=[436],
        )

    def test_virtual_native_overlay_requires_exact_pin_without_dialogue_row(self):
        actor_id = -1724034232352753
        source_sha256 = (
            "0410af8f82ee3c8a209efca093d0ebbdaf477be9f35801b1a63d4559f4e381cb"
        )
        row = {
            "actor_id": actor_id,
            "reference_id": 3819,
            "map_id": 1134,
            "instance_id": 0,
            "x": 16,
            "y": 8,
            "z": 0,
            "direction": 1,
            "dialogue_root": 2705,
            "action_ids": [703],
            "interaction_range": 3,
            "enabled": True,
            "provenance": quest_npc.PREFIX + "fixture",
        }
        proof = {"source_sha256": source_sha256, "quest_ids": [2705]}
        native = {
            **{
                key: row[key]
                for key in (
                    "actor_id",
                    "reference_id",
                    "map_id",
                    "instance_id",
                    "x",
                    "y",
                    "z",
                    "direction",
                )
            },
            "level": 100,
            "visual_id": 117903819,
            "name_es": "Magnum Deskhalzo",
            "native_action_ids": [703],
            "source_sha256": source_sha256,
        }
        published_row = dict(row)
        item = {"row": published_row, "existing_native_actor": proof}
        document = {"placements": [item]}
        published = (document, {}, {})

        class DB:
            def __init__(self, source):
                self.source = source
                self.statements = []

            def execute(self, sql, _params=()):
                self.statements.append(sql)
                return self

            def fetchone(self):
                if "world_native_npc_placements" in self.statements[-1]:
                    return self.source
                raise AssertionError(
                    f"Unexpected database query: {self.statements[-1]}"
                )

        db = DB(native)
        projected, selected = quest_npc._row(db, actor_id, published)
        self.assertEqual(projected, {**published_row, "_quest_publication": published})
        self.assertIs(selected, item)
        self.assertEqual(len(db.statements), 1)
        self.assertIn("world_native_npc_placements", db.statements[0])
        self.assertFalse(any("world_dialogue_npcs" in sql for sql in db.statements))

        for label, mutate in (
            ("native actor missing", lambda value: None),
            ("foreign source pin", lambda value: value.update(source_sha256="a" * 64)),
            ("changed position", lambda value: value.update(x=17)),
            ("missing native action", lambda value: value.update(native_action_ids=[])),
        ):
            candidate = dict(native)
            mutate(candidate)
            with self.subTest(label=label):
                db = DB(None if label == "native actor missing" else candidate)
                with self.assertRaises(ValueError):
                    quest_npc._row(db, actor_id, published)
                self.assertEqual(len(db.statements), 1)
                self.assertIn("world_native_npc_placements", db.statements[0])
                self.assertFalse(
                    any("world_dialogue_npcs" in sql for sql in db.statements)
                )

    def test_only_fresh_running_overlay_selects_the_published_native_actor(self):
        class DB:
            def execute(inner, sql, _params=()):
                inner.sql = sql
                return inner

            def fetchone(inner):
                if "world_native_npc_placements" in inner.sql:
                    return self.native_actor
                return {"id": 7}

        class Store:
            @contextmanager
            def connection(_self):
                yield DB()

            def lock_character(_self, *_args, **_kwargs):
                pass

            def character(_self, account_id, character_id, _db):
                return {"id": character_id, "account_id": account_id}

        document = {"placements": [self.item]}
        state = {
            "running": [2691],
            "active": [2691],
            "active_periods": {},
            "completed": [],
            "objectives": [],
            "variables": {},
            "completion_dates": {},
        }
        session_result = object()
        with (
            patch.object(quest_npc, "publication", return_value=(document, {}, {})),
            patch.object(quest_npc, "_owner"),
            patch("wakfu_server.achievements.storage.load_locked", return_value=state),
            patch.object(quest_npc, "begin", return_value=session_result) as begin,
            patch.object(quest_npc, "_activate") as activate,
        ):
            result = quest_npc.try_native_overlay(
                Store(),
                7,
                "lease",
                {"id": 41, "account_id": 7},
                self.actor_id,
                436,
                character_provider=lambda: {"id": 41, "account_id": 7},
            )
        self.assertIs(result, session_result)
        begin.assert_called_once()
        activate.assert_not_called()

    def test_no_running_overlay_falls_back_and_mutated_native_source_is_rejected(self):
        class DB:
            def execute(inner, sql, _params=()):
                inner.sql = sql
                return inner

            def fetchone(inner):
                if "world_native_npc_placements" in inner.sql:
                    return self.native_actor
                return {"id": 7}

        class Store:
            @contextmanager
            def connection(_self):
                yield DB()

            def lock_character(_self, *_args, **_kwargs):
                pass

            def character(_self, account_id, character_id, _db):
                return {"id": character_id, "account_id": account_id}

        document = {"placements": [self.item]}
        inactive = {
            "running": [],
            "active": [],
            "active_periods": {},
            "completed": [],
            "objectives": [],
            "variables": {},
            "completion_dates": {},
        }
        with (
            patch.object(quest_npc, "publication", return_value=(document, {}, {})),
            patch.object(quest_npc, "_owner"),
            patch(
                "wakfu_server.achievements.storage.load_locked", return_value=inactive
            ),
            patch.object(quest_npc, "begin") as begin,
        ):
            self.assertIsNone(
                quest_npc.try_native_overlay(
                    Store(),
                    7,
                    "lease",
                    {"id": 41, "account_id": 7},
                    self.actor_id,
                    436,
                    character_provider=lambda: {"id": 41, "account_id": 7},
                )
            )
        begin.assert_not_called()

        changed = dict(self.native_actor, source_sha256="b" * 64)
        with (
            patch.object(quest_npc, "publication", return_value=(document, {}, {})),
            patch.object(quest_npc, "_owner"),
            patch(
                "wakfu_server.achievements.storage.load_locked", return_value=inactive
            ),
        ):
            self.native_actor = changed
            with self.assertRaisesRegex(ValueError, "source changed"):
                quest_npc.try_native_overlay(
                    Store(),
                    7,
                    "lease",
                    {"id": 41, "account_id": 7},
                    self.actor_id,
                    436,
                    character_provider=lambda: {"id": 41, "account_id": 7},
                )
