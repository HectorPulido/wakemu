"""Scope, retained UID snapshots and persistence of explicit phase publishers."""
from copy import deepcopy
import json
from types import SimpleNamespace
import unittest

from wakfu_server.combat_npc_phase_controller import deliver_npc_table_phase


class NpcPhaseControllerTests(unittest.TestCase):
    def fixture(self):
        actor = SimpleNamespace(id=-7, controlled=False)
        fight = SimpleNamespace(
            phase="active",
            current=actor,
            actors={-7: actor},
            native_start_event_delivered=True,
            native_table_turn=4,
            native_npc_initialization_receipts={
                -7: dict(
                    ref=5664,
                    initialized=True,
                    resolved_states=[dict(state_id=8969)],
                )
            },
        )
        entries = [
            SimpleNamespace(uid=11, manager_id=-7, generic_effect=401610),
            SimpleNamespace(uid=12, manager_id=9, generic_effect=401610),
            SimpleNamespace(uid=13, manager_id=-7, generic_effect=401534),
            SimpleNamespace(uid=14, manager_id=-7, generic_effect=123),
        ]
        retention = SimpleNamespace(
            fight=fight,
            view=lambda: SimpleNamespace(entries=tuple(entries)),
        )
        calls = []

        def replay(source, **kwargs):
            calls.append((source, kwargs))
            return ("native",)

        dispatcher = SimpleNamespace(
            native_retention=retention,
            native_clone_authority=object(),
            replay_event=replay,
        )
        return fight, entries, dispatcher, calls

    def test_owned_snapshot_round_idempotence_extra_turns_and_checkpoint(self):
        fight, entries, dispatcher, calls = self.fixture()
        self.assertEqual(deliver_npc_table_phase(dispatcher, actor_id=-7), ("native",))
        source, arguments = calls[0]
        self.assertEqual(
            (source.manager_actor_id, source.event_ids, source.channel),
            (-7, (1003,), 61),
        )
        self.assertEqual(arguments["eligible_uids"], frozenset((11, 13)))
        entries.append(SimpleNamespace(uid=15, manager_id=-7, generic_effect=401623))
        fight.turn_id = 999  # An extra turn cannot repeat this table's pulse.
        self.assertEqual(deliver_npc_table_phase(dispatcher, actor_id=-7), ())
        # The production checkpoint stores ordinary primitive fight fields.
        restored = json.loads(json.dumps(fight.native_npc_phase_deliveries))
        fight.native_npc_phase_deliveries = restored
        self.assertEqual(deliver_npc_table_phase(dispatcher, actor_id=-7), ())
        fight.native_table_turn += 1
        deliver_npc_table_phase(dispatcher, actor_id=-7)
        self.assertEqual(calls[-1][1]["eligible_uids"], frozenset((11, 13, 15)))

    def test_empty_boundary_does_not_retroactively_activate_new_listener(self):
        fight, entries, dispatcher, calls = self.fixture()
        entries.clear()
        deliver_npc_table_phase(dispatcher, actor_id=-7)
        self.assertEqual(calls[0][1]["eligible_uids"], frozenset())
        entries.append(SimpleNamespace(uid=15, manager_id=-7, generic_effect=401610))
        deliver_npc_table_phase(dispatcher, actor_id=-7)
        self.assertEqual(len(calls), 1)

    def test_owned_cube_pulse_shares_the_existing_checkpointed_table_journal(self):
        from unittest.mock import patch

        fight, entries, dispatcher, calls = self.fixture()
        fight.turn_id = 1
        record = dict(policy="owned-cube", owner_id=-20, eligible_uids=[31])
        with patch(
            "wakfu_server.combat_encounter_table_listeners.deliver_owned_table_listeners",
            return_value=(("cube",), (record,)),
        ) as pulse:
            self.assertEqual(
                deliver_npc_table_phase(dispatcher, actor_id=-7), ("native", "cube")
            )
            self.assertEqual(pulse.call_args.kwargs["snapshot"], tuple(entries))
            self.assertEqual(
                next(iter(fight.native_npc_phase_deliveries.values()))[
                    "owned_listeners"
                ],
                [record],
            )
            fight.native_npc_phase_deliveries = json.loads(
                json.dumps(fight.native_npc_phase_deliveries)
            )
            fight.turn_id += 1
            self.assertEqual(deliver_npc_table_phase(dispatcher, actor_id=-7), ())
            self.assertEqual(pulse.call_count, 1)

    def test_other_descriptors_and_first_table_leave_opening_untouched(self):
        fight, entries, dispatcher, calls = self.fixture()
        fight.native_table_turn = 1
        deliver_npc_table_phase(dispatcher, actor_id=-7)
        fight.native_table_turn = 4
        fight.native_npc_initialization_receipts[-7]["ref"] = 123
        deliver_npc_table_phase(dispatcher, actor_id=-7)
        self.assertEqual(calls, [])
        self.assertFalse(hasattr(fight, "native_npc_phase_deliveries"))

    def test_failed_preview_leaves_canonical_effects_and_journal_untouched(self):
        fight, entries, dispatcher, calls = self.fixture()
        original = deepcopy(vars(fight))
        preview = deepcopy(fight)
        dispatcher.native_retention.fight = preview

        def failure(*args, **kwargs):
            preview.actors[-7].changed = True
            raise ValueError("native failure")

        dispatcher.replay_event = failure
        with self.assertRaisesRegex(ValueError, "native failure"):
            deliver_npc_table_phase(dispatcher, actor_id=-7)
        self.assertFalse(hasattr(fight, "native_npc_phase_deliveries"))
        self.assertEqual(vars(fight), original)
        self.assertFalse(hasattr(preview, "native_npc_phase_deliveries"))

    def test_invalid_turn_and_constructor_are_rejected(self):
        fight, entries, dispatcher, calls = self.fixture()
        with self.assertRaisesRegex(ValueError, "actual active"):
            deliver_npc_table_phase(dispatcher, actor_id=3)
        fight.native_npc_initialization_receipts[-7]["resolved_states"] = []
        with self.assertRaisesRegex(ValueError, "constructor receipt"):
            deliver_npc_table_phase(dispatcher, actor_id=-7)
