"""Run the actual exploration timer branch with an expiring owned hero food."""
import ast
import itertools
from pathlib import Path
import struct
from types import SimpleNamespace
from unittest.mock import Mock

from postgres_case import PostgresCase
from wakfu_server import consumable_buff_wire
from wakfu_server.characters import heroes
from wakfu_server.health_policy import apply_damage
from wakfu_server.inventory_consumable_effects import use
from wakfu_server.inventory_items import grant
from wakfu_server.territory_bonuses import world_packets


def timer_branch():
    source = Path(__file__).resolve().parents[1] / "local_game_server.py"
    tree = ast.parse(source.read_text())
    matches = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.If)
        and "last_consumable_tick" in ast.unparse(node.test)
        and "loaded" in ast.unparse(node.test)
    ]
    if len(matches) != 1:
        raise AssertionError("Expected one real consumable world timer branch")
    return compile(
        ast.fix_missing_locations(ast.Module(body=matches, type_ignores=[])),
        str(source),
        "exec",
    )


class WorldHeroConsumableExpiryTests(PostgresCase):
    def test_hero_only_expiry_removes_native_effects_and_refreshes_stats_without_actor_reset(
        self,
    ):
        clock = [1000.0]
        self.store.clock = lambda: clock[0]
        account = self.store.register("hero-expiry", "local-password")["id"]
        main = self.store.create_character(account, "Expiry Main")
        generation = self.store.begin_session(account)
        self.store.select_character(account, generation, main["id"])
        hero = self.store.create_character(account, "Expiry Hero")
        heroes.add(self.store, account, generation, main["id"], hero["id"])
        source = grant(
            self.store,
            account,
            generation,
            hero["id"],
            reference=3663,
            quantity=1,
            container=hero["inventory_containers"][0]["uid"],
            slot=0,
            allowed_references={3663},
        )
        used = use(
            self.store,
            account,
            generation,
            main["id"],
            struct.pack(">qB", source["uid"], 0),
            expected_hp=main["hp"],
            in_fight=False,
        )
        with self.store.connection() as db:
            apply_damage(db, used["character"], 10, False)
            db.execute(
                "UPDATE character_consumable_buffs SET remaining_ms=1000 WHERE character_id=%s",
                (hero["id"],),
            )
        before_hero = self.store.character(account, hero["id"])
        other_hero = self.store.create_character(account, "Unchanged Hero")
        heroes.add(self.store, account, generation, main["id"], other_hero["id"])
        other_food = grant(
            self.store,
            account,
            generation,
            other_hero["id"],
            reference=3663,
            quantity=1,
            container=other_hero["inventory_containers"][0]["uid"],
            slot=0,
            allowed_references={3663},
        )
        other_used = use(
            self.store,
            account,
            generation,
            main["id"],
            struct.pack(">qB", other_food["uid"], 0),
            expected_hp=main["hp"],
            in_fight=False,
        )
        other_state_ids = [
            (s["uid"], s["state_id"], s["level"])
            for s in other_used["character"]["consumable_states"]
        ]
        main_live = self.store.character(account, main["id"])
        self.assertFalse(main_live["consumable_states"])
        self.assertTrue(before_hero["consumable_states"])
        location_keys = ("map_id", "instance_id", "x", "y", "z", "direction")
        clock[0] = 1002.0
        packets = []
        world = SimpleNamespace(broadcast=Mock())
        publisher = Mock()
        context = dict(
            loaded=True,
            character=main_live,
            last_consumable_tick=0,
            time=SimpleNamespace(monotonic=lambda: 10),
            fight=None,
            combat_session=None,
            STORE=self.store,
            account_id=account,
            generation=generation,
            WORLD=world,
            LOCAL_WORLD_ACTIONS=itertools.count(100),
            publish_consumable_character=publisher,
            connection=object(),
            service="world",
            send=lambda _connection, _service, opcode, body: packets.append(
                (opcode, body)
            ),
        )
        exec(timer_branch(), context)
        after = self.store.character(account, hero["id"])
        self.assertEqual(after["consumable_states"], ())
        self.assertEqual(after["hp_damage"], before_hero["hp_damage"])
        self.assertEqual(after["hp_damage"], 10)
        self.assertEqual(
            tuple(after[k] for k in location_keys),
            tuple(before_hero[k] for k in location_keys),
        )
        self.assertEqual(context["character"]["id"], main["id"])
        world.broadcast.assert_not_called()
        publisher.assert_not_called()
        counter = itertools.count(100)
        expected = [
            *consumable_buff_wire.delta(
                before_hero, after, allocate_action=lambda: next(counter)
            ),
            *world_packets(after),
        ]
        self.assertTrue(expected)
        self.assertEqual(packets, expected)
        self.assertEqual([opcode for opcode, _ in packets[-3:]], [13046, 13811, 13046])

        other_after = self.store.character(account, other_hero["id"])
        self.assertEqual(
            [
                (s["uid"], s["state_id"], s["level"])
                for s in other_after["consumable_states"]
            ],
            other_state_ids,
        )
        packets.clear()
        context["time"] = SimpleNamespace(monotonic=lambda: 20)
        exec(timer_branch(), context)
        self.assertEqual(packets, [])
