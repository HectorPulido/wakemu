"""Owned movement flow against isolated PostgreSQL and map 1388 terrain."""
import random
import struct
from threading import RLock
from unittest.mock import patch

from psycopg.types.json import Jsonb
from postgres_case import PostgresCase
from wakfu_server.achievements import (
    rii_owned_lesson as owned,
    rii_training_arena as arena,
    rii_movement_contract as movement,
    storage,
)
from wakfu_server.combat_terrain import local_arena
from wakfu_server.combat_state import Fight
from wakfu_server.combat_geometry_snapshot import freeze_terrain
from wakfu_server.combat_qi_fight import (
    prepare_fresh_actor_slots,
    install_fresh_actor_slots,
)
from wakfu_server.combat_global_pv_collections import initialize_global_pv_collections
from wakfu_server.combat_server_spell import prepare_server_spell
from wakfu_server.spells import encode_deck
import test_combat_spell_transaction as fixture_module


class MovementFlowPostgresTests(PostgresCase):
    def test_floor_spawn_four_native_casts_settle_and_return(self):
        account = self.store.register("rii-movement-flow", "test-password")["id"]
        character = self.store.create_character(account, "Rii Movement")
        generation = self.store.begin_session(account)
        selected = self.store.select_character(account, generation, character["id"])
        native = {
            "d": 5143,
            "native_class": "aJM",
            "aqb": False,
            "cjI": "",
            "cjK": [],
            "cjJ": [
                {"d": objective, "ckc": "", "cke": ""}
                for objective in (10574, 10575, 10576, 10608, 10609, 10610, 10611)
            ],
        }
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO native_quest_metadata_releases(revision,source_sha256,source_export,definition_count) VALUES (%s,%s,%s,1)",
                ("d" * 64, Jsonb({}), b"fixture"),
            )
            db.execute(
                "INSERT INTO native_quest_metadata_definitions(revision,definition_id,data) VALUES (%s,5143,%s)",
                ("d" * 64, Jsonb({"native": native})),
            )
            state = storage.load_locked(db, character["id"])
            state["running"], state["objectives"] = [5143], [
                10574,
                10575,
                10576,
                10608,
                10609,
            ]
            storage.store(db, character["id"], state)
        with patch(
            "wakfu_server.characters.dungeon_modulation_health.reconcile",
            return_value=(),
        ):
            source = self.store.transition_map(
                account,
                generation,
                character["id"],
                selected,
                dict(map_id=1388, instance_id=0, x=1, y=-19, z=3),
            )
            floor = arena.enter(
                self.store,
                account,
                generation,
                source,
                10610,
                available=lambda pos: True,
            )
        marked = dict(floor, _rii_training_objective=10610)

        class Groups:
            lock = RLock()

            def available(self, *args):
                return []

            def register_transaction(self, db, map_id, instance_id, group_id, members):
                self.members = members

        groups = Groups()

        def instance(ref, level, identity, **location):
            return {"id": identity, "ref": ref, **location}

        with patch("wakfu_server.monsters.owned_instance", side_effect=instance), patch(
            "wakfu_server.combat_monster_world.spawn_group", return_value=b"spawn"
        ):
            self.assertEqual(
                owned.spawn(
                    self.store, groups, account, generation, marked, owned.MOVEMENT
                ),
                (12608, b"spawn"),
            )
        self.assertTrue(arena.setup_is_ready(self.store, account, character["id"]))
        monster = groups.members[0]
        with self.store.connection() as db:
            self.assertTrue(owned.admit(db, owned.MOVEMENT, character["id"], [monster]))
            contract = owned.bind(db, owned.MOVEMENT, character["id"], [monster])
        # Build fresh QI from the real floor and spawned sack positions. The
        # fixture supplies native actor properties, not arena geometry.
        fixture = fixture_module.SpellTransactionTests()
        actor_character, fixture_monster, seed = fixture.native_server_fixture(
            3, 15, native_qi=True, target_ref=5466
        )
        owner, sack = seed.actors[7], seed.actors[-7]
        owner.id, owner.owner_id = character["id"], account
        sack.id = monster["id"]
        for actor in (owner, sack):
            actor.native_departure_flags["actor_id"] = actor.id
            actor.state_ledger.actor_id = actor.id
        owner.position = tuple(floor[k] for k in ("x", "y", "z"))
        sack.position = tuple(monster[k] for k in ("x", "y", "z"))
        terrain = local_arena(
            1388, 0, owner.position, sack.position, relocate_monsters=False
        )
        fight = Fight(
            77,
            [owner, sack],
            terrain["validated_cells"],
            {0: {owner.position}, 1: {sack.position}},
            terrain["valid_edges"],
        )
        fight.native_qi_snapshot = {
            name: terrain[name] for name in ("x", "y", "width", "height", "cell_masks")
        }
        fight.native_qi_surface_provenance = dict(
            terrain["native_qi_surface_provenance"]
        )
        freeze_terrain(fight)
        initialize_global_pv_collections(fight, (owner.id, sack.id))
        slots = prepare_fresh_actor_slots(
            fight,
            physical_radii={
                owner.id: owner.physical_radius,
                sack.id: sack.physical_radius,
            },
        )
        install_fresh_actor_slots(fight, slots)
        fight.ready(account)
        fight.native_effect_uid_next = 1
        fight.native_obstacle_cells = frozenset()
        fight.rii_movement_lesson_contract = contract
        actor_character.update(id=owner.id, account_id=account, map_id=1388)
        fixture_monster.update(id=sack.id, map_id=1388)
        movement.initialize(fight, [], action_id=1)
        action = 2
        for index in range(1, 5):
            owner, sack = fight.actors[owner.id], fight.actors[sack.id]
            fight._refill_turn_resources(owner)
            marker = tuple(fight.rii_movement_lesson_contract["marker"])
            if index < 4:
                dx, dy = marker[0] - sack.position[0], marker[1] - sack.position[1]
                x, y, z = sack.position
                plans = (
                    (7973, (x - dx, y - dy, z)),
                    (7972, (x + 2 * dx, y + 2 * dy, z)),
                )
                spell, stand = next(
                    (spell, stand)
                    for spell, stand in plans
                    if stand in fight.walkable
                    and abs(stand[0] - owner.position[0])
                    + abs(stand[1] - owner.position[1])
                    <= 4
                    and movement._native_plan_valid(fight, owner, sack, marker, stand)
                )
                if stand != owner.position:
                    try:
                        from wakfu_server import combat_casting_context as cctx

                        evaluate = cctx.evaluate_condition
                        facts = {
                            "ledgers": {
                                i: [
                                    (x.reference, x.level, x.uid)
                                    for x in a.state_ledger.entries
                                ]
                                for i, a in fight.actors.items()
                            },
                            "records": list(fight.native_retained_order),
                        }

                        def traced(raw, ctx):
                            if "IsTargetCellFree()" in raw and "8011" in raw:
                                facts["cell"] = evaluate("IsTargetCellFree()", ctx)
                                facts["state"] = ctx.state_max_level_query(
                                    -1, -1, "caster", 8011, ""
                                )
                            return evaluate(raw, ctx)

                        with patch.object(
                            cctx, "evaluate_condition", side_effect=traced
                        ):
                            result = prepare_server_spell(
                                struct.pack(">qqiih", owner.id, 7974, *stand),
                                actor_character,
                                {sack.id: fixture_monster},
                                fight,
                                account,
                                encode_deck([]),
                                action_id=action,
                                line_of_sight=lambda *a: True,
                                critical=False,
                                rng=random.Random(1),
                            )
                    except ValueError as exc:
                        raise AssertionError(
                            f'teleport {index=} {stand=} {owner.position=} {marker=} {facts=} diagnostic={getattr(exc, "native_casting_diagnostic", None)}'
                        ) from exc
                    fight, action = result.fight, action + 1
                    self.assertEqual(fight.actors[owner.id].position, stand)
                fight._refill_turn_resources(fight.actors[owner.id])
            else:
                spell = 7975
                fight._refill_turn_resources(owner)
            result = prepare_server_spell(
                struct.pack(">qqiih", owner.id, spell, *fight.actors[sack.id].position),
                actor_character,
                {sack.id: fixture_monster},
                fight,
                account,
                encode_deck([]),
                action_id=action,
                line_of_sight=lambda *a: True,
                critical=False,
                rng=random.Random(1),
            )
            fight, action = result.fight, action + 1
            self.assertEqual(fight.rii_movement_lesson_contract["hits"], index)
        self.assertEqual((fight.phase, fight.winner), ("finished", 0))
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO combat_fights(id,status,fight_kind) OVERRIDING SYSTEM VALUE VALUES(77,'finished','pve')"
            )
            db.execute(
                "INSERT INTO combat_fight_participants(fight_id,character_id,account_id,team) VALUES(77,%s,%s,0)",
                (owner.id, account),
            )
            packets = owned.settle_participants(
                db,
                self.store,
                owned.MOVEMENT,
                fight,
                [
                    {
                        "character_id": owner.id,
                        "account_id": account,
                        "session_generation": generation,
                    }
                ],
                [monster],
                contract_name="rii_movement_lesson_contract",
            )
            self.assertIn(account, packets)
        with self.reopen().connection() as db:
            self.assertIn(10610, storage.load_locked(db, owner.id)["objectives"])
        with patch(
            "wakfu_server.characters.dungeon_modulation_health.reconcile",
            return_value=(),
        ):
            returned = arena.return_to_source(
                self.store,
                account,
                generation,
                floor,
                available=lambda p: True,
                only_completed=True,
            )
        self.assertEqual(
            tuple(returned[k] for k in arena.POSITION),
            tuple(source[k] for k in arena.POSITION),
        )
