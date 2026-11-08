"""Native source custody with selected-manager ancestry and callback freshness."""
import unittest
from unittest.mock import patch

from test_combat_ordinary_phase_read_pass import PhaseReadPassSemanticTests
from wakfu_server.combat_event_replay import NativeCloneAuthority
from wakfu_server.combat_effect_dispatch import EffectInvocation
from wakfu_server.combat_effects import _integer
from wakfu_server.combat_state_ledger import RunningState
from wakfu_server.combat_state_parameters import pack_state_identity
from wakfu_server.combat_retained_effects import RetainedEffect
from wakfu_server.combat_retained_source_provenance import capture_state_source
from wakfu_server.combat_npc_external_event_scope import qualified_npc_uids
from wakfu_server.combat_npc_source_query import selected_source_query
from wakfu_server.combat_equipment_external_events import deliver_scoped_pairs
from wakfu_server.combat_source_provenance_entries import SourceProvenanceEntries


def state_wire(state, container):
    fields = [
        (1, state.uid),
        (2, state.uid),
        (3, -1),
        (4, pack_state_identity(state.reference, state.level)),
        (6, state.caster_id),
        (7, state.target_id),
    ]
    if container["container_present"]:
        fields.extend(
            ((9, container["container_type"]), (10, container["container_id"]))
        )
    return b"".join(_integer(key, value) for key, value in fields).hex()


class SelectedNpcSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        PhaseReadPassSemanticTests.setUpClass()

    def fixture(self):
        case = PhaseReadPassSemanticTests().fixture()
        fight, retention = case.fight, case.retention
        dispatcher = case.f.dispatcher
        dispatcher.native_retention = retention
        dispatcher.replay_event = case.events.replay
        dispatcher.native_clone_authority = NativeCloneAuthority(
            case.events.executable, case.events.conditions
        )
        parent = RunningState(
            1000, 501, 1, -7, -7, -1, "target", False, (), 0, True, None
        )
        child = RunningState(1001, 502, 1, 7, 7, -1, "target", False, (), 0, True, None)
        empty = dict(
            container_present=False,
            container_type=None,
            container_id=None,
            container_kind=None,
            container_is_spell=None,
            spell_protected=None,
        )
        state_pl = dict(
            container_present=True,
            container_type=1,
            container_id=pack_state_identity(501, 1),
            container_kind="state",
            container_is_spell=False,
            spell_protected=None,
        )
        for state, parent_uid, container in (
            (parent, None, empty),
            (child, 1000, state_pl),
        ):
            actor = fight.actors[state.target_id]
            actor.state_ledger._entries += (state,)
            fight.state_wire_payloads[state.uid] = state_wire(state, container)
            retention.record(
                RetainedEffect(
                    state.uid,
                    state.target_id,
                    310,
                    -1,
                    manager_id=state.target_id,
                    **container
                )
            )
            invocation = EffectInvocation(
                101,
                1,
                state.caster_id,
                state.target_id,
                actor.position,
                state_uid=parent_uid,
            )
            capture_state_source(fight, state, invocation, container)
        fight.native_owned_group_effects[1002] = dict(
            target_id=7,
            effect_class=330,
            state_uid=1001,
            invocation={"caster_id": 7},
            payload=b"".join(
                _integer(key, value)
                for key, value in ((1, 1002), (2, 1002), (3, 101), (6, 7), (7, 7))
            ).hex(),
        )
        retention.record(
            RetainedEffect(1002, 7, 330, 101, owner_uid=1001, manager_id=7)
        )
        self.assertIs(
            type(fight.native_state_source_provenance["entries"]),
            SourceProvenanceEntries,
        )
        return case, dispatcher

    def test_native_cross_manager_ancestry_exclusions_and_callback_mutation(self):
        case, dispatcher = self.fixture()
        fight = case.fight
        selected = selected_source_query(fight, 7)
        self.assertIsNotNone(selected)
        self.assertIn(1000, {entry.uid for entry in selected.entries})
        self.assertNotIn(1000, selected.selected_uids)
        expected = qualified_npc_uids(dispatcher) & selected.selected_uids
        self.assertEqual(qualified_npc_uids(dispatcher, manager_id=7), expected)
        self.assertTrue({1001, 1002} <= expected)
        # The global API still checks all provenance. Local delivery never
        # validates an unrelated historical source as authority for this Qf.
        provenance = fight.native_state_source_provenance["entries"]
        provenance["9999"] = {"uid": 9999}
        self.assertEqual(qualified_npc_uids(dispatcher, manager_id=7), expected)
        with self.assertRaises(ValueError):
            qualified_npc_uids(dispatcher)
        del provenance["9999"]
        seen = []

        def replay(event, *, authority, eligible_uids):
            seen.append((event.channel, eligible_uids))
            # A completed native callback can alter the next channel's source
            # exclusion. Qualification must not reuse the first result.
            fight.native_consumable_initializations = {7: [{"combat_uid": 1001}]}
            return ()

        dispatcher.replay_event = replay
        case.events.replay = replay
        deliver_scoped_pairs(
            dispatcher,
            event_id=1048,
            recipients=((7, 6), (7, 60)),
            npc_sources=True,
            equipment_actor_ids=frozenset(),
        )
        self.assertEqual(len(seen), 1)
        self.assertEqual(seen[0], (6, expected))
        self.assertEqual(qualified_npc_uids(dispatcher, manager_id=7), frozenset())
        self.assertEqual(
            qualified_npc_uids(dispatcher) & selected.selected_uids, frozenset()
        )
        # Relevant malformed ancestry remains an error, not an ignored source.
        fight.native_consumable_initializations = {}
        fight.native_state_source_provenance["entries"]["1001"]["container_id"] += 1
        with self.assertRaises(ValueError):
            qualified_npc_uids(dispatcher, manager_id=7)
        with self.assertRaises(ValueError):
            qualified_npc_uids(dispatcher)

    def test_legacy_or_custom_provenance_uses_complete_fallback(self):
        case, dispatcher = self.fixture()
        fight = case.fight
        expected = qualified_npc_uids(dispatcher)
        self.assertIn(1000, expected)  # This UID belongs to the other manager.
        with patch.object(case.retention, "view", wraps=case.retention.view) as custom:
            self.assertEqual(qualified_npc_uids(dispatcher, manager_id=7), expected)
            self.assertGreater(custom.call_count, 0)
        from wakfu_server import combat_retained_source_provenance as provenance_module

        with patch.object(
            provenance_module,
            "state_source_provenance",
            wraps=provenance_module.state_source_provenance,
        ) as custom:
            self.assertEqual(qualified_npc_uids(dispatcher, manager_id=7), expected)
            self.assertGreater(custom.call_count, 0)
        fight.native_state_source_provenance["entries"] = dict(
            fight.native_state_source_provenance["entries"]
        )
        self.assertIsNone(selected_source_query(fight, 7))
        self.assertEqual(qualified_npc_uids(dispatcher, manager_id=7), expected)
