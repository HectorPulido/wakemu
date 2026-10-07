"""PostgreSQL-only lifecycle coverage from native seed to same-cell replant."""

import struct
import unittest
from unittest.mock import patch

from postgres_case import PostgresCase
from wakfu_server.combat_groups import Groups
from wakfu_server.combat_terrain import map_geometry
from wakfu_server.inventory_items import grant
from wakfu_server.planting_cells import authorize as authorize_cell
from wakfu_server.planting_probability import resolver
from wakfu_server.planting_runtime import Plantings
from wakfu_server.resource_collect import (
    acknowledge_publication,
    complete as complete_harvest,
    prepare as prepare_harvest,
    reserve as reserve_harvest,
)
from wakfu_server.planting import SEEDS
from wakfu_server.profession_store import ensure_learned
from wakfu_server.territory_weather import save as save_territory_weather
from wakfu_server.wire import proto_field


class FloraPlantingHarvestEndToEndTests(PostgresCase):
    """Exercise the actual SQL occupations without changing chance policy."""

    def setUp(self):
        super().setUp()
        self.now = [1_000.0]
        self.store.clock = lambda: self.now[0]
        # Filled per crop with native surface and same-height geometry edges
        # from map235, region95301 (ground177 for Fresno, 178 for Cardo).
        self.map_id = 235
        self.target = None
        self.actor_position = None
        self.deliveries = []
        self.groups = Groups()

    def _actor(self, profession_id, name):
        account = self.store.register(name.lower().replace(" ", "-"), "local-password")[
            "id"
        ]
        character = self.store.create_character(account, name)
        generation = self.store.begin_session(account)
        self.store.select_character(account, generation, character["id"])
        ensure_learned(
            self.store, account, generation, character["id"], [profession_id]
        )
        with self.store.connection() as db:
            db.execute(
                "UPDATE characters SET map_id=%s,x=%s,y=%s,z=%s WHERE id=%s",
                (self.map_id, *self.actor_position, character["id"]),
            )
        save_territory_weather(
            self.store,
            map_id=self.map_id,
            instance_id=character["instance_id"],
            region_id=95301,
            payload=struct.pack(">qb6fi", 95301, 0, 1, 2, 3, 4, 5, 6, 0),
        )
        character = self.store.character(account, character["id"])
        return account, generation, character

    def _runtime(self, store=None):
        store = store or self.store
        store.clock = lambda: self.now[0]
        return Plantings(
            store,
            open_test_policy=False,
            probability_context=resolver(
                store, profession_bonus=lambda _prepared: 0.0, open_test_policy=False
            ),
        )

    def _owned_seed(self, account, generation, character, reference):
        seed = SEEDS[reference]
        return grant(
            self.store,
            account,
            generation,
            character["id"],
            reference=reference,
            quantity=1,
            container=character["inventory_containers"][0]["uid"],
            slot=0,
            allowed_references=SEEDS,
        )

    def _plant(self, runtime, account, generation, character, seed):
        x, y, _z = self.target
        body = struct.pack(
            ">iqii", SEEDS[seed["reference"]]["action_id"], seed["uid"], x, y
        )
        opcode, _start = runtime.begin(
            account,
            generation,
            character,
            body,
            lambda actor, request, definition_seed, resource: authorize_cell(
                runtime.store,
                actor,
                request,
                definition_seed,
                resource,
                open_test_policy=False,
            ),
        )
        self.assertEqual(opcode, 12815)
        self.now[0] += 3
        self.assertTrue(self.store.heartbeat(account, generation))
        # Deterministic draw only; native ground/weather probability remains
        # authoritative and is recorded on the receipt.
        with patch("wakfu_server.planting.secrets.randbelow", return_value=0):
            result = runtime.complete(
                account, generation, character, struct.pack(">Bh", 2, 2)
            )
        self.assertTrue(result["success"])
        self.assertEqual(result["probability"], 0.9)
        self.assertEqual(result["packets"][0][0], 13135)
        return result["resource"]

    def _mature_one_edge(
        self, runtime, account, generation, resource_uid, expected_stage
    ):
        self.now[0] += 30
        self.assertTrue(self.store.heartbeat(account, generation))
        deliveries = runtime.mature(self.groups, publish=self.deliveries.append)
        matching = [
            entry for entry in deliveries if entry["resource_uid"] == resource_uid
        ]
        self.assertEqual(len(matching), 1)
        with runtime.store.connection() as db:
            row = db.execute(
                "SELECT * FROM planted_resources WHERE resource_uid=%s", (resource_uid,)
            ).fetchone()
            outbox = db.execute(
                "SELECT published,resource FROM planting_growth_outbox WHERE resource_uid=%s",
                (resource_uid,),
            ).fetchone()
        self.assertEqual(row["stage"], expected_stage)
        self.assertTrue(outbox["published"])
        self.assertEqual(outbox["resource"]["stage"], expected_stage)

    def _harvest(self, account, generation, character, action_id):
        x, y, _z = self.target
        wire_y = y if y >= 0 else y + (1 << 64)
        body = proto_field(8, action_id) + proto_field(16, x) + proto_field(24, wire_y)
        prepared = prepare_harvest(
            self.store,
            account,
            generation,
            character["id"],
            body,
            reachable=lambda actor, resource: (
                tuple(actor[key] for key in ("x", "y", "z")),
                tuple(resource[key] for key in ("x", "y", "z")),
            )
            in {
                (tuple(edge[0]), tuple(edge[1]))
                for edge in map_geometry(actor["map_id"])["edges"]
            },
        )
        ticket = reserve_harvest(self.store, account, generation, prepared)
        self.now[0] += 3
        self.assertTrue(self.store.heartbeat(account, generation))
        outcome = complete_harvest(self.store, ticket, struct.pack(">Bh", 2, 3))
        self.assertTrue(outcome["applied"])
        self.assertEqual(outcome["world_packets"][0][0], 12782)
        acknowledge_publication(self.store, outcome)
        return outcome

    def _run_crop(
        self,
        *,
        seed_reference,
        profession_id,
        name,
        seed_action,
        final_action,
        final_product,
    ):
        self.target, self.actor_position = (
            ((88, -158, 27), (89, -158, 27))
            if seed_reference == 8063
            else ((85, -161, 25), (86, -161, 25))
        )
        account, generation, character = self._actor(profession_id, name)
        seed = self._owned_seed(account, generation, character, seed_reference)
        runtime = self._runtime()

        first = self._plant(runtime, account, generation, character, seed)
        self.assertEqual(
            first["resource_reference"], SEEDS[seed_reference]["resource_reference"]
        )
        with runtime.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT count(*) FROM planted_resources WHERE resource_uid=%s",
                    (first["resource_uid"],),
                ).fetchone()["count"],
                1,
            )
        # Reopening storage simulates a server process boundary while the
        # durable planted resource and its growth clock continue to exist.
        runtime.store = self.reopen()
        runtime = self._runtime(runtime.store)
        self.assertEqual(len(runtime.snapshots(self.map_id, 0)), 1)
        self._mature_one_edge(runtime, account, generation, first["resource_uid"], 2)
        runtime.store = self.reopen()
        runtime = self._runtime(runtime.store)
        self._mature_one_edge(runtime, account, generation, first["resource_uid"], 3)

        seed_harvest = self._harvest(account, generation, character, seed_action)
        self.assertEqual(seed_harvest["outcome"]["item_reference"], seed_reference)
        self.assertEqual(seed_harvest["outcome"]["stage"], 2)
        self._mature_one_edge(runtime, account, generation, first["resource_uid"], 3)
        terminal = self._harvest(account, generation, character, final_action)
        self.assertEqual(terminal["outcome"]["item_reference"], final_product)
        self.assertEqual(terminal["outcome"]["stage"], 0)
        with runtime.store.connection() as db:
            self.assertIsNone(
                db.execute(
                    "SELECT 1 FROM planted_resources WHERE resource_uid=%s",
                    (first["resource_uid"],),
                ).fetchone()
            )
        runtime.store = self.reopen()
        runtime = self._runtime(runtime.store)
        self.assertEqual(runtime.snapshots(self.map_id, 0), [])

        current = runtime.store.character(account, character["id"])
        returned_seed = next(
            item
            for item in current["inventory_items"]
            if item["reference"] == seed_reference
        )
        second = self._plant(runtime, account, generation, character, returned_seed)
        self.assertNotEqual(first["resource_uid"], second["resource_uid"])
        runtime.store = self.reopen()
        runtime = self._runtime(runtime.store)
        snapshots = runtime.snapshots(self.map_id, 0)
        self.assertEqual(len(snapshots), 1)
        with runtime.store.connection() as db:
            saved = db.execute(
                "SELECT * FROM planted_resources WHERE resource_uid=%s",
                (second["resource_uid"],),
            ).fetchone()
            self.assertEqual(saved["stage"], 1)
            receipts = list(
                db.execute(
                    "SELECT success,probability FROM planting_receipts WHERE character_id=%s",
                    (character["id"],),
                )
            )
            self.assertEqual(len(receipts), 2)
            self.assertTrue(all(row["success"] for row in receipts))
            self.assertTrue(all(row["probability"] == 0.9 for row in receipts))
        # Leave the shared native cell free for the next crop's independent
        # lifecycle; this cleanup uses the same ordinary terminal harvest.
        self._mature_one_edge(runtime, account, generation, second["resource_uid"], 2)
        self._mature_one_edge(runtime, account, generation, second["resource_uid"], 3)
        cleanup = self._harvest(account, generation, character, final_action)
        self.assertEqual(cleanup["outcome"]["stage"], 0)
        self.assertEqual(runtime.snapshots(self.map_id, 0), [])

    def test_fresno_and_cardo_plant_grow_yield_cut_replant_and_survive_reopen(self):
        with self.store.connection() as db:
            policy = db.execute(
                "SELECT value FROM settings WHERE name='open_planting_probability'"
            ).fetchone()["value"]
        self.assertEqual(policy, 0.01)
        self._run_crop(
            seed_reference=8063,
            profession_id=71,
            name="Fresno Lifecycle",
            seed_action=538,
            final_action=99,
            final_product=1723,
        )
        self._run_crop(
            seed_reference=4275,
            profession_id=72,
            name="Cardo Lifecycle",
            seed_action=100,
            final_action=203,
            final_product=2504,
        )
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT value FROM settings WHERE name='open_planting_probability'"
                ).fetchone()["value"],
                policy,
            )


if __name__ == "__main__":
    unittest.main()
