"""Actual command-handler reply with a real committed Registry outcome.

SQL authorization/rebind and already-completed settlement are explicit seams;
apply_outcome, Registry ownership and the actual chat encoder remain real.
"""
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from protocol_codec import Reader
from wakfu_server import wire
from test_astrub_dispatch import AstrubDispatcherTests
from test_combat_command_recovery_registry import CommandRecoveryRegistryTests


class CommittedOutcomeFeedbackTests(unittest.TestCase):
    dispatcher = AstrubDispatcherTests.dispatcher

    def test_opposite_request_reports_actual_committed_result_without_rewriting_it(
        self,
    ):
        for team in (0, 1):
            for winner in (0, 1):
                with self.subTest(team=team, winner=winner):
                    registry, shared, owners = CommandRecoveryRegistryTests().fixture(
                        "finished"
                    )
                    owner = owners[0]
                    shared.fight.winner = winner
                    shared.fight.events = [("already-finished", winner)]
                    shared.fight.actors[owner.character_id].team = team
                    shared.settlement_ready = True
                    self.account, self.generation = owner.account_id, owner.generation
                    self.saved = dict(
                        id=owner.character_id,
                        name="Owner",
                        map_id=527,
                        instance_id=0,
                        x=0,
                        y=32,
                        z=0,
                    )
                    self.store = Mock()
                    ns, sent, _ = self.dispatcher(
                        fight=shared.fight, combat_session=owner
                    )
                    ns.update(
                        COMBAT_SESSIONS=SimpleNamespace(registry=registry),
                        wire=wire,
                        complete_test_fight=Mock(),
                        refresh_shared_combat=Mock(),
                    )
                    before = (
                        shared.fight,
                        shared.runtime,
                        shared.ack,
                        tuple(shared.fight.events),
                        shared.fight.winner,
                        dict(shared.participants),
                        set(shared.returned),
                    )
                    won = team == winner
                    command = "!losefight" if won else "!winfight"
                    with patch(
                        "wakfu_server.command_permissions.authorize_command"
                    ), patch(
                        "wakfu_server.combat_command_recovery.bind_current_owners"
                    ), patch(
                        "wakfu_server.custom_tasks.external.enabled", return_value=False
                    ), patch.object(
                        registry, "_prepare_publication"
                    ) as prepare:
                        result = ns["execute_test_command"](command)
                    self.assertEqual(
                        before,
                        (
                            shared.fight,
                            shared.runtime,
                            shared.ack,
                            tuple(shared.fight.events),
                            shared.fight.winner,
                            dict(shared.participants),
                            set(shared.returned),
                        ),
                    )
                    prepare.assert_not_called()
                    self.store.connection.assert_not_called()
                    self.assertEqual(len(sent), 1)
                    opcode, body = sent[0]
                    # wire.chat documents original On674/NQ with no channel prefix.
                    self.assertEqual(opcode, 674)
                    reader = Reader(body)
                    self.assertEqual(reader.text("B"), "Consola local")
                    self.assertEqual((reader.number("B"), reader.number("B")), (6, 4))
                    self.assertEqual(reader.number("q"), owner.character_id)
                    self.assertEqual(reader.number("B"), 1)
                    feedback = reader.text("H")
                    reader.finish()
                    expected = "Combate ganado." if won else "Combate perdido."
                    self.assertEqual(feedback, expected)
                    self.assertEqual(result["message"], feedback)


if __name__ == "__main__":
    unittest.main(defaultTest="CommittedOutcomeFeedbackTests")
