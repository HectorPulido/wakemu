"""Production ecology producers fence whole-group homes before World delivery."""
import unittest
from contextlib import ExitStack
from unittest.mock import MagicMock, patch

from wakfu_server import ecology_mobs, monster_birth_home, monster_life_plans
from wakfu_server import monster_maturation, monster_reproduction, monster_wander
from wakfu_server.planting_context import region


class BirthHomeProducerTests(unittest.TestCase):
    @staticmethod
    def fixture_member(
        reference, level, identity, *, map_id, x, y, z, team=1, instance_id=0
    ):
        return dict(
            id=identity,
            ref=reference,
            breed=reference,
            level=level,
            map_id=map_id,
            instance_id=instance_id,
            x=x,
            y=y,
            z=z,
            team=team,
            hp=100,
            max_hp=100,
        )

    def prepare(self, *, reproduction=False, inside_edge=True, native=False):
        scope, home, group_id = (546, 0), 62201, 9201
        factory = self.fixture_member
        if native:
            from wakfu_server.monsters import owned_instance

            factory = owned_instance
        member = factory(41, 10, -9201, map_id=scope[0], x=-44, y=16, z=0)
        groups = [dict(group_id=group_id, status="available", members=[member])]
        store = MagicMock()
        db = store.connection.return_value.__enter__.return_value
        db.execute.side_effect = (
            lambda sql, *_: groups if "FROM combat_groups" in sql else []
        )
        edges = [((-44, 16, 0), (-43, 16, 0))]
        if inside_edge:
            edges.append(((-44, 16, 0), (-44, 17, 0)))
        configuration = dict(
            interval_ms=60000,
            birth_probability=1.0,
            birth_stage_decay=0.5,
            new_group_probability=1.0,
            max_members=8,
            max_zone_members=5000,
            max_zone_groups=1000,
        )
        decision = dict(
            cycle=1,
            draw=0,
            group_draw=0,
            destination_draw=0,
            variant_seed="0" * 64,
            attempts=0,
        )
        ticket = dict(
            map_id=scope[0],
            instance_id=0,
            group_id=group_id,
            monster_id=-9201,
            reference=41,
            cycle=1,
            decision=decision,
            plan_policy=configuration,
        )
        snapshot = dict(
            world_epoch="home",
            players=[dict(id=40, map_id=scope[0], instance_id=0, x=-44, y=19, z=0)],
            excluded_ids=[],
            locations=[list(scope)],
            now_ms=1000,
            allow_wander=True,
        )
        with ExitStack() as patches:
            # This scope-policy fixture deliberately avoids publication/compiler
            # dependencies. Native snapshot qualification runs separately using
            # the final sealed image and its matching published generation.
            if not native:
                patches.enter_context(
                    patch(
                        "wakfu_server.monsters.owned_instance",
                        side_effect=self.fixture_member,
                    )
                )
                patches.enter_context(
                    patch(
                        "wakfu_server.combat_monster_world.spawn_group",
                        return_value=b"native-fixture",
                    )
                )
                patches.enter_context(
                    patch(
                        "wakfu_server.monster_idle_distribution.native_physical_radius",
                        return_value=0,
                    )
                )
                patches.enter_context(
                    patch(
                        "wakfu_server.monster_family_stages.initial_candidates",
                        return_value=[
                            dict(
                                reference=2, min_level=4, boss_classification="regular"
                            )
                        ],
                    )
                )
            for domain in (monster_maturation, monster_reproduction):
                patches.enter_context(
                    patch.object(domain, "policy", return_value=configuration)
                )
                patches.enter_context(patch.object(domain, "observe"))
                patches.enter_context(
                    patch.object(
                        domain,
                        "pending",
                        return_value=[ticket]
                        if domain is monster_reproduction and reproduction
                        else [],
                    )
                )
                patches.enter_context(
                    patch.object(domain, "unpublished", return_value=[])
                )
            patches.enter_context(
                patch.object(
                    monster_reproduction, "dungeon_population", return_value=False
                )
            )
            patches.enter_context(
                patch.object(
                    monster_reproduction,
                    "allocate_identity",
                    return_value=(1125900015900000, -1125900015900000),
                )
            )
            patches.enter_context(
                patch.object(
                    monster_life_plans,
                    "attach",
                    side_effect=lambda _s, _sc, _k, t, _p: t,
                )
            )
            patches.enter_context(
                patch.object(
                    monster_life_plans,
                    "choose_destination",
                    side_effect=lambda candidates, _decision: candidates[0],
                )
            )
            patches.enter_context(
                patch.object(
                    monster_life_plans, "resolve_noops", side_effect=lambda _s, p: p
                )
            )
            patches.enter_context(
                patch(
                    "wakfu_server.monster_population_cleanup.prepare", return_value=[]
                )
            )
            patches.enter_context(
                patch(
                    "wakfu_server.monster_idle_distribution_store.prepare",
                    return_value=[],
                )
            )
            patches.enter_context(
                patch.object(
                    monster_wander,
                    "policy",
                    return_value=dict(
                        move_probability=1.0, radius=20, min_steps=1, max_steps=1
                    ),
                )
            )
            patches.enter_context(
                patch.object(
                    monster_birth_home, "ensure_homes", return_value={group_id: home}
                )
            )
            patches.enter_context(
                patch.object(
                    monster_birth_home,
                    "region_for_point",
                    side_effect=lambda _map, cell: home if cell[0] <= -44 else 62202,
                )
            )
            patches.enter_context(
                patch.object(
                    ecology_mobs,
                    "_edges",
                    return_value=monster_wander.edge_index(edges),
                )
            )
            patches.enter_context(
                patch.object(
                    ecology_mobs, "habitat_destination_allowed", return_value=True
                )
            )
            patches.enter_context(
                patch.object(ecology_mobs.random, "random", return_value=0.99)
            )
            patches.enter_context(
                patch.object(ecology_mobs.time, "monotonic", return_value=0)
            )
            proposals = ecology_mobs.prepare(
                store, snapshot, limit=2 if reproduction else 1
            )
        return proposals, member

    def test_roaming_foreign_family_keeps_birth_home_without_native_family_gate(self):
        family = monster_maturation.STAGES[41][0]["family_id"]
        self.assertNotIn(
            family, {row["family_id"] for row in region(546, 62201)["monster_families"]}
        )
        proposals, member = self.prepare()
        moves = [
            move for p in proposals if p["kind"] == "wander_bulk" for move in p["moves"]
        ]
        self.assertEqual(len(moves), 1)
        self.assertEqual(
            monster_wander.point(moves[0]["moved_members"][0]), (-44, 17, 0)
        )
        self.assertEqual(moves[0]["expected_members"], [member])

    def test_reproduction_candidate_and_new_child_stay_within_parent_birth_home(self):
        for inside_edge in (True, False):
            with self.subTest(inside_edge=inside_edge):
                proposals, _ = self.prepare(reproduction=True, inside_edge=inside_edge)
                births = [
                    op
                    for p in proposals
                    if p["kind"] == "lifecycle_bulk"
                    for op in p["operations"]
                    if op["kind"] == "reproduction"
                ]
                if not inside_edge:
                    self.assertEqual(births, [])
                    continue
                self.assertEqual(len(births), 1)
                self.assertEqual(births[0]["destination"], [-44, 17, 0])
                self.assertEqual(monster_wander.point(births[0]["child"]), (-44, 17, 0))
