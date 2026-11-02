"""Isolated PG coverage for the source-qualified 33366 scene start."""
import json
import os
import struct
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from psycopg.types.json import Jsonb
from postgres_case import PostgresCase

CONFIGURATION = os.environ.get("WAKFU_TEST_TOWER_CONFIGURATION")


@unittest.skipUnless(
    os.environ.get("WAKFU_TEST_TOWER_TEMPORAL") == "1",
    "Opt-in native Tower temporal journey",
)
class TowerTemporalTests(PostgresCase):
    def setUp(self):
        super().setUp()
        from postgres_owned_schema_cleanup import empty_owned_schema

        with self.store.connection() as db:
            schema = db.execute("SELECT current_schema() AS name").fetchone()["name"]
        artifact_dir = Path(
            os.environ.get("WAKFU_TEST_TOWER_ARTIFACT_DIR", tempfile.gettempdir())
        )
        artifact_dir.mkdir(parents=True, exist_ok=True)
        (
            artifact_dir
            / (
                "schema-profile"
                + os.environ.get("WAKFU_TEST_TOWER_PROFILE", "0")
                + ".txt"
            )
        ).write_text(schema)
        self.addCleanup(empty_owned_schema, self.store, schema)

    def test_native_temporal_cycle(self):
        from wakfu_server import (
            combat_terrain,
            dungeon_difficulty,
            dungeon_entry_access,
            dungeon_instances,
            dungeon_runtime,
            dungeon_runtime_config,
            dungeon_transport,
            native_scene_start,
            special_instance_admission,
            teleporter_approach,
        )
        from wakfu_server.combat_group_store import PersistentGroups
        from wakfu_server.inventory_items import grant
        from wakfu_server.maps.movement import Movement

        if not CONFIGURATION:
            raise ValueError("Qualified Tower configuration path is required")
        config = json.loads(Path(CONFIGURATION).read_text())
        contract = json.loads(
            Path(special_instance_admission.__file__)
            .with_name("native_special_instance_admission.json")
            .read_text()
        )
        route = config["route"]
        body = struct.pack(
            ">qiBi", route["entry_object_id"], route["destination_id"], 0, 2
        )
        with self.store.connection() as db:
            dungeon_runtime_config.install_configuration(db, config)
            db.execute(
                "INSERT INTO settings(name,value) VALUES('dungeon_runtime_routes',%s) "
                "ON CONFLICT(name) DO UPDATE SET value=EXCLUDED.value",
                (Jsonb({"schema_version": 1, "routes": [route]}),),
            )
            db.execute(
                "INSERT INTO settings(name,value) VALUES('native_special_instance_admission',%s) "
                "ON CONFLICT(name) DO UPDATE SET value=EXCLUDED.value",
                (Jsonb(contract),),
            )
            native_scene_start.install(db)

        dungeon_instances.load_runtime_routes(self.store)
        leader_account = self.store.register(
            "scene-leader-" + str(id(self)), "qa-only-password"
        )["id"]
        leader = self.store.create_character(leader_account, "Scene Leader")
        leader_generation = self.store.begin_session(leader_account)
        leader = self.store.select_character(
            leader_account, leader_generation, leader["id"]
        )
        payer_account = self.store.register(
            "scene-payer-" + str(id(self)), "qa-only-password"
        )["id"]
        payer = self.store.create_character(payer_account, "Scene Payer")
        payer_generation = self.store.begin_session(payer_account)
        payer = self.store.select_character(
            payer_account, payer_generation, payer["id"]
        )
        leader_id, payer_id = leader["id"], payer["id"]

        from wakfu_server.character_levels import XP_BY_LEVEL

        with self.store.connection() as db:
            db.execute(
                "UPDATE characters SET level=50,map_id=1202,instance_id=0,x=-22,y=-7,z=0 WHERE id=ANY(%s)",
                ([leader_id, payer_id],),
            )
            db.execute(
                "UPDATE character_progression SET xp=%s WHERE character_id=ANY(%s)",
                (XP_BY_LEVEL[50], [leader_id, payer_id]),
            )
            payer_row = self.store.character(payer_account, payer_id, db)
            bag = payer_row["inventory_containers"][0]
            grant(
                self.store,
                payer_account,
                payer_generation,
                payer_id,
                reference=28028,
                quantity=1,
                container=bag["uid"],
                slot=0,
                allowed_references={28028},
                db=db,
            )
            party_id = db.execute(
                "INSERT INTO player_parties(leader_id) VALUES(%s) RETURNING id",
                (leader_id,),
            ).fetchone()["id"]
            db.execute(
                "INSERT INTO player_party_members(character_id,party_id) VALUES(%s,%s),(%s,%s)",
                (leader_id, party_id, payer_id, party_id),
            )

        def current(account, identity):
            return self.store.character(account, identity)

        def enter_criterion(actor, expression):
            return dungeon_entry_access.evaluate(
                self.store, expression, character=actor, destination_map_id=1159
            )

        result = dungeon_transport.enter(
            self.store,
            leader_account,
            leader_generation,
            leader_id,
            1202,
            body,
            criterion_allowed=enter_criterion,
            source_allowed=teleporter_approach.callback(
                Movement(current(leader_account, leader_id)), map_id=1202, instance_id=0
            ),
            resolve_destination=dungeon_runtime.entry_destination,
            initialize_instance=lambda db, session: dungeon_runtime.initialize_instance(
                db,
                session,
                groups=PersistentGroups(self.store),
                geometry=combat_terrain.map_geometry(1159),
            ),
        )
        instance_id = result["instance_id"]
        self.assertEqual(result["destination"]["map_id"], 1159)
        self.assertNotIn("entry_item_payment", result)
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM combat_groups WHERE instance_id=%s",
                    (instance_id,),
                ).fetchone()["n"],
                0,
                "33366 must gate room spawning until scene start",
            )

        # Durable Store moves put each active member on a distinct native approach.
        for account, generation, identity, point in (
            (leader_account, leader_generation, leader_id, (11, 1, 1)),
            (payer_account, payer_generation, payer_id, (11, 0, 0)),
        ):
            actor = current(account, identity)
            self.store.move(
                account,
                generation,
                identity,
                {key: actor[key] for key in ("x", "y", "z")},
                dict(zip(("x", "y", "z"), point)),
            )

        def snapshot():
            with self.store.connection() as db:
                return {
                    "receipt_count": db.execute(
                        "SELECT count(*) AS n FROM native_scene_start_receipts WHERE instance_id=%s",
                        (instance_id,),
                    ).fetchone()["n"],
                    "group_count": db.execute(
                        "SELECT count(*) AS n FROM combat_groups WHERE instance_id=%s",
                        (instance_id,),
                    ).fetchone()["n"],
                    "leader_items": db.execute(
                        "SELECT COALESCE(sum(quantity),0) AS n FROM inventory_items WHERE character_id=%s AND reference=28028",
                        (leader_id,),
                    ).fetchone()["n"],
                    "payer_items": db.execute(
                        "SELECT COALESCE(sum(quantity),0) AS n FROM inventory_items WHERE character_id=%s AND reference=28028",
                        (payer_id,),
                    ).fetchone()["n"],
                }

        rule = native_scene_start.binding(config["topology"])
        scene_body = struct.pack(">qHH", rule["source_id"], rule["wire_action"], 0)
        payer_actor = current(payer_account, payer_id)

        # Select a deterministic edge profile for the focused native Ready
        # variants. The selection API and persisted receipt remain production.
        profile_choice = int(os.environ.get("WAKFU_TEST_TOWER_PROFILE", "0"))
        self.assertIn(profile_choice, (0, 7))
        with patch.object(
            native_scene_start.secrets, "randbelow", return_value=profile_choice
        ):
            started = native_scene_start.start(
                self.store,
                payer_account,
                payer_generation,
                payer_actor,
                scene_body,
                groups=PersistentGroups(self.store),
                geometry=combat_terrain.map_geometry(1159),
                blocked=False,
                is_hero=False,
            )
        self.assertFalse(started["replay"])
        self.assertEqual(started["payment"][0]["reference"], 28028)
        self.assertEqual(started["payment"][0]["character_id"], payer_id)
        self.assertEqual(len(started["group"]["members"]), 4)
        self.assertEqual({packet for packet, _ in started["packets"]}, {12344})
        self.assertEqual(len(started["packets"]), 3)
        profile = started["profile"]
        with self.store.connection() as db:
            _, projected = dungeon_runtime.configuration_for_instance(db, instance_id)
            current_room = db.execute(
                "SELECT current_room FROM dungeon_room_runs WHERE instance_id=%s",
                (instance_id,),
            ).fetchone()["current_room"]
            first_room = next(
                row
                for row in projected["topology"]["rooms"]
                if row["order"] == current_room
            )
            scene_room = native_scene_start.scene_room(
                projected["topology"], first_room
            )
            scene = scene_room["encounter_scene"]
            self.assertEqual(len(scene["state_programs"]), 3)
            self.assertEqual(len(scene["native_initial_glyphs"]), 4)
            self.assertEqual(
                [row["level"] for row in scene["state_programs"]],
                [row["level"] for row in profile["native_states"]],
            )

        # Exercise the normal production arena → placement → sealed-scene
        # snapshots → Ready path for this actual four-NPC room group.
        from wakfu_server.combat_actor_snapshot import (
            initialize_fight_snapshots,
            native_actor_catalog,
        )
        from wakfu_server.combat_bootstrap import create_placement
        from wakfu_server.combat_encounter_scene_layout import prepare_encounter_scene
        from wakfu_server.combat_encounter_scene_policy import (
            arena_scene,
            bind_scene,
            scene_state_declarations,
        )
        from wakfu_server.combat_server_spell import prepare_server_initialization
        from wakfu_server.combat_terrain import local_arena
        from wakfu_server.equipment_stats import combat_resources
        from wakfu_server.spells import default_deck

        character = started["character"]
        monsters = {member["id"]: member for member in started["group"]["members"]}
        group_key = (1159, instance_id, started["group"]["group_id"])
        with self.store.connection() as db:
            room_record = dungeon_runtime.combat_room_scene(db, group_key)
            self.assertIsNotNone(room_record)
            self.assertEqual(
                room_record["descriptor"]["policy_id"],
                "wakemu.mineral_tower_36.native_start.v1",
            )
            _, projected_config = dungeon_runtime.configuration_for_instance(
                db, instance_id
            )
            room_anchor = tuple(
                native_scene_start.binding(projected_config["topology"])[
                    "combat_anchor"
                ]
            )
            geometry = combat_terrain.map_geometry(1159)
        # The 33366 approach is outside this scene's combat subregion. Move
        # the test participant to its source-pinned combat anchor before
        # exercising the Ready path; this does not claim client movement.
        old_position = {key: character[key] for key in ("x", "y", "z")}
        self.store.move(
            payer_account,
            payer_generation,
            payer_id,
            old_position,
            dict(zip(("x", "y", "z"), room_anchor)),
        )
        character = current(payer_account, payer_id)
        catalog = native_actor_catalog()
        member_positions = [
            tuple(member[key] for key in ("x", "y", "z"))
            for member in monsters.values()
        ]
        room_cells = [tuple(cell) for cell in room_record["room_cells"]]
        self.assertTrue(
            all(
                tuple(position) in set(room_cells)
                for position in [
                    tuple(character[key] for key in ("x", "y", "z")),
                    *member_positions,
                ]
            ),
            msg={
                "player": tuple(character[key] for key in ("x", "y", "z")),
                "members": member_positions,
                "room_has": len(room_cells),
                "outside": [
                    tuple(position)
                    for position in [
                        tuple(character[key] for key in ("x", "y", "z")),
                        *member_positions,
                    ]
                    if tuple(position) not in set(room_cells)
                ],
            },
        )
        obstacles = __import__(
            "wakfu_server.combat_encounter_glyph_bootstrap",
            fromlist=["declared_environment_blockers"],
        ).declared_environment_blockers(
            room_record["descriptor"].get("native_initial_glyphs", ())
        )
        arena = local_arena(
            1159,
            character["id"],
            tuple(character[key] for key in ("x", "y", "z")),
            member_positions,
            allowed_cells=room_cells,
            full_room_scope=room_record["descriptor"]["full_room_scope"],
            initial_obstacle_cells=obstacles,
            ordinary_npc_placement=True,
            member_radii=tuple(
                catalog["npc_profiles"][str(m["ref"])]["physical_radius"]
                for m in monsters.values()
            ),
            player_radius=catalog["default_actor_radius"],
        )
        arena = prepare_encounter_scene(character, list(monsters.values()), arena)
        arena = arena_scene(room_record, arena, character, list(monsters.values()))
        resources = combat_resources(character)
        fight, _ = create_placement(
            character,
            list(monsters.values()),
            arena,
            # The room registry's persistent group key is 64-bit; the native
            # fight timeline uses a signed int32 identity. This in-memory Ready
            # probe therefore uses its own isolated fight ID.
            fight_id=100000,
            player_ap=resources["ap"],
            player_mp=resources["mp"],
            player_wp=resources["wp"],
            player_initiative=resources["initiative"],
            terrain_effect_id=arena.get("terrain_effect_id", 46),
            terrain_instance_id=900001,
        )
        bind_scene(fight, arena, monsters)
        # Capture the real DB-produced instance context as an actual outgoing
        # packet, matching the normal socket publication tracker boundary.
        from io import BytesIO
        from wakfu_server.combat_instance_publication import (
            InstancePublicationTracker,
            bind_party_encounter,
        )
        from wakfu_server import dungeon_context

        opcode, body = dungeon_context.update_packet(
            self.store, instance_id, fight_in_progress=False
        )
        tracker = InstancePublicationTracker()
        scope = (
            payer_account,
            payer_generation,
            payer_id,
            character["map_id"],
            instance_id,
        )
        frame = struct.pack(">IH", 6 + len(body), opcode) + body
        transport = BytesIO()
        self.assertEqual(transport.write(frame), len(frame))
        tracker.after_write(transport.getvalue(), scope)
        self.assertTrue(
            bind_party_encounter(
                fight, publications=((tracker, scope),), npc_ids=tuple(monsters)
            )
        )
        initialize_fight_snapshots(
            fight,
            characters={character["id"]: character},
            monsters=monsters,
            wp_resources={
                character["id"]: (resources["wp"], resources["wp"]),
                **{
                    identity: (
                        member.get("wp", 0),
                        member.get("max_wp", member.get("wp", 0)),
                    )
                    for identity, member in monsters.items()
                },
            },
            running_effects={identity: () for identity in fight.actors},
            initial_effect_uid=1,
            scene_state_declarations=scene_state_declarations(fight, monsters),
        )
        fight.ready(payer_account)
        boss_ids = [
            identity for identity, member in monsters.items() if member["ref"] == 4651
        ]
        self.assertEqual(len(boss_ids), 1)
        boss_states = [
            entry.reference for entry in fight.actors[boss_ids[0]].state_ledger.entries
        ]
        self.assertTrue({5279, 5280, 5281}.issubset(boss_states))
        boss_levels = {
            entry.reference: entry.level
            for entry in fight.actors[boss_ids[0]].state_ledger.entries
            if entry.reference in {5279, 5280, 5281}
        }
        self.assertEqual(
            boss_levels,
            {row["id"]: row["level"] for row in profile["native_states"]},
        )
        self.assertEqual(
            sorted(row["reference"] for row in fight.native_effect_areas.values()),
            [1282] * 4,
        )
        deck = default_deck(character)
        ready, _ = prepare_server_initialization(
            character,
            monsters,
            fight,
            payer_account,
            deck,
            action_id=2,
            fight_start=True,
            player_characters={character["id"]: character},
            deck_blobs={character["id"]: deck},
        )
        self.assertTrue(ready.native_start_event_delivered)
        crystal_refs = sorted(
            actor.native_summon_source["ref"]
            for identity, actor in ready.actors.items()
            if identity not in monsters
            and identity != character["id"]
            and isinstance(getattr(actor, "native_summon_source", None), dict)
            and actor.native_summon_source.get("ref") in {4657, 4658, 4659, 4660}
        )
        self.assertEqual(crystal_refs, [4657, 4658, 4659, 4660])
        from wakfu_server.combat_spell_grant import granted_spells

        self.assertTrue({6363, 6364} <= set(granted_spells(ready, payer_id)))
        from tower_temporal_probe import run_temporal

        run_temporal(
            ready,
            {character["id"]: character},
            monsters,
            {character["id"]: deck},
            profile_choice,
        )
