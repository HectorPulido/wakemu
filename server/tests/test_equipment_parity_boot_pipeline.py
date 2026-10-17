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


class EquipmentParityBootPipelineTests(PostgresCase):
    def test_persisted_boots_pay_native_cast_and_expire_parity_mp_on_actual_turns(self):
        account = self.store.register("parity-boots-pipeline", "local-test-password")[
            "id"
        ]
        char = self.store.create_character(account, "Parity Boots Pipeline", breed=1)
        generation = self.store.begin_session(account)
        self.store.select_character(account, generation, char["id"])
        with self.store.connection() as db:
            db.execute(
                "UPDATE characters SET level=200,map_id=1134,instance_id=0,x=0,y=0,z=0 WHERE id=%s",
                (char["id"],),
            )
            db.execute(
                "UPDATE character_progression SET xp=%s WHERE character_id=%s",
                (level_xp(200), char["id"]),
            )
        char = health_store.initialize(self.store, account, generation, char["id"])
        persisted_health_before_gear = (char["hp"], char["max_hp"])
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO inventory_items(uid,character_id,reference,quantity,container,slot) "
                "VALUES(%s,%s,%s,%s,%s,%s)",
                (1000, char["id"], 15001, 1, char["inventory_containers"][0]["uid"], 0),
            )
        sheet = b"".join(
            wire.proto_field(t, v)
            for t, v in ((8, 0), (18, b"Parity Boots"), (24, 200), (56, 0))
        )
        deck = encode_deck([6972])
        char = self.store.save_build(
            account,
            generation,
            char["id"],
            0,
            dict(
                sheet=sheet,
                equipment=wire.proto_field(
                    10, wire.proto_field(8, 1000) + wire.proto_field(16, 12)
                ),
                deck=deck,
                aptitudes=b"",
            ),
        )
        char = self.store.character(account, char["id"])
        self.assertGreaterEqual(char["max_hp"], persisted_health_before_gear[1])
        resources = combat_resources(char)
        cells = [(0, 0, 0), (1, 0, 0)]
        terrain = arena(1134, 1, cells, {0: cells[0], 1: cells[1]})
        terrain["validated_cells"] = cells
        monster = owned_instance(5525, 1, -200, map_id=1134, x=1, y=0, z=0)
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
        actor = started.actors[actor_id]
        self.assertEqual(
            next(s.level for s in actor.state_ledger.entries if s.reference == 1583), 1
        )
        self.assertEqual((actor.hp, actor.max_hp), (char["hp"], char["max_hp"]))
        self.assertEqual((actor.mp, actor.max_mp), (resources["mp"], resources["mp"]))
        # Native initiative owns the first slot. Traverse actual NPC end/ACK
        # boundaries rather than changing initiative to force a player turn.
        for _ in range(len(started.actors)):
            if runtime.fight.current.id == actor_id:
                break
            advance_actual_turn(runtime)
        self.assertEqual(runtime.fight.current.id, actor_id)
        started = runtime.fight
        actor = started.actors[actor_id]
        self.assertEqual(
            next(s.level for s in actor.state_ledger.entries if s.reference == 1583), 1
        )
        self.assertEqual((actor.mp, actor.max_mp), (resources["mp"], resources["mp"]))
        # Real native Feca grant pays its own AP/WP; no resource top-up occurs.
        grant = granted_spells(started, actor_id)[7009]
        before_foreign_uid = snapshot(runtime.fight)
        foreign_uid = grant["uid"] ^ (1 << 60)
        self.assertNotIn(
            foreign_uid,
            [row["uid"] for row in granted_spells(runtime.fight, actor_id).values()],
        )
        with self.assertRaises(ValueError):
            prepare_server_spell(
                struct.pack(">qqiih", actor_id, foreign_uid, *actor.position),
                char,
                {-200: monster},
                runtime.fight,
                account,
                deck,
                action_id=runtime.action_id + 1,
                line_of_sight=lambda *args: True,
                critical=False,
                rng=rng,
            )
        self.assertEqual(snapshot(runtime.fight), before_foreign_uid)
        transaction = prepare_server_spell(
            struct.pack(">qqiih", actor_id, grant["uid"], *actor.position),
            char,
            {-200: monster},
            started,
            account,
            deck,
            action_id=runtime.action_id + 1,
            line_of_sight=lambda *args: True,
            critical=False,
            rng=rng,
        )
        self.assertEqual(
            tuple(transaction.plan["costs"][k] for k in ("ap", "mp", "wp")), (2, 0, 1)
        )
        self.assertEqual(transaction.fight.actors[actor_id].ap, resources["ap"] - 2)
        before_failed_publication = snapshot(runtime.fight)

        def fail_publication(*args):
            raise ValueError("parity publication failed")

        with self.assertRaisesRegex(ValueError, "parity publication failed"):
            commit_spell_transaction(
                runtime, transaction, stats_serializer=fail_publication
            )
        self.assertEqual(snapshot(runtime.fight), before_failed_publication)
        cast_packets = commit_spell_transaction(
            runtime, transaction, stats_serializer=lambda actor, preview: stats(actor)
        )
        self.assertTrue(cast_packets)
        self.assertIs(runtime.fight, transaction.fight)
        observed = []
        for _ in range(12):
            advance_actual_turn(runtime)
            if runtime.fight.current.id == actor_id:
                live = runtime.fight.actors[actor_id]
                table_turn = runtime.fight.native_table_turn
                self.assertEqual(
                    next(
                        s.level
                        for s in live.state_ledger.entries
                        if s.reference == 1583
                    ),
                    1,
                )
                observed.append((table_turn, live.mp, live.max_mp))
                owned_mp = [
                    row
                    for row in runtime.fight.owned_stat_effects.values()
                    if row["target_id"] == actor_id and row["effect_class"] == 41
                ]
                if table_turn % 2 == 0:
                    self.assertEqual(len(owned_mp), 1)
                    self.assertEqual(
                        owned_mp[0]["timer"],
                        dict(
                            actor_id=actor_id, expiration_round=table_turn, phase="end"
                        ),
                    )
                else:
                    self.assertEqual(owned_mp, [])
                self.assertEqual((live.hp, live.max_hp), (char["hp"], char["max_hp"]))
                self.assertEqual(live.effect_stats[4], resources["wp"] - 1)
                if len(observed) == 4:
                    break
        self.assertEqual(
            observed,
            [
                (2, resources["mp"] + 1, resources["mp"] + 1),
                (3, resources["mp"], resources["mp"]),
                (4, resources["mp"] + 1, resources["mp"] + 1),
                (5, resources["mp"], resources["mp"]),
            ],
        )
        stable = snapshot(runtime.fight)
        same, unchanged, empty = prepare_ready(
            runtime.fight,
            account,
            True,
            initialize=initialize,
            stats_serializer=stats,
            effects_serializer=actor_effects,
        )
        self.assertIs(same, runtime.fight)
        self.assertIsNone(unchanged)
        self.assertEqual(empty, ())
        self.assertEqual(snapshot(same), stable)
