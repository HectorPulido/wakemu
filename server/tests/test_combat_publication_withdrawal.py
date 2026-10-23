"""Authorized PvE exits must not revoke the remaining owners' native GN."""
from copy import deepcopy
import unittest

from wakfu_server.combat_instance_publication import (
    bind_party_encounter,
    refresh_owned_encounter,
    require_current_publication,
    withdrawn_player_ids,
)
from wakfu_server.combat_instance_publication_withdrawal import (
    retire_withdrawn_publication,
)


class PublicationWithdrawalTests(unittest.TestCase):
    def test_registry_commits_retirement_only_after_durable_exit(self):
        from test_combat_pve_withdraw import WithdrawalPlanTests
        from test_native_recovery_instance_publication_hooks import frames
        from wakfu_server.combat_instance_publication import InstancePublicationTracker

        for storage_fails in (True, False):
            with self.subTest(storage_fails=storage_fails):
                fixture = WithdrawalPlanTests()
                fixture.setUp()
                registry, shared, other = fixture.registry()
                publications = []
                for session in (fixture.session, other):
                    source = InstancePublicationTracker()
                    scope = (
                        session.account_id,
                        session.generation,
                        session.character_id,
                        session.map_id,
                        session.instance_id,
                    )
                    source.after_write(frames(5), scope)
                    publications.append((source, scope))
                bind_party_encounter(
                    shared.fight,
                    publications=tuple(publications),
                    npc_ids=(-200,),
                    player_ids=(10, 20),
                )
                initial = shared.fight

                def persist(original):
                    self.assertIs(original, initial)
                    if storage_fails:
                        raise RuntimeError("durable exit failed")
                    return {"character": {"hp": 45}}

                if storage_fails:
                    with self.assertRaisesRegex(RuntimeError, "durable exit failed"):
                        registry.withdraw_pve(fixture.session, persist=persist)
                    self.assertIs(shared.fight, initial)
                else:
                    registry.withdraw_pve(fixture.session, persist=persist)
                    self.assertIsNot(shared.fight, initial)
                publications[0][0].invalidate()
                if storage_fails:
                    with self.assertRaises(ValueError):
                        require_current_publication(shared.fight)
                else:
                    require_current_publication(shared.fight)
                    self.assertEqual(
                        shared.fight.native_instance_difficulty_snapshots[
                            -200
                        ].difficulty,
                        5,
                    )
                    self.assertIsNone(
                        shared.fight.native_instance_difficulty_snapshots[10].difficulty
                    )

    def setup_party(self):
        from test_party_instance_publication import PartyInstancePublicationTests

        fight, sources = PartyInstancePublicationTests().setup_party()
        for identity, actor in fight.actors.items():
            actor.owner_id = identity if identity in (17, 18) else None
            actor.controlled = identity in (17, 18)
        bind_party_encounter(
            fight,
            publications=sources,
            npc_ids=(99,),
            player_ids=(17, 18),
        )
        return fight, sources

    def test_committed_exit_keeps_snapshots_and_only_remaining_owner_authority(self):
        fight, sources = self.setup_party()
        fight.actors[17].pve_withdrawn = True
        snapshots = fight.native_instance_difficulty_snapshots
        self.assertTrue(retire_withdrawn_publication(fight, 17))
        self.assertIs(fight.native_instance_difficulty_snapshots, snapshots)
        self.assertIsNone(snapshots[17].difficulty)
        self.assertEqual(snapshots[99].difficulty, 2)
        sources[0][0].invalidate()
        require_current_publication(fight)
        self.assertTrue(refresh_owned_encounter(fight))
        require_current_publication(fight)
        self.assertEqual(withdrawn_player_ids(fight), (17,))
        sources[1][0].invalidate()
        with self.assertRaises(ValueError):
            require_current_publication(fight)

    def test_uncommitted_candidate_does_not_retire_original_fight_authority(self):
        fight, sources = self.setup_party()
        original_lease = fight.native_instance_publication_lease
        candidate = deepcopy(fight)
        candidate.actors[17].pve_withdrawn = True
        retire_withdrawn_publication(candidate, 17)
        self.assertIs(fight.native_instance_publication_lease, original_lease)
        require_current_publication(fight)
        sources[0][0].invalidate()
        with self.assertRaises(ValueError):
            require_current_publication(fight)
        require_current_publication(candidate)

    def test_transport_loss_or_partial_owner_roster_cannot_retire_publication(self):
        fight, sources = self.setup_party()
        with self.assertRaisesRegex(ValueError, "complete withdrawn owner"):
            retire_withdrawn_publication(fight, 17)
        fight.actors[17].pve_withdrawn = True
        fight.actors[19] = deepcopy(fight.actors[17])
        fight.actors[19].id = 19
        fight.actors[19].pve_withdrawn = False
        with self.assertRaisesRegex(ValueError, "complete withdrawn owner"):
            retire_withdrawn_publication(fight, 17)
        del fight.actors[19]
        sources[1][0].invalidate()
        with self.assertRaisesRegex(ValueError, "expired or replaced"):
            retire_withdrawn_publication(fight, 17)

    def test_inactive_binding_requires_withdrawal_and_preserves_active_owner_check(
        self,
    ):
        for withdrawn in (False, True):
            fight, sources = self.setup_party()
            fight.actors[17].pve_withdrawn = withdrawn
            with self.assertRaises(ValueError):
                bind_party_encounter(
                    fight,
                    publications=sources,
                    npc_ids=(99,),
                    player_ids=(17, 18),
                    inactive_player_ids=(17,),
                )
        fight, sources = self.setup_party()
        with self.assertRaises(ValueError):
            bind_party_encounter(
                fight,
                publications=sources[1:],
                npc_ids=(99,),
                player_ids=(17, 18),
                inactive_player_ids=(17,),
            )
