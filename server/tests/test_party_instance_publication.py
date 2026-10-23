"""Exact owner authority and revocation for multi-owner native encounters."""
from copy import deepcopy
from types import SimpleNamespace
import unittest

from test_native_recovery_instance_publication_hooks import frames
from wakfu_server.combat_instance_publication import (
    InstancePublicationTracker,
    bind_party_encounter,
    require_current_publication,
)


class PartyInstancePublicationTests(unittest.TestCase):
    def setup_party(self, levels=(2, 2), instances=(0, 0)):
        publications = []
        for identity, level, instance in zip((17, 18), levels, instances):
            scope = (identity, "owned-generation", identity, 1, instance)
            tracker = InstancePublicationTracker()
            tracker.after_write(frames(level, instance=instance), scope)
            publications.append((tracker, scope))
        fight = SimpleNamespace(
            actors={identity: SimpleNamespace(id=identity) for identity in (17, 18, 99)}
        )
        return fight, tuple(publications)

    def test_exact_cohort_unanimous_context_and_explicit_player_empty(self):
        fight, publications = self.setup_party()
        self.assertTrue(
            bind_party_encounter(fight, publications=publications, npc_ids=(99,))
        )
        require_current_publication(fight)
        self.assertEqual(fight.native_instance_difficulty_snapshots[99].difficulty, 2)
        for identity in (17, 18):
            self.assertIsNone(
                fight.native_instance_difficulty_snapshots[identity].difficulty
            )

    def test_any_owner_update_revokes_original_and_checkpoint(self):
        for changed in (0, 1):
            fight, publications = self.setup_party()
            bind_party_encounter(fight, publications=publications, npc_ids=(99,))
            checkpoint = deepcopy(fight)
            tracker, scope = publications[changed]
            tracker.after_write(frames(2), scope)
            for candidate in (fight, checkpoint):
                with self.assertRaises(ValueError):
                    require_current_publication(candidate)

    def test_disagreeing_context_or_instance_installs_no_snapshot(self):
        for levels, instances in (((2, 3), (0, 0)), ((2, 2), (0, 4))):
            fight, publications = self.setup_party(levels, instances)
            with self.assertRaises(ValueError):
                bind_party_encounter(fight, publications=publications, npc_ids=(99,))
            self.assertFalse(hasattr(fight, "native_instance_difficulty_snapshots"))
            with self.assertRaises(ValueError):
                require_current_publication(fight)

    def test_missing_owner_and_duplicate_session_are_rejected(self):
        fight, publications = self.setup_party()
        for entries in (publications[:1], (publications[0], publications[0])):
            with self.assertRaises(ValueError):
                bind_party_encounter(fight, publications=entries, npc_ids=(99,))

    def test_disconnected_owner_does_not_fall_back_to_other_context(self):
        fight, publications = self.setup_party()
        publications[1][0].invalidate()
        self.assertFalse(
            bind_party_encounter(fight, publications=publications, npc_ids=(99,))
        )
        with self.assertRaises(ValueError):
            require_current_publication(fight)

    def test_production_roster_refresh_binds_owned_heroes_companions_and_second_owner(
        self,
    ):
        from wakfu_server.combat_instance_publication import refresh_owned_encounter

        fight, publications = self.setup_party()
        del fight.actors[18]
        fight.actors[17].owner_id = 17
        fight.actors[17].controlled = True
        fight.actors[99].owner_id = None
        fight.actors[99].controlled = False
        tracker, scope = publications[0]
        tracker.bind_encounter(fight, scope, npc_ids=(99,), player_id=17)
        fight.actors[19] = SimpleNamespace(id=19, owner_id=17, controlled=True)
        fight.actors[20] = SimpleNamespace(id=20, owner_id=17, controlled=True)
        fight.native_companion_sources = {"20": {"id": 20}}
        self.assertTrue(refresh_owned_encounter(fight))
        self.assertIsNone(fight.native_instance_difficulty_snapshots[19].difficulty)
        self.assertEqual(fight.native_instance_difficulty_snapshots[20].difficulty, 2)
        fight.actors[18] = SimpleNamespace(id=18, owner_id=18, controlled=True)
        self.assertTrue(refresh_owned_encounter(fight, publication=publications[1]))
        self.assertIsNone(fight.native_instance_difficulty_snapshots[18].difficulty)
        require_current_publication(fight)
        checkpoint = deepcopy(fight)
        publications[1][0].invalidate()
        for candidate in (fight, checkpoint):
            with self.assertRaises(ValueError):
                require_current_publication(candidate)

    def test_never_published_ordinary_world_admission_preserves_unknown(self):
        from wakfu_server.combat_instance_publication import refresh_owned_encounter

        fight, publications = self.setup_party()
        unpublished = InstancePublicationTracker()
        self.assertFalse(
            unpublished.bind_encounter(
                fight, publications[0][1], npc_ids=(99, 18), player_id=17
            )
        )
        self.assertFalse(refresh_owned_encounter(fight))
        self.assertFalse(hasattr(fight, "native_instance_difficulty_snapshots"))
        with self.assertRaises(ValueError):
            require_current_publication(fight)

    def test_formerly_published_but_expired_roster_cannot_take_unknown_fallback(self):
        from wakfu_server.combat_instance_publication import refresh_owned_encounter

        fight, publications = self.setup_party()
        bind_party_encounter(fight, publications=publications, npc_ids=(99,))
        publications[0][0].invalidate()
        with self.assertRaises(ValueError):
            refresh_owned_encounter(fight)

    def test_publication_change_during_binding_never_accepts_new_lease_with_old_gn(
        self,
    ):
        from unittest.mock import patch
        from wakfu_server import combat_instance_publication as publication

        fight, publications = self.setup_party()
        original = publication.bind_fight_npc_snapshots

        def changed(*args, **kwargs):
            result = original(*args, **kwargs)
            tracker, scope = publications[1]
            tracker.after_write(frames(7), scope)
            return result

        with patch.object(publication, "bind_fight_npc_snapshots", changed):
            with self.assertRaisesRegex(ValueError, "changed during roster binding"):
                bind_party_encounter(fight, publications=publications, npc_ids=(99,))
        with self.assertRaises(ValueError):
            require_current_publication(fight)

    def test_stale_scope_reader_preserves_new_owner_generation_and_instance_publication(
        self,
    ):
        from wakfu_server.combat_instance_publication import refresh_owned_encounter

        for index, replacement in ((1, "new-owned-generation"), (4, 4)):
            fight, publications = self.setup_party()
            tracker, captured_scope = publications[1]
            changed_scope = list(captured_scope)
            changed_scope[index] = replacement
            changed_scope = tuple(changed_scope)
            tracker.after_write(frames(7, instance=changed_scope[4]), changed_scope)
            live_context, live_receipt = tracker.published, tracker.lease.current
            with self.assertRaisesRegex(ValueError, "scope changed"):
                bind_party_encounter(fight, publications=publications, npc_ids=(99,))
            self.assertEqual(tracker.scope, changed_scope)
            self.assertIs(tracker.published, live_context)
            self.assertEqual(tracker.lease.current, live_receipt)
            # The joining-owner refresh path must also remain a pure reader.
            baseline, current_sources = self.setup_party()
            del baseline.actors[18]
            baseline.actors[17].owner_id = 17
            baseline.actors[17].controlled = True
            baseline.actors[99].owner_id = None
            baseline.actors[99].controlled = False
            current_sources[0][0].bind_encounter(
                baseline, current_sources[0][1], npc_ids=(99,), player_id=17
            )
            baseline.actors[18] = SimpleNamespace(id=18, owner_id=18, controlled=True)
            with self.assertRaisesRegex(ValueError, "scope changed"):
                refresh_owned_encounter(baseline, publication=(tracker, captured_scope))
            self.assertEqual(tracker.scope, changed_scope)
            self.assertIs(tracker.published, live_context)
            self.assertEqual(tracker.lease.current, live_receipt)
