"""Authorized native reconnect on private candidates, including pending ACK."""
from copy import deepcopy
import unittest
from unittest.mock import patch

from test_native_recovery_instance_publication_hooks import frames
from wakfu_server.combat_instance_publication import (
    InstancePublicationTracker,
    bind_party_encounter,
    require_current_publication,
)
from wakfu_server.combat_instance_publication_recovery import (
    rebind_recovered_owner,
    requires_publication_recovery,
)
from wakfu_server.combat_dungeon_difficulty_condition import runtime_difficulty
from wakfu_server.combat_shared import Session


def published(session, level=2):
    tracker = InstancePublicationTracker()
    scope = (
        session.account_id,
        session.generation,
        session.character_id,
        session.map_id,
        session.instance_id,
    )
    tracker.after_write(frames(level, instance=session.instance_id), scope)
    return tracker, scope


class PartyPublicationRecoveryTests(unittest.TestCase):
    def party(self):
        from test_combat_delivery_boundary import DeliveryBoundaryTests

        fixture = DeliveryBoundaryTests().fixture()
        bindings = (published(fixture.one), published(fixture.two))
        bind_party_encounter(
            fixture.shared.fight, publications=bindings, npc_ids=(-200,)
        )
        fixture.live.remove(fixture.two)
        replacement = Session(2, 20, "new-owned-generation", 1134, 0)
        fixture.live.add(replacement)
        bindings[1][0].invalidate()
        return fixture, bindings, replacement, published(replacement)

    def test_authorized_owner_rebind_preserves_other_owner_and_gameplay(self):
        fixture, bindings, replacement, publication = self.party()
        shared = fixture.shared
        original, receipt = shared.fight, bindings[0][0].lease.current
        before = {
            identity: (actor.hp, actor.ap, actor.mp, actor.position)
            for identity, actor in original.actors.items()
        }
        observed = []

        def bootstrap(fight, view, session):
            self.assertIsNot(fight, original)
            observed.append(runtime_difficulty(fight, -200, {"is_eGj": True}))
            return ((12044, b"recovered-native-context"),)

        fixture.registry.takeover(
            99,
            replacement,
            bootstrap,
            persist_takeover=lambda previous: self.assertEqual(previous, fixture.two),
            prepare_authority=lambda fight, view, owner: rebind_recovered_owner(
                fight, view, owner, publication
            ),
        )
        self.assertEqual(observed, [2])
        self.assertIsNot(shared.fight, original)
        self.assertEqual(shared.participants[2], replacement)
        self.assertEqual(bindings[0][0].lease.current, receipt)
        self.assertEqual(
            before,
            {
                identity: (actor.hp, actor.ap, actor.mp, actor.position)
                for identity, actor in shared.fight.actors.items()
            },
        )
        require_current_publication(shared.fight)

    def test_current_peer_real_republication_rebinds_without_own_generation_takeover(
        self,
    ):
        for level in (2, 7):
            with self.subTest(level=level):
                fixture, bindings, replacement, publication = self.party()
                shared = fixture.shared
                source, scope = bindings[0]
                source.after_write(
                    frames(level, instance=fixture.one.instance_id), scope
                )
                before = shared.fight
                recover = lambda fight, view, owner: rebind_recovered_owner(
                    fight,
                    view,
                    owner,
                    publication,
                    session_live=fixture.registry._lease_live,
                )
                if level == 2:
                    fixture.registry.takeover(
                        99,
                        replacement,
                        lambda *args: ((12044, b"actual-recovery"),),
                        persist_takeover=lambda previous: None,
                        prepare_authority=recover,
                    )
                    self.assertEqual(shared.participants[1], fixture.one)
                    self.assertIn(1, shared.connected)
                    require_current_publication(shared.fight)
                else:
                    with self.assertRaises(ValueError):
                        fixture.registry.takeover(
                            99,
                            replacement,
                            lambda *args: ((12044, b"actual-recovery"),),
                            persist_takeover=lambda previous: self.fail(
                                "Must not persist"
                            ),
                            prepare_authority=recover,
                        )
                    self.assertIs(shared.fight, before)
                    self.assertEqual(shared.participants[2], fixture.two)

    def test_pending_ack_runtime_recover_sees_rebound_authority_before_bootstrap(self):
        from test_combat_reconnect_reconciliation import ReconnectReconciliationTests

        fixture = ReconnectReconciliationTests()
        fixture.setUp()
        fixture._prepare_pending_ack_reconnect()
        shared, registry = fixture.shared, fixture.adapter.registry
        old = published(fixture.old)
        old[0].bind_encounter(shared.fight, old[1], npc_ids=(-200,), player_id=10)
        registry.disconnect(fixture.old)
        fixture.live.remove((1, "generation-old", 10))
        replacement = Session(1, 10, "generation-new", 1134, 0)
        fixture.live.add((1, "generation-new", 10))
        old[0].invalidate()
        source = published(replacement)
        runtime_class = type(shared.runtime)
        recover = runtime_class.recover
        observations = []

        def observed(runtime, *args, **kwargs):
            observations.append(
                ("recover", runtime_difficulty(runtime.fight, -200, {"is_eGj": True}))
            )
            return recover(runtime, *args, **kwargs)

        def bootstrap(fight, view, owner):
            observations.append(
                ("bootstrap", runtime_difficulty(fight, -200, {"is_eGj": True}))
            )
            return ((12044, b"actual-recovery-boundary"),)

        with patch.object(runtime_class, "recover", observed):
            registry.takeover(
                99,
                replacement,
                bootstrap,
                recover_disconnected=True,
                persist_takeover=lambda previous: self.assertEqual(
                    previous, fixture.old
                ),
                prepare_authority=lambda fight, view, owner: rebind_recovered_owner(
                    fight, view, owner, source
                ),
            )
        self.assertEqual(observations, [("recover", 2), ("bootstrap", 2)])
        self.assertIsNone(shared.ack.turn)
        self.assertIsNone(shared.runtime.awaiting_ack)
        self.assertIs(shared.runtime.fight, shared.fight)
        require_current_publication(shared.fight)

    def test_durable_takeover_failure_does_not_adopt_rebound_candidate(self):
        fixture, bindings, replacement, publication = self.party()
        shared = fixture.shared
        original_fight, original_runtime, original_ack = (
            shared.fight,
            shared.runtime,
            shared.ack,
        )
        original_receipt = original_fight.native_instance_publication_receipt
        with self.assertRaisesRegex(RuntimeError, "durable rejected"):
            fixture.registry.takeover(
                99,
                replacement,
                lambda *args: ((12044, b"private"),),
                persist_takeover=lambda previous: (_ for _ in ()).throw(
                    RuntimeError("durable rejected")
                ),
                prepare_authority=lambda fight, view, owner: rebind_recovered_owner(
                    fight, view, owner, publication
                ),
            )
        self.assertIs(shared.fight, original_fight)
        self.assertIs(shared.runtime, original_runtime)
        self.assertIs(shared.ack, original_ack)
        self.assertEqual(shared.participants[2], fixture.two)
        self.assertEqual(
            original_fight.native_instance_publication_receipt, original_receipt
        )
        self.assertTrue(publication[0].lease.current)

    def test_new_difficulty_and_expired_other_owner_are_rejected(self):
        for change in ("difficulty", "other-owner"):
            fixture, bindings, replacement, publication = self.party()
            if change == "difficulty":
                publication = published(replacement, 7)
            else:
                bindings[0][0].invalidate()
            with self.assertRaises(ValueError):
                rebind_recovered_owner(
                    deepcopy(fixture.shared.fight),
                    fixture.shared,
                    replacement,
                    publication,
                )
            self.assertEqual(fixture.shared.participants[2], fixture.two)
            self.assertTrue(publication[0].lease.current)

    def test_foreign_generation_character_instance_and_missing_publication_rejected(
        self,
    ):
        fixture, bindings, replacement, publication = self.party()
        candidates = (
            None,
            published(Session(2, 20, "foreign-generation", 1134, 0)),
            published(Session(2, 21, replacement.generation, 1134, 0)),
            published(Session(2, 20, replacement.generation, 1134, 4)),
        )
        for source in candidates:
            with self.assertRaises(ValueError):
                rebind_recovered_owner(
                    deepcopy(fixture.shared.fight), fixture.shared, replacement, source
                )
            if source is not None:
                self.assertTrue(source[0].lease.current)

    def test_never_published_legacy_and_terminal_recovery_are_noops(self):
        fixture, bindings, replacement, publication = self.party()
        current = deepcopy(fixture.shared.fight)
        current.phase = "finished"
        self.assertFalse(requires_publication_recovery(current))
        self.assertFalse(
            rebind_recovered_owner(current, fixture.shared, replacement, None)
        )
        del current.native_instance_publication_lease
        del current.native_instance_publication_receipt
        del current.native_instance_difficulty_snapshots
        current.phase = "placement"
        self.assertFalse(requires_publication_recovery(current))
        self.assertFalse(
            rebind_recovered_owner(current, fixture.shared, replacement, None)
        )

    def test_other_owner_update_during_rebind_rejects_without_revoking_new_source(self):
        from wakfu_server import combat_instance_publication_recovery as recovery

        fixture, bindings, replacement, publication = self.party()
        original = recovery.bind_party_encounter
        new_receipts = []

        def changed(*args, **kwargs):
            result = original(*args, **kwargs)
            tracker, scope = bindings[0]
            tracker.after_write(frames(2), scope)
            new_receipts.append(tracker.lease.current)
            return result

        with patch.object(recovery, "bind_party_encounter", changed):
            with self.assertRaises(ValueError):
                recovery.rebind_recovered_owner(
                    deepcopy(fixture.shared.fight),
                    fixture.shared,
                    replacement,
                    publication,
                )
        self.assertEqual(bindings[0][0].lease.current, new_receipts[-1])
        self.assertTrue(publication[0].lease.current)
        self.assertEqual(fixture.shared.participants[2], fixture.two)

    def test_authority_replacement_requires_durable_takeover_fence(self):
        fixture, bindings, replacement, publication = self.party()
        original = fixture.shared.fight
        with self.assertRaisesRegex(ValueError, "durable lease fence"):
            fixture.registry.takeover(
                99,
                replacement,
                lambda *args: ((12044, b"bootstrap"),),
                prepare_authority=lambda fight, view, owner: rebind_recovered_owner(
                    fight, view, owner, publication
                ),
            )
        self.assertIs(fixture.shared.fight, original)
        self.assertEqual(fixture.shared.participants[2], fixture.two)
