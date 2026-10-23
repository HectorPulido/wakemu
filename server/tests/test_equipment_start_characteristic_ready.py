"""Persisted 2636 gear is admitted by the real Ready/start/checkpoint path."""
from copy import deepcopy
from random import Random

from postgres_case import PostgresCase
from wakfu_server import health_store, wire
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
from wakfu_server.fight_checkpoint_store import Checkpoints, snapshot
from wakfu_server.monsters import owned_instance
from wakfu_server.progression import level_xp
from wakfu_server.spells import encode_deck
from wakfu_server.combat_wire import arena


class EquipmentStartCharacteristicReadyTests(PostgresCase):
    def _start_owned_reference(self, reference, fight_id, character_name):
        account = self.store.register(
            f"start-characteristic-{reference}", "local-test-password"
        )["id"]
        character = self.store.create_character(account, character_name, breed=1)
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

        # These five real, ordinary equipment rows supply exactly 500 TACKLE,
        # satisfying the two chest pieces whose native USE criterion requires
        # 500..600. They have no 304 startup roots themselves.
        equipment = (
            (24021, 15),
            (24614, 10),
            (24618, 12),
            (24621, 3),
            (26943, 4),
            (reference, 5),
        )
        equipped = []
        for slot_index, (item_reference, equipment_slot) in enumerate(equipment):
            row = grant(
                self.store,
                account,
                generation,
                character["id"],
                reference=item_reference,
                quantity=1,
                container=character["inventory_containers"][0]["uid"],
                slot=slot_index,
                allowed_references={item_reference},
            )
            equipped.append((row["uid"], equipment_slot))
        deck = encode_deck()
        character = self.store.save_build(
            account,
            generation,
            character["id"],
            0,
            {
                "sheet": b"".join(
                    wire.proto_field(tag, value)
                    for tag, value in (
                        (8, 0),
                        (18, character_name.encode()),
                        (24, 200),
                        (56, 0),
                    )
                ),
                "equipment": b"".join(
                    wire.proto_field(
                        10, wire.proto_field(8, uid) + wire.proto_field(16, slot)
                    )
                    for uid, slot in equipped
                ),
                "deck": deck,
                "aptitudes": b"",
            },
        )
        character = self.store.character(account, character["id"])
        resources = combat_resources(character)
        cells = [(0, 0, 0), (1, 0, 0)]
        terrain = arena(1134, 1, cells, {0: cells[0], 1: cells[1]})
        terrain["validated_cells"] = cells
        monster = owned_instance(5525, 1, -200, map_id=1134, x=1, y=0, z=0)
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
            terrain_instance_id=1,
        )
        actor_id = character["id"]
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
        rng = Random(reference)

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
                    fight_id,
                    wp_current=actor.effect_stats[4],
                    wp_maximum=resources["wp"],
                )
            return actual_monster_actor_stats(
                monster,
                actor,
                fight_id,
                wp_current=monster["wp"],
                wp_maximum=monster["wp"],
            )

        prestart_fight = deepcopy(fight)
        prestart_fight.ready(account, True)
        prestart, _ = prepare_server_initialization(
            character,
            {-200: monster},
            prestart_fight,
            account,
            deck,
            action_id=1,
            rng=Random(reference),
            fight_start=False,
        )
        prestart_player = dict(prestart.actors[actor_id].effect_stats)
        prestart_monster = dict(prestart.actors[-200].effect_stats)
        started, _, _ = prepare_ready(
            fight,
            account,
            True,
            initialize=initialize,
            stats_serializer=stats,
            effects_serializer=actor_effects,
        )
        player = started.actors[actor_id]
        self.assertIn(2636, {state.reference for state in player.state_ledger.entries})
        delta = {
            stat: player.effect_stats[stat] - prestart_player.get(stat, 0)
            for stat in player.effect_stats
            if player.effect_stats[stat] != prestart_player.get(stat, 0)
        }
        self.assertEqual(
            prestart_player.get(30), 169, "actual equipped Earth-resistance PC"
        )
        self.assertEqual(
            prestart_player.get(27), 65, "actual equipped generic-resistance PC"
        )
        expected_level = 10 if reference in (18091, 23215) else 5
        self.assertEqual(
            [
                (state.reference, state.level)
                for state in player.state_ledger.entries
                if state.reference == 2636
            ],
            [(2636, expected_level)],
        )
        self.assertTrue(delta, f"native 1003 made no stat change for {reference}")
        self.assertEqual(started.actors[-200].effect_stats, prestart_monster)
        return delta

    def test_all_four_owned_2636_items_enter_real_ready_with_native_criteria(self):
        observed = {}
        names = ("Start Alpha", "Start Bravo", "Start Charlie", "Start Delta")
        for index, reference in enumerate((18091, 23215, 27297, 27298)):
            with self.subTest(reference=reference):
                observed[reference] = self._start_owned_reference(
                    reference, 90 + index, names[index]
                )
        # 1003 also fires in the ordinary class Ready path (stats 33 and 36).
        # Check only the exact four PCs used by the 2636 913 leaves.
        self.assertEqual(
            {
                reference: {pc: delta.get(pc, 0) for pc in (28, 29, 30, 31)}
                for reference, delta in observed.items()
            },
            {
                18091: {28: 23, 29: 23, 30: -69, 31: 23},
                23215: {28: 23, 29: 23, 30: -69, 31: 23},
                27297: {28: 11, 29: 11, 30: -33, 31: 11},
                27298: {28: 11, 29: 11, 30: -33, 31: 11},
            },
            "Ready deltas must match each native 2636 level after float32 scaling",
        )

    def test_owned_2636_source_runs_once_through_ready_and_checkpoint(self):
        account = self.store.register("start-characteristic", "local-test-password")[
            "id"
        ]
        character = self.store.create_character(
            account, "Start Characteristic", breed=1
        )
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

        equipped = []
        for inventory_slot, (item_reference, equipment_slot) in enumerate(
            ((24021, 15), (24614, 10), (24618, 12), (24621, 3), (26943, 4), (18091, 5))
        ):
            item = grant(
                self.store,
                account,
                generation,
                character["id"],
                reference=item_reference,
                quantity=1,
                container=character["inventory_containers"][0]["uid"],
                slot=inventory_slot,
                allowed_references={item_reference},
            )
            equipped.append((item["uid"], equipment_slot))
        deck = encode_deck()
        character = self.store.save_build(
            account,
            generation,
            character["id"],
            0,
            {
                "sheet": b"".join(
                    wire.proto_field(tag, value)
                    for tag, value in (
                        (8, 0),
                        (18, b"Start Characteristic"),
                        (24, 200),
                        (56, 0),
                    )
                ),
                "equipment": b"".join(
                    wire.proto_field(
                        10, wire.proto_field(8, uid) + wire.proto_field(16, slot)
                    )
                    for uid, slot in equipped
                ),
                "deck": deck,
                "aptitudes": b"",
            },
        )
        character = self.store.character(account, character["id"])
        resources = combat_resources(character)
        cells = [(0, 0, 0), (1, 0, 0)]
        terrain = arena(1134, 1, cells, {0: cells[0], 1: cells[1]})
        terrain["validated_cells"] = cells
        monster = owned_instance(5525, 1, -200, map_id=1134, x=1, y=0, z=0)
        fight, _ = create_placement(
            character,
            monster,
            terrain,
            fight_id=77,
            player_ap=resources["ap"],
            player_mp=resources["mp"],
            player_wp=resources["wp"],
            player_initiative=resources["initiative"],
            terrain_effect_id=46,
            terrain_instance_id=1,
        )
        initialize_fight_snapshots(
            fight,
            characters={character["id"]: character},
            monsters={-200: monster},
            wp_resources={
                character["id"]: (resources["wp"], resources["wp"]),
                -200: (monster["wp"], monster["wp"]),
            },
            running_effects={character["id"]: (), -200: ()},
            initial_effect_uid=1,
        )
        for actor in fight.actors.values():
            actor.direction = 0 if actor.controlled else 3
        rng = Random(2636)

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
                    7,
                    wp_current=actor.effect_stats[4],
                    wp_maximum=resources["wp"],
                )
            return actual_monster_actor_stats(
                monster,
                actor,
                7,
                wp_current=monster["wp"],
                wp_maximum=monster["wp"],
            )

        original = snapshot(fight)
        pre_start_fight = deepcopy(fight)
        pre_start_fight.ready(account, True)
        before_start, _ = prepare_server_initialization(
            character,
            {-200: monster},
            pre_start_fight,
            account,
            deck,
            action_id=1,
            rng=Random(2636),
            fight_start=False,
        )
        pre_start_stats = dict(before_start.actors[character["id"]].effect_stats)
        pre_start_monster_stats = dict(before_start.actors[-200].effect_stats)
        started, runtime, packets = prepare_ready(
            fight,
            account,
            True,
            initialize=initialize,
            stats_serializer=stats,
            effects_serializer=actor_effects,
        )
        self.assertEqual(snapshot(fight), original)
        self.assertTrue(packets)
        self.assertTrue(started.native_start_event_delivered)
        actor = started.actors[character["id"]]
        self.assertIn(2636, {state.reference for state in actor.state_ledger.entries})
        delta = {
            stat: actor.effect_stats[stat] - pre_start_stats.get(stat, 0)
            for stat in actor.effect_stats
            if actor.effect_stats[stat] != pre_start_stats.get(stat, 0)
        }
        self.assertEqual(
            {pc: delta.get(pc, 0) for pc in (28, 29, 30, 31)},
            {28: 23, 29: 23, 30: -69, 31: 23},
            "2636 leaves must apply their native float32-scaled resistance values",
        )
        self.assertEqual(
            {pc: delta.get(pc, 0) for pc in (33, 36)},
            {33: 30, 36: 30},
            "independent Enutrof start group remains in the same Ready projection",
        )
        self.assertEqual(
            started.actors[-200].effect_stats,
            pre_start_monster_stats,
            "the 2636 start group is self-targeted and must not modify the other actor",
        )
        self.assertTrue(getattr(actor, "native_start_event_delivered", True))
        started_snapshot = snapshot(started)

        # The actual durable checkpoint is what reconnect restores; Ready replay
        # must not re-run the native 1003 group or change its state/stat snapshot.
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO combat_fights(id,status) OVERRIDING SYSTEM VALUE VALUES(77,'active')"
            )
            db.execute(
                "INSERT INTO combat_fight_participants(fight_id,character_id,account_id,team,session_generation) "
                "VALUES(77,%s,%s,0,%s)",
                (character["id"], account, generation),
            )
        checkpoints = Checkpoints(self.store)
        revision = checkpoints.save(account, generation, started)
        restored = checkpoints.read(account, 77)
        self.assertEqual(restored["revision"], revision)
        self.assertEqual(snapshot(started), started_snapshot)
        same, messages, empty = prepare_ready(
            started,
            account,
            True,
            initialize=initialize,
            stats_serializer=stats,
            effects_serializer=actor_effects,
        )
        self.assertIs(same, started)
        self.assertIsNone(messages)
        self.assertEqual(empty, ())
        self.assertEqual(snapshot(same), started_snapshot)
        self.assertEqual(
            restored["snapshot"]["actors"][str(character["id"])]["state_ledger"][
                "entries"
            ],
            started_snapshot["actors"][str(character["id"])]["state_ledger"]["entries"],
        )
        # Exercise the actual active reconnect bootstrap from the shared fight
        # runtime. It republishes the actor snapshot without replaying 1003.
        from wakfu_server.combat_session_adapter import CombatSessionAdapter
        from wakfu_server.combat_shared import Session

        session = Session(account, character["id"], generation, 1134, 0)
        reconnect = CombatSessionAdapter(self.store)
        shared = reconnect.registry.register(
            started,
            session,
            runtime=runtime,
            join_context={
                "arena": terrain,
                "terrain_effect_id": 46,
                "terrain_instance_id": 1,
                "group_key": (1134, 0, 9001),
                "leaders": {0: character["id"], 1: -200},
                "monsters": {-200: monster},
            },
        )
        reconnect_before = snapshot(started)
        reconnect_packets = reconnect.owned_reconnect_bootstrap(
            started, shared, session
        )
        self.assertTrue(reconnect_packets)
        self.assertIn(12847, [opcode for opcode, _ in reconnect_packets])
        self.assertEqual(snapshot(started), reconnect_before)
