"""Native Oracle start boundary renews real finite aptitude listeners."""
from pathlib import Path
import sys
import unittest

_ROOT = Path(__file__).resolve().parents[3]
for _path in (str(_ROOT / "server"), str(_ROOT / "server" / "tests")):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from wakfu_ai.native.native_oracle import NativeOracle
from wakfu_server.combat_runtime_messages import RuntimeMessages


class NativeOraclePeriodicAptitudeStartTests(unittest.TestCase):
    def make_expired_fight(self):
        from test_combat_aptitude_initialization import AptitudeInitializationTests
        from wakfu_server.combat_server_spell import prepare_server_initialization
        from wakfu_server.combat_timed_expiration import prepare_timed_expiration
        from wakfu_server.spells import encode_deck

        fixture = AptitudeInitializationTests()
        fixture.setUpClass()
        character = fixture.character_with(17, 3)
        deck = encode_deck()
        monster = fixture.monster
        fight, _ = prepare_server_initialization(
            character,
            {monster["id"]: monster},
            fixture.fight,
            character["account_id"],
            deck,
            action_id=1,
            fight_start=True,
        )
        state = fight.native_class_initializations[character["id"]]
        recipes = state.get("aptitude_periodic_recipes", {})
        self.assertTrue(recipes, state)
        root_ids = {row[2] for row in state["aptitudes"]}
        self.assertIn(165201, root_ids)
        listeners = [
            row
            for row in fight.native_owned_group_effects.values()
            if row.get("invocation", {}).get("reference") == 136452
            and row.get("invocation", {}).get("target_id") == character["id"]
        ]
        self.assertTrue(listeners, fight.native_owned_group_effects)
        timer = listeners[0]["timer"]
        expired, packets = prepare_timed_expiration(
            fight,
            actor_id=character["id"],
            round_number=timer["expiration_round"],
            phase=timer["phase"],
            action_id=2,
        )
        still_live = [
            row
            for row in expired.native_owned_group_effects.values()
            if row.get("invocation", {}).get("reference") == 136452
            and row.get("invocation", {}).get("target_id") == character["id"]
        ]
        self.assertFalse(still_live)
        runtime = RuntimeMessages(expired)
        oracle = NativeOracle(
            runtime,
            characters={character["id"]: character},
            monsters={monster["id"]: monster},
            decks={character["id"]: deck},
            excluded_decks={character["id"]: frozenset()},
            viewer_id=character["id"],
            flags={},
        )
        return fight, expired, character, monster, deck, oracle

    def test_real_start_boundary_renews_expired_listener_once_without_source_mutation(
        self,
    ):
        from wakfu_server.fight_checkpoint_store import snapshot

        live, expired, character, monster, deck, oracle = self.make_expired_fight()
        before_live = snapshot(live)
        before_expired = snapshot(expired)
        state = expired.native_class_initializations[character["id"]]
        budget = sum(row[1] for row in state["aptitudes"] if row[0] == 17)
        candidate, packets = oracle.live_start_boundary(
            expired, actor_id=character["id"], action_id=3
        )
        self.assertEqual(snapshot(live), before_live)
        self.assertEqual(snapshot(expired), before_expired)
        self.assertTrue(packets)
        listeners = [
            row
            for row in candidate.native_owned_group_effects.values()
            if row.get("invocation", {}).get("reference") == 136452
            and row.get("invocation", {}).get("target_id") == character["id"]
        ]
        self.assertEqual(len(listeners), 1)
        self.assertEqual(listeners[0]["execution_count"], budget)
        with self.assertRaisesRegex(ValueError, "already delivered"):
            oracle.live_start_boundary(candidate, actor_id=character["id"], action_id=4)

    def test_disabled_native_start_callback_does_not_renew(self):
        expired, _, character, monster, deck, _ = self.make_expired_fight()
        before = [
            row
            for row in expired.native_owned_group_effects.values()
            if row.get("invocation", {}).get("reference") == 136452
            and row.get("invocation", {}).get("target_id") == character["id"]
        ]
        runtime = RuntimeMessages(expired)
        oracle = NativeOracle(
            runtime,
            characters={character["id"]: character},
            monsters={monster["id"]: monster},
            decks={character["id"]: deck},
            excluded_decks={character["id"]: frozenset()},
            viewer_id=character["id"],
            flags={"native_start_events": False},
        )
        candidate, _ = oracle.live_start_boundary(
            expired, actor_id=character["id"], action_id=3
        )
        listeners = [
            row
            for row in candidate.native_owned_group_effects.values()
            if row.get("invocation", {}).get("reference") == 136452
            and row.get("invocation", {}).get("target_id") == character["id"]
        ]
        # The expired retained listener remains part of the snapshot; the
        # disabled callback must leave it unchanged rather than reconstruct it.
        self.assertEqual(listeners, before)


if __name__ == "__main__":
    unittest.main()
