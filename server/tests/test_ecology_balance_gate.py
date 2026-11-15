import random
import unittest
from unittest.mock import patch
from collections import Counter
from unittest.mock import patch

from wakfu_server import monster_maturation, monster_reproduction
from wakfu_server import monster_family_stages, planting_runtime, planting
from wakfu_server import monster_collect, monsters

# Statistical producer gates now execute the actual Rust owner:
# - plants tests/plant_planner_contract/balance_cases.rs: exact initial pools,
#   native names/levels, uniform reachability, seeded selector and serialization.
# - mobs legacy_balance_contract.rs: 60k monotone and 300k bounded population steps.
# World receipt/idempotence assertions remain below with explicit native inputs.


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
        # Explicit Rust-native offspring proposal; World only validates and commits.
        with self.store.connection() as db:
            _, child_id = monster_reproduction.allocate_identity(db)
        child = owned_instance(
            2,
            REFERENCES[2]["min_level"],
            child_id,
            map_id=map_id,
            instance_id=instance_id,
            x=1,
            y=0,
            z=0,
        )
        prepared = dict(expected_members=[member], destination=[1, 0, 0], child=child)
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
                configuration=configuration,
                prepared=prepared,
            )
            replay = monster_reproduction.attempt(
                self.store,
                ticket,
                present=True,
                indexed=indexed,
                draw=0.9,
                group_draw=0.9,
                configuration=configuration,
                prepared=prepared,
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
        # Frozen native proposal: ordinary Gobball2 grows to qualified form1.
        # Candidate selection is exercised by Rust, never regenerated by World.
        ref, target, draw = 2, 1, 0.5
        configuration = dict(
            interval_ms=60_000,
            base_probability=0.8,
            stage_decay=0.9,
            boss_probability=0.0,
        )
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
        grown = owned_instance(
            target,
            REFERENCES[target]["min_level"],
            member["id"],
            map_id=map_id,
            instance_id=instance_id,
            x=0,
            y=0,
            z=0,
        )
        prepared = dict(expected_members=[member], grown=grown)
        first = monster_maturation.attempt(
            self.store,
            ticket,
            present=True,
            draw=draw,
            configuration=configuration,
            prepared=prepared,
        )
        replay = monster_maturation.attempt(
            self.store,
            ticket,
            present=True,
            draw=0.99,
            configuration=configuration,
            prepared=dict(expected_members=[member], grown=None),
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
