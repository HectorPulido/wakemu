"""Distance spell grants are removed by the real combat finish path."""
import unittest
from copy import deepcopy
from unittest.mock import patch

import test_rii_lesson_terminal_grants as terminal_fixture
from wakfu_server import rii_lesson_grants
from wakfu_server.combat_lifecycle import prepare_finish
from wakfu_server.combat_runtime_messages import RuntimeMessages
from wakfu_server.combat_spell_grant import granted_spells


class DistanceTerminalTests(unittest.TestCase):
    def make_distance_fight(self):
        import test_combat_maximum_resource as maximum_fixture

        fixture = maximum_fixture.MaximumResourceTests()
        fixture.setUp()
        fight = fixture.fight
        contract = {"owner": 7, "target": -7, "hits": 2}
        fight.rii_distance_lesson_contract = contract
        refs = patch(
            "wakfu_server.combat_spell_grant.native_spell_references",
            return_value=frozenset({7967}),
        )
        casts = patch(
            "wakfu_server.combat_native_spell_casting.catalog",
            return_value={"7967": {"maximum_level": 200}},
        )
        refs.start()
        casts.start()
        self.addCleanup(refs.stop)
        self.addCleanup(casts.stop)
        contract["grant_uids"] = rii_lesson_grants.install(
            fight, 7, [], action_id=1, allocate_uid=lambda: 1001, lesson="distance"
        )
        contract["initialized"] = True
        return fight

    def test_distance_grant_removed_at_finish(self):
        fight = terminal_fixture.RiiLessonTerminalGrantTests.terminal_fight(
            self.make_distance_fight()
        )
        runtime = RuntimeMessages(fight)
        character = {"id": 7, "account_id": 3, "name": "Rii"}
        store, _ = terminal_fixture.RiiLessonTerminalGrantTests.store_for(character)
        with patch("wakfu_server.combat_results.fight_report"), patch(
            "wakfu_server.combat_results.finish_messages", return_value=[]
        ), patch("wakfu_server.fight_store.finish"), patch(
            "wakfu_server.combat_scene_outcome.prepare_outcome",
            return_value=(fight, ()),
        ), patch(
            "wakfu_server.combat_equipment_finish.prepare_equipment_finish",
            return_value=(deepcopy(fight), ()),
        ), patch(
            "wakfu_server.combat_captured_roster_checkpoint.persist_captured_roster_updates"
        ), patch(
            "wakfu_server.fight_store._write_terminal_checkpoint"
        ):
            result = prepare_finish(
                store,
                3,
                5,
                character,
                runtime,
                {},
                duration_ms=1,
                fight_instance_id=fight.id,
            )
        self.assertEqual([op for op, _ in result["packets"]].count(13560), 1)
        self.assertFalse(granted_spells(runtime.fight, 7))


if __name__ == "__main__":
    unittest.main()
