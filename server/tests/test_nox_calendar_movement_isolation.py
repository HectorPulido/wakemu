"""Keep DB-scoped calendar subscriptions out of voluntary movement only."""
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from wakfu_server import combat_encounter_table_listeners as listeners
from wakfu_server import combat_global_pv_collections as population
from wakfu_server.combat_voluntary_movement_events import deliver_voluntary_movement


class NoxCalendarMovementIsolationTests(unittest.TestCase):
    def fixture(self):
        from test_combat_external_policy_events import VoluntaryMovementEventTests

        fixture = VoluntaryMovementEventTests()
        fixture.setUp()
        fixture.actor.controlled = False
        fixture.actor.hp = 100
        fixture.actor.state_ledger = SimpleNamespace(
            entries=[SimpleNamespace(uid=100, reference=8979, caster_id=7, target_id=7)]
        )
        fixture.fight.native_npc_initialization_receipts = {
            7: dict(ref=5664, initialized=True, resolved_states=[dict(state_id=8969)])
        }
        callback = dict(
            effect_reference=401749,
            owner_reference=5664,
            owner_state=8979,
            forbidden_state=9031,
            timing="owned_boss_post_start",
            event_id=1005,
            channel=60,
        )
        policy = dict(
            policy="unit-scoped-calendar",
            boss_reference=5664,
            boss_constructor_state=8969,
            callbacks=[callback],
        )
        entries = [
            SimpleNamespace(uid=11, manager_id=7, generic_effect=401749),
            SimpleNamespace(uid=12, manager_id=7, generic_effect=401749),
            SimpleNamespace(uid=13, manager_id=-7, generic_effect=401749),
            SimpleNamespace(uid=14, manager_id=7, generic_effect=999),
        ]
        fixture.fight.native_owned_group_effects = {
            11: dict(
                invocation=dict(
                    reference=401749, state_uid=100, caster_id=7, target_id=7
                )
            ),
            12: dict(
                invocation=dict(
                    reference=401749, state_uid=101, caster_id=7, target_id=7
                )
            ),
            13: dict(
                invocation=dict(
                    reference=401749, state_uid=100, caster_id=-7, target_id=-7
                )
            ),
        }
        fixture.dispatcher.native_retention.view = lambda: SimpleNamespace(
            entries=tuple(entries)
        )
        calls = []
        fixture.dispatcher.replay_event = lambda event, **kwargs: (
            calls.append((event, kwargs)) or (True,)
        )
        return fixture, policy, entries, calls

    def step(self, fixture):
        return deliver_voluntary_movement(
            fixture.dispatcher,
            actor_id=7,
            from_cell=(0, 0, 0),
            to_cell=(1, 0, 0),
            action_id=12,
        )

    def test_ordinary_absence_keeps_original_channels_and_does_not_select_uids(self):
        fixture, policy, entries, calls = self.fixture()
        fixture.dispatcher.native_retention.view = lambda: self.fail(
            "ordinary movement should not select retained UIDs"
        )
        with patch.object(
            population, "global_pv_iterator", return_value=(7, -7)
        ), patch.object(listeners, "frozen_table_listener_policy", return_value=None):
            self.step(fixture)
        self.assertEqual(
            [(event.manager_actor_id, event.channel) for event, _ in calls],
            [(7, 6), (7, 60), (7, 4), (7, 40), (7, 61), (7, 41), (-7, 61), (-7, 41)],
        )
        self.assertTrue(all(set(options) == {"authority"} for event, options in calls))

    def test_only_exact_scoped_carrier_uid_is_excluded_on_its_matching_channel(self):
        fixture, policy, entries, calls = self.fixture()
        with patch.object(
            population, "global_pv_iterator", return_value=(7, -7)
        ), patch.object(listeners, "frozen_table_listener_policy", return_value=policy):
            self.step(fixture)
        filtered = [
            (event, options) for event, options in calls if "eligible_uids" in options
        ]
        self.assertEqual(len(filtered), 1)
        event, options = filtered[0]
        self.assertEqual((event.manager_actor_id, event.channel), (7, 60))
        self.assertEqual(options["eligible_uids"], frozenset({12, 13, 14}))
        self.assertTrue(
            all(event.movement_boundary_context is not None for event, _ in calls)
        )
        for change in (
            dict(timing="other"),
            dict(event_id=1002),
            dict(owner_reference=999),
            dict(channel=99),
        ):
            calls.clear()
            altered = dict(policy, callbacks=[dict(policy["callbacks"][0], **change)])
            with patch.object(
                population, "global_pv_iterator", return_value=()
            ), patch.object(
                listeners, "frozen_table_listener_policy", return_value=altered
            ):
                self.step(fixture)
            self.assertTrue(
                all("eligible_uids" not in options for event, options in calls)
            )

    def test_movement_does_not_consume_post_start_publication_or_its_once_journal(self):
        fixture, policy, entries, calls = self.fixture()
        entries[:] = [entries[0], entries[-1]]
        fixture.fight.native_table_turn = 9
        fixture.fight.native_turn_event_deliveries = {
            "1:7:start": dict(actor_id=7, turn_id=1, phase="start", event_id=1001)
        }
        fixture.dispatcher.effects = {"401749": {}}
        fixture.dispatcher.native_retention.metadata = {"effects": {"401749": {}}}
        with patch.object(
            population, "global_pv_iterator", return_value=()
        ), patch.object(
            listeners, "frozen_table_listener_policy", return_value=policy
        ), patch.object(
            listeners, "_callback_matches_native", return_value=True
        ):
            self.step(fixture)
            self.assertFalse(
                hasattr(fixture.fight, "native_encounter_post_start_deliveries")
            )
            calls.clear()
            self.assertEqual(
                listeners.deliver_owned_post_start_listeners(
                    fixture.dispatcher, actor_id=7
                ),
                (True,),
            )
            self.assertEqual(calls[0][1]["eligible_uids"], frozenset({11}))
            self.assertIsNone(calls[0][0].movement_boundary_context)
            self.assertEqual(
                listeners.deliver_owned_post_start_listeners(
                    fixture.dispatcher, actor_id=7
                ),
                (),
            )
            self.assertEqual(len(calls), 1)
