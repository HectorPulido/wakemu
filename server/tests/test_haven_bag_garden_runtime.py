"""Garden planting, growth, harvesting and reconnect use the durable flora engine."""
import struct
import json
from unittest.mock import patch

from postgres_case import PostgresCase


class HavenBagGardenRuntimeTests(PostgresCase):
    def setUp(self):
        super().setUp()
        from wakfu_server.haven_bag_garden import active_character, authorize, reachable
        from wakfu_server.haven_bag_store import save
        from wakfu_server.inventory_items import grant
        from wakfu_server.planting import SEEDS
        from wakfu_server.planting_runtime import Plantings
        from wakfu_server.planting_probability import resolver
        from wakfu_server.profession_store import ensure_learned
        from wakfu_server.combat_groups import Groups
        from wakfu_server import resource_collect
        from wakfu_server.wire import proto_field

        self.active_character = active_character
        self.authorize = authorize
        self.reachable = reachable
        self.save_haven_bag = save
        self.grant_item = grant
        self.seeds = SEEDS
        self.Plantings = Plantings
        self.planting_resolver = resolver
        self.ensure_learned = ensure_learned
        self.Groups = Groups
        self.resource_collect = resource_collect
        self.proto_field = proto_field

    def test_plant_grow_harvest_reentry_without_moving_exterior_or_other_instance(self):
        self._exercise_garden()

    def test_guest_garden_consumes_and_rewards_only_the_visitors_inventory(self):
        self._exercise_garden(guest=True)

    def test_private_ranch_owner_plant_grow_harvest_and_reentry(self):
        self._exercise_garden(ranch=True)

    def test_private_ranch_visitor_uses_own_seeds_and_receives_own_rewards(self):
        self._exercise_garden(guest=True, ranch=True)

    def test_external_ranch_owner_scalar_prepare_and_begin_prepared(self):
        self._exercise_garden(ranch=True, external=True)

    def test_external_ranch_visitor_scalar_prepare_and_begin_prepared(self):
        self._exercise_garden(guest=True, ranch=True, external=True)

    def _exercise_garden(self, *, guest=False, ranch=False, external=False):
        if ranch:
            with patch(
                "wakfu_server.planting_cells.private_surfaces", return_value=[{"z": 4}]
            ), patch(
                "wakfu_server.combat_terrain.map_geometry",
                return_value={
                    "cells": [(7, 2, 4), (7, 3, 4)],
                    "edges": [((7, 2, 4), (7, 3, 4))],
                },
            ):
                return self._exercise_garden_runtime(
                    guest=guest, ranch=True, external=external
                )
        return self._exercise_garden_runtime(guest=guest)

    def _exercise_garden_runtime(self, *, guest=False, ranch=False, external=False):
        map_id = 1440 if ranch else 9
        now = [1000.0]
        self.store.clock = lambda: now[0]
        account = self.store.register("garden-runtime", "local-password")["id"]
        character = self.store.create_character(account, "Garden Runtime")
        generation = self.store.begin_session(account)
        self.store.select_character(account, generation, character["id"])
        exterior = {
            key: character[key] for key in ("map_id", "instance_id", "x", "y", "z")
        }
        rooms = character["haven_bag"]["rooms"]
        rooms[3].update(enabled=True, primary_ref=4266, primary_uid=900001)
        character = self.save_haven_bag(
            self.store, account, generation, character["id"], rooms=rooms
        )
        owner = character
        bag_id = character["haven_bag"]["owner_id"]
        if guest:
            account = self.store.register("garden-guest", "local-password")["id"]
            character = self.store.create_character(account, "Garden Guest")
            generation = self.store.begin_session(account)
            self.store.select_character(account, generation, character["id"])
            exterior = {key: character[key] for key in exterior}
        self.ensure_learned(self.store, account, generation, character["id"], [72])
        seed = self.grant_item(
            self.store,
            account,
            generation,
            character["id"],
            reference=4275,
            quantity=2,
            container=character["inventory_containers"][0]["uid"],
            slot=0,
            allowed_references=self.seeds,
        )
        live = [
            dict(
                character,
                map_id=map_id,
                instance_id=bag_id,
                x=7,
                y=2,
                z=4 if ranch else 0,
                haven_ranch_session=ranch,
                haven_bag=owner["haven_bag"],
                haven_bag_visitor=guest,
            )
        ]
        context = (
            lambda stored: self.active_character(stored, live, store=self.store)
            if ranch
            else self.active_character(stored, live)
        )
        runtime = self.Plantings(
            self.store,
            location_context=context,
            probability_context=self.planting_resolver(
                self.store, profession_bonus=lambda prepared: 0
            ),
        )
        body = struct.pack(">iqii", self.seeds[4275]["action_id"], seed["uid"], 7, 3)
        if external:
            from wakfu_server.ecology_planting_intents import (
                EcologyPlantingIntents,
                prepare_intents,
            )

            intents = EcologyPlantingIntents(self.store, "ranch-boot")
            runtime.ecology_intents = intents
            intents.enqueue(account, generation, live[0], body)
            scalar = {
                key: live[0][key]
                for key in ("id", "account_id", "map_id", "instance_id", "x", "y", "z")
            }
            with self.store.connection() as db:
                started_at_ms = db.execute(
                    "SELECT (extract(epoch FROM clock_timestamp()) * 1000)::bigint AS value"
                ).fetchone()["value"]
            with patch("wakfu_server.planting_bonus.current", return_value=0):
                plan = prepare_intents(
                    self.store,
                    {
                        "world_epoch": "ranch-boot",
                        "players": [scalar],
                        "open_planting": False,
                        "started_at_ms": started_at_ms,
                    },
                )[0]
            self.assertEqual(plan["kind"], "planting_begin", plan)
            plan = json.loads(json.dumps(plan))
            self.assertNotIn("haven_bag", plan["prepared"]["character"])
            self.assertNotIn("haven_ranch_session", plan["prepared"]["character"])

            def accept(db, accepted):
                return runtime.begin_prepared(
                    account,
                    generation,
                    live[0],
                    body,
                    accepted["prepared"],
                    lambda *args: self.authorize(self.store, *args),
                    db=db,
                )

            self.assertTrue(intents.apply(plan, accept)["applied"])
        else:
            runtime.begin(
                account,
                generation,
                live[0],
                body,
                lambda *args: self.authorize(self.store, *args),
            )
        now[0] += 3
        with patch("wakfu_server.planting.secrets.randbelow", return_value=0):
            result = runtime.complete(account, generation, live[0], b"\x02\x00\x02")
        self.assertTrue(result["applied"])
        self.assertEqual(result["character"]["map_id"], map_id)
        self.assertEqual(result["ecology"]["reason"], "private_haven_bag_garden")
        self.assertEqual(len(runtime.snapshots(map_id, bag_id)), 1)
        self.assertEqual(runtime.snapshots(map_id, bag_id + 1), [])
        stored = self.store.character(account, character["id"])
        self.assertEqual({key: stored[key] for key in exterior}, exterior)
        self.assertEqual(stored["inventory_items"][0]["quantity"], 1)
        now[0] += 30
        runtime.mature(self.Groups(), publish=lambda event: None)
        self.assertEqual(
            len(self.Plantings(self.reopen()).snapshots(map_id, bag_id)), 1
        )
        harvest = b"".join(
            (self.proto_field(8, 201), self.proto_field(16, 7), self.proto_field(24, 3))
        )
        prepared = self.resource_collect.prepare(
            self.store,
            account,
            generation,
            character["id"],
            harvest,
            reachable=self.reachable,
            location_context=context,
        )
        with self.store.connection() as db:
            profession_before = db.execute(
                "SELECT xp FROM account_professions WHERE account_id=%s AND profession_id=72",
                (account,),
            ).fetchone()["xp"]
        ticket = self.resource_collect.reserve(
            self.store, account, generation, prepared, location_context=context
        )
        now[0] += prepared["rule"]["duration_ms"] / 1000
        result = self.resource_collect.complete(
            self.store, ticket, b"\x02\x00\x03", location_context=context
        )
        self.assertTrue(result["applied"])
        with self.store.connection() as db:
            profession_after = db.execute(
                "SELECT xp FROM account_professions WHERE account_id=%s AND profession_id=72",
                (account,),
            ).fetchone()["xp"]
        self.assertGreater(profession_after, profession_before)
        self.assertEqual(result["map_id"], map_id)
        self.assertEqual(result["instance_id"], bag_id)
        self.assertTrue(
            any(
                i["reference"] == 2504
                for i in self.store.character(account, character["id"])[
                    "inventory_items"
                ]
            )
        )
        if guest:
            stored_owner = self.store.character(owner["account_id"], owner["id"])
            self.assertEqual(stored_owner["inventory_items"], owner["inventory_items"])
        self.assertFalse(
            self.resource_collect.complete(
                self.store, ticket, b"\x02\x00\x03", location_context=context
            )["applied"]
        )
