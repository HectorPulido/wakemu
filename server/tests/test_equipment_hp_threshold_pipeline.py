"""Persisted owned gear enters actual Ready, paid cast and end/ACK callbacks."""
from random import Random
import struct

from postgres_case import PostgresCase
from wakfu_server import health_store, wire
from wakfu_server.progression import level_xp
from wakfu_server.equipment_stats import combat_resources
from wakfu_server.combat_actor_snapshot import initialize_fight_snapshots
from wakfu_server.combat_actor import (
    actual_actor_stats,
    actual_monster_actor_stats,
    actor_effects,
)
from wakfu_server.combat_bootstrap import create_placement
from wakfu_server.combat_terrain import local_arena
from wakfu_server.combat_ready import prepare_ready
from wakfu_server.combat_server_spell import (
    prepare_server_initialization,
    prepare_server_spell,
    prepare_server_turn_end,
    prepare_server_turn_start,
    server_runtime,
)
from wakfu_server.combat_npc_spell import prepare_npc_spell
from wakfu_server.combat_retained_runtime import native_retained_condition_effects
from wakfu_server.combat_spell_commit import commit_spell_transaction
from wakfu_server.fight_checkpoint_store import snapshot
from wakfu_server.monsters import owned_instance
from wakfu_server.spells import encode_deck

# unittest discovery adds server/tests but does not add server/tools. Resolve
# this existing API driver explicitly and restore the process import path.
from pathlib import Path
import sys

_tools = next(
    parent / "server" / "tools"
    for parent in Path(__file__).resolve().parents
    if (parent / "server" / "tools" / "combat_audit_turns.py").is_file()
)
_saved_path = list(sys.path)
try:
    sys.path.insert(0, str(_tools))
    import combat_audit_turns as _turn_driver

    if (
        Path(_turn_driver.__file__).resolve()
        != (_tools / "combat_audit_turns.py").resolve()
    ):
        raise ImportError("Combat turn driver has a foreign source origin")
    advance_actual_turn = _turn_driver.advance_actual_turn
finally:
    sys.path[:] = _saved_path


class EquipmentHpThresholdPipelineTests(PostgresCase):
    def test_owned_cape_paid_damage_crossing_and_paid_healing_recross_generic_identity(
        self,
    ):
        account = self.store.register("hp-threshold-pipeline", "local-test-password")[
            "id"
        ]
        char = self.store.create_character(account, "HP Threshold Pipeline", breed=7)
        generation = self.store.begin_session(account)
        self.store.select_character(account, generation, char["id"])
        with self.store.connection() as db:
            db.execute(
                "UPDATE characters SET level=200,map_id=1134,instance_id=0,x=-9,y=-7,z=-1 WHERE id=%s",
                (char["id"],),
            )
            db.execute(
                "UPDATE character_progression SET xp=%s WHERE character_id=%s",
                (level_xp(200), char["id"]),
            )
        char = health_store.initialize(self.store, account, generation, char["id"])
        base_maximum = char["max_hp"]
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO inventory_items(uid,character_id,reference,quantity,container,slot) "
                "VALUES(%s,%s,%s,%s,%s,%s)",
                (
                    (100000 + char["id"]),
                    char["id"],
                    18089,
                    1,
                    char["inventory_containers"][0]["uid"],
                    0,
                ),
            )
        sheet = b"".join(
            wire.proto_field(t, v)
            for t, v in ((8, 0), (18, b"HP Threshold"), (24, 200), (56, 0))
        )
        deck = encode_deck([779])
        char = self.store.save_build(
            account,
            generation,
            char["id"],
            0,
            dict(
                sheet=sheet,
                equipment=wire.proto_field(
                    10,
                    wire.proto_field(8, (100000 + char["id"]))
                    + wire.proto_field(16, 13),
                ),
                deck=deck,
                aptitudes=b"",
            ),
        )
        char = self.store.character(account, char["id"])
        self.assertEqual(char["max_hp"], base_maximum + 148)
        resources = combat_resources(char)
        player_cell, monster_cell = (-9, -7, -1), (-8, -7, -1)
        terrain = local_arena(
            1134,
            0,
            player_cell,
            monster_cell,
            relocate_monsters=False,
            compact=True,
            variation_seed=1,
            minimum_dimensions=(9, 9),
        )
        self.assertIn(player_cell, terrain["validated_cells"])
        self.assertIn(monster_cell, terrain["validated_cells"])
        monster = owned_instance(
            1,
            8,
            -200,
            map_id=1134,
            x=monster_cell[0],
            y=monster_cell[1],
            z=monster_cell[2],
        )
        terrain_identity = 900000 + char["id"]
        self.assertNotIn(terrain_identity, {char["id"], monster["id"]})
        self.assertEqual((char["map_id"], char["instance_id"]), (1134, 0))
        self.assertEqual((monster["map_id"], monster["instance_id"]), (1134, 0))
        fight, _ = create_placement(
            char,
            monster,
            terrain,
            fight_id=7,
            player_ap=resources["ap"],
            player_mp=resources["mp"],
            player_wp=resources["wp"],
            player_initiative=resources["initiative"],
            terrain_effect_id=46,
            terrain_instance_id=terrain_identity,
        )
        from wakfu_server.monsters import native_abilities

        self.assertEqual(
            {
                row["spell_id"]: row["spell_level"]
                for row in native_abilities(monster["ref"], monster["level"])
            },
            {5767: 8},
        )
        self.assertNotIn(terrain_identity, fight.actors)
        actor_id = char["id"]
        initialize_fight_snapshots(
            fight,
            characters={actor_id: char},
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
        rng = Random(7)

        def initialize(preview, action_id):
            return prepare_server_initialization(
                char,
                {-200: monster},
                preview,
                account,
                deck,
                action_id=action_id,
                rng=rng,
                fight_start=True,
            )

        def unbound_stats(actor):
            raise ValueError("Runtime stats require the actual preview Fight")

        def stats(actor, preview):
            self.assertIs(preview.actors[actor.id], actor)
            if actor.controlled:
                return actual_actor_stats(
                    char,
                    actor,
                    7,
                    wp_current=actor.effect_stats[4],
                    wp_maximum=resources["wp"],
                    fight=preview,
                )
            return actual_monster_actor_stats(
                monster,
                actor,
                7,
                wp_current=actor.effect_stats[4],
                wp_maximum=monster["wp"],
                fight=preview,
            )

        self.assertEqual(
            (fight.actors[actor_id].hp, fight.actors[actor_id].max_hp),
            (char["hp"], char["max_hp"]),
        )
        before = snapshot(fight)
        started, runtime, packets = prepare_ready(
            fight,
            account,
            True,
            initialize=initialize,
            stats_serializer=unbound_stats,
            runtime_stats_serializer=stats,
            effects_serializer=actor_effects,
            turn_end_provider=lambda p, **b: prepare_server_turn_end(
                char, {-200: monster}, p, deck, rng=rng, **b
            ),
            turn_start_provider=lambda p, **b: prepare_server_turn_start(
                char, {-200: monster}, p, deck, rng=rng, area_callbacks=True, **b
            ),
            expiration_runtime_factory=lambda *, action_id: server_runtime(
                char,
                {-200: monster},
                deck,
                action_id=action_id,
                critical=False,
                rng=rng,
            )[0],
        )
        self.assertEqual(snapshot(fight), before)
        self.assertTrue(packets)
        actor = started.actors[actor_id]
        # Native Eniripsa3911 / 1003 / level-group999 applies3230 at
        # 200% of the actor level, then143553/eWN adds that exact HP amount
        # to current AND maximum. This is independent of snapshot-owned148HP.
        innate_delta = 2 * char["level"]
        innate_state = next(
            row for row in actor.state_ledger.entries if row.reference == 3230
        )
        self.assertEqual(innate_state.level, innate_delta)
        innate_rows = [
            row
            for row in native_retained_condition_effects(started, actor_id)
            if row[0] == 143553
        ]
        self.assertEqual(len(innate_rows), 1)
        self.assertEqual(innate_rows[0][1], 20)
        native_hp = started.owned_stat_effects[innate_rows[0][2]]
        self.assertEqual(native_hp["state_uid"], innate_state.uid)
        self.assertEqual(
            (
                native_hp["stat_id"],
                native_hp["actual"],
                native_hp["effective_delta"],
                native_hp["remove_current"],
            ),
            (1, innate_delta, innate_delta, True),
        )
        self.assertEqual(
            (actor.hp, actor.max_hp),
            (char["hp"] + innate_delta, char["max_hp"] + innate_delta),
        )
        self.assertEqual(actor.hp, actor.max_hp)

        def native_los(source, target, preview):
            from wakfu_server.combat_los import authoritative_visible
            from wakfu_server.combat_qi_fight import current_registry

            current_registry(preview)
            footprints = {}
            for member in preview.actors.values():
                if member.hp <= 0:
                    continue
                radius = member.physical_radius
                if type(radius) is not int or not 0 <= radius <= 127:
                    raise ValueError("Missing native actor physical footprint")
                x, y = member.position[:2]
                footprints[member.id] = {
                    (px, py)
                    for px in range(x - radius, x + radius + 1)
                    for py in range(y - radius, y + radius + 1)
                }
            return authoritative_visible(
                1134, source, target, preview, blocking_footprints=footprints
            )

        def generic_rows():
            return tuple(native_retained_condition_effects(runtime.fight, actor_id))

        def actor_turn():
            for _ in range(len(runtime.fight.actors) + 1):
                if runtime.fight.current.id == actor_id:
                    return
                advance_actual_turn(runtime)
            self.fail("Native turn order did not reach the owned player")

        actor_turn()
        self.assertTrue(any(row[0] == 109059 for row in generic_rows()))
        self.assertTrue(any(row[0] == 109021 for row in generic_rows()))
        original_state = next(
            row
            for row in runtime.fight.actors[actor_id].state_ledger.entries
            if row.reference == 2514
        )
        original_state_uid = original_state.uid
        # Start healthy. Only admitted paid native attacks lower HP. There is no
        # raw-HP seed, forged PA field, resource grant or clock injection.
        for _ in range(64):
            advance_actual_turn(runtime)
            if runtime.fight.current.id != -200:
                continue
            live = runtime.fight.actors[actor_id]
            before_ap = runtime.fight.actors[-200].ap
            tx = prepare_npc_spell(
                runtime.fight,
                dict(
                    type="cast",
                    spellId=5767,
                    level=8,
                    targetId=actor_id,
                    target=list(live.position),
                ),
                char,
                {-200: monster},
                deck,
                action_id=runtime.action_id + 1,
                rng=rng,
            )
            self.assertGreater(tx.plan["costs"]["ap"], 0)
            self.assertEqual(
                tx.fight.actors[-200].ap, before_ap - tx.plan["costs"]["ap"]
            )
            self.assertLess(tx.fight.actors[actor_id].hp, live.hp)
            commit_spell_transaction(runtime, tx, stats_serializer=stats)
            self.assertGreater(runtime.fight.actors[actor_id].hp, 0)
            if (
                runtime.fight.actors[actor_id].hp * 100
                < runtime.fight.actors[actor_id].max_hp * 90
            ):
                break
        else:
            self.fail(
                "Actual paid native attacks did not cross the ninety-percent threshold"
            )
        self.assertFalse(any(row[0] == 109059 for row in generic_rows()))
        self.assertTrue(any(row[0] == 109021 for row in generic_rows()))
        actor_turn()
        # The real owned healing book produces healing and pays its native AP.
        # If a single heal is insufficient, another real player turn supplies
        # its normal resources; the test never tops them up.
        for _ in range(8):
            live = runtime.fight.actors[actor_id]
            old_hp, old_ap = live.hp, live.ap
            tx = prepare_server_spell(
                struct.pack(">qqiih", actor_id, (actor_id << 32) | 779, *live.position),
                char,
                {-200: monster},
                runtime.fight,
                account,
                deck,
                action_id=runtime.action_id + 1,
                line_of_sight=native_los,
                critical=False,
                rng=rng,
            )
            self.assertEqual(tx.plan["costs"]["ap"], 3)
            self.assertEqual(tx.fight.actors[actor_id].ap, old_ap - 3)
            self.assertGreater(tx.fight.actors[actor_id].hp, old_hp)
            stable = snapshot(runtime.fight)

            def failed_serializer(actor, preview):
                raise ValueError("deliberate HP threshold publication failure")

            with self.assertRaisesRegex(ValueError, "deliberate HP threshold"):
                commit_spell_transaction(
                    runtime, tx, stats_serializer=failed_serializer
                )
            self.assertEqual(snapshot(runtime.fight), stable)
            commit_spell_transaction(runtime, tx, stats_serializer=stats)
            if (
                runtime.fight.actors[actor_id].hp * 100
                >= runtime.fight.actors[actor_id].max_hp * 90
            ):
                break
            advance_actual_turn(runtime)
            actor_turn()
        else:
            self.fail("Actual paid healing did not recross the native threshold")
        self.assertEqual(sum(row[0] == 109059 for row in generic_rows()), 1)
        self.assertEqual(sum(row[0] == 109021 for row in generic_rows()), 1)
        self.assertEqual(
            next(
                row.uid
                for row in runtime.fight.actors[actor_id].state_ledger.entries
                if row.reference == 2514
            ),
            original_state_uid,
        )
