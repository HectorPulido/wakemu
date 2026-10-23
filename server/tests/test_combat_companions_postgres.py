"""PostgreSQL-backed admission and action authority for owned companions."""
import struct
import unittest
import uuid
import json
from pathlib import Path
from unittest.mock import patch

from postgres_case import PostgresCase
from wakfu_server import fight_store
from wakfu_server.characters import companions as companion_domain
from wakfu_server.combat_companions import admit_owned_companions, resolve_action
from wakfu_server.combat_shared import Session
from wakfu_server.combat_state import Actor, Fight
from wakfu_server.combat_actor_snapshot import initialize_fight_snapshots
from wakfu_server.combat_global_pv_collections import initialize_global_pv_collections
from wakfu_server.builds import effective_sheet_level
from wakfu_server.equipment_stats import combat_resources
from wakfu_server.monsters import owned_instance
from wakfu_server.inventory_items import grant


class OwnedCompanionCombatPostgresTests(PostgresCase):
    def setUp(self):
        super().setUp()
        # These two exact native exports were just qualified and are waiting
        # for the next shared catalog release. Keep every other path on the
        # normal immutable PostgreSQL loader used by production.
        from wakfu_server import native_catalog

        original_load = native_catalog.load
        common_files = {
            "native-common-spell-effect-trees.json",
            "native-common-spell-casting-roots.json",
        }

        def load_qualified(path):
            path = Path(path)
            if path.name in common_files:
                return json.loads(path.read_text())
            return original_load(path)

        catalog_patcher = patch.object(
            native_catalog, "load", side_effect=load_qualified
        )
        catalog_patcher.start()
        self.addCleanup(catalog_patcher.stop)
        self.account = self.store.register(
            "companion-fight-" + uuid.uuid4().hex[:10], "local-password"
        )["id"]
        self.main = self.store.create_character(self.account, "Sidekick Owner")
        with self.store.connection() as db:
            db.execute(
                "UPDATE characters SET map_id=1134,instance_id=0,x=-4,y=-18,z=0 WHERE id=%s",
                (self.main["id"],),
            )
        self.main = self.store.character(self.account, self.main["id"])
        self.generation = self.store.begin_session(self.account)
        self.store.select_character(self.account, self.generation, self.main["id"])
        self.session = Session(
            self.account,
            self.main["id"],
            self.generation,
            self.main["map_id"],
            self.main.get("instance_id", 0),
        )
        descriptor = next(
            row
            for row in companion_domain.descriptors().values()
            if row["item_ref"] == 17878
        )
        container = next(
            row["uid"] for row in self.main["inventory_containers"] if row["kind"] == 0
        )
        source = grant(
            self.store,
            self.account,
            self.generation,
            self.main["id"],
            reference=descriptor["item_ref"],
            quantity=1,
            container=container,
            slot=0,
            allowed_references={descriptor["item_ref"]},
        )
        activated = companion_domain.use(
            self.store,
            self.account,
            self.generation,
            self.main["id"],
            struct.pack(">iq", descriptor["action_id"], source["uid"]),
            in_fight=False,
        )
        self.companion_id = activated["companion"]["id"]
        companion_domain.add_to_party(
            self.store,
            self.account,
            self.generation,
            self.main["id"],
            struct.pack(">q", self.companion_id),
        )
        self.fight_id = fight_store.create(
            self.store, self.account, self.generation, self.main["id"], team=0
        )
        player_resources = combat_resources(self.main)
        player = Actor(
            self.main["id"],
            0,
            (self.main["x"], self.main["y"], self.main["z"]),
            self.main["hp"],
            player_resources["ap"],
            player_resources["mp"],
            player_resources["initiative"],
            effective_sheet_level(self.main, self.main.get("active_build_index", 0)),
            self.account,
            True,
            max_hp=self.main["max_hp"],
        )
        # Use the authentic timeline with a deterministic sidekick-first
        # initiative ordering for this disposable integration encounter.
        player.initiative = -1
        enemy_position = (-4, -17, 0)
        enemy = owned_instance(5525, 1, -200, map_id=1134, x=-4, y=-17, z=0, team=1)
        self.enemy = enemy
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
        from wakfu_server.combat_terrain import local_arena
        from wakfu_server.combat_geometry_snapshot import freeze_terrain

        arena = local_arena(
            self.main["map_id"],
            self.main.get("instance_id", 0),
            player.position,
            enemy_position,
            relocate_monsters=False,
        )
        self.fight = Fight(
            self.fight_id,
            [player, opponent],
            arena["validated_cells"],
            arena["placement_cells"],
            arena["valid_edges"],
        )
        self.fight.native_qi_snapshot = {
            key: arena[key] for key in ("x", "y", "width", "height", "cell_masks")
        }
        self.fight.native_qi_surface_provenance = dict(
            arena["native_qi_surface_provenance"]
        )
        freeze_terrain(self.fight)
        initialize_global_pv_collections(
            self.fight, (player.id, opponent.id), controller_registration=True
        )
        initialize_fight_snapshots(
            self.fight,
            characters={player.id: self.main},
            monsters={opponent.id: enemy},
            wp_resources={
                player.id: (player_resources["wp"], player_resources["wp"]),
                opponent.id: (enemy["wp"], enemy["wp"]),
            },
            running_effects={player.id: (), opponent.id: ()},
            initial_effect_uid=1,
        )

    def test_owned_companion_enters_native_placement_with_account_authority(self):
        with self.store.connection() as db:
            result = admit_owned_companions(
                db, self.store, self.session, self.fight, owner_character=self.main
            )
            row = db.execute(
                "SELECT companion_id,account_id,owner_character_id,team,session_generation "
                "FROM combat_fight_companions WHERE fight_id=%s AND companion_id=%s",
                (self.fight_id, self.companion_id),
            ).fetchone()
        self.assertIn(self.companion_id, result["fight"].actors)
        actor = result["fight"].actors[self.companion_id]
        source = result["sources"][self.companion_id]
        self.assertEqual(5, source["native_actor_type"])
        self.assertEqual(self.account, actor.owner_id)
        self.assertTrue(actor.controlled)
        self.assertEqual(self.main["id"], source["owner_character_id"])
        self.assertEqual(self.account, source["account_id"])
        self.assertEqual(
            (self.main["map_id"], self.main["instance_id"]),
            (source["map_id"], source["instance_id"]),
        )
        self.assertEqual(
            (self.companion_id, self.account, self.main["id"], 0, self.generation),
            tuple(row.values()),
        )
        self.assertEqual((12608,), tuple(op for op, _ in result["packets"]))
        self.assertEqual(5, result["packets"][0][1][2])  # actor identity kind
        self.assertEqual(1, actor.native_controlled_by_ai is False)
        self.assertEqual(1, len(result["actors"]))

        from wakfu_server.combat_npc_spellbook import ordinary_npc_spellbook

        book = ordinary_npc_spellbook(result["fight"], actor, source)
        self.assertTrue(book.levels)
        spell_uid = next(iter(book.levels))
        self.assertEqual(
            (spell_uid, book.levels[spell_uid]),
            resolve_action(result["fight"], actor, self.main, self.account, spell_uid),
        )
        with self.assertRaises(ValueError):
            resolve_action(
                result["fight"], actor, self.main, self.account + 100000, spell_uid
            )

        from wakfu_server.combat_session_adapter import CombatSessionAdapter

        adapter = CombatSessionAdapter(self.store)
        ready = adapter.ready_transition(
            self.session, result["fight"], None, True, {-200: self.enemy}
        )
        self.assertEqual("active", ready.fight.phase)
        self.assertIn(str(self.companion_id), ready.fight.native_companion_sources)
        self.assertTrue(ready.fight.actors[self.companion_id].controlled)

        # The normal timeline must place the fixture's sidekick first; no
        # direct assignment to Fight.current or order is used.
        fight = ready.fight
        self.assertEqual(self.companion_id, fight.current.id)

        from wakfu_server.combat_server_spell import prepare_server_spell
        from wakfu_server.spells import default_deck

        deck = default_deck(self.main)
        spell_uid, spell_level = resolve_action(
            fight, fight.actors[self.companion_id], self.main, self.account, spell_uid
        )
        self.assertGreater(spell_level, 0)
        from wakfu_server.combat_qi_fight import move_registered_actor

        caster_position = fight.actors[self.companion_id].position
        transaction = None
        last_target_rejection = None
        for target in sorted(fight.walkable):
            distance = abs(target[0] - caster_position[0]) + abs(
                target[1] - caster_position[1]
            )
            if not 1 <= distance <= 12 or any(
                actor.id != -200 and actor.position[:2] == target[:2]
                for actor in fight.actors.values()
            ):
                continue
            move_registered_actor(fight, fight.actors[-200], target)
            try:
                transaction = prepare_server_spell(
                    struct.pack(">qqiih", self.companion_id, spell_uid, *target),
                    self.main,
                    {-200: self.enemy},
                    fight,
                    self.account,
                    deck,
                    action_id=1,
                    line_of_sight=lambda *args: True,
                    critical=False,
                    player_characters={self.main["id"]: self.main},
                    deck_blobs={self.main["id"]: deck},
                )
                break
            except ValueError as error:
                if str(error).startswith("Native spell casting eligibility rejected: "):
                    last_target_rejection = error
                    continue
                raise
        self.assertIsNotNone(
            transaction, msg=f"No native target accepted: {last_target_rejection}"
        )
        self.assertEqual(self.companion_id, transaction.plan["actor_id"])
        self.assertTrue(transaction.outcomes)


if __name__ == "__main__":
    unittest.main()
