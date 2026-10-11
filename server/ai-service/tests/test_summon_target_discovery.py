"""Native range hints and observed summons order targets without hiding any."""
import unittest
from unittest.mock import patch
from wakfu_ai.bridge.world_bridge import _advisory_spell_capabilities
from wakfu_ai.context.native_context import NativeGraph
from wakfu_ai.planning.query_search import candidates
from test_query_search import ACTOR_ID, ENEMY_ID, FakeNativeSession, actor


class SummonTargetDiscoveryTests(unittest.TestCase):
    def test_missing_advisory_metadata_does_not_remove_owned_spell(self):
        with patch(
            "wakfu_server.combat_ai_capabilities.describe_spell",
            side_effect=KeyError("effects"),
        ):
            self.assertIsNone(_advisory_spell_capabilities(1152, 12))

    def test_unexpected_advisory_runtime_error_is_not_hidden(self):
        with patch(
            "wakfu_server.combat_ai_capabilities.describe_spell",
            side_effect=RuntimeError("broken runtime"),
        ):
            with self.assertRaisesRegex(RuntimeError, "broken runtime"):
                _advisory_spell_capabilities(1152, 12)

    def test_advisory_summon_tries_empty_native_range_without_losing_targets(self):
        cells = [(x, 0, 0) for x in range(7)] + [(0, 0, 1)]
        session = FakeNativeSession(spells=[], cells=cells, edges=[])
        session.root_state["actors"] = [
            actor(ACTOR_ID, 1, (0, 0, 0)),
            actor(ENEMY_ID, 0, (6, 0, 0)),
        ]
        spell = dict(
            spellId=1152, level=1, casting=dict(levels=[[3, 6, []]], conditional=[])
        )
        spell["advisoryCapabilities"] = dict(spellId=1152, level=1, tags=["summon"])
        graph = NativeGraph(session.root_graph)
        actions = list(
            candidates(graph, session.root_state, dict(spells=[spell]), ACTOR_ID)
        )
        casts = [a for a in actions if a["type"] == "cast"]
        self.assertEqual(casts[0]["target"], [3, 0, 0])
        self.assertEqual(casts[1]["target"], [4, 0, 0])
        self.assertEqual({tuple(a["target"]) for a in casts}, set(cells))

    def test_observed_summoning_prioritizes_empty_recipients_without_hiding_actors(
        self,
    ):
        cells = [(x, 0, 0) for x in range(7)] + [(0, 0, 1)]
        session = FakeNativeSession(spells=[], cells=cells, edges=[])
        spell = dict(
            spellId=1152, level=1, casting=dict(levels=[[3, 6, []]], conditional=[])
        )
        actions = list(
            candidates(
                NativeGraph(session.root_graph),
                session.root_state,
                dict(spells=[spell]),
                ACTOR_ID,
                {(1152, 1): {"summoning"}},
            )
        )
        casts = [a for a in actions if a["type"] == "cast"]
        self.assertNotIn("targetId", casts[0])
        self.assertEqual(casts[0]["target"], [4, 0, 0])
        self.assertTrue(any(a.get("targetId") == ENEMY_ID for a in casts))
        self.assertEqual({tuple(a["target"]) for a in casts}, set(cells))

    def test_advisory_range_orders_summons_with_unknown_casting_metadata(self):
        cells = [(x, 0, 0) for x in range(7)]
        session = FakeNativeSession(spells=[], cells=cells, edges=[])
        session.root_state["actors"] = [
            actor(ACTOR_ID, 1, (0, 0, 0)),
            actor(ENEMY_ID, 0, (6, 0, 0)),
        ]
        spell = dict(
            spellId=1152,
            level=1,
            casting=dict(levels=[[3, 6, []]], conditional=[], future_field=True),
            advisoryCapabilities=dict(
                spellId=1152, level=1, tags=["summon"], minimum=3, maximum=6
            ),
        )
        actions = list(
            candidates(
                NativeGraph(session.root_graph),
                session.root_state,
                dict(spells=[spell]),
                ACTOR_ID,
            )
        )
        casts = [a for a in actions if a["type"] == "cast"]
        self.assertEqual(casts[0]["target"], [3, 0, 0])
        self.assertEqual({tuple(a["target"]) for a in casts}, set(cells))
