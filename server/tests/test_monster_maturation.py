"""World maturation receipts/validators with explicit Rust due-cycle fixtures.

Autonomous active-clock coverage moved to lifecycle_contract/clock_cases.rs;
that test module maps the former clock case names to the real Rust observer.
"""

from postgres_case import PostgresCase
from psycopg.types.json import Jsonb
from wakfu_server import monster_maturation
from wakfu_server.combat_group_store import PersistentGroups
from wakfu_server.monsters import REFERENCES, owned_instance


class MonsterMaturationTests(PostgresCase):
    def test_miaumiau_world_commits_preserve_full_interval_after_each_transition(self):
        map_id, instance_id, group_id, monster_id = 527, 0, 87563, -87563
        configuration = dict(
            interval_ms=900000,
            base_probability=1.0,
            stage_decay=1.0,
            boss_probability=0.0,
        )
        with self.store.connection() as db:
            db.execute(
                "UPDATE settings SET value=%s WHERE name='monster_maturation'",
                (Jsonb(configuration),),
            )
        groups = PersistentGroups(self.store)
        kitten = owned_instance(
            2616,
            REFERENCES[2616]["min_level"],
            monster_id,
            map_id=map_id,
            instance_id=instance_id,
            x=27,
            y=4,
            z=0,
        )
        key = groups.register(map_id, instance_id, group_id, [kitten])
        for cycle, source, destination in ((1, 2616, 2598), (2, 2598, 1816)):
            with self.subTest(cycle=cycle):
                # A frozen external ticket is input, never a Python observation.
                with self.store.connection() as db:
                    db.execute(
                        "INSERT INTO monster_maturation_timers"
                        "(map_id,instance_id,monster_id,reference,remaining_ms,due,cycle) "
                        "VALUES(%s,%s,%s,%s,0,true,%s) ON CONFLICT(map_id,instance_id,monster_id) "
                        "DO UPDATE SET reference=EXCLUDED.reference,remaining_ms=0,due=true,"
                        "cycle=EXCLUDED.cycle,last_active_ms=NULL",
                        (map_id, instance_id, monster_id, source, cycle),
                    )
                ticket = dict(
                    map_id=map_id,
                    instance_id=instance_id,
                    group_id=group_id,
                    monster_id=monster_id,
                    reference=source,
                    cycle=cycle,
                )
                # Frozen native proposal: construction and monotone validation
                # remain World-owned; transition selection belongs to Rust.
                before = list(groups.snapshot(map_id, instance_id)[0]["members"])
                source_member = next(
                    member for member in before if member["id"] == monster_id
                )
                grown = owned_instance(
                    destination,
                    REFERENCES[destination]["min_level"],
                    monster_id,
                    map_id=map_id,
                    instance_id=instance_id,
                    x=source_member["x"],
                    y=source_member["y"],
                    z=source_member["z"],
                    team=source_member["team"],
                )
                receipt = monster_maturation.attempt(
                    self.store,
                    ticket,
                    present=True,
                    draw=0.1,
                    configuration=configuration,
                    prepared=dict(expected_members=before, grown=grown),
                )
                self.assertEqual(
                    (source, destination),
                    (receipt["from_reference"], receipt["to_reference"]),
                )
                with self.store.connection() as db:
                    timer = db.execute(
                        "SELECT * FROM monster_maturation_timers WHERE map_id=%s "
                        "AND instance_id=%s AND monster_id=%s",
                        (map_id, instance_id, monster_id),
                    ).fetchone()
                self.assertEqual(
                    (destination, 900000, False, cycle),
                    (
                        timer["reference"],
                        timer["remaining_ms"],
                        timer["due"],
                        timer["cycle"],
                    ),
                )
        with self.store.connection() as db:
            transitions = db.execute(
                "SELECT from_reference,to_reference FROM monster_maturation_receipts "
                "WHERE map_id=%s AND instance_id=%s AND monster_id=%s ORDER BY cycle",
                (map_id, instance_id, monster_id),
            ).fetchall()
        self.assertEqual(
            [(2616, 2598), (2598, 1816)], [tuple(row.values()) for row in transitions]
        )
        self.assertEqual(key, groups.snapshot(map_id, instance_id)[0]["key"])

    def test_world_policy_rejects_combined_probability_above_one(self):
        configuration = dict(
            interval_ms=60000,
            base_probability=1.0,
            stage_decay=0.5,
            boss_probability=0.00001,
        )
        with self.store.connection() as db:
            db.execute(
                "UPDATE settings SET value=%s WHERE name='monster_maturation'",
                (Jsonb(configuration),),
            )
        with self.assertRaises(ValueError):
            monster_maturation.policy(self.store)
