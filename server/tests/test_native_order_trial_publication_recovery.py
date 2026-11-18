"""A typed one-team order fight can rebind its actual written GN source."""

from copy import deepcopy
import unittest

from test_native_recovery_instance_publication_hooks import frames
from test_combat_summon_retirement import SummonRetirementTests
from wakfu_server import combat_state, native_order_trial_encounter
from wakfu_server.combat_instance_publication import (
    InstancePublicationTracker,
    require_current_publication,
)
from wakfu_server.combat_instance_publication_recovery import rebind_recovered_owner
from wakfu_server.combat_shared import Session, SharedFight
from wakfu_server.native_order_trial_encounter import ConstructorPolicy


class NativeOrderTrialPublicationRecoveryTests(unittest.TestCase):
    def fixture(self, *, typed=True):
        account_id, character_id, map_id, instance_id = 2, 20, 1134, 91
        old = Session(account_id, character_id, "old-generation", map_id, instance_id)
        owner = combat_state.Actor(
            character_id,
            1,
            (0, 0, 0),
            60,
            6,
            3,
            100,
            1,
            account_id,
            True,
        )
        policy = ConstructorPolicy(
            character_id,
            account_id,
            instance_id,
            77,
            "normal",
            "a" * 64,
            "b" * 64,
            map_id,
            1,
            0,
        )
        fight = combat_state.Fight(
            77,
            [owner],
            {(0, 0, 0), (1, 0, 0)},
            {1: {(0, 0, 0)}, 0: {(1, 0, 0)}},
            native_order_policy=policy,
        )
        if not typed:
            # Model an untyped one-team snapshot presented to the recovery guard.
            fight.native_order_trial_constructor = None
        old_tracker = InstancePublicationTracker()
        old_scope = (account_id, old.generation, character_id, map_id, instance_id)
        old_tracker.after_write(frames(2, instance=instance_id), old_scope)
        self.assertTrue(
            old_tracker.bind_encounter(
                fight, old_scope, npc_ids=(), player_id=character_id
            )
        )
        receipt = fight.native_instance_publication_receipt
        old_tracker.invalidate()
        shared = SharedFight(fight, map_id, instance_id, runtime=None)
        shared.participants[account_id] = old
        shared.connected.clear()
        return fight, shared, old, receipt

    @staticmethod
    def publication(session, level=2):
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

    def summoned_fixture(self):
        (
            source_fight,
            source_owner,
            _enemy,
            source_larva,
        ) = SummonRetirementTests().fight(origin="ordinary")
        owner = deepcopy(source_owner)
        owner.team = 1
        account_id, character_id, map_id, instance_id = (
            owner.owner_id,
            owner.id,
            1134,
            91,
        )
        old = Session(account_id, character_id, "old-generation", map_id, instance_id)
        policy = native_order_trial_encounter.ConstructorPolicy(
            character_id,
            account_id,
            instance_id,
            99,
            "normal",
            "c" * 64,
            "d" * 64,
            map_id,
            1,
            0,
        )
        cells = {(0, 0, 0), (1, 0, 0), (2, 0, 0), (3, 0, 0)}
        owner.position = (0, 0, 0)
        fight = combat_state.Fight(
            99,
            [owner],
            cells,
            {1: {owner.position}, 0: {(3, 0, 0)}},
            native_order_policy=policy,
        )
        original = InstancePublicationTracker()
        scope = (account_id, old.generation, character_id, map_id, instance_id)
        original.after_write(frames(2, instance=instance_id), scope)
        self.assertTrue(
            original.bind_encounter(fight, scope, npc_ids=(), player_id=character_id)
        )
        root = deepcopy(source_larva)
        root.position = (1, 0, 0)
        root.team = 0
        root.controlled = False
        root.owner_id = None
        root.native_summon_source.update(
            ref=3206, caster_id=owner.id, controller_id=owner.id
        )
        root_row = deepcopy(source_fight.native_summon_registrations[root.id])
        root_row["authority"]["breed_id"] = 3206
        fight.actors[root.id] = root

        live = deepcopy(root)
        live.id = 902
        live.position = (2, 0, 0)
        live.native_summon_source.update(caster_id=root.id, controller_id=owner.id)
        live_row = deepcopy(root_row)
        live_row.update(actor_id=live.id, caster_id=root.id)
        live_row["authority"].update(native_controller_id=owner.id, breed_id=3206)
        fight.actors[live.id] = live

        dead = deepcopy(live)
        dead.id = 903
        dead.position = (3, 0, 0)
        dead.hp = 0
        dead.native_summon_source.update(caster_id=root.id, controller_id=owner.id)
        dead_row = deepcopy(live_row)
        dead_row.update(actor_id=dead.id, caster_id=root.id)
        fight.actors[dead.id] = dead
        fight.native_summon_registrations = {
            root.id: root_row,
            live.id: live_row,
            dead.id: dead_row,
        }

        original.invalidate()
        shared = SharedFight(fight, map_id, instance_id, runtime=None)
        shared.participants[account_id] = old
        return fight, shared, old, live, dead

    def test_typed_empty_roster_rebinds_same_written_gn_without_actor_mutation(self):
        fight, shared, old, receipt = self.fixture()
        replacement = Session(
            old.account_id,
            old.character_id,
            "new-generation",
            old.map_id,
            old.instance_id,
        )
        publication = self.publication(replacement, 2)
        actors = dict(fight.actors)
        actor_snapshot = {
            key: (
                actor.hp,
                actor.max_hp,
                actor.ap,
                actor.mp,
                actor.position,
                actor.team,
                actor.state_ledger.entries,
            )
            for key, actor in fight.actors.items()
        }
        walkable, placement = deepcopy(fight.walkable), deepcopy(fight.placement)
        self.assertTrue(rebind_recovered_owner(fight, shared, replacement, publication))
        require_current_publication(fight)
        self.assertEqual(fight.native_instance_publication_receipt[0][4], receipt[4])
        self.assertEqual(
            fight.native_instance_difficulty_snapshots[old.character_id].difficulty,
            None,
        )
        self.assertEqual(fight.actors, actors)
        self.assertEqual(
            {
                key: (
                    actor.hp,
                    actor.max_hp,
                    actor.ap,
                    actor.mp,
                    actor.position,
                    actor.team,
                    actor.state_ledger.entries,
                )
                for key, actor in fight.actors.items()
            },
            actor_snapshot,
        )
        self.assertEqual((fight.walkable, fight.placement), (walkable, placement))

    def test_untyped_empty_roster_changed_gn_and_wrong_owner_are_rejected(self):
        fight, shared, old, _receipt = self.fixture(typed=False)
        replacement = Session(
            old.account_id,
            old.character_id,
            "new-generation",
            old.map_id,
            old.instance_id,
        )
        with self.assertRaisesRegex(ValueError, "original concrete NPC difficulty"):
            rebind_recovered_owner(
                fight, shared, replacement, self.publication(replacement, 2)
            )

        fight, shared, old, _receipt = self.fixture()
        replacement = Session(
            old.account_id,
            old.character_id,
            "new-generation",
            old.map_id,
            old.instance_id,
        )
        with self.assertRaisesRegex(
            ValueError, "change the frozen encounter difficulty"
        ):
            rebind_recovered_owner(
                fight, shared, replacement, self.publication(replacement, 7)
            )

        fight, shared, old, _receipt = self.fixture()
        foreign = Session(
            3, old.character_id, "foreign-generation", old.map_id, old.instance_id
        )
        with self.assertRaisesRegex(ValueError, "authorized same owner"):
            rebind_recovered_owner(fight, shared, foreign, self.publication(foreign, 2))

    def test_larva_roster_rebind_follows_registered_and_retained_summon_ancestry(self):
        fight, shared, old, live, dead = self.summoned_fixture()
        replacement = Session(
            old.account_id,
            old.character_id,
            "new-generation",
            old.map_id,
            old.instance_id,
        )
        original_actors = dict(fight.actors)
        before = {
            identity: (
                actor.hp,
                actor.ap,
                actor.mp,
                actor.position,
                actor.team,
                deepcopy(actor.effect_stats),
                actor.state_ledger.entries,
            )
            for identity, actor in fight.actors.items()
        }
        publication = self.publication(replacement, 2)
        self.assertTrue(rebind_recovered_owner(fight, shared, replacement, publication))
        require_current_publication(fight)
        self.assertEqual(fight.actors, original_actors)
        self.assertEqual(
            {
                identity: (
                    actor.hp,
                    actor.ap,
                    actor.mp,
                    actor.position,
                    actor.team,
                    deepcopy(actor.effect_stats),
                    actor.state_ledger.entries,
                )
                for identity, actor in fight.actors.items()
            },
            before,
        )
        self.assertEqual(
            (fight.actors[live.id].hp > 0, fight.actors[dead.id].hp), (True, 0)
        )

        for corruption in ("unregistered", "foreign-breed", "foreign-parent"):
            candidate, candidate_shared, prior, _live, _dead = self.summoned_fixture()
            if corruption == "unregistered":
                del candidate.native_summon_registrations[902]
            elif corruption == "foreign-breed":
                candidate.actors[902].native_summon_source["ref"] = 2382
            else:
                candidate.actors[902].native_summon_source["caster_id"] = 999
                candidate.native_summon_registrations[902]["caster_id"] = 999
            next_session = Session(
                prior.account_id,
                prior.character_id,
                "new-generation",
                prior.map_id,
                prior.instance_id,
            )
            with self.subTest(corruption=corruption), self.assertRaises(ValueError):
                rebind_recovered_owner(
                    candidate,
                    candidate_shared,
                    next_session,
                    self.publication(next_session, 2),
                )


if __name__ == "__main__":
    unittest.main()
