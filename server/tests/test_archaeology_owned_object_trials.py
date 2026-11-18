"""The reviewed archaeology declaration follows its actual native walking graph."""

from collections import deque
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import wakfu_server
from wakfu_server import owned_object_trials as trials
from wakfu_server.application import owned_object_trial_dispatch, owned_story_dispatch
from wakfu_server.spatial_native import NativeSpatial
from wakfu_server.spatial_topology import directed_path


ROOT = Path(__file__).parents[1] / "wakfu_server/maps/owned_object_trial_profiles"
STORY_ROOT = Path(__file__).parents[1] / "wakfu_server/maps/owned_story_profiles"


def _shortest_reviewed_path(geometry, trial, start):
    edges = {(tuple(a), tuple(b)) for a, b in geometry["edges"]}
    hazards = set(map(tuple, trial["hazard_cells"]))
    safe_edges = {tuple(map(tuple, edge)) for edge in trial["safe_edges"]}
    goal = tuple(trial["destination_cells"][0])
    previous = {tuple(start): None}
    queue = deque([tuple(start)])
    while queue and goal not in previous:
        current = queue.popleft()
        for source, target in edges:
            if source != current or target in hazards or target in previous:
                continue
            if (
                abs(current[2] - target[2]) > trial["max_height_delta"]
                and (current, target) not in safe_edges
            ):
                continue
            previous[target] = current
            queue.append(target)
    if goal not in previous:
        raise AssertionError("No reviewed safe path reaches the relic destination")
    path = []
    current = goal
    while current is not None:
        path.append(current)
        current = previous[current]
    return list(reversed(path))


def _request(path):
    return dict(
        start_position=dict(zip(("x", "y", "z"), path[0])),
        end_position=dict(zip(("x", "y", "z"), path[-1])),
        steps=[
            dict(dx=b[0] - a[0], dy=b[1] - a[1], dz=b[2] - a[2])
            for a, b in zip(path, path[1:])
        ],
    )


class ArchaeologyOwnedObjectTrialTests(unittest.TestCase):
    def setUp(self):
        self.profile = json.loads((ROOT / "archaeology-2698.json").read_text())
        self.geometry = json.loads(
            (ROOT / "archaeology-1001.exploration.json").read_text()
        )
        self.native = json.loads(
            (STORY_ROOT / "archaeology-1001.native.v1.json").read_text()
        )

    def test_four_scrolls_four_distinct_digs_and_native_safe_relic_route(self):
        selected = trials.policy({"topology": {"owned_object_trials": self.profile}})
        state = trials.initial_state(selected)
        wrong = trials.reduce(selected, state, dict(kind="interact", source_id=25514))
        self.assertEqual(
            wrong["effects"][0],
            dict(kind="scenario_event", scenario=2048, event=16228, arguments=[0]),
        )
        self.assertEqual(wrong["effects"][1]["kind"], "information")
        state = wrong["state"]

        for identity in (25512, 25514, 25513, 25515):
            step = trials.reduce(
                selected, state, dict(kind="interact", source_id=identity)
            )
            self.assertTrue(step["changed"])
            state = step["state"]
        self.assertTrue(state["trials"]["chronological-scrolls"]["complete"])
        self.assertIn(
            dict(kind="quest_objective", quest_id=2698, objective_id=5330),
            step["effects"],
        )

        for identity in (25488, 25489, 25490, 25521):
            discovery = trials.reduce(
                selected, state, dict(kind="interact", source_id=identity)
            )
            self.assertTrue(discovery["changed"])
            state = discovery["state"]
            if identity == 25488:
                duplicate = trials.reduce(
                    selected, state, dict(kind="interact", source_id=identity)
                )
                self.assertFalse(duplicate["changed"])
                self.assertEqual(duplicate["effects"], [])
        self.assertTrue(state["trials"]["ancient-relic-identification"]["complete"])

        trial = selected["trials"][2]
        pickup = next(row for row in selected["sources"] if row["id"] == 25491)
        start = pickup["approaches"][-1]
        path = _shortest_reviewed_path(self.geometry, trial, start)
        self.assertEqual(len(path) - 1, 37)
        self.assertEqual(path[-1], tuple(trial["destination_cells"][0]))
        self.assertFalse(set(path) & set(map(tuple, trial["hazard_cells"])))

        with NativeSpatial("archaeology-2698-safe-carry-test") as native_spatial:
            self.assertEqual(
                directed_path(
                    native_spatial,
                    self.geometry,
                    _request(path),
                    trial["hazard_cells"],
                ),
                list(path[-1]),
            )
            # This adjacent 3-level upper/lower shortcut is not one of the
            # explicitly reviewed staircase edges and is absent from native edges.
            shortcut = [(-14, -18, 0), (-13, -18, -3)]
            with self.assertRaisesRegex(ValueError, "native exploration edges"):
                directed_path(
                    native_spatial,
                    self.geometry,
                    _request(shortcut),
                    trial["hazard_cells"],
                )

        picked = trials.reduce(selected, state, dict(kind="interact", source_id=25491))
        self.assertEqual(picked["effects"][0]["event"], 16183)
        carrying = picked["state"]
        delivered = trials.reduce(
            selected,
            carrying,
            dict(kind="movement", cells=[list(cell) for cell in path]),
        )
        self.assertTrue(delivered["state"]["trials"]["fragile-relic-carry"]["complete"])
        self.assertIn(
            dict(kind="quest_objective", quest_id=2698, objective_id=5332),
            delivered["effects"],
        )
        rejected_shortcut = trials.reduce(
            selected,
            carrying,
            dict(kind="movement", cells=[list(cell) for cell in shortcut]),
        )
        self.assertFalse(
            rejected_shortcut["state"]["trials"]["fragile-relic-carry"].get(
                "complete", False
            )
        )
        self.assertFalse(
            rejected_shortcut["state"]["trials"]["fragile-relic-carry"]["carrying"]
        )
        self.assertEqual(
            rejected_shortcut["effects"][0]["position"], list(shortcut[-1])
        )

    def test_actual_1001_noncombat_manifest_compiles_against_native_sources(self):
        from wakfu_server import generic_transports
        from wakfu_server.combat_geometry import published_geometry
        from wakfu_server.owned_story_configuration import compile_object_trials

        manifest = json.loads((ROOT / "archaeology-2698.instance.json").read_text())
        sources = {
            (row["map_id"], row["id"]): row for row in generic_transports._CATALOG
        }
        compiled = compile_object_trials(
            manifest,
            trials=self.profile,
            geometry=published_geometry(1001),
            exploration=self.geometry,
            sources=sources,
        )
        self.assertEqual(compiled["topology"]["asset_map_id"], 1001)
        self.assertEqual(compiled["topology"]["policy"], trials.SCHEMA)
        self.assertEqual(compiled["topology"]["rooms"], [])
        self.assertEqual(compiled["compiled_plan"]["rooms"], [])
        self.assertEqual(compiled["route"]["entry_object_id"], 25474)
        self.assertEqual(compiled["route"]["destination_id"], 2290)
        self.assertEqual(
            [
                (row["source_id"], row["destination_id"])
                for row in compiled["topology"]["native_story_exits"]
            ],
            [(31332, 3943)],
        )

    def test_native_source_fallback_authenticates_all_scrolls_and_rejects_drift(self):
        from copy import deepcopy
        from wakfu_server import world_static

        selected = trials.policy({"topology": {"owned_object_trials": self.profile}})
        by_id = {row["id"]: row for row in world_static.objects(selected["map_id"])}
        self.assertEqual(len(selected["sources"]), 9)
        for source in selected["sources"]:
            current = dict(zip(("x", "y", "z"), source["approaches"][0]))
            actual = by_id[source["id"]]
            self.assertNotIn("descriptor_id", actual)
            trials._native_source(selected, current, source, source["action"])

        source = selected["sources"][0]
        current = dict(zip(("x", "y", "z"), source["approaches"][0]))
        original = by_id[source["id"]]
        for label, mutate, action, parameter, position in (
            (
                "payload",
                lambda row: row.update(payload_hex="00"),
                source["action"],
                0,
                current,
            ),
            (
                "explicit descriptor",
                lambda row: row.update(descriptor_id=source["descriptor_id"] + 1),
                source["action"],
                0,
                current,
            ),
            (
                "explicit parameters",
                lambda row: row.update(native_parameters=source["descriptor_id"] + 1),
                source["action"],
                0,
                current,
            ),
            ("action", lambda row: None, source["action"] + 1, 0, current),
            ("parameter", lambda row: None, source["action"], 1, current),
            (
                "approach",
                lambda row: None,
                source["action"],
                0,
                dict(x=999, y=999, z=0),
            ),
        ):
            with self.subTest(rejection=label):
                changed = deepcopy(original)
                mutate(changed)
                rows = tuple(
                    changed if row["id"] == source["id"] else row
                    for row in by_id.values()
                )
                with patch.object(
                    world_static, "objects", return_value=rows
                ), self.assertRaisesRegex(ValueError, "exact native authority"):
                    trials._native_source(selected, position, source, action, parameter)

    def test_public_session_hooks_are_safe_before_bootstrap_and_ready_only_after_load(
        self,
    ):
        connection = SimpleNamespace(
            owned_object_trials_active=False,
            owned_story_active=False,
        )
        state = SimpleNamespace(
            connection=connection,
            character=dict(id=7, instance_id=0),
            loaded=False,
            fight=None,
            combat_session=None,
            spectator_session=None,
            account_id=3,
            generation="qa-generation",
        )
        session = SimpleNamespace(state=state, runtime=SimpleNamespace())
        unknown_db = Mock()
        fake_runtime = SimpleNamespace()
        with patch.dict(
            sys.modules, {"wakfu_server.dungeon_runtime": fake_runtime}
        ), patch.object(wakfu_server, "dungeon_runtime", fake_runtime, create=True):
            self.assertIsNone(
                owned_object_trial_dispatch._configuration(
                    unknown_db, dict(id=7, account_id=3, instance_id=99, map_id=777)
                )
            )
            state.character = dict(id=7, account_id=3, instance_id=99, map_id=777)
            state.loaded = True
            connection.owned_object_trials_active = True
            owned_object_trial_dispatch.poll(session)
            self.assertFalse(connection.owned_object_trials_active)
        unknown_db.execute.assert_not_called()

        runtime = SimpleNamespace(STORE=Mock())
        unloaded = SimpleNamespace(
            state=SimpleNamespace(
                connection=SimpleNamespace(owned_object_trials_active=False),
                character=dict(id=7, instance_id=99, map_id=1001),
                loaded=False,
            ),
            runtime=runtime,
        )
        owned_object_trial_dispatch.ready(unloaded)
        runtime.STORE.connection.assert_not_called()

        state.character = dict(id=7, instance_id=0)
        state.loaded = False
        with patch.object(
            owned_object_trial_dispatch, "hydrate", return_value=False
        ), patch.object(
            owned_story_dispatch, "stage_ready", return_value=False
        ), patch.object(
            owned_story_dispatch, "stage_poll", return_value=False
        ), patch.object(
            owned_object_trial_dispatch, "ready"
        ) as ready:
            self.assertFalse(owned_story_dispatch.hydrate(session))
            owned_story_dispatch.arm_movement(session, [])
            owned_story_dispatch.poll(session)
            ready.assert_not_called()

            state.character["instance_id"] = 99
            state.character["map_id"] = 1001
            state.loaded = True
            connection.owned_object_trials_active = True
            owned_object_trial_dispatch.poll(session)
            ready.assert_called_once_with(session)


if __name__ == "__main__":
    unittest.main()
