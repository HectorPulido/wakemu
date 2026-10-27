"""Exact advisory reuse; real SDK/World paths with small sealed native inputs."""
from copy import deepcopy
import gc
import json
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import weakref

from wakfu_ai.bridge.jondo_los import casting_visible
from wakfu_ai.bridge.jondo_los_cache import AdvisoryLosCache, cache_for_oracle
from wakfu_server import native_catalog, prepared_los, combat_native_los_ray as ray
from wakfu_server import combat_input_observation as observation
from wakfu_server.combat_los_geometry import prepare_los_geometry
from wakfu_server.combat_obstacle_condition import footprint


REVISION = "a" * 64


@unittest.skipUnless(
    hasattr(ray, "sealed_generation"), "Requires staged native static seal"
)
class AdvisoryLosCacheTests(unittest.TestCase):
    def setUp(self):
        ray.topology_columns.cache_clear()
        ray.ray_program.cache_clear()
        ray.static_ray.cache_clear()
        self.program = dict(
            schema="native-Sf-bfZ-int-v1",
            instructions=[
                ["aload", 0],
                ["constant", 2147483647],
                ["putfield", "bnU"],
                ["aload", 0],
                ["constant", 0],
                ["constant", 0],
                ["constant", 0],
                ["invokevirtual", "m"],
                ["aload", 0],
                ["constant", 1],
                ["constant", 0],
                ["constant", 0],
                ["invokevirtual", "m"],
                ["aload", 0],
                ["invokevirtual", "bfX"],
                ["ireturn"],
            ],
        )

        def read(name):
            if name == "native-los-ray-program.json":
                return json.dumps(self.program).encode()
            map_id = int(name.rsplit("/", 1)[1].split(".")[0])
            return json.dumps(
                dict(
                    schema="native-Sf-Vz-columns-v1",
                    map_id=map_id,
                    columns=[
                        [x, y, [[0, 0, True]]]
                        for x in range(-1, 7)
                        for y in range(-1, 3)
                    ],
                )
            ).encode()

        for patched in (
            patch.object(native_catalog, "read_published_bytes", side_effect=read),
            patch.object(native_catalog, "release", return_value=REVISION),
            patch.object(native_catalog, "_exists", return_value=True),
            patch.object(prepared_los, "published_columns", return_value=None),
        ):
            patched.start()
            self.addCleanup(patched.stop)

        def actor(identity, position):
            return SimpleNamespace(
                id=identity,
                hp=100,
                ap=6,
                position=position,
                physical_radius=0,
                native_los_height=6,
                native_obstacle_id=identity - 1,
            )

        self.fight = SimpleNamespace(
            actors={
                1: actor(1, (0, 0, 0)),
                2: actor(2, (3, 0, 0)),
                3: actor(3, (2, 1, 0)),
            },
            walkable={
                (x, y, z) for x in range(-1, 7) for y in range(-1, 3) for z in (0, 1)
            },
            native_qi_visibility_ignored_slots=[],
            native_los_ignored_affiliations=frozenset(),
        )
        self.cache = AdvisoryLosCache(catalog_revision=REVISION)

    def read(self, *, cache=True, map_id=17, target=None, prepared=True):
        fight = self.fight
        token = prepare_los_geometry(map_id, fight.walkable) if prepared else object()
        bodies = {
            actor.id: footprint(actor.position, actor.physical_radius)
            for actor in fight.actors.values()
            if actor.hp > 0
        }
        return casting_visible(
            map_id,
            fight.actors[1].position,
            fight.actors[2].position if target is None else target,
            fight,
            blocking_footprints=bodies,
            prepared_geometry=token,
            advisory_cache=self.cache if cache else None,
        )

    def test_positive_hp_ap_changes_reuse_exact_fact_with_fresh_prepared_terrain(self):
        self.assertTrue(self.read())
        first = self.cache.metrics()
        self.fight.actors[2].hp -= 1
        self.fight.actors[1].ap -= 2
        self.assertTrue(self.read())
        self.assertEqual(self.cache.metrics()["hits"], first["hits"] + 1)
        self.assertEqual(self.cache.metrics()["misses"], first["misses"])
        self.assertEqual(self.read(), self.read(cache=False))

    def test_movement_radius_and_world_slot_exclusions_are_fresh(self):
        self.assertTrue(self.read())
        self.fight.actors[3].position = (1, 0, 0)
        self.assertFalse(self.read())
        self.assertFalse(self.read())  # Measured false is a reusable Boolean.
        self.fight.native_los_ignored_affiliations = frozenset({2})
        self.assertTrue(self.read())
        self.fight.native_los_ignored_affiliations = frozenset()
        self.fight.actors[3].position = (1, 1, 0)
        self.fight.actors[3].physical_radius = 1
        self.assertFalse(self.read())
        self.assertEqual(self.read(), self.read(cache=False))

    def test_cast_ignored_slots_and_qk_byte_change_invalidate(self):
        self.fight.actors[3].position = (1, 0, 0)
        self.assertFalse(self.read())
        self.fight.native_qi_visibility_ignored_slots = [2]
        self.assertTrue(self.read())
        misses = self.cache.metrics()["misses"]
        self.fight.actors[3].native_obstacle_id = 4
        self.assertFalse(self.read())
        self.assertEqual(self.cache.metrics()["misses"], misses + 1)

    def test_roster_death_resurrection_floor_and_heights_invalidate(self):
        self.assertTrue(self.read())
        for actor, field, value in (
            (3, "hp", 0),
            (3, "hp", 100),
            (1, "native_los_height", 12),
            (2, "position", (3, 0, 1)),
        ):
            before = self.cache.metrics()["misses"] + self.cache.metrics()["hits"]
            setattr(self.fight.actors[actor], field, value)
            self.assertEqual(self.read(), self.read(cache=False))
            # Returning to an EXACT previously observed semantic roster may
            # reuse that earlier fact; a dead roster cannot reuse a live key.
            self.assertEqual(
                self.cache.metrics()["misses"] + self.cache.metrics()["hits"],
                before + 1,
            )

    def test_target_body_side_uses_fresh_height_and_ambiguity_rejects_before_lookup(
        self,
    ):
        self.fight.actors[2].physical_radius = 1
        before = deepcopy(vars(self.fight.actors[2]))
        self.assertTrue(self.read(target=(4, 0, 0)))
        self.assertEqual(vars(self.fight.actors[2]), before)
        misses = self.cache.metrics()["misses"]
        self.fight.actors[2].native_los_height = 15
        self.assertTrue(self.read(target=(4, 0, 0)))
        self.assertEqual(self.cache.metrics()["misses"], misses + 1)
        self.fight.actors[3].position = (4, 0, 0)
        with self.assertRaisesRegex(ValueError, "unambiguous target body"):
            self.read(target=(4, 0, 0))

    def test_terrain_change_map_and_static_program_generation_never_reuse_stale_fact(
        self,
    ):
        self.assertTrue(self.read())
        self.fight.walkable.remove((1, 0, 0))
        self.fight.walkable.remove((1, 0, 1))
        self.assertFalse(self.read())
        misses = self.cache.metrics()["misses"]
        self.assertFalse(self.read(map_id=18))
        self.assertEqual(self.cache.metrics()["misses"], misses + 1)
        self.program["instructions"] = [["constant", 0], ["ireturn"]]
        ray.ray_program.cache_clear()
        ray.static_ray.cache_clear()
        self.assertFalse(self.read())
        self.assertEqual(self.cache.metrics()["misses"], misses + 2)

    def test_mutable_unknown_static_proof_and_unknown_terrain_bypass(self):
        self.assertTrue(self.read())
        actual = ray.topology_columns(17)
        with patch.object(ray, "topology_columns", return_value=dict(actual)):
            before = self.cache.metrics()["bypasses"]
            self.assertTrue(self.read())
            self.assertEqual(self.cache.metrics()["bypasses"], before + 1)
        before = self.cache.metrics()["bypasses"]
        self.assertTrue(self.read(prepared=False))
        self.assertEqual(self.cache.metrics()["bypasses"], before + 1)

    def test_capture_and_replay_bypass_with_equivalent_catalog_evidence(self):
        self.assertTrue(self.read())
        before = self.cache.metrics()["hits"]
        with observation.observe_combat_inputs() as cached_capture:
            self.assertTrue(self.read())
        with observation.observe_combat_inputs() as ordinary_capture:
            self.assertTrue(self.read(cache=False))
        self.assertEqual(cached_capture.snapshot(), ordinary_capture.snapshot())
        token = observation._replaying.set(object())
        try:
            self.assertTrue(self.read())
        finally:
            observation._replaying.reset(token)
        self.assertEqual(self.cache.metrics()["hits"], before)

    def test_native_errors_are_not_cached_as_false(self):
        self.fight.actors[1].native_los_height = None
        for _ in range(2):
            with self.assertRaises(ValueError):
                self.read()
        self.assertEqual(self.cache.metrics()["rays"], 0)
        self.assertEqual(self.cache.metrics()["misses"], 2)

    def test_session_miss_keeps_world_validation_and_every_hit_checks_live_terrain(
        self,
    ):
        from wakfu_server import combat_los_geometry

        session = self.cache.snapshot_session()
        prepared = prepare_los_geometry(17, self.fight.walkable)
        bodies = {
            a.id: footprint(a.position, a.physical_radius)
            for a in self.fight.actors.values()
        }

        def query(target):
            return casting_visible(
                17,
                (0, 0, 0),
                target,
                self.fight,
                blocking_footprints=bodies,
                prepared_geometry=prepared,
                advisory_cache=session,
            )

        with patch.object(
            combat_los_geometry,
            "prepared_permitted_xy",
            wraps=combat_los_geometry.prepared_permitted_xy,
        ) as checked:
            self.assertTrue(query((3, 0, 0)))
            before = checked.call_count
            self.assertTrue(
                query((4, 0, 0))
            )  # MISS: unchanged World reader validates it.
            self.assertEqual(checked.call_count, before + 1)
            before = checked.call_count
            self.assertTrue(
                query((3, 0, 0))
            )  # Pending HIT: still one fresh proof check.
            self.assertEqual(checked.call_count, before + 1)
        self.assertEqual(self.cache.metrics()["rays"], 0)
        session.publish()
        self.assertEqual(self.cache.metrics()["rays"], 2)
        session = self.cache.snapshot_session()
        self.assertTrue(query((3, 0, 0)))
        self.fight.walkable.remove((1, 0, 0))
        self.fight.walkable.remove((1, 0, 1))
        self.assertFalse(
            query((3, 0, 0))
        )  # Cached key alone cannot grant a stale clear.
        session.publish()
        self.fight.walkable.update({(1, 0, 0), (1, 0, 1)})
        self.assertTrue(self.read())  # Failed HIT did not overwrite the old true fact.

    def test_private_weak_owner_turn_scope_and_ray_context_memory_bounds(self):
        class Owner:
            pass

        owner = Owner()
        source = dict(
            fightInstanceId="private",
            fightId=1,
            actorId=1,
            turnId=1,
            catalogRevision=REVISION,
        )
        first = cache_for_oracle(owner, source)
        self.assertIs(first, cache_for_oracle(owner, source))
        changed = dict(source, turnId=2)
        self.assertIsNot(first, cache_for_oracle(owner, changed))
        owner_ref = weakref.ref(owner)
        del owner
        gc.collect()
        self.assertIsNone(owner_ref())
        self.cache = AdvisoryLosCache(
            catalog_revision=REVISION, max_rays=3, max_contexts=2, max_units=100
        )
        for x in (2, 3, 4, 5):
            self.fight.actors[3].position = (x, 1, 0)
            self.read()
        self.assertLessEqual(self.cache.metrics()["contexts"], 2)
        self.assertLessEqual(self.cache.metrics()["rays"], 3)
        self.assertLessEqual(self.cache.metrics()["units"], 100)
        for target in ((3, 0, 0), (4, 0, 0), (5, 0, 0), (6, 0, 0)):
            self.read(target=target)
        self.assertEqual(self.cache.metrics()["rays"], 3)
        self.assertLessEqual(self.cache.metrics()["contexts"], 2)

    def test_real_snapshot_cache_hits_still_reject_a_changed_native_source(self):
        import test_jondo_bridge as bridge_tests
        from wakfu_ai.bridge.jondo_snapshot import build_snapshot

        class Owner:
            pass

        original, _, _ = bridge_tests.JondoSnapshotLosTests().fixture()
        owner = Owner()
        owner.__dict__.update(vars(original))
        owner.state_identity = lambda runtime: owner.identity
        mutation = [False]
        source = dict(
            fightInstanceId="private-snapshot",
            fightId=7,
            actorId=1,
            turnId=1,
            catalogRevision=REVISION,
            nativeIdentity="source",
        )

        def baseline(oracle):
            if mutation[0]:
                oracle.identity = "changed-after-baseline"
            return dict(source)

        with patch(
            "wakfu_ai.bridge.jondo_snapshot.source", side_effect=baseline
        ), patch(
            "wakfu_ai.bridge.jondo_snapshot.effective_affiliation",
            side_effect=lambda f, a: a.team,
        ), patch(
            "wakfu_server.combat_tackle_movement.movement_tackle_cost",
            return_value=(0, 0),
        ):
            first = build_snapshot(owner)
            self.assertTrue(first["board"]["lineOfSight"])
            cache = cache_for_oracle(owner, source)
            mutation[0] = True
            with self.assertRaisesRegex(ValueError, "Native source changed"):
                build_snapshot(owner)
            self.assertGreater(cache.metrics()["hits"], 0)
            cold = Owner()
            cold.__dict__.update(vars(original))
            cold.state_identity = lambda runtime: cold.identity
            with self.assertRaisesRegex(ValueError, "Native source changed"):
                build_snapshot(cold)
            self.assertEqual(cache_for_oracle(cold, source).metrics()["rays"], 0)


if __name__ == "__main__":
    unittest.main()
