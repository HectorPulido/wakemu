"""Owned cat-story choreography follows real room victories and native callbacks."""

import copy
from contextlib import ExitStack, contextmanager
from datetime import datetime, timezone
import struct
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

from server.tests.test_astrub_cat_story_authority import Database as ScopeDatabase
from wakfu_server.achievements import astrub_cat_story as story
from wakfu_server import astrub_cat_presentation as presentation


def definition():
    ids = (11508, 11509, 11510, 11511, 11512, 11513, 11514, 11515, 11544)
    return dict(
        d=5568,
        native_class="aJM",
        aqb=False,
        cjI="",
        cjK=[],
        cjJ=[
            dict(
                d=identity,
                native_class="aJN",
                ckb=True,
                ckc=(
                    ""
                    if index == 0
                    else f"IsAchievementObjectiveComplete({ids[index-1]})"
                ),
                cke="",
                ckf=[],
                ckd=[],
            )
            for index, identity in enumerate(ids)
        ],
    )


class Fixture(ScopeDatabase):
    """Rollback fixture retaining actual mission planner and dependency logic."""

    def __init__(self):
        super().__init__()
        self.character.update(x=4, y=2, z=0)
        self.state = dict(
            variables={},
            objectives=[11508, 11509, 11510],
            running=[5568],
            completed=[],
            tracking=[5568],
            recent=[],
            completion_dates={},
        )
        self.receipts = {}
        self.victories = {}
        self.native = definition()
        self.room_members = {
            room: [
                dict(
                    id=-(room * 100 + index),
                    ref=ref,
                    x=(room - 1) * 10 + index,
                    y=0 if room < 3 else -8,
                    z=0 if room < 3 else -11,
                    map_id=312,
                    instance_id=99,
                )
                for index, ref in enumerate(refs)
            ]
            for room, refs in (
                (1, (2616, 2616, 2616)),
                (2, (2616, 2616, 2617)),
                (3, (1816, 2616, 2617)),
            )
        }
        self.store = MagicMock()
        self.store.connection.side_effect = self.connection
        self.store.character.side_effect = lambda *_: dict(self.character)
        self.store.now.return_value = datetime(2026, 11, 14, tzinfo=timezone.utc)

    @contextmanager
    def connection(self):
        saved = copy.deepcopy((self.character, self.state, self.receipts))
        try:
            yield self
        except BaseException:
            self.character, self.state, self.receipts = saved
            raise

    def execute(self, sql, params=()):
        if "SELECT e.fight_id,e.result FROM dungeon_room_encounters" in sql:
            value = self.victories.get(params[1]) if params[2:] == (7, 2) else None
            return SimpleNamespace(fetchone=lambda: copy.deepcopy(value))
        if "SELECT g.members FROM dungeon_room_spawn_receipts" in sql:
            members = self.room_members.get(params[1])
            return SimpleNamespace(
                fetchone=lambda: (
                    None if members is None else dict(members=copy.deepcopy(members))
                )
            )
        if "native_quest_metadata_definitions" in sql:
            return SimpleNamespace(
                fetchone=lambda: (
                    None
                    if self.native is None
                    else dict(data=dict(native=copy.deepcopy(self.native)))
                )
            )
        if "UPDATE characters SET x=" in sql:
            if params[-4:] != (7, 2, 312, 99):
                raise AssertionError("Position write escaped its owner")
            self.character.update(zip(("x", "y", "z"), params[:3]))
            return SimpleNamespace(rowcount=1)
        if "SELECT c.id,p.state,e.payload FROM dungeon_instance_members" in sql:
            receipt = self.receipts.get(params[0])
            values = (
                []
                if receipt is None or self.member["status"] != "active"
                else [
                    dict(
                        id=7,
                        state=copy.deepcopy(self.state),
                        payload=copy.deepcopy(receipt),
                    )
                ]
            )
            return SimpleNamespace(fetchall=lambda: values)
        return super().execute(sql, params)

    def record(self, _db, owner, key, payload):
        if owner != 7:
            raise AssertionError("Foreign story receipt")
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
                    side_effect=lambda _db, _id, value: setattr(
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
            stack.enter_context(
                patch(
                    "wakfu_server.npc_actor_identity.allocate_block", return_value=1000
                )
            )
            # Actor skin hydration is independently covered by presentation
            # tests. Keep exact event, argument, position and removal codecs live.
            stack.enter_context(
                patch.object(
                    presentation,
                    "visual_packets",
                    return_value=((12608, b"owned-visuals"),),
                )
            )
            yield self

    def poll(self, **kwargs):
        return story.poll(self.store, 2, "generation", dict(self.character), **kwargs)

    def callback(self, event, **kwargs):
        return story.callback(
            self.store,
            2,
            "generation",
            dict(self.character),
            struct.pack(">i", event),
            pending_event=kwargs.pop("pending_event", (99, event)),
            **kwargs,
        )

    def win(self, room, *, victory=True):
        self.victories[room] = dict(
            fight_id=100 + room, result=dict(victory=victory, completed=room == 3)
        )
        self.progress["current_room"] = min(3, room + 1)
        if room == 3:
            self.progress["status"] = "completed"


def scenario_events(packets):
    return [
        struct.unpack_from(">i", body, 1)[0]
        for opcode, body in packets
        if opcode == 13411
    ]


class AstrubCatStoryTests(unittest.TestCase):
    def test_full_native_phase_flow_needs_three_victories_and_completes_only_story_steps(
        self,
    ):
        fixture = Fixture()
        with fixture.patched():
            first = fixture.poll(bootstrap=True)
            self.assertEqual(first["pending_event"], (99, 23920))
            self.assertEqual(scenario_events(first["packets"]), [10021, 23920])
            self.assertTrue(first["blocks_travel"])
            self.assertEqual(
                fixture.poll(pending_event=first["pending_event"])["packets"], ()
            )
            self.assertTrue(story.defer_auto_exit(fixture, 99))
            self.assertEqual(
                scenario_events(fixture.callback(23920)["packets"]), [23921]
            )
            self.assertIsNone(fixture.poll()["pending_event"])
            self.assertEqual(fixture.state["objectives"], [11508, 11509, 11510])
            for room, event in ((1, 23922), (2, 23924), (3, 23926)):
                fixture.win(room)
                offered = fixture.poll()
                self.assertEqual(offered["pending_event"], (99, event))
                self.assertIn(story.ROOM_OBJECTIVES[room], fixture.state["objectives"])
                self.assertEqual(scenario_events(offered["packets"]), [event])
                self.assertEqual(fixture.poll(pending_event=(99, event))["packets"], ())
                acknowledged = fixture.callback(event)
                if room == 3:
                    self.assertEqual(acknowledged["pending_event"], (99, 23927))
                    self.assertEqual(scenario_events(acknowledged["packets"]), [23927])
                else:
                    self.assertIsNone(acknowledged["pending_event"])
            self.assertNotIn(11514, fixture.state["objectives"])
            self.assertNotIn(11515, fixture.state["objectives"])
            self.assertTrue(story.defer_auto_exit(fixture, 99))
            exit_scene = fixture.callback(23927)
            self.assertEqual(exit_scene["pending_event"], (99, 23928))
            self.assertEqual(scenario_events(exit_scene["packets"]), [23928])
            self.assertIn(11514, fixture.state["objectives"])
            self.assertEqual(
                tuple(fixture.character[k] for k in ("x", "y", "z")), (149, 125, 0)
            )
            finished = fixture.callback(23928)
            self.assertTrue(finished["finished"])
            self.assertEqual(scenario_events(finished["packets"]), [23929])
            self.assertIn(11515, fixture.state["objectives"])
            self.assertNotIn(11544, fixture.state["objectives"])
            self.assertEqual(fixture.state["running"], [5568])
            self.assertFalse(story.defer_auto_exit(fixture, 99))
            self.assertTrue(fixture.poll()["finished"])

    def test_reconnect_resumes_only_unfinished_scene_without_advancing_again(self):
        fixture = Fixture()
        with fixture.patched():
            fixture.poll()
            fixture.callback(23920)
            fixture.win(1)
            offered = fixture.poll()
            state = copy.deepcopy(fixture.state)
            receipts = copy.deepcopy(fixture.receipts)
            resumed = fixture.poll(bootstrap=True)
            self.assertEqual(resumed["pending_event"], offered["pending_event"])
            self.assertEqual(scenario_events(resumed["packets"]), [10021, 23922])
            self.assertEqual(fixture.state, state)
            self.assertEqual(fixture.receipts, receipts)
            fixture.callback(23922)
            self.assertEqual(fixture.poll()["packets"], ())
            with self.assertRaisesRegex(ValueError, "out of order"):
                fixture.callback(23922)

    def test_malformed_stale_and_out_of_order_callbacks_cannot_mutate_progress(self):
        fixture = Fixture()
        with fixture.patched():
            fixture.poll()
            initial = copy.deepcopy(
                (fixture.state, fixture.receipts, fixture.character)
            )
            for event, kwargs in (
                (23922, {}),
                (23928, {}),
                (23920, dict(pending_event=(100, 23920))),
                (23920, dict(in_combat=True)),
                (23920, dict(pending_event=None)),
            ):
                with self.subTest(event=event, kwargs=kwargs), self.assertRaises(
                    ValueError
                ):
                    fixture.callback(event, **kwargs)
                self.assertEqual(
                    (fixture.state, fixture.receipts, fixture.character), initial
                )
            with self.assertRaises(ValueError):
                story.callback(
                    fixture.store,
                    2,
                    "generation",
                    fixture.character,
                    b"bad",
                    pending_event=(99, 23920),
                )

    def test_defeat_or_forged_victory_never_emits_story_room_objective(self):
        fixture = Fixture()
        with fixture.patched():
            fixture.poll()
            fixture.callback(23920)
            fixture.win(1, victory=False)
            result = fixture.poll()
            self.assertIsNone(result["pending_event"])
            self.assertNotIn(11511, fixture.state["objectives"])
            self.assertNotIn(story._key(99, "scene:23922"), fixture.receipts)
            with self.assertRaisesRegex(ValueError, "out of order"):
                fixture.callback(23922)
            fixture.win(1)
            fixture.victories[1]["result"][
                "victory"
            ] = 1  # Truthy data is not an authoritative boolean.
            self.assertIsNone(fixture.poll()["pending_event"])

    def test_missing_native_definition_rolls_back_scene_and_objective(self):
        fixture = Fixture()
        with fixture.patched():
            fixture.poll()
            fixture.callback(23920)
            fixture.win(1)
            fixture.native = None
            initial = copy.deepcopy(
                (fixture.state, fixture.receipts, fixture.character)
            )
            with self.assertRaisesRegex(ValueError, "mission definition"):
                fixture.poll()
            self.assertEqual(
                (fixture.state, fixture.receipts, fixture.character), initial
            )

    def test_auto_exit_ignores_unrelated_or_forged_story_receipts(self):
        fixture = Fixture()
        self.assertFalse(story.defer_auto_exit(fixture, 99))
        fixture.receipts[story._key(99, "start")] = dict(
            schema=story.SCHEMA, owner=8, instance_id=99
        )
        self.assertFalse(story.defer_auto_exit(fixture, 99))
        fixture.receipts[story._key(99, "start")]["owner"] = 7
        self.assertTrue(story.defer_auto_exit(fixture, 99))
        fixture.state["objectives"].append(11515)
        self.assertFalse(story.defer_auto_exit(fixture, 99))
