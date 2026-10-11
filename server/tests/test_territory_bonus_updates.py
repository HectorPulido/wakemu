import copy
from contextlib import contextmanager
import threading
import time
import unittest
from unittest.mock import patch

from wakfu_server import territory_bonus_updates as updates


class Store:
    def __init__(self, revisions=(5,), world=None):
        self.revisions = iter(revisions)
        self.last = 5
        self.world = world
        self.queries = []

    @contextmanager
    def connection(self):
        if self.world is not None:
            assert not self.world.lock._is_owned(), "SQL under world lock"
        yield self

    def execute(self, query, scope):
        self.queries.append(scope)
        self.last = next(self.revisions, self.last)
        return self

    def fetchone(self):
        return {"revision": self.last}


class World:
    def __init__(self, character, peer):
        self.lock = threading.RLock()
        self.players = {character["id"]: ("lease", peer, copy.deepcopy(character))}

    def update_territory_projection(self, generation, character, *, peer, bonuses):
        with self.lock:
            entry = self.players.get(character["id"])
            if (
                entry is None
                or entry[0] != generation
                or entry[1] is not peer
                or any(
                    entry[2].get(key) != character.get(key)
                    for key in ("map_id", "instance_id", "x", "y", "z")
                )
            ):
                return False
            entry[2]["territory_stat_bonuses"] = dict(bonuses)
            entry[2]["_published_territory_stat_bonuses"] = dict(bonuses)
        return True


class RegionalBonusUpdatesTests(unittest.TestCase):
    def setUp(self):
        self.peer = object()
        self.character = dict(
            id=10,
            map_id=327,
            instance_id=2,
            x=1,
            y=2,
            z=0,
            hp=420,
            active_build_index=2,
            direction=6,
        )
        self.world = World(self.character, self.peer)
        self.store = Store(world=self.world)
        self.now = 10
        self.manager = updates.RegionalBonusUpdates(
            self.store, self.world, clock=lambda: self.now
        )
        self.locate = patch.object(
            updates.territory_cells, "region_at", return_value=56601
        )
        self.locate.start()
        self.addCleanup(self.locate.stop)
        self.codec = patch.object(
            updates.territory_bonuses, "world_packet", side_effect=self.packet
        )
        self.codec.start()
        self.addCleanup(self.codec.stop)

    def packet(self, character):
        self.assertFalse(self.world.lock._is_owned())
        return (
            13046,
            repr(
                (
                    character["hp"],
                    character["active_build_index"],
                    character["direction"],
                    sorted(character["territory_stat_bonuses"].items()),
                )
            ).encode(),
        )

    def proposal(self, *, revision=5, bonuses=None, epoch="epoch", observed=None):
        return dict(
            domain="bonuses",
            operation="regional_snapshot",
            world_epoch=epoch,
            map_id=327,
            instance_id=2,
            revision=revision,
            regions={"56601": {"33": 30, "36": 30} if bonuses is None else bonuses},
            observed_at=time.time() if observed is None else observed,
            observation_bucket=int(time.time() // 2),
        )

    def apply(self, **kwargs):
        result = self.manager.apply(self.proposal(**kwargs), world_epoch="epoch")
        self.assertEqual(result["status"], "applied")

    def test_stationary_updates_publish_once_and_only_ack_after_successful_send(self):
        self.apply()
        untouched = copy.deepcopy(self.character)
        packets = self.manager.packets_for(self.character, "lease", self.peer)
        self.assertEqual([opcode for opcode, _ in packets], [13046])
        self.assertEqual(self.character, untouched)
        # A failed send leaves the same pending update available for retry.
        self.assertEqual(
            self.manager.packets_for(self.character, "lease", self.peer), packets
        )
        self.assertTrue(
            self.manager.acknowledge(self.character, "lease", self.peer, packets)
        )
        self.assertEqual(
            self.manager.packets_for(self.character, "lease", self.peer), []
        )
        self.assertEqual(self.character["hp"], 420)
        self.assertEqual(self.character["active_build_index"], 2)
        self.assertEqual(
            self.world.players[10][2]["_published_territory_stat_bonuses"],
            {33: 30, 36: 30},
        )

    def test_removal_publishes_empty_derived_bonus(self):
        self.character["_published_territory_stat_bonuses"] = {33: 60, 36: 60}
        self.apply(bonuses={})
        packets = self.manager.packets_for(self.character, "lease", self.peer)
        self.assertTrue(
            self.manager.acknowledge(self.character, "lease", self.peer, packets)
        )
        self.assertEqual(self.character["territory_stat_bonuses"], {})

    def test_changed_dirty_revision_and_epoch_are_rejected(self):
        self.assertEqual(
            self.manager.apply(self.proposal(revision=4), world_epoch="epoch"),
            {"status": "stale"},
        )
        self.assertEqual(
            self.manager.apply(self.proposal(epoch="old"), world_epoch="epoch"),
            {"status": "stale"},
        )
        self.assertEqual(self.manager.snapshots, {})

    def test_other_instance_region_peer_and_generation_cannot_consume(self):
        self.apply()
        self.assertEqual(
            self.manager.packets_for(self.character, "old-lease", self.peer), []
        )
        self.assertEqual(
            self.manager.packets_for(self.character, "lease", object()), []
        )
        other = dict(self.character, instance_id=3)
        self.assertEqual(self.manager.packets_for(other, "lease", self.peer), [])
        with patch.object(updates.territory_cells, "region_at", return_value=56602):
            self.character["_published_territory_stat_bonuses"] = {}
            self.assertEqual(
                self.manager.packets_for(self.character, "lease", self.peer), []
            )

    def test_movement_or_replacement_before_ack_rejects_batch(self):
        self.apply()
        packets = self.manager.packets_for(self.character, "lease", self.peer)
        self.world.players[10][2]["x"] = 20
        self.assertFalse(
            self.manager.acknowledge(self.character, "lease", self.peer, packets)
        )
        self.assertNotIn("_published_territory_stat_bonuses", self.character)

    def test_current_owner_hp_build_and_direction_are_used_and_fenced(self):
        self.apply()
        self.character.update(hp=200, active_build_index=3, direction=4)
        packets = self.manager.packets_for(self.character, "lease", self.peer)
        self.assertIn(b"(200, 3, 4,", packets[0][1])
        self.character["hp"] = 210
        self.assertFalse(
            self.manager.acknowledge(self.character, "lease", self.peer, packets)
        )

    def test_fresh_context_supersedes_prepared_cache_and_pending_batch(self):
        self.apply()
        packets = self.manager.packets_for(self.character, "lease", self.peer)
        self.manager.mark_context_refreshed(self.character)
        self.assertEqual(
            self.manager.packets_for(self.character, "lease", self.peer), []
        )
        self.assertFalse(
            self.manager.acknowledge(self.character, "lease", self.peer, packets)
        )

    def test_new_cache_supersedes_pending_batch_and_expired_cache_is_not_sent(self):
        self.apply()
        packets = self.manager.packets_for(self.character, "lease", self.peer)
        self.apply(bonuses={"33": 60, "36": 60})
        self.assertFalse(
            self.manager.acknowledge(self.character, "lease", self.peer, packets)
        )
        self.now += 11
        self.assertEqual(
            self.manager.packets_for(self.character, "lease", self.peer), []
        )

    def test_sql_failure_never_installs_or_acknowledges_cache(self):
        with patch.object(
            self.store, "connection", side_effect=RuntimeError("SQL failed")
        ):
            with self.assertRaises(RuntimeError):
                self.manager.apply(self.proposal(), world_epoch="epoch")
        self.assertEqual(self.manager.snapshots, {})

    def test_prepare_reads_once_per_scope_not_per_player_and_rotates_budget(self):
        snapshot = dict(
            world_epoch="epoch",
            planning_tick=0,
            players=[
                self.character,
                dict(self.character, id=11),
                dict(self.character, id=12, instance_id=3),
            ],
        )
        population = {"complete": True, "regions": {}}
        with (
            patch.object(
                updates.ecology_population, "snapshot", return_value=population
            ) as read,
            patch.object(
                updates.territory_bonuses,
                "_catalog",
                return_value={"territories": {"56601": {"map_id": 327}}},
            ),
            patch.object(
                updates.territory_bonuses, "evaluate_population", return_value={}
            ),
            patch.object(
                updates.territory_bonuses, "stat_bonuses", return_value={33: 30}
            ),
        ):
            first = updates.prepare(self.store, snapshot, limit=1)
            second = updates.prepare(
                self.store, dict(snapshot, planning_tick=1), limit=1
            )
        self.assertEqual(read.call_count, 2)
        self.assertEqual((first[0]["instance_id"], second[0]["instance_id"]), (2, 3))
        self.assertEqual(first[0]["regions"], {"56601": {"33": 30}})
        self.assertIn("observed_at", first[0])
        self.assertIn("observation_bucket", first[0])

    def test_prepare_concurrent_revision_discards_partial_snapshot_and_incomplete_clears(
        self,
    ):
        snapshot = dict(world_epoch="epoch", players=[self.character])
        with (
            patch.object(
                updates.ecology_population,
                "snapshot",
                return_value={"complete": False, "regions": {}},
            ),
            patch.object(
                updates.territory_bonuses,
                "_catalog",
                return_value={"territories": {"56601": {"map_id": 327}}},
            ),
        ):
            self.assertEqual(updates.prepare(Store((5, 6)), snapshot), [])
            proposals = updates.prepare(Store(), snapshot)
        self.assertEqual(proposals[0]["regions"], {"56601": {}})

    def test_actual_world_projection_merges_only_derived_stats(self):
        from wakfu_server.world import World as ActualWorld

        def forbidden(*args):
            self.fail("A derived projection must not write sockets or serialize spawns")

        world = ActualWorld(forbidden, forbidden, forbidden)
        authoritative = dict(
            self.character,
            hp=200,
            active_build_index=4,
            builds={4: {"deck": b"current"}},
        )
        world.players[10] = ("lease", self.peer, authoritative)
        before = copy.deepcopy(authoritative)
        # The caller's unrelated fields can be stale; they must never overwrite
        # the registry's current health, selected build or inventory graph.
        self.assertTrue(
            world.update_territory_projection(
                "lease", self.character, peer=self.peer, bonuses={33: 60, 36: 60}
            )
        )
        current = world.players[10][2]
        self.assertEqual({key: current[key] for key in before}, before)
        self.assertEqual(current["territory_stat_bonuses"], {33: 60, 36: 60})
        self.assertEqual(current["_published_territory_stat_bonuses"], {33: 60, 36: 60})
        self.assertNotIn("territory_stat_bonuses", self.character)

    def test_actual_world_projection_rejects_replaced_lease_or_changed_location(self):
        from wakfu_server.world import World as ActualWorld

        world = ActualWorld(lambda value: b"", lambda value: b"", lambda *args: None)
        world.players[10] = ("lease", self.peer, copy.deepcopy(self.character))
        for generation, peer, character in (
            ("old", self.peer, self.character),
            ("lease", object(), self.character),
            ("lease", self.peer, dict(self.character, x=100)),
            ("lease", self.peer, dict(self.character, instance_id=100)),
            ("lease", self.peer, dict(self.character, map_id=100)),
        ):
            with self.subTest(generation=generation, character=character):
                self.assertFalse(
                    world.update_territory_projection(
                        generation, character, peer=peer, bonuses={33: 60}
                    )
                )
        self.assertNotIn("territory_stat_bonuses", world.players[10][2])

    def test_prepare_five_domain_cadence_does_not_alias_sixteen_scope_budget(self):
        players = [
            dict(self.character, id=index + 10, instance_id=index)
            for index in range(80)
        ]
        covered = set()
        with (
            patch.object(
                updates.ecology_population,
                "snapshot",
                return_value={"complete": True, "regions": {}},
            ),
            patch.object(
                updates.territory_bonuses, "_catalog", return_value={"territories": {}}
            ),
        ):
            for tick in range(0, 80, 5):
                proposals = updates.prepare(
                    self.store,
                    dict(world_epoch="epoch", planning_tick=tick, players=players),
                    limit=16,
                )
                covered.update(row["instance_id"] for row in proposals)
        self.assertEqual(covered, set(range(80)))

    def test_domain_planning_tick_rotates_all_scopes_even_with_one_remaining_slot(self):
        players = [
            dict(self.character, id=index + 10, instance_id=index)
            for index in range(80)
        ]
        covered = []
        with (
            patch.object(
                updates.ecology_population,
                "snapshot",
                return_value={"complete": True, "regions": {}},
            ) as read,
            patch.object(
                updates.territory_bonuses, "_catalog", return_value={"territories": {}}
            ),
        ):
            for invocation in range(80):
                proposals = updates.prepare(
                    self.store,
                    dict(
                        world_epoch="epoch",
                        planning_tick=invocation * 5,
                        domain_planning_tick=invocation,
                        players=players,
                    ),
                    limit=1,
                )
                self.assertEqual(len(proposals), 1)
                covered.append(proposals[0]["instance_id"])
        self.assertEqual(covered, list(range(80)))
        self.assertEqual(read.call_count, 80)


if __name__ == "__main__":
    unittest.main()
