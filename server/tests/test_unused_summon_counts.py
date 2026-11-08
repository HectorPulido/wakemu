"""Property/corpse readers skip GF; condition projections remain complete."""
from dataclasses import replace
import unittest
from unittest.mock import patch

from test_event_recipient_authority_local import EventRecipientAuthorityLocalTests
from wakfu_server import combat_summon as summon
from wakfu_server.combat_summon_count import registered_summon_counts


class UnusedSummonCountsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        EventRecipientAuthorityLocalTests.setUpClass()

    def setUp(self):
        EventRecipientAuthorityLocalTests.setUp(self)
        self.fight = self.case.fight
        self.actor = self.fight.actors[7]
        self.fight.native_owned_group_effects[900] = {
            "invocation": {"target_id": 7, "caster_id": 7},
        }
        self.invocation = replace(self.case.inv, base_uid=900)

    def read_consumers(self):
        return (
            self.case.adapter.actor_authority.properties(self.fight, self.actor),
            self.case.events.executable(self.case.effect, self.invocation, None),
        )

    def test_native_consumers_match_full_authority_without_gf(self):
        with patch.object(
            summon,
            "authority_without_summon_counts",
            side_effect=lambda authority, fight, actor: authority(fight, actor),
        ):
            expected = self.read_consumers()
        with patch(
            "wakfu_server.combat_summon_count.registered_summon_counts",
            side_effect=AssertionError("Unused GF query"),
        ):
            self.assertEqual(self.read_consumers(), expected)
            actual = summon.authority_without_summon_counts(
                self.wrapper, self.fight, self.actor
            )
        full = self.wrapper(self.fight, self.actor)
        self.assertEqual(
            replace(
                actual,
                summon_count=full.summon_count,
                summon_counts_by_breed=full.summon_counts_by_breed,
                native_summon_counts_complete=full.native_summon_counts_complete,
            ),
            full,
        )

    def test_custom_wrapper_keeps_complete_calls(self):
        calls = []

        class Custom(summon.RegisteredSummonAuthority):
            def __call__(self, fight, actor, **kwargs):
                calls.append(kwargs)
                return super().__call__(fight, actor, **kwargs)

        custom = Custom(self.ordinary)
        self.case.adapter.actor_authority = custom
        with patch(
            "wakfu_server.combat_summon_count.registered_summon_counts",
            wraps=registered_summon_counts,
        ) as counts:
            self.read_consumers()
        self.assertEqual(len(calls), 4)  # properties + caster/target/original target
        self.assertTrue(all(call == {} for call in calls))
        self.assertEqual(counts.call_count, 4)

    def test_condition_projection_keeps_fresh_gf_counts(self):
        with patch(
            "wakfu_server.combat_summon_count.registered_summon_counts",
            wraps=registered_summon_counts,
        ) as counts:
            before = self.wrapper.condition_projection(self.fight, self.actor)[0]
            self.fight.actors[-8].native_fight_properties = frozenset({103})
            after = self.wrapper.condition_projection(self.fight, self.actor)[0]
        self.assertEqual((before.summon_count, after.summon_count), (1, 0))
        self.assertTrue(before.native_summon_counts_complete)
        self.assertTrue(after.native_summon_counts_complete)
        self.assertEqual(counts.call_count, 2)
