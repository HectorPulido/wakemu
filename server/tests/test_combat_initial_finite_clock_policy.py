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
