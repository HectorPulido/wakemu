"""Focused contracts for the finite Kelba investigation and hideout chapter."""

from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import struct
import unittest
from unittest.mock import patch

from wakfu_server import owned_story_controller, owned_story_mechanics
from wakfu_server.achievements import (
    storage,
    tutorial_presentation_once as presentation_once,
)


ROOT = Path(__file__).resolve().parents[1]
PROFILES = ROOT / "wakfu_server/maps/owned_story_profiles"
ACHIEVEMENTS = ROOT / "wakfu_server/achievements"
PRIVATE = ROOT.parent / ".runtime/quest-archetypes"


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def selected(path):
    return owned_story_controller.policy(
        {"topology": {"owned_story_controller": load(path)}}
    )


class _MemoryDB:
    def __init__(self):
        self.rows = {}

    def execute(self, query, params):
        class Result:
            def __init__(self, row):
                self.row = row

            def fetchone(self):
                return self.row

        character_id = params[0]
        if "ORDER BY (payload->>'order_ns')" in query:
            prefix = params[2]
            rows = [
                (key, payload)
                for (owner, key), payload in self.rows.items()
                if owner == character_id and key.startswith(prefix)
            ]
            rows.sort(key=lambda pair: int(pair[1]["order_ns"]), reverse=True)
            return Result(None if not rows else {"payload": rows[0][1]})
        key = params[1]
        payload = self.rows.get((character_id, key))
        return Result(None if payload is None else {"payload": payload})


def record(db, character_id, key, payload):
    identity = (character_id, key)
    if identity in db.rows:
        return False
    db.rows[identity] = deepcopy(payload)
    return True


class KelbaInvestigationChapterTests(unittest.TestCase):
    def test_black_crow_reveal_requires_the_native_callback_order_and_once_group(self):
        profile = PROFILES / "kelba-lair-951.json"
        native_path = PROFILES / "kelba-lair-951.native.v1.json"
        instance = load(PROFILES / "kelba-lair-951.instance.json")
        story = selected(profile)
        native = owned_story_mechanics.sources(story)
        from wakfu_server import owned_story_admission

        self.assertEqual(
            instance["entry"],
            {"map_id": 949, "object_id": 25127, "destination_id": 2210},
        )
        self.assertEqual(native["scenario_id"], 1977)
        self.assertEqual(
            native["scenes"]["15758"],
            {
                "argument_count": 1,
                "duration_ms": 6500,
                "callback": 15876,
            },
        )
        self.assertEqual(native["scenes"]["15774"]["callback"], 15774)
        self.assertEqual(native["scenes"]["15759"]["callback"], 19800)

        # Resolve the render-only Kabrok from the real monster prototype and
        # the published Sm geometry; no actor or combat state is fabricated.
        character = {"id": 77, "instance_id": (1 << 57) + 1}
        with patch.object(
            owned_story_controller, "_scope", return_value=(story, set())
        ):
            actors = owned_story_admission.scene_actor_rows(None, None, character)
        self.assertEqual(len(actors), 1)
        kabrok = actors[0]
        self.assertEqual(
            (
                kabrok["reference_id"],
                kabrok["level"],
                kabrok["x"],
                kabrok["y"],
                kabrok["z"],
            ),
            (3580, 154, -2, 0, 0),
        )
        self.assertEqual(kabrok["visual_id"], 173603580)
        start = owned_story_controller.plan(
            story, set(), kind="world_ready", reference=951
        )
        self.assertEqual(start["id"], "kabrok-reveal-start")
        self.assertEqual(
            start["effects"],
            [
                {
                    "kind": "scenario_event",
                    "scenario": 1977,
                    "event": 15758,
                    "arguments": ["scene_actor:kabrok"],
                }
            ],
        )
        packet = owned_story_mechanics.scenario_packet(
            story, 15758, [kabrok["actor_id"]]
        )
        self.assertEqual(struct.unpack(">BiiB", packet[1][:10]), (0, 15758, 1977, 1))
        self.assertEqual(struct.unpack(">q", packet[1][10:]), (kabrok["actor_id"],))
        self.assertFalse(
            any(effect["kind"] == "quest_objective" for effect in start["effects"])
        )

        completed = {start["id"]}
        expected = ((15876, 15774), (15774, 15759), (19800, 19800))
        for callback, offered_event in expected:
            pending = owned_story_controller.pending_callback_step(story, completed)
            self.assertEqual(pending["reference"], callback)
            if callback != 19800:
                self.assertIsNone(
                    owned_story_controller.plan(
                        story, completed, kind="scenario_complete", reference=19800
                    )
                )
            step = owned_story_controller.plan(
                story, completed, kind="scenario_complete", reference=callback
            )
            self.assertEqual(step["effects"][0]["event"], offered_event)
            if callback == 19800:
                self.assertIn(
                    {"kind": "quest_objective", "quest_id": 2544, "objective_id": 5043},
                    step["effects"],
                )
            completed.add(step["id"])
        self.assertIsNone(
            owned_story_controller.pending_callback_step(story, completed)
        )

        # The three actual cinematic phases use the shared once-per-context
        # ledger; reconnecting cannot replay a vanished Kabrok actor.
        group = native["presentation_groups"][0]
        self.assertEqual(group["events"], [15758, 15774, 15759])
        db = _MemoryDB()
        owner = {"id": 77, "instance_id": 1001}
        with patch.object(storage, "_lock"), patch.object(
            storage, "record_event", side_effect=record
        ), patch.object(presentation_once.time, "time_ns", side_effect=(1, 2)):
            presentation_once.register_context(db, owner, "a" * 32)
            for event in group["events"]:
                self.assertTrue(
                    presentation_once.claim_group_event(db, owner, group, 1977, event)
                )
                self.assertFalse(
                    presentation_once.claim_group_event(db, owner, group, 1977, event)
                )
            presentation_once.register_context(db, owner, "b" * 32)
            self.assertFalse(
                presentation_once.claim_group_event(db, owner, group, 1977, 15758)
            )

    def test_late_kabrok_context_is_physical_only_and_native_exit_is_preserved(self):
        instance = load(PROFILES / "kelba-shop-945-late.instance.json")
        story = selected(PROFILES / "kelba-shop-945-late.json")
        compiled = load(PROFILES / "kelba-shop-945-late.configuration.json")

        self.assertEqual(
            instance["entry"],
            {
                "map_id": 943,
                "object_id": 25107,
                "destination_id": 2191,
            },
        )
        self.assertEqual(
            instance["exit_sources"],
            [
                {"source_id": 25122, "destination_id": 2174},
            ],
        )
        self.assertEqual(compiled["compiled_plan"]["rooms"], [])
        self.assertEqual(
            owned_story_controller.plan(
                story, set(), kind="world_ready", reference=945
            )["effects"],
            [],
        )
        self.assertIsNone(
            owned_story_controller.plan(story, set(), kind="room_victory", reference=1)
        )

    def test_native_attack_clues_keep_their_shared_original_guard_and_exact_objectives(
        self,
    ):
        manifest = load(
            ACHIEVEMENTS / "quest_interactions/kelba-attack-investigations.json"
        )
        native = load(PRIVATE / "kelba-investigation-native-approaches.json")
        bindings = {
            row["object_id"]: (row["quest_id"], row["objective_id"])
            for row in manifest["bindings"]
        }
        expected = {
            25178: (2571, 5085),
            25177: (2572, 5086),
            25124: (2539, 5038),
        }
        self.assertEqual(bindings, expected)
        self.assertEqual(len(native), 3)
        for binding, source in zip(
            sorted(manifest["bindings"], key=lambda row: row["object_id"]),
            sorted(native, key=lambda row: row["source"]["id"]),
        ):
            with self.subTest(source=binding["object_id"]):
                self.assertEqual(source["source"]["id"], binding["object_id"])
                self.assertEqual(source["source"]["map_id"], 943)
                self.assertEqual(source["descriptor"]["descriptor_id"], 848)
                action = source["descriptor"]["groups"][0]["actions"][0]
                guard = (
                    "IsAchievementRunning(2571) or "
                    "IsAchievementRunning(2572) or IsAchievementRunning(2539)"
                )
                self.assertEqual(action["criterion"], guard)
                self.assertEqual(action["effects"][0]["criterion"], guard)
                self.assertEqual(action["effects"][0]["action_reference"], 2232)
                self.assertEqual(binding["script_id"], 0)

    def test_hideout_requires_real_room_order_and_once_group_but_suppression_still_settles(
        self,
    ):
        story = selected(PROFILES / "kelba-hideout-948.json")
        instance = load(PROFILES / "kelba-hideout-948.instance.json")
        native = owned_story_mechanics.sources(story)
        steps = set()

        self.assertEqual(
            instance["entry"],
            {
                "map_id": 943,
                "object_id": 25137,
                "destination_id": 2184,
            },
        )
        self.assertEqual(
            instance["exit_sources"],
            [
                {"source_id": 25118, "destination_id": 2172},
            ],
        )

        discovered = owned_story_controller.plan(
            story, steps, kind="world_ready", reference=948
        )
        self.assertEqual(discovered["id"], "hideout-discovered")
        self.assertIsNone(
            owned_story_controller.plan(story, steps, kind="room_victory", reference=1)
        )
        steps.add("hideout-discovered")
        admitted = owned_story_controller.plan(
            story, steps, kind="room_admission", reference=1
        )
        self.assertEqual(admitted["id"], "hideout-riktus-admitted")
        self.assertIsNone(
            owned_story_controller.plan(story, steps, kind="room_victory", reference=1)
        )
        steps.add("hideout-riktus-admitted")
        victory = owned_story_controller.plan(
            story, steps, kind="room_victory", reference=1
        )
        self.assertEqual(victory["id"], "hideout-riktus-defeated")
        self.assertIsNone(
            owned_story_controller.plan(story, steps, kind="world_ready", reference=948)
        )
        steps.add("hideout-riktus-defeated")
        intervention = owned_story_controller.plan(
            story, steps, kind="world_ready", reference=948
        )
        self.assertEqual(intervention["id"], "hideout-hadibal-intervention")
        self.assertEqual(intervention["effects"][0]["event"], 15699)
        self.assertEqual(
            native["scenes"]["15699"],
            {
                "argument_count": 1,
                "duration_ms": 20000,
                "callback": 15700,
            },
        )
        self.assertEqual(
            native["presentation_groups"],
            [
                {
                    "id": "kelba-hideout-hadibal",
                    "start_event": 15699,
                    "initializers": {"1966": 15699},
                    "events": [15699, 15700],
                }
            ],
        )

        # The global presentation ledger claims the original group once for
        # this character and instance, and a reconnect cannot replay it.
        db = _MemoryDB()
        character = {"id": 77, "instance_id": 1001}
        group = native["presentation_groups"][0]
        with patch.object(storage, "_lock"), patch.object(
            storage, "record_event", side_effect=record
        ), patch.object(presentation_once.time, "time_ns", return_value=1):
            presentation_once.register_context(db, character, "a" * 32)
            self.assertTrue(
                presentation_once.claim_group_event(db, character, group, 1966, 15699)
            )
            self.assertFalse(
                presentation_once.claim_group_event(db, character, group, 1966, 15699)
            )
            self.assertTrue(
                presentation_once.claim_group_event(db, character, group, 1966, 15700)
            )
            presentation_once.register_context(db, character, "b" * 32)
            self.assertFalse(
                presentation_once.claim_group_event(db, character, group, 1966, 15699)
            )

        # When the presentation has already been shown elsewhere, the native
        # end callback still stages the camera return and objective together.
        callback = owned_story_controller.plan(
            story,
            steps | {"hideout-hadibal-intervention"},
            kind="scenario_complete",
            reference=15700,
        )
        self.assertEqual(callback["id"], "hideout-film-finished")
        self.assertIn(
            {"kind": "stage_position", "event": 15700, "position": [10, 1, 0]},
            callback["effects"],
        )
        self.assertIn(
            {"kind": "quest_objective", "quest_id": 2542, "objective_id": 5041},
            callback["effects"],
        )
        after_film = steps | {
            "hideout-hadibal-intervention",
            "hideout-film-finished",
        }
        debrief = owned_story_controller.plan(
            story, after_film, kind="npc_spoken", reference=3588
        )
        self.assertEqual(debrief["id"], "hideout-hadibal-debrief")
        self.assertEqual(
            debrief["effects"],
            [{"kind": "quest_objective", "quest_id": 2543, "objective_id": 5042}],
        )

    def test_hideout_victory_requires_finished_original_native_roster(self):
        story = selected(PROFILES / "kelba-hideout-948.json")
        configuration = load(PROFILES / "kelba-hideout-948.configuration.json")
        room = configuration["compiled_plan"]["rooms"][0]
        originals = [
            {"id": -100 - index, "ref": row["ref_id"]}
            for index, row in enumerate(room["monsters"])
        ]
        members = [{"id": row["id"], "ref": row["ref"]} for row in originals]
        encounter = {
            "fight_status": "finished",
            "encounter_scope": "main",
            "room_order": 1,
            "team": 0,
            "player_team": 0,
            "status": "victory",
            "result": {"victory": True},
            "context_route_key": "quest-map-948-25137-2184",
            "context_policy_version": 1,
        }
        spawned = {"members": members, "status": "defeated", "asset_map_id": 948}

        class Cursor:
            def __init__(self, row):
                self.row = row

            def fetchone(self):
                return self.row

        class DB:
            def execute(self, query, _params):
                if "FROM dungeon_room_encounters e" in query:
                    return Cursor(encounter)
                if "FROM dungeon_room_spawn_receipts r" in query:
                    return Cursor(spawned)
                raise AssertionError(query)

        actors = {
            row["id"]: type(
                "Monster",
                (),
                {"team": 1, "controlled": False, "hp": 0},
            )()
            for row in originals
        }
        fight = type(
            "Fight",
            (),
            {
                "id": 902,
                "phase": "finished",
                "winner": 0,
                "actors": actors,
                "events": [dict(kind="death", actor_id=row["id"]) for row in originals],
            },
        )()
        character = {"id": 7, "account_id": 2, "map_id": 948, "instance_id": 123}
        applied = []

        def apply_effects(_db, _store, _character, effects):
            applied.extend(effects)
            return [(13411, b"native-win")]

        completed = {"hideout-discovered", "hideout-riktus-admitted"}
        store = type(
            "Store",
            (),
            {"now": lambda _self: datetime.fromtimestamp(1, timezone.utc)},
        )()
        with (
            patch.object(
                owned_story_controller, "_scope", return_value=(story, completed)
            ),
            patch(
                "wakfu_server.dungeon_runtime_config.pinned_configuration",
                return_value=configuration,
            ),
            patch.object(storage, "record_event", return_value=True) as record,
        ):
            outcome = owned_story_controller.on_room_victory(
                DB(), store, character, fight, originals, apply_effects=apply_effects
            )
            self.assertTrue(outcome["applied"])
            self.assertEqual(outcome["step"], "hideout-riktus-defeated")
            self.assertEqual(
                applied[0], dict(kind="scenario_event", scenario=1966, event=15694)
            )
            self.assertEqual(
                record.call_args.args[2],
                "owned-story:kelba-hideout-948:123:hideout-riktus-defeated",
            )

            # A living original Riktus cannot qualify, even with a nominal
            # finished winner and a matching room receipt.
            actors[originals[0]["id"]].hp = 1
            with self.assertRaisesRegex(
                ValueError, "original defeated native formation"
            ):
                owned_story_controller.on_room_victory(
                    DB(),
                    store,
                    character,
                    fight,
                    originals,
                    apply_effects=apply_effects,
                )


if __name__ == "__main__":
    unittest.main()
