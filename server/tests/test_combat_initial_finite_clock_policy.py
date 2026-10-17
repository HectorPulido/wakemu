"""Actual detached constructor -> real Fight timeline policy integration."""
import unittest
from unittest.mock import patch
import test_combat_initial_state_finite_constructor as original
from wakfu_server.combat.combat_summon_initialization import (
    detached_summon_scope,
    install_initial_states,
)
from wakfu_server.combat.combat_summon_initial_states import initial_state_plan
from wakfu_server.combat.combat_initial_finite_clock_policy import (
    bind_initial_finite_clocks,
)
from wakfu_server.wire import proto_fields


class InitialFiniteClockPolicyTests(unittest.TestCase):
    def constructor(self):
        f = original.FiniteInitialConstructorTests()
        f.setUp()
        with detached_summon_scope(f.fight, f.actor, f.authority):
            install_initial_states(
                f.fight,
                f.actor,
                initial_state_plan([123, 1, 1], 1),
                runtime_factory=lambda *a: (f.dispatcher, f.packets),
            )
        self.assertIsNone(f.actor.state_ledger.entries[0].timer)
        f.actor.team = 1
        f.fight.actors[f.actor.id] = f.actor
        f.fight.actors[7].controlled = True
        f.fight.actors[7].owner_id = 3
        f.fight.native_npc_initialization_receipts = {
            f.actor.id: dict(initialized=True)
        }
        return f

    def test_actual_constructor_binds_on_real_ready_once_and_expires(self):
        f = self.constructor()
        before = f.actor.state_ledger.entries[0]
        old_payload = f.fight.state_wire_payloads[before.uid]
        with patch(
            "wakfu_server.combat.combat_server_spell.states_catalog",
            return_value=f.catalog,
        ):
            f.fight.ready(3)
        entry = f.actor.state_ledger.entries[0]
        self.assertIsNotNone(entry.timer)
        self.assertEqual(entry.uid, before.uid)
        self.assertEqual(bind_initial_finite_clocks(f.fight, f.catalog), ())
        old = dict(proto_fields(bytes.fromhex(old_payload)))
        new = dict(proto_fields(bytes.fromhex(f.fight.state_wire_payloads[entry.uid])))
        self.assertNotEqual(old.pop(90), new.pop(90))
        self.assertEqual(old, new)
        self.assertEqual(
            f.fight.expire_states(
                actor_id=entry.timer.actor_id,
                round_number=entry.timer.expiration_round - 1,
                phase="start",
            ),
            (),
        )
        self.assertEqual(
            f.fight.expire_states(
                actor_id=entry.timer.actor_id,
                round_number=entry.timer.expiration_round,
                phase=entry.timer.phase,
            ),
            (entry,),
        )
        self.assertEqual(f.actor.state_ledger.entries, ())

    def test_pending_clock_binds_once_at_repeated_current_slot_without_losing_cursor(
        self,
    ):
        from wakfu_server.combat.combat_additional_turn import additional_turn_insertion
        from wakfu_server.combat.combat_native_timing_context import (
            native_state_timeline,
        )

        f = self.constructor()
        entry = f.actor.state_ledger.entries[0]
        old_payload = f.fight.state_wire_payloads[entry.uid]
        # Hold only this integration policy to reproduce a pending constructor
        # checkpoint at a real repeated activation. Real Ready/advance and
        # native insertion arithmetic still own the timeline and turn counts.
        with patch(
            "wakfu_server.combat.combat_initial_finite_clock_policy.bind_initial_finite_clocks",
            return_value=(),
        ):
            f.fight.ready(3)
            self.assertEqual(f.fight.order, [7, f.actor.id])
            f.fight.native_base_turn_order = list(f.fight.order)
            for identity, offset in ((7, 2), (f.actor.id, 3)):
                inserted = additional_turn_insertion(
                    f.fight.order,
                    f.fight.turn_index,
                    mode=0,
                    offset=offset,
                    caster_id=7,
                    target_id=identity,
                )
                self.assertTrue(inserted["applied"])
                f.fight.order = inserted["order"]
            f.fight._advance()
            f.fight._advance()
        self.assertEqual(f.fight.order, [7, f.actor.id, 7, f.actor.id])
        self.assertEqual((f.fight.current.id, f.fight.turn_index), (7, 2))
        self.assertEqual(f.fight.current.turn_count, 2)
        timeline = native_state_timeline(f.fight, f.actor.id)
        self.assertEqual(
            (timeline.current_actor_index, timeline.clock_actor_index), (2, 1)
        )
        bindings = []
        ledger_type = type(f.actor.state_ledger)
        original_bind = ledger_type.bind_registered_timer

        def track_bind(ledger, previous, updated):
            bindings.append(previous.uid)
            return original_bind(ledger, previous, updated)

        order, base = list(f.fight.order), list(f.fight.native_base_turn_order)
        with patch.object(ledger_type, "bind_registered_timer", track_bind):
            self.assertEqual(
                bind_initial_finite_clocks(f.fight, f.catalog), (entry.uid,)
            )
            self.assertEqual(bind_initial_finite_clocks(f.fight, f.catalog), ())
        self.assertEqual(bindings, [entry.uid])
        updated = f.actor.state_ledger.entries[0]
        # Native SU's actual cursor is after the first clock-actor slot: a
        # duration2 clock starts from the following round and expires at4.
        self.assertEqual(
            (
                updated.timer.actor_id,
                updated.timer.expiration_round,
                updated.timer.phase,
            ),
            (f.actor.id, 4, "start"),
        )
        self.assertEqual((updated.uid, updated.duration), (entry.uid, entry.duration))
        self.assertEqual((f.fight.order, f.fight.native_base_turn_order), (order, base))
        old = dict(proto_fields(bytes.fromhex(old_payload)))
        new = dict(proto_fields(bytes.fromhex(f.fight.state_wire_payloads[entry.uid])))
        self.assertNotEqual(old.pop(90), new.pop(90))
        self.assertEqual(old, new)
        self.assertEqual(
            f.fight.expire_states(actor_id=f.actor.id, round_number=3, phase="start"),
            (),
        )
        self.assertEqual(
            f.fight.expire_states(actor_id=f.actor.id, round_number=4, phase="start"),
            (updated,),
        )

    def test_duplicate_slots_without_valid_saved_base_reject_before_binding(self):
        for base in (None, [7, 7, -3], [7], [7, -3, 999]):
            with self.subTest(base=base):
                f = self.constructor()
                with patch(
                    "wakfu_server.combat.combat_initial_finite_clock_policy.bind_initial_finite_clocks",
                    return_value=(),
                ):
                    f.fight.ready(3)
                f.fight.order.insert(1, 7)
                f.fight.native_base_turn_order = base
                entry = f.actor.state_ledger.entries[0]
                payload = f.fight.state_wire_payloads[entry.uid]
                order = list(f.fight.order)
                with self.assertRaisesRegex(
                    ValueError, "registered finite-clock timeline"
                ):
                    bind_initial_finite_clocks(f.fight, f.catalog)
                self.assertIs(f.actor.state_ledger.entries[0], entry)
                self.assertIsNone(entry.timer)
                self.assertEqual(f.fight.state_wire_payloads[entry.uid], payload)
                self.assertEqual(f.fight.order, order)
                self.assertEqual(f.fight.native_base_turn_order, base)

    def test_protected_or_unregistered_constructor_keeps_original_unscheduled_clock(
        self,
    ):
        from dataclasses import replace

        for kind in ("protected", "unregistered"):
            with self.subTest(kind=kind):
                f = self.constructor()
                entry = f.actor.state_ledger.entries[0]
                if kind == "protected":
                    f.actor.state_ledger._entries = (replace(entry, protected=True),)
                else:
                    f.fight.native_npc_initialization_receipts = {}
                with patch(
                    "wakfu_server.combat.combat_server_spell.states_catalog",
                    return_value=f.catalog,
                ):
                    f.fight.ready(3)
                self.assertIsNone(f.actor.state_ledger.entries[0].timer)
