"""New maturation never regresses; committed historical outcomes remain durable."""
import unittest
from unittest.mock import patch

from postgres_case import PostgresCase
from psycopg.types.json import Jsonb
from wakfu_server import monster_maturation as maturation
from wakfu_server import monster_life_plans as plans
from wakfu_server.monster_group_balance import valid_transition
from wakfu_server.combat_group_store import PersistentGroups
from wakfu_server.monsters import REFERENCES, owned_instance


class MonotoneMaturationTests(unittest.TestCase):
    configuration = dict(base_probability=0.97, stage_decay=0.5, boss_probability=0.02)

    def test_every_family_and_roster_size_keeps_or_increases_its_stage(self):
        for reference, (family, rank) in maturation.STAGES.items():
            for size in (1, 4, 8):
                for draw in (0.0, 0.019, 0.02, 0.2, 0.5, 0.9, 0.999999):
                    for choose in (lambda rows: rows[0], lambda rows: rows[-1]):
                        candidate = maturation.choose_next(
                            reference,
                            self.configuration,
                            draw=draw,
                            members=[dict(ref=reference)] * size,
                            choose=choose,
                        )
                        if candidate is None:
                            continue
                        target_family, target_rank = maturation.STAGES[
                            candidate["reference"]
                        ]
                        self.assertIs(target_family, family)
                        self.assertGreaterEqual(
                            target_rank,
                            rank,
                            (
                                family["family_id"],
                                reference,
                                candidate["reference"],
                                size,
                                draw,
                            ),
                        )
                        self.assertGreaterEqual(
                            candidate["min_level"], REFERENCES[reference]["min_level"]
                        )

    def test_adult_gobball_never_becomes_a_black_or_white_gobbly(self):
        self.assertGreater(maturation.STAGES[41][1], maturation.STAGES[2][1])
        for target in (2, 39):
            self.assertFalse(valid_transition(41, target, maturation.STAGES))
        for draw in (0.0, 0.1, 0.3, 0.5, 0.8, 0.999):
            candidate = maturation.choose_next(
                41,
                self.configuration,
                draw=draw,
                members=[dict(ref=41)] * 8,
                choose=lambda rows: rows[-1],
            )
            self.assertNotIn(
                None if candidate is None else candidate["reference"], (2, 39)
            )

    def test_same_band_or_administrative_level_cannot_be_reduced(self):
        self.assertEqual(maturation.STAGES[41][1], maturation.STAGES[1][1])
        self.assertGreater(REFERENCES[41]["min_level"], REFERENCES[1]["min_level"])
        self.assertFalse(valid_transition(41, 1, maturation.STAGES))
        for level in (REFERENCES[41]["min_level"], 20):
            for draw in (0.0, 0.02, 0.2, 0.5, 0.9, 0.999):
                candidate = maturation.choose_next(
                    41,
                    self.configuration,
                    draw=draw,
                    members=[dict(ref=41, level=level)],
                    source_level=level,
                    choose=lambda rows: rows[0],
                )
                if candidate is not None:
                    self.assertGreaterEqual(candidate["min_level"], level)


class MonotoneMaturationPostgresTests(PostgresCase):
    def test_prepared_regressions_do_not_mutate_but_historical_receipts_reconcile_and_replay(
        self,
    ):
        key = (1134, 0, 889901)
        actor = -889901
        configuration = dict(
            interval_ms=1000,
            base_probability=1.0,
            stage_decay=0.5,
            boss_probability=0.0,
        )

        def member(reference):
            return owned_instance(
                reference,
                REFERENCES[reference]["min_level"],
                actor,
                map_id=key[0],
                instance_id=0,
                x=0,
                y=0,
                z=0,
            )

        seed = member(41)
        groups = PersistentGroups(self.store)
        groups.register(*key, [seed])
        ticket = dict(
            map_id=key[0],
            instance_id=0,
            group_id=key[2],
            monster_id=actor,
            reference=41,
            cycle=1,
        )
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO monster_maturation_timers"
                "(map_id,instance_id,monster_id,reference,remaining_ms,due,cycle) "
                "VALUES(%s,0,%s,41,0,true,1)",
                (key[0], actor),
            )
            timer_before = db.execute(
                "SELECT * FROM monster_maturation_timers"
            ).fetchone()
        for target in (2, 39):
            self.assertIsNone(
                maturation.attempt(
                    self.store,
                    ticket,
                    present=True,
                    draw=0.2,
                    configuration=configuration,
                    prepared=dict(expected_members=[seed], grown=member(target)),
                )
            )
        planned = plans.attach(
            self.store, key[:2], "maturation", [ticket], configuration
        )[0]
        self.assertIsNone(
            maturation.attempt(
                self.store,
                planned,
                present=True,
                draw=planned["decision"]["draw"],
                configuration=planned["plan_policy"],
                prepared=dict(expected_members=[seed], grown=member(2)),
            )
        )
        with patch.object(
            plans.secrets,
            "token_hex",
            side_effect=AssertionError("Rejected DOWN rerolled its fixed seed"),
        ):
            refreshed = plans.attach(
                self.reopen(), key[:2], "maturation", [ticket], configuration
            )[0]
        self.assertEqual(refreshed, planned)
        self.assertEqual(refreshed["decision"]["attempts"], 0)
        with self.store.connection() as db:
            row = db.execute("SELECT members,revision FROM combat_groups").fetchone()
            self.assertEqual(row["members"], [seed])
            self.assertEqual(row["revision"], 0)
            self.assertEqual(
                db.execute("SELECT * FROM monster_maturation_timers").fetchone(),
                timer_before,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM monster_maturation_receipts"
                ).fetchone()["n"],
                0,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM monster_maturation_outbox"
                ).fetchone()["n"],
                0,
            )

            # Reproduce an already committed model-1 downgrade. Compatibility
            # must retain its native current actor without granting new DOWNs.
            current = member(2)
            db.execute(
                "INSERT INTO monster_maturation_receipts(map_id,instance_id,monster_id,cycle,"
                "group_id,from_reference,to_reference,draw,policy) VALUES(%s,0,%s,1,%s,41,2,0.2,%s)",
                (
                    key[0],
                    actor,
                    key[2],
                    Jsonb(dict(configuration, composition_model=1)),
                ),
            )
            db.execute(
                "UPDATE combat_groups SET members=%s,revision=1", (Jsonb([current]),)
            )
            db.execute(
                "UPDATE monster_maturation_timers SET reference=2,due=false,remaining_ms=1000"
            )
        self.assertEqual(
            maturation.reconcile_seed(self.store, key, [seed], [current]), key
        )
        self.assertEqual(groups.register_seed(*key, [seed]), key)
        with patch.object(
            maturation.secrets,
            "randbelow",
            side_effect=AssertionError("Committed cycle redrew its outcome"),
        ):
            for _ in range(2):
                replay = maturation.attempt(
                    self.store, ticket, present=True, configuration=configuration
                )
                self.assertTrue(replay["duplicate"])
                self.assertEqual(replay["to_reference"], 2)
        with self.store.connection() as db:
            row = db.execute("SELECT members,revision FROM combat_groups").fetchone()
            self.assertEqual(row["members"], [current])
            self.assertEqual(row["revision"], 1)
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM monster_maturation_receipts"
                ).fetchone()["n"],
                1,
            )

        admin_key = (key[0], 0, key[2] + 1)
        admin = owned_instance(
            41,
            REFERENCES[41]["max_level"],
            actor - 1,
            map_id=key[0],
            instance_id=0,
            x=2,
            y=0,
            z=0,
        )
        groups.register(*admin_key, [admin])
        admin_ticket = dict(ticket, group_id=admin_key[2], monster_id=admin["id"])
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO monster_maturation_timers"
                "(map_id,instance_id,monster_id,reference,remaining_ms,due,cycle) "
                "VALUES(%s,0,%s,41,0,true,1)",
                (key[0], admin["id"]),
            )
        lower = owned_instance(
            41,
            REFERENCES[41]["min_level"],
            admin["id"],
            map_id=key[0],
            instance_id=0,
            x=2,
            y=0,
            z=0,
        )
        self.assertIsNone(
            maturation.attempt(
                self.store,
                admin_ticket,
                present=True,
                draw=0.2,
                configuration=configuration,
                prepared=dict(expected_members=[admin], grown=lower),
            )
        )
        with self.store.connection() as db:
            row = db.execute(
                "SELECT members,revision FROM combat_groups WHERE group_id=%s",
                (admin_key[2],),
            ).fetchone()
            self.assertEqual(row["members"], [admin])
            self.assertEqual(row["revision"], 0)
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM monster_maturation_receipts"
                ).fetchone()["n"],
                1,
            )
