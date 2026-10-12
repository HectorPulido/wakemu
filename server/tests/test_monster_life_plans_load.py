"""Full-map lifecycle work uses bounded SQL statements at configured capacity."""
from contextlib import contextmanager
from types import SimpleNamespace
import json
import resource
import time
from postgres_case import PostgresCase
from psycopg.types.json import Jsonb
from wakfu_server import monster_life_plans as plans, monster_reproduction


class MonsterLifePlansLoadTests(PostgresCase):
    def test_five_thousand_actors_use_batched_attach_and_noop_resolution(self):
        groups = [
            dict(
                group_id=g,
                members=[dict(id=-(g * 5 + j), ref=4, x=g, y=j, z=0) for j in range(5)],
            )
            for g in range(1, 1001)
        ]
        tickets = [
            dict(
                map_id=1134,
                instance_id=0,
                group_id=g["group_id"],
                monster_id=m["id"],
                reference=4,
                cycle=1,
            )
            for g in groups
            for m in g["members"]
        ]
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO combat_groups(map_id,instance_id,group_id,members,status) SELECT 1134,0,x.group_id,x.members,'available' FROM jsonb_to_recordset(%s) x(group_id bigint,members jsonb)",
                (Jsonb(groups),),
            )
            db.execute(
                "INSERT INTO combat_group_members(map_id,instance_id,group_id,monster_id) SELECT 1134,0,x.group_id,x.monster_id FROM jsonb_to_recordset(%s) x(group_id bigint,monster_id bigint)",
                (Jsonb(tickets),),
            )
            db.execute(
                "INSERT INTO monster_reproduction_timers(map_id,instance_id,monster_id,reference,remaining_ms,due,cycle) SELECT 1134,0,x.monster_id,4,0,true,1 FROM jsonb_to_recordset(%s) x(monster_id bigint)",
                (Jsonb(tickets),),
            )
        policy = monster_reproduction.policy(self.store)
        policy["birth_probability"] = 0.0
        statements = []

        @contextmanager
        def connection():
            with self.store.connection() as db:

                def execute(sql, *args, **kwargs):
                    statements.append(sql.split()[0])
                    return db.execute(sql, *args, **kwargs)

                yield SimpleNamespace(execute=execute)

        counted = SimpleNamespace(connection=connection)
        started = time.monotonic()
        attached = plans.attach(counted, (1134, 0), "reproduction", tickets, policy)
        attach_statements = len(statements)
        self.assertEqual(len(attached), 5000)
        self.assertLessEqual(attach_statements, 4)
        members = {g["group_id"]: g["members"] for g in groups}
        proposals = [
            dict(
                kind="reproduction",
                ticket=t,
                configuration=policy,
                expected_members=members[t["group_id"]],
                draw=t["decision"]["draw"],
            )
            for t in attached
        ]
        statements.clear()
        self.assertEqual(plans.resolve_noops(counted, proposals), [])
        self.assertLessEqual(len(statements), 4)
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM monster_reproduction_receipts"
                ).fetchone()["n"],
                5000,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM monster_reproduction_timers WHERE due"
                ).fetchone()["n"],
                0,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM personal_ecology_receipts"
                ).fetchone()["n"],
                0,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM ecology_service_proposals"
                ).fetchone()["n"],
                0,
            )
        print(
            json.dumps(
                dict(
                    event="lifecycle_load_gate",
                    actors=5000,
                    groups=1000,
                    attach_statements=attach_statements,
                    noop_statements=len(statements),
                    elapsed_seconds=round(time.monotonic() - started, 3),
                    process_peak_rss=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                )
            )
        )
