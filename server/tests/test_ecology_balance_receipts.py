"""Receipt compatibility and prepared proposal authority for balanced ecology."""
import unittest
from psycopg.types.json import Jsonb
from postgres_case import PostgresCase
from wakfu_server import monster_maturation as maturation
from wakfu_server.combat_group_store import PersistentGroups
from wakfu_server.monsters import REFERENCES, owned_instance


class EcologyBalanceReceiptTests(PostgresCase):
    def setUp(self):
        super().setUp()
        self.key = (1134, 0, 889101)
        self.actor = -889101
        self.groups = PersistentGroups(self.store)
        self.configuration = dict(
            interval_ms=1000,
            base_probability=1.0,
            stage_decay=0.5,
            boss_probability=0.0,
        )

    def member(self, reference):
        return owned_instance(
            reference,
            REFERENCES[reference]["min_level"],
            self.actor,
            map_id=self.key[0],
            instance_id=self.key[1],
            x=0,
            y=0,
            z=0,
        )

    def receipt(self, source, target, *, marked):
        policy = dict(self.configuration)
        if marked:
            policy["composition_model"] = 1
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO monster_maturation_receipts(map_id,instance_id,monster_id,cycle,"
                "group_id,from_reference,to_reference,draw,policy) VALUES(%s,%s,%s,1,%s,%s,%s,0,%s)",
                (*self.key[:2], self.actor, self.key[2], source, target, Jsonb(policy)),
            )

    def test_marked_same_band_variant_replays_without_advancing_level_band(self):
        self.assertEqual(maturation.STAGES[2][1], maturation.STAGES[39][1])
        seed, current = self.member(2), self.member(39)
        self.groups.register(*self.key, [seed])
        self.receipt(2, 39, marked=True)
        self.assertEqual(
            maturation.reconcile_seed(self.store, self.key, [seed], [current]), self.key
        )

    def test_legacy_upward_receipt_survives_regrouping_into_same_band(self):
        self.assertEqual(
            maturation.ORIGINAL_STAGES[41][1], maturation.ORIGINAL_STAGES[1][1] + 1
        )
        self.assertEqual(maturation.STAGES[1][1], maturation.STAGES[41][1])
        seed, current = self.member(1), self.member(41)
        self.groups.register(*self.key, [seed])
        self.receipt(1, 41, marked=False)
        self.assertEqual(
            maturation.reconcile_seed(self.store, self.key, [seed], [current]), self.key
        )

    def test_unmarked_same_band_receipt_does_not_gain_new_transition_authority(self):
        seed, current = self.member(2), self.member(39)
        self.groups.register(*self.key, [seed])
        self.receipt(2, 39, marked=False)
        with self.assertRaisesRegex(
            ValueError, "Invalid monster maturation receipt transition"
        ):
            maturation.reconcile_seed(self.store, self.key, [seed], [current])

    def test_foreign_family_prepared_transition_rolls_back_without_receipt(self):
        seed = self.member(2)
        self.groups.register(*self.key, [seed])
        family = maturation.STAGES[2][0]
        foreign = next(
            reference
            for reference, (other, _) in maturation.STAGES.items()
            if other is not family and REFERENCES[reference].get("name")
        )
        maturation.observe(
            self.store,
            *self.key[:2],
            present=True,
            generation="balance-test",
            now_ms=0,
            configuration=self.configuration
        )
        tickets = maturation.observe(
            self.store,
            *self.key[:2],
            present=True,
            generation="balance-test",
            now_ms=1000,
            configuration=self.configuration
        )
        ticket = next(row for row in tickets if row["monster_id"] == self.actor)
        with self.assertRaisesRegex(
            ValueError, "Invalid prepared maturation transition"
        ):
            maturation.attempt(
                self.store,
                ticket,
                present=True,
                draw=0,
                configuration=self.configuration,
                prepared=dict(expected_members=[seed], grown=self.member(foreign)),
            )
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM monster_maturation_receipts"
                ).fetchone()["n"],
                0,
            )
            roster = db.execute(
                "SELECT members FROM combat_groups WHERE map_id=%s AND instance_id=%s AND group_id=%s",
                self.key,
            ).fetchone()["members"]
        self.assertEqual(roster, [seed])


if __name__ == "__main__":
    unittest.main()
