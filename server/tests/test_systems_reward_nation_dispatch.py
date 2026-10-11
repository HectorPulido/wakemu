"""Exercise the actual dispatcher seams without opening network services."""
import ast
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch


def dispatcher_code(predicate, *, function=False):
    tree = ast.parse(
        (Path(__file__).resolve().parents[1] / "local_game_server.py").read_text()
    )
    node = next(node for node in ast.walk(tree) if predicate(node))
    body = [node] if function else node.body
    return compile(
        ast.fix_missing_locations(ast.Module(body=body, type_ignores=[])),
        "<actual-systems-dispatcher>",
        "exec",
    )


class SystemsRewardNationDispatchTests(unittest.TestCase):
    def test_rift_currency_uses_ordinary_resolver_after_terminal_item_settlement(self):
        from wakfu_server.maps import rift_currency_rewards

        actors = {
            1: SimpleNamespace(id=1, team=0, pve_withdrawn=False),
            2: SimpleNamespace(id=2, team=0, pve_withdrawn=True),
            -1: SimpleNamespace(id=-1, team=1),
        }
        fight = SimpleNamespace(
            rift_wave_state={"instance_id": 7}, winner=0, actors=actors
        )
        ordered = []
        scope = dict(
            fight=fight,
            owner_characters={1: {}, 2: {}},
            STORE=object(),
            settle_rift_rewards=lambda db: ordered.append("settled"),
        )
        exec(
            dispatcher_code(
                lambda n: isinstance(n, ast.FunctionDef) and n.name == "shared_policy",
                function=True,
            ),
            scope,
        )
        member = dict(account_id=5, session_generation="lease", character_id=1)
        source = {"id": 1}
        expected = object()
        with patch.object(
            rift_currency_rewards,
            "resolve",
            side_effect=lambda *a, **kw: (ordered.append(kw), expected)[1],
        ):
            actual = scope["shared_policy"](object(), member, source)
        self.assertIs(actual, expected)
        self.assertEqual(ordered[0], "settled")
        self.assertEqual(ordered[1]["eligible_character_ids"], (1,))
        self.assertIs(ordered[1]["character"], source)

    def enrollment_scope(self, *, fight=None):
        return dict(
            fight=fight,
            STORE=object(),
            account_id=5,
            generation="lease",
            character={"id": 1},
            body=b"choice",
            bag_session=None,
            connection=object(),
            service="world",
            send=Mock(),
            record=Mock(),
            fixture=lambda opcode: b"fixture",
            wire=SimpleNamespace(adapt=lambda *args: b"owned-nation"),
            guild_company_packet=lambda *args: (13873, b"company-nation"),
            WORLD=Mock(),
            information=lambda text: (999, text.encode()),
        )

    def run_enrollment(self, scope):
        exec(
            dispatcher_code(
                lambda n: isinstance(n, ast.If)
                and ast.unparse(n.test) == "opcode == 12463 and loaded"
            ),
            scope,
        )

    def test_enrollment_refreshes_owned_company_and_peers_without_actor_reset(self):
        from wakfu_server.characters import nation_state, guild_wire

        saved = dict(id=1, nation_id=32, guild_native=None)
        scope = self.enrollment_scope()
        with patch.object(
            nation_state, "enroll", return_value=saved
        ) as enroll, patch.object(
            guild_wire, "remote_actor_update", return_value=(15548, b"peer")
        ) as remote:
            self.run_enrollment(scope)
        enroll.assert_called_once_with(scope["STORE"], 5, "lease", 1, b"choice")
        self.assertIs(scope["character"], saved)
        self.assertEqual(
            [call.args[2] for call in scope["send"].call_args_list], [15548, 13873]
        )
        self.assertEqual(remote.call_args.kwargs["nation_id"], 32)
        self.assertEqual(remote.call_args.kwargs["nation_synchro"], bytes(27))
        scope["WORLD"].update.assert_called_once_with(
            "lease", saved, 15548, b"peer", include_sender=False
        )

    def test_combat_or_rejected_enrollment_never_changes_world_or_company(self):
        from wakfu_server.characters import nation_state

        for fight in (object(), None):
            scope = self.enrollment_scope(fight=fight)
            with patch.object(
                nation_state, "enroll", side_effect=ValueError("denied")
            ) as enroll:
                self.run_enrollment(scope)
            if fight is not None:
                enroll.assert_not_called()
            scope["WORLD"].update.assert_not_called()
            self.assertEqual(scope["character"], {"id": 1})
            scope["send"].assert_called_once()
            self.assertEqual(scope["send"].call_args.args[2], 999)

    def difficulty_scope(self, *, fight=None, actor_id=1):
        import struct

        world = Mock()
        world.snapshot.return_value = [
            dict(map_id=10, instance_id=88),
            dict(map_id=10, instance_id=88),
            dict(map_id=11, instance_id=88),
            dict(map_id=10, instance_id=99),
        ]
        return dict(
            fight=fight,
            STORE=object(),
            account_id=5,
            generation="lease",
            character={"id": 1},
            body=struct.pack(">qiq", actor_id, 3, 88),
            WORLD=world,
            connection=object(),
            service="world",
            send=Mock(),
            record=Mock(),
            DatabaseError=RuntimeError,
            PoolTimeout=TimeoutError,
            information=lambda text: (999, text.encode()),
        )

    def run_difficulty(self, scope):
        exec(
            dispatcher_code(
                lambda n: isinstance(n, ast.If)
                and ast.unparse(n.test) == "opcode == 12223 and loaded"
            ),
            scope,
        )

    def test_difficulty_checks_durable_instance_and_updates_all_instance_maps_once(
        self,
    ):
        from wakfu_server.maps import dungeon_context, dungeon_difficulty

        scope = self.difficulty_scope()
        with patch.object(
            dungeon_difficulty,
            "select",
            return_value={"instance_id": 88, "stasis_level": 3},
        ) as select, patch.object(
            dungeon_context, "update_packet", return_value=(13339, b"context")
        ) as update:
            self.run_difficulty(scope)
        select.assert_called_once_with(
            scope["STORE"], 5, "lease", 1, stasis_level=3, expected_instance_id=88
        )
        update.assert_called_once_with(scope["STORE"], 88, fight_in_progress=False)
        self.assertEqual(
            {call.args for call in scope["WORLD"].emit_location.call_args_list},
            {(10, 88, 13339, b"context"), (11, 88, 13339, b"context")},
        )
        self.assertEqual(scope["WORLD"].emit_location.call_count, 2)
        scope["send"].assert_not_called()

    def test_difficulty_rejects_combat_forged_actor_malformed_and_denied_selection(
        self,
    ):
        from wakfu_server.maps import dungeon_context, dungeon_difficulty

        for case in ("combat", "actor", "malformed", "denied"):
            scope = self.difficulty_scope(
                fight=object() if case == "combat" else None,
                actor_id=2 if case == "actor" else 1,
            )
            if case == "malformed":
                scope["body"] = b"invalid"
            with patch.object(
                dungeon_difficulty, "select", side_effect=ValueError("denied")
            ) as select, patch.object(dungeon_context, "update_packet") as update:
                self.run_difficulty(scope)
            if case != "denied":
                select.assert_not_called()
            update.assert_not_called()
            scope["WORLD"].emit_location.assert_not_called()
            scope["send"].assert_called_once()


if __name__ == "__main__":
    unittest.main()
