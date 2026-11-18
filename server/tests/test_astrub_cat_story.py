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
        if "payload @>" in sql:
            character_id, prefix_length, prefix, expected = params
            expected = getattr(expected, "obj", expected)
            excluded = getattr(params[4], "obj", params[4]) if len(params) > 4 else None
            matched = False
            for key, payload in self.receipts.items():
                if not (
                    key.startswith(prefix)
                    and len(key[:prefix_length]) == prefix_length
                    and payload.get("owner") == character_id
                    and all(
                        payload.get(name) == value for name, value in expected.items()
                    )
                ):
                    continue
                if excluded and all(
                    payload.get(name) == value for name, value in excluded.items()
                ):
                    continue
                matched = True
                break
            return SimpleNamespace(
                fetchone=lambda: ({"present": 1} if matched else None)
            )
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
            if params[-4:] != (
                self.character["id"],
                self.character["account_id"],
                312,
                self.character["instance_id"],
            ):
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
        if "SELECT m.* FROM dungeon_instance_members" in sql:
            expected = (
                self.character["instance_id"],
                self.character["id"],
                self.character["account_id"],
            )
            row = self.member if params == expected else None
            return SimpleNamespace(fetchone=lambda: copy.deepcopy(row))
        if "FROM combat_groups " in sql:
            expected = (312, self.character["instance_id"], self.spawn["group_id"])
            row = self.group if params == expected else None
            return SimpleNamespace(fetchone=lambda: copy.deepcopy(row))
        return super().execute(sql, params)

    def record(self, _db, owner, key, payload):
        if owner != self.character["id"]:
            raise AssertionError("Foreign story receipt")
        stored_key = (
            key
            if key.startswith("astrub-cat-story:")
            else f"tutorial-owner:{owner}:{key}"
        )
        if stored_key in self.receipts:
            return False
        self.receipts[stored_key] = copy.deepcopy(payload)
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
            self.earned_links = stack.enter_context(
                patch(
                    "wakfu_server.achievements.earned_achievement_links.settle",
                    return_value=[],
                )
            )
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
            pending_event=kwargs.pop(
                "pending_event", (self.character["instance_id"], event)
            ),
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
    @staticmethod
    def _new_instance(character_id, instance_id, global_receipts=None):
        fixture = Fixture()
        fixture.character.update(id=character_id, instance_id=instance_id)
        fixture.run["instance_id"] = instance_id
        fixture.member.update(
            instance_id=instance_id,
            character_id=character_id,
            party_id=fixture.run["party_id"],
            status="active",
        )
        fixture.progress["instance_id"] = instance_id
        fixture.progress["party_id"] = fixture.run["party_id"]
        fixture.spawn["instance_id"] = instance_id
        fixture.receipts = copy.deepcopy(global_receipts or {})
        first_room_ids = [member["id"] for member in fixture.room_members[1]]
        fixture.receipts[story._key(instance_id, "start")] = dict(
            schema=story.SCHEMA,
            owner=character_id,
            instance_id=instance_id,
            cat_ids=first_room_ids + [-(1000 + index) for index in range(9)],
            nekark_ids=[-(2000 + index) for index in range(5)],
            authority="fixture-owned-initial-story-receipt",
        )
        return fixture

    def test_same_character_sees_cat_scene_and_guide_once_across_instances(self):
        first = Fixture()
        with first.patched():
            offered = first.poll()
            self.assertEqual(scenario_events(offered["packets"]), [23920])
            first.callback(23920)
        global_receipts = {
            key: value
            for key, value in first.receipts.items()
            if key.startswith("tutorial-owner:7:")
        }
        self.assertEqual(len(global_receipts), 2)

        repeat = self._new_instance(7, 100, global_receipts)
        with repeat.patched():
            resumed = repeat.poll()
            self.assertIsNone(resumed["pending_event"])
            self.assertNotIn(23920, scenario_events(resumed["packets"]))
            self.assertNotIn(23921, scenario_events(resumed["packets"]))
            self.assertIn(story._key(100, "callback:23920"), repeat.receipts)

        other = self._new_instance(8, 101, global_receipts)
        with other.patched():
            offered_other = other.poll()
            self.assertIn(23920, scenario_events(offered_other["packets"]))
            acknowledged = other.callback(23920)
            self.assertIn(23921, scenario_events(acknowledged["packets"]))

    def test_historical_scene_and_callback_receipts_backfill_presentation_claims(self):
        fixture = self._new_instance(7, 100)
        fixture.receipts.pop(story._key(100, "start"))
        fixture.receipts.update(
            {
                story._key(99, "scene:23920"): dict(
                    kind="owned_cat_story_scene",
                    owner=7,
                    instance_id=99,
                    event_id=23920,
                ),
                story._key(99, "callback:23920"): dict(
                    kind="owned_cat_story_callback",
                    owner=7,
                    instance_id=99,
                    event_id=23920,
                ),
            }
        )
        with fixture.patched():
            offered = fixture.poll()
            self.assertNotIn(23920, scenario_events(offered["packets"]))
            self.assertIn(story._key(100, "callback:23920"), fixture.receipts)
            self.assertNotIn(23921, scenario_events(offered["packets"]))

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
            self.assertEqual(
                {
                    call.kwargs["source_objective"]
                    for call in fixture.earned_links.call_args_list
                },
                {11511, 11513},
            )
            self.assertTrue(
                all(
                    call.kwargs["event_key"] in fixture.receipts
                    for call in fixture.earned_links.call_args_list
                )
            )

    def test_reconnect_suppresses_seen_scene_and_commits_its_mechanics_once(self):
        fixture = Fixture()
        with fixture.patched():
            fixture.poll()
            fixture.callback(23920)
            fixture.win(1)
            offered = fixture.poll()
            state = copy.deepcopy(fixture.state)
            receipts = copy.deepcopy(fixture.receipts)
            resumed = fixture.poll(bootstrap=True)
            self.assertIsNone(resumed["pending_event"])
            self.assertEqual(scenario_events(resumed["packets"]), [10021, 23923])
            self.assertEqual(fixture.state, state)
            callback_key = story._key(99, "callback:23922")
            self.assertNotIn(callback_key, receipts)
            self.assertIn(callback_key, fixture.receipts)
            self.assertEqual(sum(key == callback_key for key in fixture.receipts), 1)
            self.assertEqual(fixture.poll()["packets"], ())
            replay_before = copy.deepcopy((fixture.state, fixture.receipts))
            duplicate = fixture.callback(23922)
            self.assertEqual(duplicate["packets"], ())
            self.assertEqual(duplicate["pending_event"], (99, 23922))
            self.assertEqual((fixture.state, fixture.receipts), replay_before)

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
