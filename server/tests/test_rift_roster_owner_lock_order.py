"""Real PostgreSQL owner-lock ordering for two genuine MHH companies.

The original loaded roster is exercised as an explicit RED control when its
private source artifact is present. No live account or native combat is used.
"""
from concurrent.futures import ThreadPoolExecutor
import ast
from pathlib import Path
from queue import Queue
from threading import Event
from time import monotonic
import os
import unittest

from psycopg.errors import LockNotAvailable
from postgres_case import PostgresCase
from wakfu_server import heroes, player_parties, rift_entry_adapter
from wakfu_server.objectives import environmental_service


class RiftRosterOwnerLockOrderTests(PostgresCase):
    def companies(self):
        owners = []
        for suffix in ("Alpha", "Beta"):
            account = self.store.register(
                "lock-company-" + suffix.lower(), "test-password"
            )["id"]
            main = self.store.create_character(account, "Lock" + suffix)["id"]
            generation = self.store.begin_session(account, ttl=10000)
            self.store.select_character(account, generation, main)
            owners.append((account, generation, main))
        first, second = owners
        token = player_parties.invite(self.store, *first, second[2])
        party = player_parties.answer(self.store, *second, token, True)
        members = [first[2], second[2]]
        for index, owner in enumerate(owners):
            for suffix in ("A", "B"):
                identity = self.store.create_character(
                    owner[0], "Hero" + ("Alpha", "Beta")[index] + suffix
                )["id"]
                heroes.add(self.store, *owner, identity)
                members.append(identity)
        return owners, party, sorted(members)

    def wait_blocked(self, db, waiter, holder):
        deadline = monotonic() + 4
        while monotonic() < deadline:
            if (
                holder
                in db.execute(
                    "SELECT pg_blocking_pids(%s) AS pids", (waiter,)
                ).fetchone()["pids"]
            ):
                return
            Event().wait(0.01)
        self.fail("Actual portal worker did not wait on the held owner transaction")

    def portal(self, function, owner, pid_queue):
        with self.store.connection() as db:
            db.execute("SET LOCAL lock_timeout='5s'")
            db.execute("SET LOCAL statement_timeout='7s'")
            pid_queue.put(
                db.execute("SELECT pg_backend_pid() AS pid").fetchone()["pid"]
            )
            rows = function(db, self.store, *owner)
            if function is not rift_entry_adapter._roster:
                # Execute the original caller's second UPDATE stage verbatim.
                # This is an admission-lock component using current coordinates,
                # not a claim to have created or entered a native Rift instance.
                tree = ast.parse(Path(rift_entry_adapter.__file__).read_text())
                enter = next(
                    node
                    for node in tree.body
                    if isinstance(node, ast.FunctionDef) and node.name == "enter"
                )
                loop = next(
                    node
                    for node in next(
                        node for node in enter.body if isinstance(node, ast.With)
                    ).body
                    if isinstance(node, ast.For)
                    and isinstance(node.target, ast.Name)
                    and node.target.id == "row"
                    and any(
                        isinstance(child, ast.Constant)
                        and isinstance(child.value, str)
                        and child.value.startswith("UPDATE characters SET map_id=")
                        for child in ast.walk(node)
                    )
                )
                source = rows[0]
                namespace = dict(
                    db=db,
                    rows=rows,
                    destination={k: source[k] for k in ("map_id", "x", "y", "z")},
                    run={"instance_id": source["instance_id"]},
                )
                exec(
                    compile(
                        ast.Module(body=[loop], type_ignores=[]),
                        rift_entry_adapter.__file__,
                        "exec",
                    ),
                    namespace,
                )
            return rows

    def test_bulk_owner_prefix_allows_actual_environmental_owner_and_rejects_roster_race(
        self,
    ):
        owners, party, members = self.companies()
        first, second = owners
        old_path = Path(".runtime/rift-bulk-owner-lock-20261024/old_loaded_roster.py")
        functions = [("current", rift_entry_adapter._roster)]
        if os.environ.get("WAKFU_QA_RIFT_ROSTER_OLD_CONTROL") == "1":
            self.assertTrue(
                old_path.is_file(), "Explicit old control requires exact loaded source"
            )
            namespace = dict(vars(rift_entry_adapter))
            exec(compile(old_path.read_text(), str(old_path), "exec"), namespace)
            functions.insert(0, ("old_loaded", namespace["_roster"]))
        old_only = os.environ.get("WAKFU_QA_RIFT_ROSTER_OLD_ONLY") == "1"
        if old_only:
            functions = [pair for pair in functions if pair[0] == "old_loaded"]
            self.assertTrue(
                functions, "Old-only mode requires explicit original source control"
            )
        observations = []
        for label, function in functions:
            with self.subTest(source=label):
                pids = Queue()
                with ThreadPoolExecutor(max_workers=1) as executor:
                    with self.store.connection() as environmental:
                        environmental.execute("SET LOCAL lock_timeout='150ms'")
                        holder = environmental.execute(
                            "SELECT pg_backend_pid() AS pid"
                        ).fetchone()["pid"]
                        # Pause the real environmental ACCOUNT prefix. The old
                        # portal's actual caller UPDATE waits for this owner after
                        # holding SESSION; the real owner service needs SESSION.
                        environmental.execute(
                            "SELECT id FROM accounts WHERE id=%s FOR UPDATE",
                            (second[0],),
                        )
                        future = executor.submit(self.portal, function, first, pids)
                        waiter = pids.get(timeout=4)
                        self.wait_blocked(environmental, waiter, holder)
                        if label == "old_loaded":
                            with self.assertRaises(LockNotAvailable):
                                with environmental.transaction():
                                    environmental.execute(
                                        "SELECT account_id FROM sessions WHERE account_id=%s FOR UPDATE NOWAIT",
                                        (second[0],),
                                    )
                            # The actual environmental call cannot progress while
                            # the inverse portal transaction holds this session.
                            with self.assertRaises(LockNotAvailable):
                                with environmental.transaction():
                                    environmental_service._lock_owner(
                                        self.store, environmental, *second
                                    )
                            observations.append(
                                "old actual environmental owner blocked by portal-held session"
                            )
                        else:
                            session = environmental.execute(
                                "SELECT account_id FROM sessions WHERE account_id=%s FOR UPDATE NOWAIT",
                                (second[0],),
                            ).fetchone()
                            self.assertEqual(session["account_id"], second[0])
                            environmental_service._lock_owner(
                                self.store, environmental, *second
                            )
                            observations.append(
                                "new actual environmental owner completed before portal resumed"
                            )
                    rows = future.result(timeout=7)
                self.assertEqual([row["id"] for row in rows], members)
                self.assertEqual(
                    {row["account_id"] for row in rows}, {first[0], second[0]}
                )
                self.assertEqual(sum("hero_main_id" in row for row in rows), 4)
        if old_only:
            self.observed_interleavings = observations
            return
        self.assertIn(
            "new actual environmental owner completed before portal resumed",
            observations,
        )

        # A party mutation after the unlocked snapshot must not admit an
        # unpinned owner. This is an isolated SQL race/tamper negative, not a
        # claim that the public party API permits a seventh company unit.
        third_account = self.store.register("lock-company-third", "test-password")["id"]
        third = self.store.create_character(third_account, "LockGamma")["id"]
        generation = self.store.begin_session(third_account, ttl=10000)
        self.store.select_character(third_account, generation, third)
        pids = Queue()
        with ThreadPoolExecutor(max_workers=1) as executor:
            with self.store.connection() as owner:
                holder = owner.execute("SELECT pg_backend_pid() AS pid").fetchone()[
                    "pid"
                ]
                owner.execute(
                    "SELECT id FROM accounts WHERE id=%s FOR UPDATE", (second[0],)
                )
                future = executor.submit(
                    self.portal, rift_entry_adapter._roster, first, pids
                )
                self.wait_blocked(owner, pids.get(timeout=4), holder)
                with self.store.connection() as change:
                    change.execute(
                        "INSERT INTO player_party_members(character_id,party_id) VALUES(%s,%s)",
                        (third, party),
                    )
                    change.execute(
                        "UPDATE player_parties SET revision=revision+1 WHERE id=%s",
                        (party,),
                    )
            with self.assertRaisesRegex(
                ValueError, "Party changed|party leader|ownership changed"
            ):
                future.result(timeout=7)
        with self.store.connection() as db:
            # Failed preparation created no Rift or pending movement, and
            # preserved all genuine hero slots rather than repairing the race.
            self.assertEqual(
                db.execute("SELECT count(*) AS n FROM rift_instances").fetchone()["n"],
                0,
            )
            self.assertEqual(
                db.execute("SELECT count(*) AS n FROM account_hero_slots").fetchone()[
                    "n"
                ],
                4,
            )
            db.execute(
                "DELETE FROM player_party_members WHERE character_id=%s", (third,)
            )
            db.execute(
                "UPDATE player_parties SET revision=revision+1 WHERE id=%s", (party,)
            )
            with self.assertRaisesRegex(ValueError, "session"):
                rift_entry_adapter._roster(
                    db, self.store, first[0], "stale-generation", first[2]
                )
        self.observed_interleavings = observations


if __name__ == "__main__":
    unittest.main()
