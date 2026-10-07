import os
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

from world_hook_template import HOOK


class WorldHookTests(unittest.TestCase):
    def test_absent_encounter_does_not_access_stale_shared_session(self):
        from world_host import execute

        world = dict(combat_session=object())
        for runtime in (None, SimpleNamespace(fight=None)):
            with self.subTest(runtime=runtime):
                self.assertEqual(
                    list(
                        execute(
                            runtime,
                            dict(globals=world, scopes=[]),
                            lambda *args, **kwargs: self.fail(
                                "No encounter may execute"
                            ),
                        )
                    ),
                    [],
                )

    def hook(self, *, shared=False, nested=False):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        directory = Path(temporary.name)
        directory.joinpath("world_loader.py").write_text(
            "def load_entry(directory):\n"
            "    def entry(runtime, **kwargs):\n"
            "        from world_host import execute\n"
            "        def runner(native, **bindings):\n"
            "            native.calls.append(bindings)\n"
            "            yield [(12588,b'native')], {'protocol':3,'action':{'type':'cast'}}\n"
            "        yield from execute(runtime, kwargs['world_context'], runner)\n"
            "    return entry\n"
        )
        calls = []
        npc = SimpleNamespace(
            id=-7, team=1, hp=20, controlled=False, effect_stats={97: 0}
        )
        fight = SimpleNamespace(
            id=41, current=npc, phase="active", turn_id=1, sequence=1, actors={-7: npc}
        )
        runtime = SimpleNamespace(
            fight=fight, awaiting_ack=None, pending=[], calls=calls
        )
        sent, records, refreshed, drained = [], [], [], []
        context = dict(
            __file__=str(directory / "local_game_server.py"),
            os=os,
            fight=fight,
            fight_messages=runtime,
            STORE=object(),
            character={"id": 7, "future": b"all"},
            TEST_MONSTERS_BY_ID={-7: {"ref": 5525}},
            COMBAT_SESSIONS=SimpleNamespace(
                registry=SimpleNamespace(
                    lookup=lambda identity: SimpleNamespace(
                        runtime=runtime, fight=fight
                    )
                )
            ),
            combat_session=object() if shared else None,
            refresh_shared_combat=lambda: refreshed.append(True),
            drain_shared_combat=lambda: drained.append(True),
            current_combat_stats=lambda actor: b"native-stats",
            connection=object(),
            service="world",
            send=lambda connection, service, opcode, body: sent.append((opcode, body)),
            record=lambda **fields: records.append(fields),
            complete_test_fight=lambda: None,
        )
        exec(HOOK, context)
        if nested:
            exec(
                "def session():\n"
                "    character = {'id': 8, 'future_owner': b'complete-owner'}\n"
                "    def helper():\n"
                "        character = {'id': 999, 'temporary': True}\n"
                "        pass_test_monster_turn()\n"
                "    helper()\n",
                context,
            )
        with patch.dict(os.environ, {"WAKFU_AI_SDK_DIR": str(directory)}):
            context["session" if nested else "pass_test_monster_turn"]()
        return context, calls, sent, records, refreshed, drained

    def test_local_hook_loads_the_sdk_and_passes_full_authorities_without_deck_projection(
        self,
    ):
        context, calls, sent, records, refreshed, drained = self.hook()
        self.assertIs(calls[0]["store"], context["STORE"])
        self.assertIs(calls[0]["viewer_character"], context["character"])
        self.assertIs(calls[0]["monsters"], context["TEST_MONSTERS_BY_ID"])
        self.assertEqual(sent, [(12588, b"native")])
        self.assertEqual(records[0]["decision"]["protocol"], 3)
        self.assertEqual(refreshed, [])
        self.assertEqual(drained, [])

    def test_shared_hook_uses_coordinator_outbox_and_never_direct_sends_its_packets(
        self,
    ):
        context, calls, sent, records, refreshed, drained = self.hook(shared=True)
        self.assertIs(calls[0]["shared_adapter"], context["COMBAT_SESSIONS"])
        self.assertIs(calls[0]["session"], context["combat_session"])
        self.assertEqual(sent, [])
        self.assertEqual(len(refreshed), 2)
        self.assertEqual(len(drained), 1)

    def test_complete_scope_bridge_preserves_outer_owner_over_temporary_helper_character(
        self,
    ):
        _, calls, sent, _, _, _ = self.hook(nested=True)
        self.assertEqual(
            calls[0]["viewer_character"], {"id": 8, "future_owner": b"complete-owner"}
        )
        self.assertEqual(sent, [(12588, b"native")])

    def test_legacy_embedding_needs_no_shared_adapter_or_shared_helper_symbols(self):
        from world_host import execute

        _, calls, _, _, _, _ = self.hook()
        npc = SimpleNamespace(
            id=-7, team=1, hp=20, controlled=False, effect_stats={97: 0}
        )
        runtime = SimpleNamespace(
            fight=SimpleNamespace(
                current=npc,
                actors={-7: npc},
                turn_id=1,
                sequence=1,
                id=41,
                phase="active",
            ),
            awaiting_ack=None,
            pending=[],
        )
        arguments = []

        def runner(runtime, **kwargs):
            arguments.append(kwargs)
            yield [], {"action": {"type": "end_turn"}}

        world = dict(
            STORE=object(),
            character={"id": 7},
            TEST_MONSTERS_BY_ID={},
            connection=object(),
            service="world",
            send=lambda *args: None,
            record=lambda **kwargs: None,
        )
        list(execute(runtime, dict(globals=world, scopes=[]), runner))
        self.assertIsNone(arguments[0]["session"])
        self.assertIsNone(arguments[0]["shared_adapter"])
