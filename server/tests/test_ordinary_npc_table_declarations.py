"""Book-independent admission preserves original source and live carrier ownership."""
from contextlib import ExitStack
from copy import deepcopy
import sys
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch

from wakfu_server import combat_npc_table_start_events as events


class OrdinaryTableDeclarationTests(unittest.TestCase):
    def setUp(self):
        self.catalog = {
            "states": {"5745": {"effect_ids": [270355]}},
            "effects": {
                "270355": {
                    "effect_class": 330,
                    "target_masks": [None, None, None, None, None, [1003], None],
                }
            },
        }
        self.metadata = {
            "270355": {
                "subscription": True,
                "event_global_subscription": True,
                "event_reverse_subscription": False,
                "event_caster_code": 2,
                "event_target_code": 2,
                "event_execution_count": -1,
                "event_execution_count_per_level": 0,
            }
        }
        self.declaration = dict(
            policy=events.POLICY,
            state_id=5745,
            root_id=270355,
            source_sha256=events._digest(events._program(self.catalog, 5745, 270355)),
            metadata_sha256=events._digest(self.metadata["270355"]),
            authority="fixture",
            source_uri="fixture:5745/270355",
        )
        self.carrier = SimpleNamespace(
            uid=12, reference=5745, caster_id=-7, target_id=-7
        )
        self.actor = SimpleNamespace(
            id=-7,
            controlled=False,
            effective_level=157,
            hp=100,
            state_ledger=SimpleNamespace(entries=[self.carrier]),
        )
        self.receipt = dict(
            ref=4534,
            initialized=True,
            descriptor_level=157,
            resolved_states=[dict(state_id=5745)],
        )

    def sources(self):
        stack = ExitStack()
        modules = {}
        definitions = {
            "combat_npc_attack": {
                "npc_spell_catalog": lambda: {"activation_policy": {}}
            },
            "combat_npc_event_controller": {
                "event_controller_record": lambda *args: None
            },
            "combat_server_spell": {"states_catalog": lambda: self.catalog},
            "combat_retained_runtime": {
                "native_retained_metadata": lambda: {"effects": self.metadata}
            },
            "combat_npc_external_event_scope": {
                "qualified_npc_uids": lambda dispatcher: frozenset({13})
            },
            "combat_encounter_player_table_events": {
                "freeze_player_table_listeners": lambda *args: None
            },
        }
        for name, attributes in definitions.items():
            module = ModuleType("wakfu_server." + name)
            module.__dict__.update(attributes)
            modules[module.__name__] = module
        stack.enter_context(patch.dict(sys.modules, modules))
        stack.enter_context(
            patch(
                "wakfu_server.combat_npc_table_declarations.constructor_table_declarations",
                return_value=[self.declaration],
            )
        )
        return stack

    def test_owned_spell_book_keeps_actual_constructor_callback_without_state_application(
        self,
    ):
        with self.sources():
            result = events.freeze_initial_listeners(
                None, self.actor, 4534, self.receipt
            )
            self.assertEqual(result, [dict(declaration=self.declaration, state_uid=12)])
            self.assertIsNot(result[0]["declaration"], self.declaration)
            self.assertEqual(self.actor.state_ledger.entries, [self.carrier])
            self.receipt["resolved_states"] = []
            with self.assertRaisesRegex(ValueError, "constructor-state source"):
                events.freeze_initial_listeners(None, self.actor, 4534, self.receipt)

    def test_removed_or_foreign_carriers_never_receive_synthetic_callbacks(self):
        with self.sources():
            self.receipt["table_start_listeners"] = events.freeze_initial_listeners(
                None, self.actor, 4534, self.receipt
            )
            fight = SimpleNamespace(
                actors={-7: self.actor},
                native_npc_initialization_receipts={-7: self.receipt},
                native_owned_group_effects={13: dict(invocation=dict(state_uid=12))},
            )
            dispatcher = SimpleNamespace(
                native_retention=SimpleNamespace(
                    fight=fight,
                    view=lambda: SimpleNamespace(
                        entries=[
                            SimpleNamespace(
                                uid=13, manager_id=-7, generic_effect=270355
                            )
                        ]
                    ),
                )
            )
            self.assertEqual(
                events.initial_table_deliveries(dispatcher),
                [dict(actor_id=-7, eligible_uids=[13])],
            )
            self.actor.state_ledger.entries = []
            self.assertEqual(
                events.initial_table_deliveries(dispatcher),
                [dict(actor_id=-7, eligible_uids=[])],
            )
            self.actor.state_ledger.entries = [deepcopy(self.carrier)]
            self.actor.state_ledger.entries[0].caster_id = 7
            with self.assertRaisesRegex(ValueError, "source UID changed"):
                events.initial_table_deliveries(dispatcher)

    def test_additive_reapplication_requires_exact_original_constructor_ancestry(self):
        with self.sources():
            self.receipt["table_start_listeners"] = events.freeze_initial_listeners(
                None, self.actor, 4534, self.receipt
            )
            successor = deepcopy(self.carrier)
            successor.uid = 15
            self.actor.state_ledger.entries = [successor]
            fight = SimpleNamespace(
                actors={-7: self.actor},
                native_npc_initialization_receipts={-7: self.receipt},
                native_owned_group_effects={13: dict(invocation=dict(state_uid=15))},
            )
            dispatcher = SimpleNamespace(
                native_retention=SimpleNamespace(
                    fight=fight,
                    view=lambda: SimpleNamespace(
                        entries=[
                            SimpleNamespace(
                                uid=13, manager_id=-7, generic_effect=270355
                            )
                        ]
                    ),
                )
            )
            ancestry = {
                uid: dict(
                    state_reference=5745,
                    caster_id=-7,
                    target_id=-7,
                    parent_known=True,
                    parent_state_uid=parent,
                )
                for uid, parent in ((15, 14), (14, 12), (12, None))
            }
            with patch(
                "wakfu_server.combat_retained_source_provenance.state_source_provenance",
                return_value=ancestry,
            ):
                self.assertEqual(
                    events.initial_table_deliveries(dispatcher),
                    [dict(actor_id=-7, eligible_uids=[13])],
                )
                self.assertEqual(
                    self.receipt["table_start_listeners"][0]["state_uid"], 12
                )
                # A new self-cast state with no ancestry cannot inherit a
                # removed constructor's callback merely by its definition ID.
                ancestry[15]["parent_state_uid"] = None
                self.assertEqual(
                    events.initial_table_deliveries(dispatcher),
                    [dict(actor_id=-7, eligible_uids=[])],
                )
                ancestry[15]["parent_state_uid"] = 14
                for key, invalid in (
                    ("caster_id", 7),
                    ("target_id", 7),
                    ("state_reference", 999),
                    ("parent_known", False),
                ):
                    valid = ancestry[14][key]
                    ancestry[14][key] = invalid
                    self.assertEqual(
                        events.initial_table_deliveries(dispatcher),
                        [dict(actor_id=-7, eligible_uids=[])],
                    )
                    ancestry[14][key] = valid
                fight.native_owned_group_effects[13]["invocation"]["state_uid"] = 12
                self.assertEqual(
                    events.initial_table_deliveries(dispatcher),
                    [dict(actor_id=-7, eligible_uids=[])],
                )


if __name__ == "__main__":
    unittest.main()
