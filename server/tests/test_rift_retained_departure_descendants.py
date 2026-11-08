"""Activated retained children preserve source proof without changing Qe UIDs."""
from copy import deepcopy
from dataclasses import replace
import unittest

import test_rift_retained_departure_source as departure_fixture
from test_combat_effect_dispatch import effect
from native_combat_fixture import initialize_fixture_qi
from wakfu_server.combat_conditions import ConditionContext
from wakfu_server.combat_effect_dispatch import EffectDispatcher
from wakfu_server.combat_summon import RegisteredSummonAuthority
from wakfu_server.combat_pve_departure import retire_pve_actor
from wakfu_server import combat_retained_departure_source as proof


class DepartureDescendantTests(unittest.TestCase):
    def fixture(self, handler):
        fixture = departure_fixture.RetainedDepartureSourceTests()
        fight = fixture.fight_with_retained_effect()
        root = replace(fixture.invocation(), reference=317553)
        row = fight.native_owned_group_effects[root.base_uid]
        row["invocation"] = vars(replace(root, base_uid=None))
        row["children"] = [317554]
        initialize_fixture_qi(fight)
        fight.phase = "active"
        proof.capture_departure_sources(
            fight, {159}, RegisteredSummonAuthority(fixture.ordinary())
        )
        retire_pve_actor(fight, fight.actors[159], root_actor_id=159, owner_id=98)
        fight.actors[159].pve_withdrawn = True
        dispatcher = EffectDispatcher(
            {"317553": effect(330, children=(317554,)), "317554": effect(421)},
            {421: handler},
            resolve=lambda definition, invocation: (invocation,),
            condition_context=lambda invocation: ConditionContext({}),
            probability_accepts=lambda *args: True,
            group_cells=lambda *args: (),
            actor_position=lambda identity: (0, 0, 0),
        )
        return fight, root, dispatcher

    def activate(self, fight, root, dispatcher):
        with proof.retained_activation_scope(fight, dispatcher, root):
            return dispatcher.execute_activation(
                root,
                source=None,
                condition_context=lambda *args: ConditionContext({}),
                executable=True,
                allocate_uid=lambda: 9000,
            )

    def test_authentic_330_to_421_child_keeps_fresh_uid_and_scoped_source(self):
        seen = []

        def handler(_effect, _values, child):
            self.assertIsNone(child.base_uid)
            self.assertEqual(child.reference, 317554)
            seen.append(child)
            self.assertIsNotNone(
                proof.retained_departure_source(fight, fight.actors[159], child)
            )
            return True

        fight, root, dispatcher = self.fixture(handler)
        self.activate(fight, root, dispatcher)
        self.assertEqual(len(seen), 1)
        with self.assertRaisesRegex(ValueError, "Missing exact"):
            proof.retained_departure_source(fight, fight.actors[159], seen[0])
        self.assertIsNone(proof._ACTIVATION.get())
        self.assertIsNone(proof._DESCENDANT.get())

    def test_actual_native_replay_opens_and_releases_descendant_authority(self):
        from test_combat_event_replay import NativeEventReplayTests
        from wakfu_server.combat_event_replay import (
            NativeCloneAuthority,
            NativeExternalEvent,
        )
        from wakfu_server.combat_effect_dispatch import EffectInvocation

        NativeEventReplayTests.setUpClass()
        fixture = NativeEventReplayTests()
        fixture.setUp()
        fight, dispatcher = fixture.fight, fixture.dispatcher
        dispatcher.execute(EffectInvocation(308265, 1, 7, -7, (1, 0, 0)))
        rows = [
            (uid, row)
            for uid, row in fight.native_owned_group_effects.items()
            if row["invocation"]["caster_id"] == 7
            and row["invocation"]["target_id"] == -7
        ]
        self.assertEqual(len(rows), 1)
        uid, row = rows[0]
        row["native_subscription_masks"][5] = [1003]
        fixture.retention.metadata["effects"]["308265"][
            "event_reverse_subscription"
        ] = False
        proof.capture_departure_sources(
            fight,
            {7},
            RegisteredSummonAuthority(
                departure_fixture.RetainedDepartureSourceTests.ordinary()
            ),
        )
        retire_pve_actor(fight, fight.actors[7], root_actor_id=7, owner_id=3)
        fight.actors[7].pve_withdrawn = True
        seen = []

        def handle(_effect, _values, child):
            self.assertIsNone(child.base_uid)
            self.assertIsNotNone(
                proof.retained_departure_source(fight, fight.actors[7], child)
            )
            seen.append(child)
            return True

        dispatcher.handlers[400] = handle
        fixture.replay(
            NativeExternalEvent(-7, (1003,), 6),
            authority=NativeCloneAuthority(
                lambda *args: True, lambda *args: ConditionContext({})
            ),
            eligible_uids=frozenset((uid,)),
        )
        self.assertTrue(seen)
        self.assertIsNone(proof._ACTIVATION.get())
        self.assertIsNone(proof._DESCENDANT.get())

    def test_ungranted_root_without_source_read_keeps_legacy_execution(self):
        seen = []
        fight, root, dispatcher = self.fixture(
            lambda _effect, _values, child: seen.append(child) is None
        )
        fight.native_retained_departure_sources = {}
        root = replace(root, target_id=root.caster_id)
        self.activate(fight, root, dispatcher)
        self.assertEqual(len(seen), 1)
        self.assertIsNone(seen[0].base_uid)
        self.assertIsNone(proof._ACTIVATION.get())

        def reads_metadata(_effect, _values, child):
            proof.retained_departure_source(fight, fight.actors[159], child)
            return True

        dispatcher.handlers[421] = reads_metadata
        with self.assertRaisesRegex(ValueError, "Missing exact"):
            self.activate(fight, root, dispatcher)
        self.assertIsNone(proof._ACTIVATION.get())
        self.assertIsNone(proof._DESCENDANT.get())

    def test_foreign_fight_caster_uid_and_self_target_stay_rejected(self):
        def handler(_effect, _values, child):
            foreign = deepcopy(fight)
            cases = [
                (foreign, foreign.actors[159], child),
                (fight, fight.actors[159], replace(child, caster_id=160)),
                (fight, fight.actors[159], replace(child, base_uid=999)),
                (fight, fight.actors[159], replace(child, target_id=159)),
            ]
            for current, actor, invocation in cases:
                with self.assertRaises(ValueError):
                    proof.retained_departure_source(current, actor, invocation)
            return True

        fight, root, dispatcher = self.fixture(handler)
        self.activate(fight, root, dispatcher)

    def test_other_dispatcher_and_undeclared_ancestry_do_not_inherit(self):
        def handler(_effect, _values, child):
            for current, ancestry in (
                (object(), (317553,)),
                (dispatcher, (999,)),
                (dispatcher, (317553, 999)),
            ):
                with proof.retained_descendant_scope(current, child, ancestry):
                    with self.assertRaisesRegex(ValueError, "Missing exact"):
                        proof.retained_departure_source(fight, fight.actors[159], child)
            return True

        fight, root, dispatcher = self.fixture(handler)
        self.activate(fight, root, dispatcher)

    def test_original_group_mutation_or_removal_revokes_descendant(self):
        for remove in (False, True):

            def handler(_effect, _values, child):
                if remove:
                    del fight.native_owned_group_effects[root.base_uid]
                else:
                    fight.native_owned_group_effects[root.base_uid]["invocation"][
                        "target_id"
                    ] = 159
                with self.assertRaisesRegex(ValueError, "original group"):
                    proof.retained_departure_source(fight, fight.actors[159], child)
                return True

            fight, root, dispatcher = self.fixture(handler)
            self.activate(fight, root, dispatcher)

    def test_nested_unrelated_activation_and_exception_restore_scope(self):
        class Stop(Exception):
            pass

        def handler(_effect, _values, child):
            with proof.retained_activation_scope(
                fight, dispatcher, replace(root, caster_id=160)
            ):
                with self.assertRaisesRegex(ValueError, "Missing exact"):
                    proof.retained_departure_source(fight, fight.actors[159], child)
            self.assertIsNotNone(
                proof.retained_departure_source(fight, fight.actors[159], child)
            )
            raise Stop()

        fight, root, dispatcher = self.fixture(handler)
        with self.assertRaises(Stop):
            self.activate(fight, root, dispatcher)
        self.assertIsNone(proof._ACTIVATION.get())
        self.assertIsNone(proof._DESCENDANT.get())


if __name__ == "__main__":
    unittest.main()
