"""Reachable zone-wide placement on native terrain and bounded sparse controls."""
from collections import defaultdict, deque
import unittest

from wakfu_server.objectives.environmental_resource_placement import plan


class EnvironmentalResourcePlacementTests(unittest.TestCase):
    def test_native_tainela_mission_zone_paths_spread_and_no_spill_capacity(self):
        import csv
        import hashlib
        import io
        import json
        from pathlib import Path

        geometry_raw = Path(
            ".runtime/environmental-map527-native-geometry.json"
        ).read_bytes()
        self.assertEqual(
            hashlib.sha256(geometry_raw).hexdigest(),
            "0bfbbc314349dd929561c9a93dd65fed6c3d52a78a886cbabb28515893394cb0",
        )
        geometry = json.loads(geometry_raw)
        raw = Path(
            ".runtime/parallel-readiness-20261021/environmental-original-native-cells.csv"
        ).read_bytes()
        self.assertEqual(
            hashlib.sha256(raw).hexdigest(),
            "83832651b128780860ec32390bff8ea4c9e406b3560377da7d790829f074961e",
        )
        surfaces = defaultdict(list)
        for source in csv.DictReader(io.StringIO(raw.decode())):
            row = {key: int(value) for key, value in source.items()}
            if row["map_id"] == 527:
                surfaces[(row["x"], row["y"])].append(
                    dict(z=row["z"], region_id=row["region_id"])
                )
        origin = (-238, -84, 0)
        zone = {
            (x, y, row["z"])
            for (x, y), candidates in surfaces.items()
            for row in candidates
            if row["region_id"] == 76101
        }
        foreign = {
            (x, y, row["z"])
            for (x, y), candidates in surfaces.items()
            for row in candidates
            if row["region_id"] != 76101
        }
        self.assertTrue(zone)
        self.assertTrue(foreign - zone)
        kwargs = dict(
            region_id=76101,
            origins=[origin],
            taken=set(),
            quantity=100,
            seed="tainela-original-mission-zone",
            reserve=0,
        )
        rows = plan(surfaces, geometry, **kwargs)
        self.assertEqual(len(rows), 100)
        self.assertEqual(rows, plan(surfaces, geometry, **kwargs))
        positions = {(row["x"], row["y"], row["z"]) for row in rows}
        self.assertEqual(len(positions), 100)
        self.assertTrue(positions <= zone)
        self.assertFalse(positions & (foreign - zone))
        edges = {(tuple(a), tuple(b)) for a, b in geometry["edges"]}
        occupied = {p[:2] for p in positions}
        for row in rows:
            route = tuple(map(tuple, row["path"]))
            approach = tuple(row["approach"])
            point = (row["x"], row["y"], row["z"])
            self.assertEqual(route[0], origin)
            self.assertEqual(route[-1], approach)
            self.assertFalse(any(p[:2] in occupied for p in route))
            for a, b in zip(route, route[1:]):
                self.assertIn((a, b), edges)
                self.assertIn((b, a), edges)
            self.assertIn((approach, point), edges)
            self.assertIn((point, approach), edges)
        for a in positions:
            for b in positions:
                if a != b:
                    self.assertGreaterEqual(abs(a[0] - b[0]) + abs(a[1] - b[1]), 3)
        for axis in (0, 1):
            available = max(p[axis] for p in zone) - min(p[axis] for p in zone)
            spread = max(p[axis] for p in positions) - min(p[axis] for p in positions)
            self.assertGreaterEqual(spread, available * 0.7)

        # Declared two-zone bridge control: native paths may cross another
        # zone, but its resources cannot fill capacity in the small mission.
        ground = [(x, 0, 0) for x in range(18)]
        upper = [(x, 0, 9) for x in range(18)]
        control_edges = []
        for level in (ground, upper):
            for a, b in zip(level, level[1:]):
                control_edges.extend(((a, b), (b, a)))
        control_edges.extend(((ground[0], upper[0]), (upper[0], ground[0])))
        control_surfaces = {
            (x, 0): [dict(z=9, region_id=1 if 4 <= x < 9 else 2)] for x in range(18)
        }
        control = plan(
            control_surfaces,
            dict(cells=ground + upper, edges=control_edges),
            region_id=1,
            origins=[ground[0]],
            taken=set(),
            quantity=100,
            reserve=0,
            seed="small-zone-upper-native-bridge",
        )
        self.assertGreater(len(control), 0)
        self.assertLess(len(control), 100)
        self.assertTrue(all(4 <= row["x"] < 9 and row["z"] == 9 for row in control))
        for row in control:
            self.assertTrue(any(point[0] < 4 for point in row["path"]))
        disconnected = plan(
            control_surfaces,
            dict(cells=ground + upper, edges=control_edges[:-2]),
            region_id=1,
            origins=[ground[0]],
            taken=set(),
            quantity=100,
            reserve=0,
            seed="no-upper-access",
        )
        self.assertEqual(disconnected, ())

    def test_native_zone_spread_preserves_access_and_caps_disconnected_sparse_capacity(
        self,
    ):
        from wakfu_server.planting_cells import cells
        from wakfu_server.combat_terrain import map_geometry

        surfaces = cells(546)
        geometry = map_geometry(546)
        floor = {tuple(p) for p in geometry["cells"]}
        edges = {(tuple(a), tuple(b)) for a, b in geometry["edges"]}
        neighbors = defaultdict(set)
        for a, b in edges:
            if a in floor and b in floor and (b, a) in edges:
                neighbors[a].add(b)
        remaining, components = set(floor), []
        while remaining:
            root = min(remaining)
            reached, queue = {root}, deque([root])
            while queue:
                for neighbor in neighbors[queue.popleft()]:
                    if neighbor not in reached:
                        reached.add(neighbor)
                        queue.append(neighbor)
            remaining.difference_update(reached)
            components.append(reached)
        original = {
            (x, y, row["z"]) for (x, y), rows in surfaces.items() for row in rows
        }
        connected = max(components, key=lambda component: len(component & original))
        source_region = {
            (x, y, row["z"])
            for (x, y), candidates in surfaces.items()
            for row in candidates
            if row["region_id"] == 62201
        }
        origin = min(connected & source_region)
        kwargs = dict(
            region_id=62201,
            origins=[origin],
            taken=set(),
            quantity=200,
            seed="native-map546-map-spread",
            reserve=0,
        )
        rows = plan(surfaces, geometry, **kwargs)
        self.assertEqual(len(rows), 200)
        self.assertEqual(rows, plan(surfaces, geometry, **kwargs))
        self.assertNotEqual(
            rows, plan(surfaces, geometry, **dict(kwargs, seed="another-event"))
        )
        positions = {(row["x"], row["y"], row["z"]) for row in rows}
        xy = {point[:2] for point in positions}
        self.assertEqual(len(xy), 200)
        self.assertTrue(positions <= original & connected)
        self.assertEqual(
            {r["region_id"] for candidates in surfaces.values() for r in candidates},
            {62201},
        )

        for row in rows:
            point = (row["x"], row["y"], row["z"])
            route = tuple(map(tuple, row["path"]))
            approach = tuple(row["approach"])
            self.assertEqual(route[0], origin)
            self.assertEqual(route[-1], approach)
            self.assertTrue(all(p[:2] not in xy for p in route))
            for a, b in zip(route, route[1:]):
                self.assertIn((a, b), edges)
                self.assertIn((b, a), edges)
            self.assertIn((approach, point), edges)
            self.assertIn((point, approach), edges)
        for a in positions:
            for b in positions:
                if a != b:
                    self.assertGreaterEqual(abs(a[0] - b[0]) + abs(a[1] - b[1]), 3)
        # Independent extent check catches sorted-prefix or near-player clustering.
        available = original & connected
        for axis in (0, 1):
            extent = max(p[axis] for p in available) - min(p[axis] for p in available)
            selected_extent = max(p[axis] for p in positions) - min(
                p[axis] for p in positions
            )
            self.assertGreaterEqual(selected_extent, extent * 0.7)

        # Declared synthetic control: upper floor is disconnected, an occupied
        # bridge blocks its far component, and sparse capacity must not fill gaps.
        ground = [(x, 0, 0) for x in range(18)]
        upper = [(x, 0, 9) for x in range(18)]
        control_edges = []
        for level in (ground, upper):
            for a, b in zip(level, level[1:]):
                control_edges.extend(((a, b), (b, a)))
        control_surfaces = {
            (x, 0): [dict(z=z, region_id=1 if x < 9 else 2) for z in (0, 9)]
            for x in range(18)
        }
        control = plan(
            control_surfaces,
            dict(cells=ground + upper, edges=control_edges),
            region_id=1,
            origins=[ground[0]],
            taken={(9, 0)},
            quantity=200,
            reserve=0,
            seed="sparse-native-contract",
        )
        self.assertGreater(len(control), 0)
        self.assertTrue(
            all(row["x"] < 9 for row in control),
            "Sparse mission capacity must not spill into the other region",
        )
        self.assertLess(len(control), 200)
        self.assertTrue(all(row["z"] == 0 and row["x"] < 9 for row in control))
        linked = plan(
            {(x, 0): [dict(z=9, region_id=1)] for x in range(18)},
            dict(
                cells=ground + upper,
                edges=control_edges + [(ground[0], upper[0]), (upper[0], ground[0])],
            ),
            region_id=1,
            origins=[ground[0]],
            taken={(9, 0)},
            quantity=200,
            reserve=0,
            seed="upper-floor-now-reachable",
        )
        self.assertTrue(
            any(row["z"] == 9 for row in linked),
            "Reachable upper floors must remain eligible",
        )

        self.assertEqual(
            plan(
                control_surfaces,
                dict(cells=ground + upper, edges=control_edges),
                region_id=1,
                origins=[(99, 99, 0)],
                taken=set(),
                quantity=200,
                reserve=0,
                seed="absent-origin",
            ),
            (),
        )

        # Real storage/presence/population boundary. The second reported region
        # is an explicit caller-context fixture, not a paid movement/native-zone
        # attestation: map327's source export has only56601 plus unset surfaces.
        from test_environmental_owned_resource_population import (
            EnvironmentalOwnedResourcePopulationTests,
        )
        from wakfu_server.objectives import environmental_storage as storage

        fixture = EnvironmentalOwnedResourcePopulationTests(
            "test_original_population_real_profession_zero_occupation_and_atomic_cleanup"
        )
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        fixture.profile()
        first = fixture.refresh()
        event = first["instances"][0]["instance_id"]
        with fixture.store.connection() as db:
            markers = db.execute(
                "SELECT m.source_key FROM environmental_event_memberships m JOIN environmental_owned_resources o ON o.instance_id=m.instance_id AND o.resource_uid=m.entity_id WHERE m.instance_id=%s",
                (event,),
            ).fetchall()
            self.assertTrue(markers)
            self.assertTrue(
                all(
                    row["source_key"].endswith(
                        ":wakemu.environmental-resource-reachable-zone-spread.v4"
                    )
                    for row in markers
                )
            )
            db.execute(
                "INSERT INTO environmental_runtime_profiles (profile_key,version,family,mode,map_id,region_id,duration_ms,anchor_ms,level_min,level_max,authority,source_sha256,catalog_revision) VALUES('other-reported-region',1,'resource_collect','solo',327,56602,900000,%s,1,245,'test-only reported-region boundary',%s,%s)",
                (fixture.now_ms - 1000, "0" * 64, "1" * 64),
            )
            db.execute(
                "INSERT INTO environmental_profile_objectives VALUES('other-reported-region',1,'collect','resource_collect',60,100,3,'interaction',1)"
            )
            db.execute(
                "INSERT INTO environmental_profile_rewards VALUES('other-reported-region',1,0,'xp',NULL,1,'test-only')"
            )
            db.execute(
                "UPDATE environmental_runtime_profiles SET sealed=true,enabled=true WHERE profile_key='other-reported-region'"
            )
            location = dict(fixture.location, region_id=56602)
            before_location = dict(location)
            crossed = storage.refresh(
                db,
                account_id=fixture.account,
                character_id=fixture.character["id"],
                location=location,
                now_ms=fixture.now_ms + 1,
            )
            self.assertEqual(location, before_location)
            self.assertEqual(len(crossed["instances"]), 1)
            self.assertNotEqual(crossed["instances"][0]["instance_id"], event)
            self.assertEqual(crossed["instances"][0]["region_id"], 56602)
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM environmental_event_instances"
                ).fetchone()["n"],
                2,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM environmental_event_instances WHERE profile_key='other-reported-region'"
                ).fetchone()["n"],
                1,
            )

        # Protocol-only caller contexts: another region selects its own event.
        # Repeated same-region publication stays quiet, while a genuinely new
        # instance of the same challenge still initializes its context.
        from types import SimpleNamespace
        from unittest.mock import Mock, patch
        from wakfu_server.objectives import environmental_service as service
        from wakfu_server.objectives.environmental_world import (
            SelectedEnvironmentalEvents,
        )

        view = dict(
            instance_id=event,
            native_scenario_id=-1320,
            protector_id=1,
            started_at_ms=1000,
            deadline_ms=900000,
            now_ms=2000,
            challenge_value=1,
            available=True,
            xp_rate_bp=100000,
            variables=[dict(variable_index=0, value=1)],
            native_publication=dict(
                challenge_id=-1320,
                secondary_id=1,
                protector_id=1,
                state_ordinal=1,
                variable_names=["collected"],
            ),
        )
        snapshot = dict(instances=[view], deliveries=[])
        publication_store = SimpleNamespace(
            current_character_session=Mock(return_value=True)
        )
        publication_world = SimpleNamespace(
            scope_presence=Mock(return_value=1), send_batch_to=Mock(return_value=True)
        )
        cursor = SelectedEnvironmentalEvents()
        with patch.object(service, "refresh", return_value=snapshot), patch.object(
            service, "acknowledge"
        ):
            self.assertTrue(
                cursor.refresh(
                    publication_store,
                    publication_world,
                    1,
                    "same-lease",
                    2,
                    location=fixture.location,
                    ready=True,
                    checkpoint=lambda: None,
                )
            )
            first_packets = publication_world.send_batch_to.call_args.args[-1]
            self.assertEqual([op for op, _ in first_packets].count(12549), 1)
            publication_world.send_batch_to.reset_mock()
            other_view = dict(
                view,
                instance_id=event + 1000,
                native_scenario_id=-1321,
                native_publication=dict(view["native_publication"], challenge_id=-1321),
            )
            snapshot["instances"] = [other_view]
            cursor.refresh(
                publication_store,
                publication_world,
                1,
                "same-lease",
                2,
                location=location,
                ready=True,
                checkpoint=lambda: None,
            )
            replacement = publication_world.send_batch_to.call_args.args[-1]
            self.assertEqual([op for op, _ in replacement].count(12549), 1)
            publication_world.send_batch_to.reset_mock()
            cursor.refresh(
                publication_store,
                publication_world,
                1,
                "same-lease",
                2,
                location=location,
                ready=True,
                checkpoint=lambda: None,
            )
            publication_world.send_batch_to.assert_not_called()
            snapshot["instances"] = [dict(other_view, instance_id=event + 1001)]
            self.assertTrue(
                cursor.refresh(
                    publication_store,
                    publication_world,
                    1,
                    "same-lease",
                    2,
                    location=location,
                    ready=True,
                    checkpoint=lambda: None,
                )
            )
            new_packets = publication_world.send_batch_to.call_args.args[-1]
            self.assertEqual([op for op, _ in new_packets].count(12549), 1)
            self.assertNotIn(12276, [op for op, _ in new_packets])
