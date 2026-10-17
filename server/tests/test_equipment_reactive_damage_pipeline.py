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
from wakfu_server.combat_wire import arena
from wakfu_server.combat_ready import prepare_ready
from wakfu_server.combat_server_spell import (
    prepare_server_initialization,
    prepare_server_spell,
    prepare_server_turn_end,
    prepare_server_turn_start,
    server_runtime,
)
from wakfu_server.combat_spell_grant import granted_spells
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


from wakfu_server.combat_los import authoritative_visible
from wakfu_server.combat_obstacle_condition import footprint
from wakfu_server.combat_movement_runtime import apply_client
from wakfu_server.combat_area_transaction import prepare_area_movement


class ReactiveEquipmentDamagePipelineTests(PostgresCase):
    def _fixture(self, order):
        account = self.store.register("ebony-" + order, "local-test-password")["id"]
        char = self.store.create_character(
            account,
            ("Ebony Distance" if order == "distance-first" else "Ebony Melee"),
            breed=8,
        )
        generation = self.store.begin_session(account)
        self.store.select_character(account, generation, char["id"])
        with self.store.connection() as db:
            db.execute(
                "UPDATE characters SET level=245,map_id=1134,instance_id=0,x=-8,y=-7,z=-1 WHERE id=%s",
                (char["id"],),
            )
            db.execute(
                "UPDATE character_progression SET xp=%s WHERE character_id=%s",
                (level_xp(245), char["id"]),
            )
        char = health_store.initialize(self.store, account, generation, char["id"])
        base_maximum = char["max_hp"]
        gear_uid = 1000 if order == "distance-first" else 1001
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO inventory_items(uid,character_id,reference,quantity,container,slot) "
                "VALUES(%s,%s,%s,%s,%s,%s)",
                (
                    gear_uid,
                    char["id"],
                    32351,
                    1,
                    char["inventory_containers"][0]["uid"],
                    0,
                ),
            )
        sheet = b"".join(
            wire.proto_field(t, v)
            for t, v in ((8, 0), (18, b"Ebony"), (24, (1 << 64) - 1), (56, 0))
        )
        deck = encode_deck([4780])
        char = self.store.save_build(
            account,
            generation,
            char["id"],
            0,
            dict(
                sheet=sheet,
                equipment=wire.proto_field(
                    10, wire.proto_field(8, gear_uid) + wire.proto_field(16, 17)
                ),
                deck=deck,
                aptitudes=b"",
            ),
        )
        char = self.store.character(account, char["id"])
        resources = combat_resources(char)
        from wakfu_server.combat_terrain import local_arena

        initial = (-5, -7, -1) if order == "distance-first" else (-6, -7, -1)
        terrain = local_arena(
            1134, 1, (-8, -7, -1), initial, relocate_monsters=False, compact=True
        )
        monster = owned_instance(
            4168, 190, -200, map_id=1134, x=initial[0], y=initial[1], z=initial[2]
        )
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
            terrain_instance_id=9001,
        )
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

        def stats(actor):
            if actor.controlled:
                return actual_actor_stats(
                    char,
                    actor,
                    7,
                    wp_current=actor.effect_stats[4],
                    wp_maximum=resources["wp"],
                )
            return actual_monster_actor_stats(
                monster, actor, 7, wp_current=monster["wp"], wp_maximum=monster["wp"]
            )

        before = snapshot(fight)
        started, runtime, packets = prepare_ready(
            fight,
            account,
            True,
            initialize=initialize,
            stats_serializer=stats,
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
        for _ in range(len(started.actors)):
            if runtime.fight.current.id == actor_id:
                break
            advance_actual_turn(runtime)
        self.assertEqual(runtime.fight.current.id, actor_id)
        self.assertTrue(
            any(
                entry.reference == 8784
                for entry in runtime.fight.actors[actor_id].state_ledger.entries
            )
        )
        return char, monster, deck, rng, runtime, stats

    @staticmethod
    def _states(actor, reference):
        return [
            entry
            for entry in actor.state_ledger.entries
            if entry.reference == reference
        ]

    def _cast(self, values):
        char, monster, deck, rng, runtime, stats = values
        actor_id = char["id"]
        target = runtime.fight.actors[-200]

        def los(origin, destination, current):
            return authoritative_visible(
                char["map_id"],
                origin,
                destination,
                current,
                blocking_footprints={
                    actor.id: footprint(actor.position, actor.physical_radius)
                    for actor in current.actors.values()
                    if actor.hp > 0
                },
            )

        before = snapshot(runtime.fight)
        transaction = prepare_server_spell(
            struct.pack(">qqiih", actor_id, (actor_id << 32) | 4780, *target.position),
            char,
            {-200: monster},
            runtime.fight,
            char["account_id"],
            deck,
            action_id=runtime.action_id + 1,
            line_of_sight=los,
            critical=False,
            rng=rng,
        )
        self.assertEqual(snapshot(runtime.fight), before)
        self.assertGreater(transaction.plan["costs"]["ap"], 0)
        self.assertLess(transaction.fight.actors[-200].hp, target.hp)
        packets = commit_spell_transaction(
            runtime, transaction, stats_serializer=lambda actor, preview: stats(actor)
        )
        self.assertTrue(packets)
        return transaction

    def _move(self, values, destination):
        char, monster, deck, rng, runtime, stats = values

        def provider(preview, **boundary):
            return prepare_area_movement(
                char, {-200: monster}, preview, deck, rng=rng, **boundary
            )

        before = runtime.fight.actors[char["id"]].mp
        packets, result = apply_client(
            runtime,
            char["account_id"],
            struct.pack(">qiih", char["id"], *destination),
            stats,
            runtime_stats_serializer=lambda actor, preview: stats(actor),
            area_provider=provider,
        )
        self.assertTrue(result)
        self.assertTrue(packets)
        self.assertLess(runtime.fight.actors[char["id"]].mp, before)

    def test_paid_melee_then_distance_completes_same_owner_cycle_once(self):
        for order in ("distance-first", "melee-first"):
            with self.subTest(order=order):
                values = self._fixture(order)
                char, monster, deck, rng, runtime, stats = values
                owner = char["id"]
                first = 8785 if order == "distance-first" else 8786
                other = 8786 if first == 8785 else 8785
                self._cast(values)
                victim = runtime.fight.actors[-200]
                earned = self._states(victim, first)
                self.assertEqual(len(earned), 1)
                self.assertEqual(earned[0].caster_id, owner)
                self.assertFalse(self._states(victim, other))
                self.assertFalse(self._states(runtime.fight.actors[owner], 8788))
                step = (-7, -7, -1) if order == "distance-first" else (-9, -7, -1)
                self._move(values, step)
                self._cast(values)
                victim, caster = runtime.fight.actors[-200], runtime.fight.actors[owner]
                self.assertFalse(self._states(victim, 8785))
                self.assertFalse(self._states(victim, 8786))
                self.assertEqual(len(self._states(caster, 8788)), 1)
                self.assertEqual(len(self._states(caster, 8787)), 1)
                self.assertEqual(self._states(caster, 8787)[0].caster_id, owner)
