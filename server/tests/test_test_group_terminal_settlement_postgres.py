"""Native test groups cannot award progression, loot, or corpses."""
import ast
import copy
import struct
from pathlib import Path
import unittest

from test_combat_companions_postgres import OwnedCompanionCombatPostgresTests
from wakfu_server import fight_store, item_test_spawns
from wakfu_server.combat_group_store import PersistentGroups
from wakfu_server.inventory_items import grant


def world_callback(name, bindings):
    source = Path(__file__).resolve().parents[1] / "local_game_server.py"
    tree = ast.parse(source.read_text())
    outer = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == "complete_test_fight"
    )
    node = next(
        node
        for node in ast.walk(outer)
        if isinstance(node, ast.FunctionDef) and node.name == name
    )

    class Scope(ast.NodeTransformer):
        def visit_Nonlocal(self, item):
            return ast.copy_location(ast.Global(names=item.names), item)

    module = ast.fix_missing_locations(
        ast.Module(body=[Scope().visit(node)], type_ignores=[])
    )
    exec(compile(module, str(source), "exec"), bindings)
    return bindings[name]


class TestGroupTerminalSettlementPostgresTests(OwnedCompanionCombatPostgresTests):
    def test_shared_terminal_test_group_zeroes_rewards_and_preserves_companion_report(
        self,
    ):
        from wakfu_server import monsters
        from wakfu_server.combat_state import Actor, Fight
        from wakfu_server.combat_session_adapter import CombatSessionAdapter
        from wakfu_server.combat_global_pv_collections import (
            initialize_global_pv_collections,
        )
        from wakfu_server.combat_actor_snapshot import initialize_fight_snapshots
        from wakfu_server.equipment_stats import combat_resources
        from wakfu_server.builds import effective_sheet_level
        from wakfu_server.combat_lifecycle import prepare_finish_shared
        from wakfu_server.combat_companions import admit_owned_companions
        from wakfu_server.combat_runtime_messages import RuntimeMessages
        from wakfu_server.combat_terrain import map_geometry
        from wakfu_server.wire import proto_fields

        with self.store.connection() as db:
            db.execute(
                "UPDATE combat_fights SET status='aborted' WHERE id=%s",
                (self.fight_id,),
            )
            db.execute("UPDATE accounts SET is_admin=true WHERE id=%s", (self.account,))
        container = next(
            row["uid"] for row in self.main["inventory_containers"] if row["kind"] == 0
        )
        source = grant(
            self.store,
            self.account,
            self.generation,
            self.main["id"],
            reference=30532,
            quantity=1,
            container=container,
            slot=1,
            allowed_references={30532},
        )
        groups = PersistentGroups(self.store)
        spawn = item_test_spawns.use(
            self.store,
            groups,
            self.account,
            self.generation,
            self.main["id"],
            struct.pack(">iq", item_test_spawns.ACTION_ID, source["uid"]),
            in_fight=False,
            geometry=map_geometry,
        )
        with self.store.connection() as db:
            members = db.execute(
                "SELECT members FROM combat_groups WHERE map_id=%s AND instance_id=%s AND group_id=%s",
                spawn["key"],
            ).fetchone()["members"]
        member = members[0]
        fight_id = fight_store.create(
            self.store,
            self.account,
            self.generation,
            self.main["id"],
            team=0,
        )
        self.fight_id = fight_id
        lease, _ = groups.claim(spawn["key"], self.generation, fight_id)
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
        player.initiative = -1
        dummy = monsters.owned_instance(
            member["ref"],
            member["level"],
            member["id"],
            map_id=1134,
            instance_id=0,
            x=-4,
            y=-17,
            z=0,
            team=1,
        )
        opponent = Actor(
            dummy["id"],
            1,
            (-4, -17, 0),
            dummy["hp"],
            dummy["ap"],
            dummy["mp"],
            dummy["initiative"],
            dummy["level"],
            max_hp=dummy["max_hp"],
        )
        opponent.initiative = -100
        arena_fight = Fight(
            fight_id,
            [player, opponent],
            self.fight.walkable,
            self.fight.placement,
            self.fight.edges,
        )
        arena_fight.native_qi_snapshot = copy.deepcopy(self.fight.native_qi_snapshot)
        arena_fight.native_qi_surface_provenance = copy.deepcopy(
            self.fight.native_qi_surface_provenance
        )
        from wakfu_server.combat_geometry_snapshot import freeze_terrain

        freeze_terrain(arena_fight)
        initialize_global_pv_collections(
            arena_fight,
            tuple(arena_fight.actors),
            controller_registration=True,
        )
        initialize_fight_snapshots(
            arena_fight,
            characters={self.main["id"]: self.main},
            monsters={dummy["id"]: dummy},
            wp_resources={
                self.main["id"]: (player_resources["wp"], player_resources["wp"]),
                dummy["id"]: (dummy["wp"], dummy["wp"]),
            },
            running_effects={self.main["id"]: (), dummy["id"]: ()},
            initial_effect_uid=1,
        )
        with self.store.connection() as db:
            admitted = admit_owned_companions(
                db,
                self.store,
                self.session,
                arena_fight,
                owner_character=self.main,
            )
        ready = CombatSessionAdapter(self.store).ready_transition(
            self.session,
            admitted["fight"],
            None,
            True,
            {dummy["id"]: dummy},
        )
        fight = ready.fight
        fight.actors[dummy["id"]].hp = 0
        fight.actors[self.companion_id].hp = 1
        fight.phase, fight.winner = "finished", 0
        runtime = RuntimeMessages(fight)
        test_monsters = [dummy]
        bindings = dict(
            is_developer_test_fight=item_test_spawns.is_fight,
            finish_developer_test_group=item_test_spawns.finish,
            finish_world_group=lambda *args, **kwargs: (_ for _ in ()).throw(
                AssertionError("test group reached ordinary world settlement")
            ),
            fight=fight,
            group_lease=lease,
            COMBAT_GROUPS=groups,
            STORE=self.store,
            account_id=self.account,
            generation=self.generation,
            character=self.main,
            TEST_MONSTERS=test_monsters,
            DUNGEON_ROOM_RUNTIME_AVAILABLE=False,
            committed_task_candidates=[],
            frozen_contexts={},
        )
        callbacks = {
            name: world_callback(name, bindings)
            for name in (
                "settle_achievements",
                "shared_policy",
                "shared_loot",
                "shared_group_settlement",
            )
        }
        individual_callbacks = {
            name: world_callback(name, bindings)
            for name in (
                "resolve_fight_reward",
                "resolve_fight_loot",
                "settle_individual_group",
            )
        }
        with self.store.connection() as db:
            individual_policy = individual_callbacks["resolve_fight_reward"](db)
            self.assertEqual((0, 0), (individual_policy.xp, individual_policy.kamas))
            individual_loot = individual_callbacks["resolve_fight_loot"](
                db,
                individual_policy,
            )
            self.assertEqual({"loots": [], "packets": []}, individual_loot)
        metadata = {
            self.main["id"]: dict(
                kind="player",
                account_id=self.account,
                name=self.main["name"],
                breed=self.main["breed"],
                is_male=self.main["sex"] == 0,
            ),
            dummy["id"]: dict(kind="monster", ref=dummy["ref"]),
            self.companion_id: dict(
                kind="monster", ref=admitted["sources"][self.companion_id]["ref"]
            ),
        }
        with groups.lock:
            packets = prepare_finish_shared(
                self.store,
                self.account,
                self.generation,
                self.main["id"],
                runtime,
                metadata,
                duration_ms=500,
                fight_instance_id=fight.id,
                policy_resolver=callbacks["shared_policy"],
                loot_resolver=callbacks["shared_loot"],
                progression_resolver=callbacks["settle_achievements"],
                expected_accounts={self.account},
                owner_character_ids={self.account: self.main["id"]},
                group_settlement=callbacks["shared_group_settlement"],
            )
        # The individual group callback shares the same durable retirement
        # fence and is safe after terminal replay.
        with groups.lock, self.store.connection() as db:
            self.assertFalse(
                individual_callbacks["settle_individual_group"](db, lease, True)[
                    "applied"
                ]
            )

        with self.store.connection() as db:
            reward = db.execute(
                "SELECT xp,kamas FROM fight_rewards WHERE fight_id=%s AND character_id=%s",
                (fight.id, self.main["id"]),
            ).fetchone()
            self.assertEqual((0, 0), tuple(reward.values()))
            wallet = db.execute(
                "SELECT p.xp,w.kamas FROM character_progression p CROSS JOIN account_wallets w "
                "WHERE p.character_id=%s AND w.account_id=%s",
                (self.main["id"], self.account),
            ).fetchone()
            self.assertEqual(
                (self.main["xp"], self.main["kamas"]), tuple(wallet.values())
            )
            self.assertEqual(
                0,
                db.execute(
                    "SELECT count(*) AS n FROM fight_drop_awards WHERE fight_id=%s",
                    (fight.id,),
                ).fetchone()["n"],
            )
            self.assertEqual(
                0,
                db.execute(
                    "SELECT count(*) AS n FROM monster_corpses WHERE fight_id=%s",
                    (fight.id,),
                ).fetchone()["n"],
            )
            self.assertEqual(
                0,
                db.execute(
                    "SELECT count(*) AS n FROM character_achievement_events WHERE character_id=%s",
                    (self.main["id"],),
                ).fetchone()["n"],
            )
            self.assertEqual(
                0,
                db.execute(
                    "SELECT count(*) AS n FROM character_custom_task_events WHERE character_id=%s",
                    (self.main["id"],),
                ).fetchone()["n"],
            )
            group = db.execute(
                "SELECT g.status,t.ended_at FROM combat_groups g JOIN developer_item_test_groups t "
                "USING(map_id,instance_id,group_id) WHERE g.map_id=%s AND g.instance_id=%s AND g.group_id=%s",
                spawn["key"],
            ).fetchone()
            self.assertEqual("defeated", group["status"])
            self.assertIsNotNone(group["ended_at"])
            sidekick = db.execute(
                "SELECT hp,max_hp,xp FROM account_companions WHERE id=%s",
                (self.companion_id,),
            ).fetchone()
            self.assertEqual(sidekick["max_hp"], sidekick["hp"])
            self.assertEqual(0, sidekick["xp"])
        report_packet = next(
            body for opcode, body in packets[self.account] if opcode == 12755
        )
        report = dict(proto_fields(report_packet[12:]))
        rows = [
            dict(proto_fields(value))
            for tag, value in proto_fields(report[42])
            if tag == 26
        ]
        companion_report = next(row for row in rows if row.get(8) == self.companion_id)
        self.assertEqual(self.account, companion_report[16])
        self.assertEqual([], list(proto_fields(companion_report.get(34, b""))))


def load_tests(loader, tests, pattern):
    return loader.loadTestsFromName(
        __name__
        + ".TestGroupTerminalSettlementPostgresTests.test_shared_terminal_test_group_zeroes_rewards_and_preserves_companion_report"
    )
