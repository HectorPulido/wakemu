import random
import unittest
from unittest.mock import patch
from collections import Counter
from unittest.mock import patch

from wakfu_server import monster_maturation, monster_reproduction
from wakfu_server import monster_family_stages, planting_runtime, planting
from wakfu_server import monster_collect, monsters


class EcologyBalanceStatisticalGate(unittest.TestCase):
    def test_gobball_planting_initial_variants_are_uniform_and_reachable(self):
        candidates = monster_family_stages.initial_candidates(68)
        refs = [candidate["reference"] for candidate in candidates]
        self.assertEqual([2, 39], sorted(refs))
        rng = random.Random(20261012)
        draws = Counter(rng.choice(refs) for _ in range(20_000))
        self.assertEqual(set(refs), set(draws))
        self.assertLessEqual(abs(draws[2] - draws[39]), 400)

        # Repeatedly exercise the production selector with a seeded chooser and
        # narrow native fixtures. Both legal Gobball templates remain in the
        # exact candidate pool and each durable result gets a one-time draw.
        resource = dict(map_id=1134, instance_id=0, x=0, y=0, z=0)
        definition = dict(resource_reference=999999, monster_family_ids=[68])
        rng = random.Random(20261012)
        seed_refs = {71001, 71002}
        fake_refs = {ref: monsters.REFERENCES[ref] for ref in refs}
        actions = {
            (ref, 1): {"csP": seed, "clT": ""}
            for ref, seed in zip(refs, sorted(seed_refs))
        }
        counts = Counter()
        with patch.object(
            planting,
            "SEEDS",
            {
                seed: {"item_reference": seed, "resource_reference": 999999}
                for seed in seed_refs
            },
        ), patch.object(monsters, "REFERENCES", fake_refs), patch.object(
            monster_collect, "_actions", return_value=actions
        ), patch(
            "secrets.choice", side_effect=rng.choice
        ):
            for _ in range(10_000):
                result = planting_runtime.monster_growth_member(resource, definition)
                counts[result["ref"]] += 1
        self.assertEqual(set(refs), set(counts))
        self.assertLessEqual(abs(counts[2] - counts[39]), 500)

    def test_wabbit_near_level_male_female_are_initial_alternatives(self):
        family = monster_family_stages.FAMILIES[1113]
        tier = family["tiers"][0]
        refs = {row["reference"] for row in tier["candidates"]}
        self.assertTrue({5455, 5456}.issubset(refs))
        pool_rows = monster_family_stages.initial_candidates(1113)
        pool = {row["reference"] for row in pool_rows}
        self.assertEqual({5455, 5456}, pool)
        from wakfu_server.monsters import REFERENCES

        self.assertEqual(
            {"Wonejo", "Mamá wonejo"}, {REFERENCES[ref]["name"] for ref in pool}
        )
        levels = [REFERENCES[ref]["min_level"] for ref in pool]
        self.assertLessEqual(max(levels) - min(levels), 2)
        rng = random.Random(1113)
        draws = Counter(rng.choice(sorted(pool)) for _ in range(10_000))
        self.assertLessEqual(abs(draws[5455] - draws[5456]), 400)

    def test_selected_ecology_forms_are_native_publishable_and_unnamed_ref_is_excluded(
        self,
    ):
        from wakfu_server.monsters import REFERENCES, owned_instance
        from wakfu_server.combat_monster_world import spawn_group
        from wakfu_server.monster_family_stages import publication_viable

        self.assertFalse(publication_viable(5405, REFERENCES[5405]["min_level"]))
        for family_id in monster_family_stages.FAMILIES:
            for row in monster_family_stages.initial_candidates(family_id):
                self.assertTrue(publication_viable(row["reference"], row["min_level"]))

        configuration = {
            "base_probability": 1.0,
            "stage_decay": 1.0,
            "boss_probability": 0.0,
        }
        for reference, (family, _) in monster_maturation.STAGES.items():
            if reference == 5405:
                continue
            for draw in (0.0, 0.2, 0.4, 0.6, 0.8, 0.999):
                selected = monster_maturation.choose_next(
                    reference,
                    configuration,
                    draw=draw,
                    members=[{"ref": reference}],
                    choose=lambda rows: rows[0],
                )
                if selected is None:
                    continue
                target = selected["reference"]
                self.assertTrue(
                    publication_viable(
                        target,
                        REFERENCES[target]["min_level"],
                    ),
                    (reference, target, draw),
                )
                member = owned_instance(
                    target, REFERENCES[target]["min_level"], -1, map_id=1, x=0, y=0, z=0
                )
                self.assertTrue(spawn_group([member], group_id=1))

    def test_seeded_population_trajectory_never_regresses_and_respects_soft_sizes_and_caps(
        self,
    ):
        rng = random.Random(681113)
        family = monster_maturation.STAGES[2][0]
        ordinary = [
            candidate["reference"]
            for tier in family["tiers"]
            for candidate in tier["candidates"]
            if candidate.get("boss_classification") == "regular"
        ]
        roster = [{"ref": rng.choice(ordinary)} for _ in range(4)]
        config = {
            "base_probability": 0.72,
            "stage_decay": 0.92,
            "boss_probability": 0.0,
        }
        up = down = 0
        rank_hits = Counter()
        for _ in range(60_000):
            index = rng.randrange(len(roster))
            old = roster[index]["ref"]
            old_rank = monster_maturation.STAGES[old][1]
            selected = monster_maturation.choose_next(
                old,
                config,
                draw=rng.random(),
                members=roster,
                choose=lambda rows: rng.choice(rows),
            )
            if selected is not None:
                new_rank = monster_maturation.STAGES[selected["reference"]][1]
                up += new_rank > old_rank
                down += new_rank < old_rank
                roster[index] = {**roster[index], "ref": selected["reference"]}
            for member in roster:
                rank_hits[monster_maturation.STAGES[member["ref"]][1]] += 1
        self.assertGreater(up, 0)
        self.assertEqual(down, 0)

        # Seeded public habitat run: groups start at2–5, births can extend an
        # existing roster or establish an external group, with hard caps at
        # 500 members,100 groups,8 members/group.
        groups = [[2] * rng.randint(2, 5) for _ in range(24)]
        reproduction = {
            "birth_probability": 0.25,
            "birth_stage_decay": 0.85,
            "new_group_probability": 0.5,
        }
        external_births = 0
        for _ in range(300_000):
            population = sum(map(len, groups))
            if population >= 500:
                break
            parent_group = rng.choice(groups)
            probability = monster_reproduction.birth_probability(
                parent_group[0], reproduction, group_size=len(parent_group)
            )
            if rng.random() >= probability:
                continue
            separate = len(
                groups
            ) < 100 and rng.random() < monster_reproduction.new_group_probability(
                len(parent_group), reproduction
            )
            if separate:
                groups.append([2])
                external_births += 1
            elif len(parent_group) < 8:
                parent_group.append(2)
        self.assertGreater(external_births, 0)
        sizes = [len(group) for group in groups]
        counts = Counter(sizes)
        self.assertLessEqual(sum(sizes), 500)
        self.assertLessEqual(len(groups), 100)
        self.assertLessEqual(max(sizes), 8)
        self.assertGreater(counts[4] + counts[5], counts[1])
        self.assertLess(counts[8], max(2, len(sizes) // 10 + 1))

        self.assertGreater(
            monster_reproduction.new_group_probability(4, reproduction), 0
        )
        self.assertGreater(
            monster_reproduction.new_group_probability(5, reproduction),
            monster_reproduction.new_group_probability(4, reproduction),
        )
        self.assertGreater(
            monster_reproduction.new_group_probability(7, reproduction),
            monster_reproduction.new_group_probability(5, reproduction),
        )


from postgres_case import PostgresCase
from psycopg.types.json import Jsonb
from wakfu_server.combat_group_store import PersistentGroups
from wakfu_server.monsters import REFERENCES, owned_instance


class EcologyBalanceReceiptGate(PostgresCase):
    def _group_with_timer(self, ref, group_id, monster_id, cycle, extras=()):
        map_id, instance_id = 1134, 0
        member = owned_instance(
            ref,
            REFERENCES[ref]["min_level"],
            monster_id,
            map_id=map_id,
            instance_id=instance_id,
            x=0,
            y=0,
            z=0,
        )
        members = [member]
        for offset, extra_ref in enumerate(extras, start=1):
            members.append(
                owned_instance(
                    extra_ref,
                    REFERENCES[extra_ref]["min_level"],
                    monster_id - offset,
                    map_id=map_id,
                    instance_id=instance_id,
                    x=offset,
                    y=0,
                    z=0,
                )
            )
        PersistentGroups(self.store).register(map_id, instance_id, group_id, members)
        table = (
            "monster_maturation_timers"
            if "maturation" in self._testMethodName
            else "monster_reproduction_timers"
        )
        with self.store.connection() as db:
            db.execute(
                f"INSERT INTO {table}(map_id,instance_id,monster_id,reference,remaining_ms,due,cycle) "
                "VALUES(%s,%s,%s,%s,0,true,%s)",
                (map_id, instance_id, monster_id, ref, cycle),
            )
        return map_id, instance_id, group_id, member, members

    def test_reproduction_receipt_replays_external_birth_once(self):
        map_id, instance_id, group_id, member, _ = self._group_with_timer(
            2, 991001, -991001, 1
        )
        ticket = dict(
            map_id=map_id,
            instance_id=instance_id,
            group_id=group_id,
            monster_id=member["id"],
            cycle=1,
            reference=member["ref"],
        )
        configuration = dict(
            interval_ms=60_000,
            birth_probability=1.0,
            birth_stage_decay=1.0,
            new_group_probability=1.0,
            max_members=8,
            max_zone_members=500,
            max_zone_groups=100,
        )
        indexed = (None, {(0, 0, 0): [(1, 0, 0)]})
        # This test covers receipt idempotence after a candidate destination is
        # selected. The synthetic edge index above is not map 1134's native
        # topology, so bypass only the native-habitat eligibility query here.
        with patch(
            "wakfu_server.monster_habitat_cells.habitat_destination_allowed",
            return_value=True,
        ):
            first = monster_reproduction.attempt(
                self.store,
                ticket,
                present=True,
                indexed=indexed,
                draw=0.0,
                group_draw=0.0,
                choose=lambda rows: rows[0],
                configuration=configuration,
            )
            replay = monster_reproduction.attempt(
                self.store,
                ticket,
                present=True,
                indexed=indexed,
                draw=0.9,
                group_draw=0.9,
                choose=lambda rows: rows[-1],
                configuration=configuration,
            )
        self.assertFalse(first["duplicate"])
        self.assertTrue(replay["duplicate"])
        self.assertEqual(first["child_id"], replay["child_id"])
        self.assertEqual(first["child_group_id"], replay["child_group_id"])
        with self.store.connection() as db:
            receipts = db.execute(
                "SELECT count(*) AS n FROM monster_reproduction_receipts WHERE map_id=%s AND instance_id=%s AND monster_id=%s AND cycle=1",
                (map_id, instance_id, member["id"]),
            ).fetchone()["n"]
            outbox = db.execute(
                "SELECT count(*) AS n FROM monster_reproduction_outbox WHERE map_id=%s AND instance_id=%s AND monster_id=%s AND cycle=1",
                (map_id, instance_id, member["id"]),
            ).fetchone()["n"]
        self.assertEqual(1, receipts)
        self.assertEqual(1, outbox)

    def test_maturation_receipt_replays_the_same_upward_transition(self):
        # A committed growth draw remains authoritative when the cycle is retried.
        family = monster_maturation.STAGES[2][0]
        candidate = None
        configuration = dict(
            interval_ms=60_000,
            base_probability=0.8,
            stage_decay=0.9,
            boss_probability=0.0,
        )
        for ref, (candidate_family, rank) in monster_maturation.STAGES.items():
            if candidate_family is not family:
                continue
            draw = next(
                (
                    i / 1000
                    for i in range(1000)
                    if (
                        lambda result: result is not None
                        and monster_maturation.STAGES[result["reference"]][1] > rank
                    )(
                        monster_maturation.choose_next(
                            ref,
                            configuration,
                            draw=i / 1000,
                            members=[{"ref": ref}],
                            choose=lambda rows: rows[0],
                        )
                    )
                ),
                None,
            )
            if draw is not None:
                candidate = (ref, draw)
                break
        self.assertIsNotNone(candidate)
        ref, draw = candidate
        map_id, instance_id, group_id, member, _ = self._group_with_timer(
            ref, 991002, -991002, 1
        )
        ticket = dict(
            map_id=map_id,
            instance_id=instance_id,
            group_id=group_id,
            monster_id=member["id"],
            cycle=1,
            reference=ref,
        )
        first = monster_maturation.attempt(
            self.store,
            ticket,
            present=True,
            draw=draw,
            choose=lambda rows: rows[0],
            configuration=configuration,
        )
        replay = monster_maturation.attempt(
            self.store,
            ticket,
            present=True,
            draw=0.99,
            choose=lambda rows: rows[-1],
            configuration=configuration,
        )
        self.assertFalse(first["duplicate"])
        self.assertTrue(replay["duplicate"])
        self.assertGreater(
            monster_maturation.STAGES[first["to_reference"]][1],
            monster_maturation.STAGES[ref][1],
        )
        self.assertEqual(first["policy"]["composition_model"], 2)
        self.assertEqual(first["to_reference"], replay["to_reference"])
        with self.store.connection() as db:
            receipts = db.execute(
                "SELECT count(*) AS n FROM monster_maturation_receipts WHERE map_id=%s AND instance_id=%s AND monster_id=%s AND cycle=1",
                (map_id, instance_id, member["id"]),
            ).fetchone()["n"]
        self.assertEqual(1, receipts)
