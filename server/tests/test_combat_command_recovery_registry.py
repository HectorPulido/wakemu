"""Registry boundary checks; SQL health qualification lives in the PG case."""
from collections import deque
from contextlib import contextmanager
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from wakfu_server.combat_command_recovery import (
    apply_outcome,
    bind_selected,
    cancel,
    take_cancelled,
)
from wakfu_server.combat_shared import Registry, Session, SharedFight


class Store:
    @contextmanager
    def connection(self):
        yield SimpleNamespace(
            execute=lambda *args: SimpleNamespace(fetchone=lambda: dict(revision=4))
        )

    def now(self):
        return 1


class CommandRecoveryRegistryTests(unittest.TestCase):
    def fixture(self, phase):
        sessions = (Session(1, 11, "a", 527, 0), Session(2, 22, "b", 527, 0))
        registry = Registry(lambda session: session in sessions)
        fight = SimpleNamespace(
            id=10,
            phase=phase,
            actors={
                11: SimpleNamespace(controlled=True, owner_id=1),
                22: SimpleNamespace(controlled=True, owner_id=2),
            },
        )
        shared = SharedFight(fight, 527, 0, None)
        shared.participants = {s.account_id: s for s in sessions}
        shared.connected = {1, 2}
        shared.outboxes = {1: deque(), 2: deque()}
        registry.fights[10] = shared
        registry.by_character = {11: 10, 22: 10}
        registry.by_actor = dict(registry.by_character)
        return registry, shared, sessions

    def test_selected_replacement_rebinds_only_after_writer_drain_and_durable_takeover(
        self,
    ):
        registry, shared, sessions = self.fixture("active")
        previous = sessions[0]
        current = Session(1, 11, "new", 527, 0)
        registry.live_session = lambda session: session in (current, sessions[1])
        writer = Mock()
        writer.flush_for_takeover.return_value = True
        writer.takeover_writer.side_effect = lambda *args, persist: persist()
        native = (shared.fight, shared.runtime, shared.ack)
        with patch("wakfu_server.fight_store.takeover_participant") as persist:
            self.assertIs(bind_selected(Store(), registry, current, writer), shared)
        writer.flush_for_takeover.assert_called_once_with(10, 1, "a", "new", timeout=10)
        persist.assert_called_once()
        self.assertEqual(shared.participants[1], current)
        self.assertNotIn(1, shared.connected)
        self.assertEqual((shared.fight, shared.runtime, shared.ack), native)
        self.assertFalse(hasattr(shared, "command_outcome_owner"))

    def test_rebind_does_not_replace_live_previous_owner_or_claim_a_native_publication(
        self,
    ):
        registry, shared, sessions = self.fixture("active")
        current = Session(1, 11, "new", 527, 0)
        registry.live_session = lambda session: True
        writer = Mock()
        writer.flush_for_takeover.return_value = True
        with patch("wakfu_server.fight_store.takeover_participant") as persist:
            with self.assertRaisesRegex(ValueError, "still live"):
                bind_selected(Store(), registry, current, writer)
        persist.assert_not_called()
        self.assertEqual(shared.participants[1], sessions[0])

    def test_native_operator_outcomes_preserve_real_ack_with_destroyed_publication(
        self,
    ):
        import test_party_publication_staged_recovery as staged_fixtures
        from wakfu_server.combat_instance_publication import require_current_publication

        for win in (True, False):
            with self.subTest(win=win):
                helper = staged_fixtures.StagedPartyPublicationRecoveryTests()
                fixture, first, source1, second, source2 = helper.fixture(active=True)
                helper.takeover(fixture, first, source1)
                source1[0].invalidate()
                shared = fixture.shared
                with self.assertRaises(ValueError):
                    require_current_publication(shared.fight)

                previous_ack = (
                    shared.ack.turn,
                    dict(shared.ack.expected),
                    set(shared.ack.received),
                    shared.runtime.awaiting_ack,
                )
                before_counter = shared.runtime.native_action_id
                self.assertIs(apply_outcome(fixture.registry, first, win=win), shared)
                self.assertEqual(shared.fight.phase, "finished")
                self.assertEqual(shared.fight.winner, 0 if win else 1)
                self.assertEqual(
                    (
                        shared.ack.turn,
                        shared.ack.expected,
                        shared.ack.received,
                        shared.runtime.awaiting_ack,
                    ),
                    previous_ack,
                )
                self.assertEqual(shared.runtime.native_action_id, before_counter)
                with self.assertRaises(ValueError):
                    require_current_publication(shared.fight)

    def test_administrative_terminal_settlement_does_not_pin_normal_peer_return(self):
        import test_party_publication_staged_recovery as staged_fixtures

        helper = staged_fixtures.StagedPartyPublicationRecoveryTests()
        fixture, first, source1, second, source2 = helper.fixture(active=True)
        helper.takeover(fixture, first, source1)
        shared = fixture.shared
        shared.participants[second.account_id] = second
        shared.connected.add(second.account_id)
        apply_outcome(fixture.registry, first, win=True)
        # Callback receipt storage is qualified by the PG socket case; here
        # execute the real Registry settlement and normal peer-return gates.
        fixture.registry.settle_finished(
            99, first, lambda current: {account: () for account in current.participants}
        )
        fixture.registry.mark_returned(99, second)
        self.assertIn(second.account_id, shared.returned)

    def test_operator_outcome_works_for_dead_owner_during_private_recovery(self):
        for win in (True, False):
            with self.subTest(win=win):
                registry, shared, sessions = self.fixture("active")
                shared.fight.winner = None
                shared.fight._event = Mock()
                for team, actor in enumerate(shared.fight.actors.values()):
                    actor.team, actor.hp = team, 0
                shared.reconnect_presentations[1] = SimpleNamespace(session=sessions[0])
                shared.pending_publication_recoveries[1] = object()

                def prepare(current, candidate, runtime, packets, **kwargs):
                    self.assertEqual(candidate.winner, 0 if win else 1)
                    self.assertEqual(candidate.phase, "finished")
                    return SimpleNamespace(
                        fight=candidate, runtime=runtime, ack=current.ack, packets=()
                    )

                shared.runtime = SimpleNamespace(fight=shared.fight)
                with patch.object(
                    registry, "_prepare_publication", side_effect=prepare
                ) as publication, patch.object(registry, "_broadcast") as broadcast:
                    self.assertIs(apply_outcome(registry, sessions[0], win=win), shared)
                publication.assert_called_once()
                broadcast.assert_called_once_with(shared, ())

    def test_operator_outcome_does_not_rewrite_an_already_settled_result(self):
        registry, shared, sessions = self.fixture("finished")
        shared.settlement_ready = True
        with patch.object(registry, "_prepare_publication") as publication:
            self.assertIs(apply_outcome(registry, sessions[0], win=False), shared)
        publication.assert_not_called()

    def test_each_live_peer_can_recover_once_after_all_fight_indexes_retire(self):
        for phase in ("placement", "active", "finished"):
            with self.subTest(phase=phase):
                registry, shared, sessions = self.fixture(phase)
                exits = {11: dict(applied=True), 22: dict(applied=True)}
                with patch(
                    "wakfu_server.combat_health.persist_aborted_shared_fight",
                    return_value=exits,
                ), patch(
                    "wakfu_server.fight_checkpoint_store.snapshot", return_value={}
                ):
                    cancel(Store(), registry, sessions[0])
                self.assertIsNone(registry.lookup_character(22))
                self.assertIs(take_cancelled(registry, sessions[1]), shared)
                self.assertIsNone(take_cancelled(registry, sessions[1]))
                self.assertIs(take_cancelled(registry, sessions[0]), shared)
                self.assertFalse(registry.command_cancellations)

    def test_failed_health_commit_retains_fight_and_does_not_publish_recovery(self):
        registry, shared, sessions = self.fixture("active")
        with patch(
            "wakfu_server.combat_health.persist_aborted_shared_fight",
            side_effect=ValueError("health CAS changed"),
        ):
            with self.assertRaisesRegex(ValueError, "health CAS"):
                cancel(Store(), registry, sessions[0])
        self.assertIs(registry.lookup_character(22), shared)
        self.assertIsNone(take_cancelled(registry, sessions[1]))
        self.assertFalse(hasattr(shared, "publication_recovery_aborted"))

    def test_replaced_generation_cannot_consume_another_sessions_recovery(self):
        registry, shared, sessions = self.fixture("active")
        registry.command_cancellations = {sessions[1]: shared}
        newer = Session(2, 22, "new", 527, 0)
        self.assertIsNone(take_cancelled(registry, newer))
        self.assertIs(take_cancelled(registry, sessions[1]), shared)
