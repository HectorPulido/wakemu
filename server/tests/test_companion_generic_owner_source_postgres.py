"""A real companion NPC runs its fully admitted 13574 source through Ready."""
import struct
import unittest

import test_companion_combat_lifecycle_postgres as _fixture


class CompanionGenericOwnerSourcePostgresTests(unittest.TestCase):
    def setUp(self):
        self.fixture = _fixture.CompanionCombatLifecyclePostgresTests()
        self.addCleanup(self.fixture.doCleanups)
        self.fixture.setUp()

    def _owned(self, uid):
        f = self.fixture
        with f.store.connection() as db:
            return db.execute(
                "SELECT uid,character_id,reference,quantity FROM inventory_items "
                "WHERE uid=%s AND character_id=%s",
                (uid, f.main["id"]),
            ).fetchone()

    def test_13574_companion_source_preflight_ready_checkpoint_and_clear(self):
        from wakfu_server import (
            companion_equipment,
            combat_companion_owned_equipment_adapter,
        )
        from wakfu_server import health_store
        from wakfu_server import fight_store
        from wakfu_server.character_levels import XP_BY_LEVEL
        from wakfu_server.combat_actor_snapshot import initialize_fight_snapshots
        from wakfu_server.combat_companions import admit_owned_companions
        from wakfu_server.combat_global_pv_collections import (
            initialize_global_pv_collections,
        )
        from wakfu_server.combat_session_adapter import CombatSessionAdapter
        from wakfu_server.combat_state import Actor, Fight
        from wakfu_server.combat_terrain import local_arena
        from wakfu_server.combat_geometry_snapshot import freeze_terrain
        from wakfu_server.fight_checkpoint_store import Checkpoints
        from wakfu_server.equipment import RULES
        from wakfu_server.equipment_stats import CATALOG, combat_resources
        from wakfu_server.inventory_items import grant
        from wakfu_server.builds import effective_sheet_level
        from wakfu_server.monsters import owned_instance
        from wakfu_server.spells import default_deck

        f = self.fixture
        store = f.store
        from wakfu_server.characters import companions

        f.container = next(
            row["uid"] for row in f.main["inventory_containers"] if row["kind"] == 0
        )
        # The actual native graph is level 75+ and occupies companion slot 7.
        with store.connection() as db:
            db.execute("UPDATE characters SET level=75 WHERE id=%s", (f.main["id"],))
            db.execute(
                "UPDATE character_progression SET xp=%s WHERE character_id=%s",
                (XP_BY_LEVEL[75], f.main["id"]),
            )
            db.execute(
                "UPDATE account_companions SET xp=%s WHERE id=%s",
                (XP_BY_LEVEL[75], f.companion_id),
            )
        main = health_store.initialize(store, f.account, f.generation, f.main["id"])
        f.main = main
        self.assertEqual([7, 8], RULES[13574]["slots"])
        self.assertGreaterEqual(75, RULES[13574]["minimum_level"])
        self.assertIn(13574, CATALOG)

        # Close the setup placement so the ordinary opcode-save fence permits
        # equipment custody before the actual combat placement is created.
        self.assertTrue(
            fight_store.abort(
                store,
                f.account,
                f.main["id"],
                f.fight_id,
                expected_generation=f.generation,
            )
        )
        # Add a second real, distinct native companion. Both carry the same
        # complete graph so this exercises repeated pin composition, rather
        # than only a one-NPC Ready path.
        first_breed = None
        with store.connection() as db:
            first_breed = db.execute(
                "SELECT breed_ref FROM account_companions WHERE id=%s",
                (f.companion_id,),
            ).fetchone()["breed_ref"]
        second_descriptor = next(
            row
            for row in sorted(
                companions.descriptors().values(), key=lambda value: value["item_ref"]
            )
            if row["breed_ref"] != first_breed
        )
        activation = grant(
            store,
            f.account,
            f.generation,
            f.main["id"],
            reference=second_descriptor["item_ref"],
            quantity=1,
            container=f.container,
            slot=0,
            allowed_references={second_descriptor["item_ref"]},
        )
        second = companions.use(
            store,
            f.account,
            f.generation,
            f.main["id"],
            struct.pack(">iq", second_descriptor["action_id"], activation["uid"]),
            in_fight=False,
        )["companion"]
        second_id = second["id"]
        companions.add_to_party(
            store, f.account, f.generation, f.main["id"], struct.pack(">q", second_id)
        )
        with store.connection() as db:
            db.execute(
                "UPDATE account_companions SET xp=%s WHERE id=ANY(%s)",
                (XP_BY_LEVEL[75], [f.companion_id, second_id]),
            )
        item = grant(
            store,
            f.account,
            f.generation,
            f.main["id"],
            reference=13574,
            quantity=1,
            container=f.container,
            slot=1,
            allowed_references={13574},
        )
        second_item = grant(
            store,
            f.account,
            f.generation,
            f.main["id"],
            reference=13574,
            quantity=1,
            container=f.container,
            slot=2,
            allowed_references={13574},
        )
        native_calls = []

        def native_admission(companion, owner, entries, level):
            result = combat_companion_owned_equipment_adapter.preflight_custody(
                owner, companion, entries, level
            )
            native_calls.append((level, result))
            return result

        # This is the opcode 13191 save API with the same real preflight
        # callback wired by local_game_server; it is not a direct handler bypass.
        saved = companion_equipment.save(
            store,
            f.account,
            f.generation,
            f.main["id"],
            f._save_body(f.companion_id, item["uid"], slot=7),
            in_fight=False,
            native_admission=native_admission,
        )
        second_saved = companion_equipment.save(
            store,
            f.account,
            f.generation,
            f.main["id"],
            f._save_body(second_id, second_item["uid"], slot=7),
            in_fight=False,
            native_admission=native_admission,
        )
        self.assertEqual(12646, saved["packets"][2][0])
        self.assertEqual(12646, second_saved["packets"][2][0])
        self.assertEqual(2, len(native_calls))
        self.assertEqual("supported", native_calls[0][1]["status"])
        self.assertEqual("supported", native_calls[1][1]["status"])
        self.assertIsNone(self._owned(item["uid"]))
        self.assertIsNone(self._owned(second_item["uid"]))

        # Build a fresh, real owner placement at the persisted level and admit
        # the account-owned companion through the ordinary production path.
        fight_id = fight_store.create(
            store, f.account, f.generation, f.main["id"], team=0
        )
        resources = combat_resources(main)
        player_position = (main["x"], main["y"], main["z"])
        player = Actor(
            main["id"],
            0,
            player_position,
            main["hp"],
            resources["ap"],
            resources["mp"],
            resources["initiative"],
            effective_sheet_level(main, main.get("active_build_index", 0)),
            f.account,
            True,
            max_hp=main["max_hp"],
        )
        player.initiative = -1
        enemy_position = (-4, -17, 0)
        enemy = owned_instance(
            5525,
            1,
            -200,
            map_id=1134,
            x=enemy_position[0],
            y=enemy_position[1],
            z=enemy_position[2],
            team=1,
        )
        opponent = Actor(
            -200,
            1,
            enemy_position,
            enemy["hp"],
            enemy["ap"],
            enemy["mp"],
            enemy["initiative"],
            enemy["level"],
            max_hp=enemy["max_hp"],
        )
        opponent.initiative = -100
        arena = local_arena(
            1134, 0, player_position, enemy_position, relocate_monsters=False
        )
        fight = Fight(
            fight_id,
            [player, opponent],
            arena["validated_cells"],
            arena["placement_cells"],
            arena["valid_edges"],
        )
        fight.native_qi_snapshot = {
            key: arena[key] for key in ("x", "y", "width", "height", "cell_masks")
        }
        fight.native_qi_surface_provenance = dict(arena["native_qi_surface_provenance"])
        freeze_terrain(fight)
        initialize_global_pv_collections(
            fight, (player.id, opponent.id), controller_registration=True
        )
        initialize_fight_snapshots(
            fight,
            characters={player.id: main},
            monsters={opponent.id: enemy},
            wp_resources={
                player.id: (resources["wp"], resources["wp"]),
                opponent.id: (enemy["wp"], enemy["wp"]),
            },
            running_effects={player.id: (), opponent.id: ()},
            initial_effect_uid=1,
        )
        with store.connection() as db:
            admitted = admit_owned_companions(
                db, store, f.session, fight, owner_character=main
            )
        adapter = CombatSessionAdapter(store)
        ready = adapter.ready_transition(
            f.session, admitted["fight"], None, True, {-200: enemy}
        )
        active = ready.fight
        actors, sources, pins = {}, {}, {}
        for companion_id, expected_item in (
            (f.companion_id, item),
            (second_id, second_item),
        ):
            actor = active.actors[companion_id]
            source = active.native_companion_sources[str(companion_id)]
            self.assertEqual(5, source["native_actor_type"])
            self.assertEqual(f.account, actor.owner_id)
            self.assertEqual(
                expected_item["uid"],
                source["equipment_entries"][0]["entry"]["item"]["uid"],
            )
            pin = active.native_owned_equipment_sources[str(companion_id)]
            self.assertEqual([67259], [row["roots"][0] for row in pin["sources"]])
            self.assertTrue(pin["sources"][0]["_generic_operation_admission"])
            actors[companion_id], sources[companion_id], pins[companion_id] = (
                actor,
                source,
                pin,
            )
        player_characters, _decks = adapter.player_sources(active)
        self.assertEqual({f.main["id"]}, set(player_characters))
        self.assertNotIn(f.companion_id, player_characters)
        self.assertNotIn(second_id, player_characters)

        factory, _ = __import__(
            "wakfu_server.combat_server_spell", fromlist=["server_runtime"]
        ).server_runtime(
            main, {-200: enemy}, default_deck(main), action_id=9001, critical=False
        )
        for actor in actors.values():
            authority = factory.summon_authority(active, actor)
            self.assertEqual(5, authority.native_actor_type)
            self.assertIs(authority.native_is_ehp, False)

        checkpoints = Checkpoints(store)
        revision = checkpoints.save(f.account, f.generation, active)
        saved_checkpoint = checkpoints.read(f.account, fight_id)
        recovered = checkpoints._read_snapshot(saved_checkpoint["snapshot"])
        self.assertEqual(revision, saved_checkpoint["revision"])
        for companion_id, expected_item in (
            (f.companion_id, item),
            (second_id, second_item),
        ):
            restored_source = recovered["native_companion_sources"][str(companion_id)]
            self.assertEqual(5, restored_source["native_actor_type"])
            self.assertEqual(
                expected_item["uid"],
                restored_source["equipment_entries"][0]["entry"]["item"]["uid"],
            )
        self.assertEqual("active", recovered["phase"])

        self.assertTrue(
            fight_store.abort(
                store,
                f.account,
                f.main["id"],
                fight_id,
                expected_generation=f.generation,
            )
        )
        for companion_id, expected_item in (
            (f.companion_id, item),
            (second_id, second_item),
        ):
            companion_equipment.save(
                store,
                f.account,
                f.generation,
                f.main["id"],
                struct.pack(">qhBb", companion_id, 1, 0, 7),
                in_fight=False,
            )
            self.assertIsNotNone(self._owned(expected_item["uid"]))
        with store.connection() as db:
            self.assertEqual(
                0,
                db.execute(
                    "SELECT count(*) AS n FROM companion_equipment WHERE companion_id=ANY(%s)",
                    ([f.companion_id, second_id],),
                ).fetchone()["n"],
            )


if __name__ == "__main__":
    unittest.main()
