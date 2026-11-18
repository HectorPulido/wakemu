"""Mission-free physical visits retain all non-mission entrance guards."""

from contextlib import contextmanager
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from wakfu_server import owned_physical_entry, dungeon_transport
from wakfu_server.maps import dungeon_entry_access
from wakfu_server.maps.dungeon_instances import EntryRoute


class SettingsStore:
    def __init__(self):
        self.settings = {
            dungeon_entry_access.SETTING: {
                "version": 1,
                "bypass_mission_prerequisites": False,
                "bypass_state_prerequisites": False,
            },
            "instance_entry_level_policy": {
                "version": 1,
                "enforce_minimum_level": True,
            },
            "dungeon_server_mode": {"version": 1, "is_neo_server": False},
        }

    @contextmanager
    def connection(self):
        yield self

    def execute(self, sql, params):
        if sql == "SELECT value FROM settings WHERE name=%s":
            return SimpleNamespace(
                fetchone=lambda: (
                    None
                    if params[0] not in self.settings
                    else {"value": self.settings[params[0]]}
                )
            )
        raise AssertionError(sql)

    def clock(self):
        return 2_000_000_000.0


class PhysicalVisitQualificationStore(SettingsStore):
    def __init__(self, row):
        super().__init__()
        self.row = row

    def execute(self, sql, params):
        if "owned_quest_encounter" in sql and "owned_story_controller" in sql:
            return SimpleNamespace(fetchone=lambda: self.row)
        return super().execute(sql, params)


class OwnedPhysicalEntryTests(unittest.TestCase):
    def setUp(self):
        self.store = SettingsStore()
        self.route = EntryRoute(
            key="owned-test",
            template_id=1000887,
            definition_id=1000887,
            entry_map_id=747,
            entry_object_id=23621,
            destination_id=4029,
            start_map_id=887,
            criterion="",
        )
        self.character = dict(
            id=7,
            account_id=3,
            map_id=747,
            level=20,
            effective_level=20,
            inventory_items=[],
            quest_items=[],
            account_quest_items=[],
        )

    def test_questless_active_and_completed_states_all_pass_owned_mission_gate(self):
        self.assertFalse(
            dungeon_entry_access.policy(self.store)["bypass_mission_prerequisites"]
        )
        mission_by_state = {
            "questless": "IsAchievementRunning(2165)",
            "active": "IsAchievementRunning(2165)",
            "completed": "IsAchievementComplete(2165)",
        }
        for state, mission in mission_by_state.items():
            with self.subTest(state=state):
                self.route = EntryRoute(**{**self.route.__dict__, "criterion": mission})
                self.assertTrue(
                    owned_physical_entry.allowed(self.store, self.character, self.route)
                )

    def test_false_level_item_and_server_predicates_still_deny_for_each_quest_state(
        self,
    ):
        non_mission_failures = (
            "GetRealLevel() >= 50",
            "GetItemQuantity(18747) > 0",
            "IsNeoServer()",
        )
        for state, mission in (
            ("questless", "IsAchievementRunning(2165)"),
            ("active", "IsAchievementRunning(2165)"),
            ("completed", "IsAchievementComplete(2165)"),
        ):
            for predicate in non_mission_failures:
                with self.subTest(state=state, predicate=predicate):
                    route = EntryRoute(
                        **{
                            **self.route.__dict__,
                            "criterion": f"{mission} and {predicate}",
                        }
                    )
                    self.assertFalse(
                        owned_physical_entry.allowed(self.store, self.character, route)
                    )

    def test_only_valid_installed_owned_marker_qualifies(self):
        root = Path(__file__).parents[1] / "wakfu_server/maps/quest_encounter_profiles"
        config = json.loads(
            (root / "astrub-grambo-camp.configuration.json").read_text()
        )
        route = EntryRoute(
            key=config["route"]["key"],
            template_id=config["route"]["template_id"],
            definition_id=config["route"]["definition_id"],
            entry_map_id=config["route"]["entry_map_id"],
            entry_object_id=config["route"]["entry_object_id"],
            destination_id=config["route"]["destination_id"],
            start_map_id=config["route"]["start_map_id"],
            criterion="IsAchievementComplete(2165)",
        )
        active_owned = PhysicalVisitQualificationStore(
            dict(
                quest_policy=config["topology"]["owned_quest_encounter"],
                story_policy=None,
            )
        )
        self.assertTrue(owned_physical_entry.qualifies(active_owned, route))
        active_ordinary = PhysicalVisitQualificationStore(
            dict(quest_policy=None, story_policy=None)
        )
        self.assertFalse(owned_physical_entry.qualifies(active_ordinary, route))

    def test_published_crypt_and_nest_keep_physical_revisits_independent_of_assignment(
        self,
    ):
        root = Path(__file__).parents[1] / "wakfu_server/maps/owned_story_profiles"
        for slug in ("astrub-crypt-889", "astrub-nest-728"):
            with self.subTest(slug=slug):
                config = json.loads((root / (slug + ".configuration.json")).read_text())
                route = EntryRoute(
                    **{
                        key: config["route"][key]
                        for key in (
                            "key",
                            "template_id",
                            "definition_id",
                            "entry_map_id",
                            "entry_object_id",
                            "destination_id",
                            "start_map_id",
                            "criterion",
                        )
                    }
                )
                store = PhysicalVisitQualificationStore(
                    dict(
                        quest_policy=None,
                        story_policy=config["topology"]["owned_story_controller"],
                        trial_policy=None,
                    )
                )
                self.assertFalse(
                    dungeon_entry_access.policy(store)["bypass_mission_prerequisites"]
                )
                self.assertTrue(owned_physical_entry.qualifies(store, route))
                # No achievement authority is supplied: the qualified physical path
                # must not require an assignment, even with a native negated completion.
                self.assertTrue(
                    owned_physical_entry.allowed(store, self.character, route)
                )
                paid_route = EntryRoute(
                    **{
                        **route.__dict__,
                        "criterion": route.criterion
                        + " and GetItemQuantity(18747) > 0",
                    }
                )
                self.assertFalse(
                    owned_physical_entry.allowed(store, self.character, paid_route)
                )

    def test_native_mount_entry_requires_running_quest_despite_global_mission_bypass(
        self,
    ):
        root = Path(__file__).parents[1] / "wakfu_server/maps/owned_story_profiles"
        config = json.loads(
            (root / "astrub-mount-training-879.configuration.json").read_text()
        )
        controller = dict(config["topology"]["owned_story_controller"])
        # Exercise the opt-in contract while remaining compatible with the
        # source fixture during the profile publication transition.
        controller["enforce_native_entry_criterion"] = True
        route = EntryRoute(
            **{
                key: config["route"][key]
                for key in (
                    "key",
                    "template_id",
                    "definition_id",
                    "entry_map_id",
                    "entry_object_id",
                    "destination_id",
                    "start_map_id",
                    "criterion",
                )
            }
        )
        store = PhysicalVisitQualificationStore(
            dict(quest_policy=None, story_policy=controller, trial_policy=None)
        )
        store.settings[dungeon_entry_access.SETTING] = {
            "version": 1,
            "bypass_mission_prerequisites": True,
            "bypass_state_prerequisites": True,
        }
        self.assertEqual(owned_physical_entry.entry_policy(store, route), "native")

        # Supply trusted achievement state but use the real native criterion
        # evaluator. Completion alone is not Running; the active running case is.
        from wakfu_server import dungeon_achievement_authority

        resolved = dict(
            source={"id": route.entry_object_id},
            route=route,
            difficulty_selection={"stasis_level": 2, "competitive": False},
            native_destination={},
            destination={"map_id": route.start_map_id, "x": 0, "y": 0, "z": 0},
        )

        def admission(snapshot, *, selected_controller=controller):
            store.row["story_policy"] = selected_controller
            decisions = []

            def create(_store, _account, _generation, _character, _route, **kwargs):
                decisions.append(kwargs["authorize_entry"](self.character, route))
                return dict(
                    instance_id=99,
                    transition={"map_id": route.start_map_id, "x": 0, "y": 0, "z": 0},
                    reused=False,
                )

            queries = {
                "IsAchievementRunning": lambda quest: quest in snapshot["running"],
                "IsAchievementComplete": lambda quest: quest in snapshot["completed"],
                "IsAchievementActive": lambda quest: quest in snapshot["active"],
                "IsAchievementObjectiveComplete": lambda quest: quest
                in snapshot["objectives"],
            }
            with patch.object(
                dungeon_achievement_authority, "queries", return_value=queries
            ), patch.object(
                dungeon_transport.dungeon_instances,
                "create_or_reuse",
                side_effect=create,
            ):
                result = dungeon_transport.enter_resolved(
                    store,
                    3,
                    "generation",
                    self.character["id"],
                    resolved,
                    criterion_allowed=lambda *_: self.fail(
                        "native owned gate must use its criterion"
                    ),
                    source_allowed=lambda *_: True,
                )
            self.assertEqual(result["instance_id"], 99)
            return decisions

        self.assertEqual(
            admission(
                {"running": [2014], "completed": [], "active": [2014], "objectives": []}
            ),
            [True],
        )
        self.assertEqual(
            admission(
                {"running": [], "completed": [2014], "active": [], "objectives": []}
            ),
            [False],
        )

        # With the opt-in absent, the same published route retains the prior
        # persistent visit behavior (the mission bypass is explicitly enabled).
        legacy_controller = dict(controller)
        legacy_controller.pop("enforce_native_entry_criterion")
        self.assertEqual(
            admission(
                {"running": [], "completed": [2014], "active": [], "objectives": []},
                selected_controller=legacy_controller,
            ),
            [True],
        )
        with self.assertRaises(ValueError):
            owned_physical_entry.allowed(
                store,
                self.character,
                route,
                enforce_native_entry_criterion=1,
            )

    def test_nonowned_route_still_uses_native_criterion_callback(self):
        route = EntryRoute(
            key="ordinary",
            template_id=123,
            definition_id=123,
            entry_map_id=527,
            entry_object_id=12345,
            destination_id=678,
            start_map_id=900,
            criterion="IsAchievementComplete(123)",
        )
        resolved = dict(
            route=route,
            source=dict(id=12345),
            difficulty_selection=dict(stasis_level=2, competitive=False),
            native_destination=dict(cyW=0, item_reference=0),
            destination=dict(map_id=900, x=1, y=2, z=0, direction=1),
        )
        criterion_calls = []
        authorization = []

        def create(_store, _account, _generation, _character, _route, **kwargs):
            actor = dict(id=7, map_id=527)
            authorization.append(kwargs["authorize_entry"](actor, route))
            return dict(
                instance_id=99,
                transition=dict(map_id=900, x=1, y=2, z=0),
                reused=False,
            )

        with patch.object(
            dungeon_transport, "resolve_request", return_value=resolved
        ), patch.object(
            owned_physical_entry, "qualifies", return_value=False
        ), patch.object(
            dungeon_transport.dungeon_instances,
            "create_or_reuse",
            side_effect=create,
        ):
            dungeon_transport._enter(
                self.store,
                3,
                "generation",
                7,
                527,
                b"native-request",
                criterion_allowed=lambda actor, criterion: criterion_calls.append(
                    (actor, criterion)
                )
                or False,
                source_allowed=lambda *_: True,
            )

        self.assertEqual(authorization, [False])
        self.assertEqual(criterion_calls, [({"id": 7, "map_id": 527}, route.criterion)])


if __name__ == "__main__":
    unittest.main()
