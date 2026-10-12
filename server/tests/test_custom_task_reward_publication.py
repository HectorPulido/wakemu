"""Execute the actual reward-publication closure with mocked wire boundaries."""
import ast
from contextlib import contextmanager
import os
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

SOURCE = Path(
    os.environ.get("WAKFU_CUSTOM_REWARD_MAIN_CANDIDATE", "server/local_game_server.py")
)


class CustomTaskRewardPublicationTests(unittest.TestCase):
    def setUp(self):
        from wakfu_server.characters import (
            hero_wire,
        )  # Load only the lightweight wire boundary.

        tree = ast.parse(SOURCE.read_text())
        helper = next(
            n
            for n in ast.walk(tree)
            if isinstance(n, ast.FunctionDef)
            and n.name == "deliver_custom_task_rewards"
        )
        wrapper = ast.parse("def capture(character):\n    pass\n").body[0]
        wrapper.body = [helper] + ast.parse(
            "return deliver_custom_task_rewards, lambda: character"
        ).body
        self.events = []
        self.before = dict(id=2, account_id=1, level=1, xp=0, map_id=1134)
        self.after = dict(self.before, level=5, xp=1000)
        self.result = dict(
            character=self.after,
            packets=[(13613, b"xp"), (13873, b"unlocks")],
            delivered=[("hunter", 0)],
            capacity_pending=[],
        )
        self.deliver = Mock(return_value=self.result)
        self.active = None
        self.private = None

        @contextmanager
        def connection():
            yield SimpleNamespace(
                execute=lambda *args: SimpleNamespace(fetchone=lambda: self.active)
            )

        self.store = SimpleNamespace(
            connection=connection,
            characters=Mock(return_value=[self.after]),
            current_character_session=Mock(return_value=True),
        )
        self.public = []
        self.health = SimpleNamespace(initialize=Mock(return_value=self.after))
        self.level = SimpleNamespace(
            refresh=Mock(return_value=[(15548, b"owned-level"), (23548, b"roster")])
        )
        self.hero = SimpleNamespace(
            refresh=Mock(side_effect=lambda template, char: (13046, b"owned-level"))
        )
        self.progression = SimpleNamespace(
            outside_progression=Mock(return_value=(13046, b"absolute"))
        )
        self.patchers = [
            patch.dict(
                "sys.modules",
                {
                    "wakfu_server.custom_tasks.reward_delivery": SimpleNamespace(
                        deliver=self.deliver
                    ),
                    "wakfu_server.combat_lifecycle": self.progression,
                    "wakfu_server.level_publication": self.level,
                },
            ),
            patch("wakfu_server.characters.hero_wire", self.hero),
        ]
        for patcher in self.patchers:
            patcher.start()
            self.addCleanup(patcher.stop)
        context = dict(
            STORE=self.store,
            account_id=1,
            generation="a" * 32,
            connection=object(),
            service="world",
            active_private_session=lambda: self.private,
            send=lambda connection, service, opcode, body: self.events.append(
                (opcode, body)
            ),
            send_batch=lambda connection, service, packets: self.events.extend(packets),
            rich_inventory_packet=lambda character: (13713, b"inventory"),
            OWNED_HERO_TEMPLATE=b"\x0aowned",
            COMBAT_TEST_WP=6,
            CHARACTERS=b"roster",
            PLAYER_TEMPLATE=b"public",
            health_store=self.health,
            WORLD=SimpleNamespace(update=lambda *args: self.public.append(args)),
            wire=SimpleNamespace(
                refresh_player=lambda template, char: (15548, b"public")
            ),
            send_native_planting_bonus=lambda *args: None,
            record=lambda **kwargs: None,
        )
        exec(
            compile(
                ast.fix_missing_locations(ast.Module(body=[wrapper], type_ignores=[])),
                str(SOURCE),
                "exec",
            ),
            context,
        )
        self.context = context
        self.call, self.current = context["capture"](self.before)

    def test_live_delta_precedes_owned_level_spellbook_and_absolute_inventory(self):
        self.call()
        self.assertEqual(
            self.events,
            [
                (13613, b"xp"),
                (13873, b"unlocks"),
                (15548, b"owned-level"),
                (23548, b"roster"),
                (13046, b"absolute"),
                (13713, b"inventory"),
            ],
        )
        self.assertEqual(self.current(), self.after)
        self.level.refresh.assert_called_once_with(
            self.after,
            [self.after],
            entity_template=b"\x0aowned",
            roster_template=b"roster",
        )
        self.health.initialize.assert_called_once_with(
            self.store, 1, "a" * 32, 2, coefficient=1
        )
        self.assertEqual(self.public, [("a" * 32, self.after, 15548, b"public")])
        self.progression.outside_progression.assert_called_once_with(self.after, wp=6)

    def test_bootstrap_suppresses_additive_packets_and_retains_account_snapshots(self):
        self.result["packets"] += [
            (12471, b"item"),
            (12266, b"emote"),
            (13873, b"titles"),
        ]
        self.call(bootstrap=True)
        self.assertEqual(self.events, [(13873, b"unlocks"), (13873, b"titles")])
        self.assertEqual(self.current(), self.after)
        self.level.refresh.assert_not_called()
        self.progression.outside_progression.assert_not_called()

    def test_active_recovered_fight_defers_without_grant_or_publication(self):
        self.active = {"active": 1}
        self.assertTrue(self.call(bootstrap=True)["deferred"])
        self.deliver.assert_not_called()
        self.assertEqual(self.events, [])
        self.assertEqual(self.current(), self.before)

    def test_private_context_survives_saved_character_reload(self):
        self.private = SimpleNamespace(
            owns=Mock(return_value=True),
            refresh=Mock(
                side_effect=lambda before, saved: dict(saved, map_id=9, instance_id=123)
            ),
        )
        self.call()
        self.assertEqual(self.current()["map_id"], 9)
        self.assertEqual(self.current()["instance_id"], 123)
        self.private.refresh.assert_called_once_with(self.before, self.after)
        self.progression.outside_progression.assert_called_once_with(
            self.current(), wp=6
        )

    def test_no_entitlement_does_not_publish_and_same_level_skips_owned_refresh(self):
        self.result["delivered"] = []
        self.result["packets"] = []
        self.call()
        self.assertEqual(self.events, [])
        self.level.refresh.assert_not_called()
        self.result["delivered"] = [("hunter", 0)]
        self.after["level"] = 1
        self.call()
        self.level.refresh.assert_not_called()
        self.assertEqual(self.events, [(13046, b"absolute"), (13713, b"inventory")])

    def test_commit_or_authorization_failure_never_emits_or_replaces_context(self):
        for error in (
            RuntimeError("Commit failed"),
            ValueError("Stale selected lease"),
        ):
            self.deliver.side_effect = error
            self.store.current_character_session.return_value = False
            with self.subTest(error=error), self.assertRaises(type(error)):
                self.call()
            self.assertEqual(self.events, [])
            self.assertEqual(self.current(), self.before)

    def test_recoverable_native_reward_failure_defers_only_current_owned_session(self):
        self.deliver.side_effect = ValueError("Invalid configured entitlement")
        self.assertTrue(self.call()["deferred"])
        self.assertEqual(self.events, [])
        self.assertEqual(self.public, [])
        self.assertEqual(self.current(), self.before)

    def test_actual_world_cache_refresh_broadcasts_only_public_packet(self):
        from wakfu_server.world import World

        self.before["instance_id"] = 0
        self.after["instance_id"] = 0
        self.after["hp"] = 80
        public = []
        world = World(
            lambda character: b"",
            lambda identity: b"",
            lambda peer, opcode, body: public.append((peer, opcode, body)),
        )
        world.players[2] = ("a" * 32, "owner", dict(self.before))
        world.players[3] = ("b" * 32, "peer", dict(self.before, id=3))
        self.context["WORLD"] = world
        self.call()
        self.assertEqual(world.players[2][2]["level"], 5)
        self.assertEqual(world.players[2][2]["hp"], 80)
        self.assertEqual(
            public, [("owner", 15548, b"public"), ("peer", 15548, b"public")]
        )
        self.assertTrue(
            all(body != b"xp" and body != b"owned-level" for _, _, body in public)
        )
