"""Fresh summon native control and physical carry must have separate live facts."""
import unittest
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import patch
from wakfu_server.combat_summon import RegisteredSummonAuthority
from wakfu_server.combat_runtime_adapter import NativeActorAuthority


class SummonRelationshipAuthorityTests(unittest.TestCase):
    def facts(self, controller=7):
        actor = SimpleNamespace(
            id=91,
            native_controller_id=controller,
            native_master_id=controller,
            native_carrier_id=None,
            native_carried_actor_id=None,
            spell_ap_cost_modifiers={},
            spell_range_modifiers={},
            native_summon_source=dict(
                ref=111,
                level=20,
                caster_id=7,
                controller_id=controller,
                native_relation_source="big.new_bje.fdt_initial_registration",
            ),
        )
        registration = dict(caster_id=7, controller_id=controller)
        authority = NativeActorAuthority(
            dict(dpr_id=controller, dpu_id=controller, buX=False),
            False,
            frozenset(),
            frozenset(),
            False,
            111,
            0,
            {},
            True,
            is_summon=True,
            summon_root_id=7,
            is_carrying=False,
            native_real_level=20,
            native_controller_id=controller,
        )
        return actor, registration, authority

    def check(self, facts):
        RegisteredSummonAuthority._fresh_relationships(*facts)

    def test_direct_and_self_controlled_fresh_relations_are_valid(self):
        self.check(self.facts(7))
        self.check(self.facts(91))

    def test_recursive_root_cannot_replace_direct_controller(self):
        actor, registration, authority = self.facts(91)
        with self.assertRaisesRegex(ValueError, "controller provenance"):
            self.check(
                (actor, registration, replace(authority, native_controller_id=7))
            )

    def test_master_change_needs_an_actual_native_producer(self):
        actor, registration, authority = self.facts()
        actor.native_master_id = 92
        with self.assertRaisesRegex(ValueError, "master.*producer"):
            self.check((actor, registration, authority))

    def test_carrying_and_carried_mutations_each_require_native_producer(self):
        for field in ("native_carrier_id", "native_carried_actor_id"):
            actor, registration, authority = self.facts()
            setattr(actor, field, 92)
            with self.assertRaisesRegex(ValueError, "physical carry.*producer"):
                self.check((actor, registration, authority))

    def test_old_missing_relationship_facts_are_not_assumed_empty(self):
        actor, registration, authority = self.facts()
        del actor.native_carrier_id
        with self.assertRaisesRegex(ValueError, "physical carry.*producer"):
            self.check((actor, registration, authority))

    def test_range_snapshot_is_required_independently_of_ap(self):
        actor, registration, authority = self.facts()
        actor.spell_range_modifiers = None
        with self.assertRaisesRegex(ValueError, "category modifier snapshot"):
            self.check((actor, registration, authority))

    def test_phase_delivers_to_summon_qf_at_summon_identity(self):
        from wakfu_server.combat_ordinary_events import OrdinaryHealingEvents

        summon, registration, summon_authority = self.facts(91)
        caster = SimpleNamespace(id=7)
        preview = SimpleNamespace(actors={7: caster, 91: summon})
        checked = []

        def actor_authority(_, actor):
            checked.append(actor.id)
            if actor.id == 91:
                self.check((summon, registration, summon_authority))
            return summon_authority

        recipients = []
        retention = SimpleNamespace(
            definition=lambda effect, invocation: dict(
                event_suppresses_level_one=False
            ),
            view=lambda: SimpleNamespace(entries=()),
        )
        events = OrdinaryHealingEvents.__new__(OrdinaryHealingEvents)
        events.adapter = SimpleNamespace(actor_authority=actor_authority)
        events.preview = preview
        events.retention = retention
        events.authority = object()
        events.replay = lambda source, **kwargs: recipients.append(
            (source.manager_actor_id, source.channel)
        )
        invocation = SimpleNamespace(
            reference=304,
            caster_id=7,
            target_id=91,
            cell=(1, 0, 0),
            native_trigger_context=None,
        )
        effect = dict(effect_class=304, native_effect_flags=[])
        with patch(
            "wakfu_server.combat_ordinary_events.source_cost_descriptor",
            return_value=None,
        ), patch(
            "wakfu_server.combat_trigger_identifiers.source_identifiers",
            return_value={},
        ):
            events.phase(
                effect, invocation, uid=501, value=0, channel=1, _event_ids=(0,)
            )

        self.assertEqual(recipients, [(7, 10), (91, 1)])
        self.assertIn(91, checked)
        self.assertNotIn(7, [identity for identity, _ in recipients[1:]])

    def test_phase_rejects_summon_with_changed_master_before_replay(self):
        from wakfu_server.combat_ordinary_events import OrdinaryHealingEvents

        summon, registration, summon_authority = self.facts(91)
        summon.native_master_id = 92
        preview = SimpleNamespace(actors={7: SimpleNamespace(id=7), 91: summon})

        def actor_authority(_, actor):
            if actor.id == 91:
                self.check((summon, registration, summon_authority))
            return summon_authority

        replayed = []
        retention = SimpleNamespace(
            definition=lambda effect, invocation: dict(
                event_suppresses_level_one=False
            ),
            view=lambda: SimpleNamespace(entries=()),
        )
        events = OrdinaryHealingEvents.__new__(OrdinaryHealingEvents)
        events.adapter = SimpleNamespace(actor_authority=actor_authority)
        events.preview = preview
        events.retention = retention
        events.authority = object()
        events.replay = lambda source, **kwargs: replayed.append(source)
        invocation = SimpleNamespace(
            reference=304,
            caster_id=7,
            target_id=91,
            cell=(1, 0, 0),
            native_trigger_context=None,
        )
        with patch(
            "wakfu_server.combat_ordinary_events.source_cost_descriptor",
            return_value=None,
        ), patch(
            "wakfu_server.combat_trigger_identifiers.source_identifiers",
            return_value={},
        ), self.assertRaisesRegex(
            ValueError, "master.*producer"
        ):
            events.phase(
                dict(effect_class=304, native_effect_flags=[]),
                invocation,
                uid=501,
                value=0,
                channel=1,
                _event_ids=(0,),
            )
        self.assertEqual(replayed, [])


if __name__ == "__main__":
    unittest.main()
