"""Native external read-pass ownership and callback regressions."""
from contextlib import nullcontext
from dataclasses import replace
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from test_combat_ordinary_phase_read_pass import PhaseReadPassSemanticTests
from wakfu_server import combat_cast_events as cast
from wakfu_server import combat_death_events as death
from wakfu_server import combat_external_read_pass as external
from wakfu_server import combat_ordinary_events as ordinary
from wakfu_server.combat_effect_dispatch import EffectInvocation


class ExternalReadPassTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        PhaseReadPassSemanticTests.setUpClass()

    def fixture(self):
        case = PhaseReadPassSemanticTests().fixture()
        case.dispatcher = SimpleNamespace(
            native_retention=case.retention,
            replay_event=case.replay,
            native_clone_authority=case.events.authority,
        )
        return case

    def deliver(self, case, kind):
        if kind == "cast":
            return cast._deliver(case.dispatcher, {"actor_id": 7}, 1024)
        # Exercise precisely the post-area/finisher production reaction scope;
        # this fixture does not claim to perform an actual lethal transition.
        source = replace(
            case.f.source(), event_ids=(1013,), channel=6, manager_actor_id=7
        )
        with external.external_read_pass(
            case.fight, case.replay, case.events.authority, case.retention
        ):
            return death._deliver_death_reactions(
                case.fight, source, case.replay, case.events.authority, case.retention
            )

    def test_cast_and_death_reactions_share_one_view_without_observers(self):
        for kind in ("cast", "death"):
            with self.subTest(kind=kind):
                case = self.fixture()
                case.fight.native_owned_group_effects[900][
                    "native_subscription_masks"
                ] = [None] * 7
                with patch.object(
                    case.retention, "view", wraps=case.retention.view
                ) as view:
                    self.assertEqual(self.deliver(case, kind), ())
                self.assertEqual(view.call_count, 1)
                self.assertIsNone(case.replay._read_pass)
                self.assertEqual(ordinary._PHASE_READ_SCOPES.get(), ())

    def mutation_run(self, kind, enabled):
        case = self.fixture()
        event_ids = [1024] if kind == "cast" else [1010, 1012, 1013]
        # Global-only observers ensure the callback happens between iterator
        # recipients, after the iterator has captured its original containers.
        masks = [None] * 7
        masks[5] = event_ids
        case.fight.native_owned_group_effects[900]["native_subscription_masks"] = masks
        case.retention.metadata["effects"]["308265"]["event_global_subscription"] = True
        case.f.dispatcher.execute(EffectInvocation(308265, 1, -7, -7, (1, 0, 0)))
        added = max(case.fight.native_owned_group_effects)
        case.fight.native_owned_group_effects[added][
            "native_subscription_masks"
        ] = masks
        observed = []
        mutations = []

        class MutatingStatus(dict):
            def get(self, key, default=None):
                if not mutations:
                    mutations.append(key)
                    # An opaque native-eligibility read corrupts an existing
                    # owned record after the preceding callback has returned.
                    case.fight.native_owned_group_effects[900]["target_id"] = 999999
                return super().get(key, default)

        def activation(invocation, **kwargs):
            observed.append(invocation.target_id)
            self.assertIsNone(case.replay._read_pass)
            # Reentry/exception cleanup must restore the callback's suspended
            # context, not leak the inner ordinary phase to its outer caller.
            with self.assertRaisesRegex(RuntimeError, "nested callback"):
                with external.external_read_pass(
                    case.fight, case.replay, case.events.authority, case.retention
                ):
                    raise RuntimeError("nested callback")
            self.assertIsNone(case.replay._read_pass)
            state = case.fight.native_global_pv_collections
            state["fighter_status"] = MutatingStatus(state["fighter_status"])
            return False

        case.f.dispatcher.execute_activation = activation
        scope = (
            nullcontext()
            if enabled
            else patch.object(
                external, "external_read_pass", side_effect=lambda *args: nullcontext()
            )
        )
        failure = None
        try:
            with scope:
                self.deliver(case, kind)
        except (ValueError, KeyError) as error:
            failure = (type(error), str(error))
        self.assertTrue(observed, "actual global activation must reach the callback")
        self.assertTrue(mutations, "next recipient must read the replacement status")
        self.assertIsNotNone(
            failure, "fresh full validation must reject the corrupt owned record"
        )
        self.assertIsNone(case.replay._read_pass)
        self.assertEqual(ordinary._PHASE_READ_SCOPES.get(), ())
        return observed, mutations, failure

    def test_callback_status_replacement_revokes_view_and_matches_without_pass(self):
        for kind in ("cast", "death"):
            with self.subTest(kind=kind):
                baseline = self.mutation_run(kind, False)
                candidate = self.mutation_run(kind, True)
                self.assertEqual(candidate, baseline)


if __name__ == "__main__":
    unittest.main()
