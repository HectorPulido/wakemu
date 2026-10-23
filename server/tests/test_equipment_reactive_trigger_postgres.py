"""Public build and combat lifecycle coverage for native reactive gear."""
from random import Random
import json
import struct
from pathlib import Path

from postgres_case import PostgresCase
from wakfu_server import health_store, wire
from wakfu_server.progression import level_xp
from wakfu_server.spells import encode_deck
from wakfu_server.combat_actor import (
    actual_actor_stats,
    actual_monster_actor_stats,
    actor_effects,
)
from wakfu_server.combat_actor_snapshot import initialize_fight_snapshots
from wakfu_server.combat_bootstrap import create_placement
from wakfu_server.combat_ready import prepare_ready
from wakfu_server.combat_server_spell import prepare_server_initialization
from wakfu_server.equipment_stats import combat_resources
from wakfu_server.combat_terrain import local_arena
from wakfu_server.fight_checkpoint_store import Checkpoints, snapshot
from wakfu_server.monsters import owned_instance
from wakfu_server.combat_area_transaction import prepare_area_movement
from wakfu_server.combat_movement_runtime import apply_client
from wakfu_server.combat_server_spell import prepare_server_spell
from wakfu_server.combat import fight_store


class EquipmentReactiveTriggerPostgresTests(PostgresCase):
    def _owner_with_weapon(self):
        account = self.store.register("reactive-gear-owner", "local-test-password")[
            "id"
        ]
        character = self.store.create_character(account, "Reactive Gear", breed=1)
        generation = self.store.begin_session(account)
        self.store.select_character(account, generation, character["id"])
        with self.store.connection() as db:
            db.execute(
                "UPDATE characters SET level=200,map_id=1134,instance_id=0,x=0,y=0,z=0 WHERE id=%s",
                (character["id"],),
            )
            db.execute(
                "UPDATE character_progression SET xp=%s WHERE character_id=%s",
                (level_xp(200), character["id"]),
            )
        character = health_store.initialize(
            self.store, account, generation, character["id"]
        )
        from wakfu_server.items.inventory_items import grant

        weapon = grant(
            self.store,
            account,
            generation,
            character["id"],
            reference=26593,
            quantity=1,
            container=character["inventory_containers"][0]["uid"],
            slot=0,
            allowed_references={26593},
        )
        blobs = {
            "sheet": b"".join(
                wire.proto_field(tag, value)
                for tag, value in (
                    (8, 0),
                    (18, b"Reactive Gear"),
                    (24, 200),
                    (56, 0),
                )
            ),
            "equipment": wire.proto_field(
                10,
                wire.proto_field(8, weapon["uid"]) + wire.proto_field(16, 15),
            ),
            "deck": encode_deck([6969]),
            "aptitudes": b"",
        }
        return account, generation, character, weapon, blobs

    def test_26593_moves_casts_and_survives_checkpoint_reconnect(self):
        account, generation, character, weapon, blobs = self._owner_with_weapon()
        character = self.store.save_build(
            account, generation, character["id"], 0, blobs
        )
        self.assertEqual(character["active_build_index"], 0)
        self.assertTrue(character["builds"][0]["equipment"])
        # Use the installed map's actual selected cells and surfaces.
        with self.store.connection() as db:
            db.execute(
                "UPDATE characters SET x=-8,y=-7,z=-1 WHERE id=%s",
                (character["id"],),
            )
        character = self.store.character(account, character["id"])
        monster = owned_instance(1069, 50, -200, map_id=1134, x=-6, y=-7, z=-1)
        terrain = local_arena(
            1134,
            7,
            (-8, -7, -1),
            (-6, -7, -1),
            relocate_monsters=False,
            variation_seed=26593,
        )
        resources = combat_resources(character)
        actor_id = character["id"]
        fight_id = fight_store.create(self.store, account, generation, actor_id, team=0)
        fight, _ = create_placement(
            character,
            monster,
            terrain,
            fight_id=fight_id,
            player_ap=resources["ap"],
            player_mp=resources["mp"],
            player_wp=resources["wp"],
            player_initiative=resources["initiative"],
            terrain_effect_id=46,
            terrain_instance_id=7,
        )
        deck = encode_deck([6969])
        initialize_fight_snapshots(
            fight,
            characters={actor_id: character},
            monsters={-200: monster},
            wp_resources={
                actor_id: (resources["wp"], resources["wp"]),
                -200: (monster["wp"], monster["wp"]),
            },
            running_effects={actor_id: (), -200: ()},
            initial_effect_uid=1,
        )
        for actor in fight.actors.values():
            actor.direction = 0 if actor.controlled else 3
        rng = Random(26593)

        def initialize(preview, action_id):
            return prepare_server_initialization(
                character,
                {-200: monster},
                preview,
                account,
                deck,
                action_id=action_id,
                rng=rng,
                fight_start=True,
            )

        def stats(actor):
            if actor.controlled:
                return actual_actor_stats(
                    character,
                    actor,
                    fight.id,
                    wp_current=actor.effect_stats[4],
                    wp_maximum=resources["wp"],
                )
            return actual_monster_actor_stats(
                monster,
                actor,
                fight.id,
                wp_current=monster["wp"],
                wp_maximum=monster["wp"],
            )

        started, runtime, _packets = prepare_ready(
            fight,
            account,
            True,
            initialize=initialize,
            stats_serializer=stats,
            effects_serializer=actor_effects,
        )
        player = started.actors[actor_id]
        self.assertIn(5886, {state.reference for state in player.state_ledger.entries})
        self.assertNotIn(
            5886,
            {
                state.reference
                for state in runtime.fight.actors[-200].state_ledger.entries
            },
        )
        while runtime.fight.current.id != actor_id:
            npc_id = runtime.fight.current.id
            turn = runtime.fight.turn_id
            # This focused test has no NPC AI transport. It advances the
            # native server-controlled actor through the real turn boundary
            # without changing any stats or injecting events.
            runtime.end_server_turn(npc_id, turn)
            runtime.acknowledge_turn(struct.pack(">i", turn))
        self.assertEqual(runtime.fight.current.id, actor_id)
        fight_store.activate(
            self.store, account, generation, actor_id, runtime.fight.id
        )

        # Commit one legal real movement step, allowing the equipment's 1005
        # listener to run through the native area-event producer.
        origin = tuple(runtime.fight.actors[actor_id].position)
        target = tuple(runtime.fight.actors[-200].position)
        destinations = [
            end
            for start, end in sorted(runtime.fight.edges)
            if start == origin
            and end != target
            and 1 <= abs(end[0] - target[0]) + abs(end[1] - target[1]) <= 5
        ]
        self.assertTrue(destinations, "fixture has a legal movement step")
        destination = destinations[0]

        def movement_provider(candidate, **boundary):
            return prepare_area_movement(
                character,
                {-200: monster},
                candidate,
                deck,
                rng=rng,
                **boundary,
            )

        from wakfu_server.combat_diagnostics import combat_diagnostic_scope
        from unittest.mock import patch
        from wakfu_server.combat_trigger_value_modifier import NativeRunnerAmount

        diagnostic_rows = []
        runner_mutations = []
        mutate = NativeRunnerAmount.mutate

        def observe_runner_mutation(runner, mode, value, replace):
            before = runner.value
            result = mutate(runner, mode, value, replace)
            runner_mutations.append(
                {
                    "uid": runner.uid,
                    "family": runner.family,
                    "mode": mode,
                    "amount": value,
                    "replace": replace,
                    "before": before,
                    "after": runner.value,
                }
            )
            return result

        mutation_patch = patch.object(
            NativeRunnerAmount, "mutate", observe_runner_mutation
        )
        mutation_patch.start()
        self.addCleanup(mutation_patch.stop)
        with combat_diagnostic_scope(
            lambda **row: diagnostic_rows.append(row), limit=4096
        ):
            movement_packets, movement_event = apply_client(
                runtime,
                account,
                struct.pack(">qiih", actor_id, *destination),
                lambda actor: actual_actor_stats(
                    character,
                    actor,
                    runtime.fight.id,
                    wp_current=actor.effect_stats[4],
                    wp_maximum=resources["wp"],
                ),
                area_provider=movement_provider,
            )
        self.assertEqual(movement_event["path"], [destination])
        self.assertEqual(tuple(runtime.fight.actors[actor_id].position), destination)
        self.assertTrue(movement_packets)

        # A real Feca elemental hit crosses the public native 1024/1025
        # boundaries and executes the item's scoped 430 runner modifiers.
        caster = runtime.fight.actors[actor_id]
        before_ap = caster.ap
        spell_uid = (actor_id << 32) | 6969
        enemy = runtime.fight.actors[-200]
        before_enemy_hp = enemy.hp
        with combat_diagnostic_scope(
            lambda **row: diagnostic_rows.append(row), limit=4096
        ):
            cast = prepare_server_spell(
                struct.pack(">qqiih", actor_id, spell_uid, *enemy.position),
                character,
                {-200: monster},
                runtime.fight,
                account,
                deck,
                action_id=runtime.action_id + 1,
                line_of_sight=lambda *args: True,
                critical=False,
                rng=rng,
            )
        self.assertLess(cast.fight.actors[-200].hp, before_enemy_hp)
        self.assertEqual(cast.plan["costs"]["ap"], 3)
        self.assertEqual(cast.fight.actors[actor_id].ap, before_ap - 3)
        reactive_modifiers = [
            (
                row.get("effect_reference"),
                row.get("caster_id"),
                row.get("target_id"),
                row.get("status"),
            )
            for row in diagnostic_rows
            if row.get("event") == "combat_effect" and row.get("effect_class") == 430
        ]
        completed_modifiers = [
            row for row in reactive_modifiers if row[3] == "completed"
        ]
        self.assertTrue(completed_modifiers, reactive_modifiers)
        self.assertTrue(
            any(caster_id == actor_id for _, caster_id, _, _ in completed_modifiers),
            completed_modifiers,
        )
        cleanup_rows = [
            row
            for row in diagnostic_rows
            if row.get("event") == "combat_effect"
            and row.get("effect_class") == 421
            and row.get("effect_reference") in (279783, 280544)
            and row.get("status") == "completed"
        ]
        self.assertEqual(
            {row["effect_reference"] for row in cleanup_rows},
            {279783, 280544},
            cleanup_rows,
        )
        self.assertTrue(
            all(
                row.get("caster_id") == actor_id
                and row.get("target_id") == actor_id
                and row.get("state_uid") == 2
                for row in cleanup_rows
            ),
            cleanup_rows,
        )
        self.assertTrue(
            any(
                row["family"] == 2
                and row["mode"] == 1
                and row["amount"] == 800
                and row["replace"] is False
                and row["before"] == 76
                and row["after"] == 876
                for row in runner_mutations
            ),
            {"mutations": runner_mutations, "effects": completed_modifiers},
        )
        self.assertIn(
            5886,
            {
                state.reference
                for state in cast.fight.actors[actor_id].state_ledger.entries
            },
        )

        # Persist and reread the exact post-cast checkpoint, including the
        # equipment-owned reactive state and transition markers.
        checkpoints = Checkpoints(self.store)
        checkpoints.save(account, generation, cast.fight)
        recovered = checkpoints.read(account, cast.fight.id)
        self.assertIsNotNone(recovered)
        self.assertEqual(recovered["fight_id"], cast.fight.id)
        self.assertEqual(recovered["snapshot"], snapshot(cast.fight))
        evidence_path = (
            Path(__file__).resolve().parents[2]
            / ".runtime"
            / "equipment-reactive-trigger-20261020"
            / f"fight-{cast.fight.id}-evidence.json"
        )
        evidence_path.parent.mkdir(parents=True, exist_ok=True)
        evidence_path.write_text(
            json.dumps(
                {
                    "fight_id": cast.fight.id,
                    "actor_id": actor_id,
                    "enemy_id": -200,
                    "completed_430": completed_modifiers,
                    "completed_421_cleanup": cleanup_rows,
                    "runner_mutations": runner_mutations,
                    "diagnostics": diagnostic_rows,
                    "checkpoint_snapshot": recovered["snapshot"],
                },
                sort_keys=True,
                default=str,
            ),
            encoding="utf-8",
        )
