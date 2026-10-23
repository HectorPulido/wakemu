"""Persisted equipment consumes real opening, paid and successful-cast events."""
from copy import deepcopy
import struct
from unittest.mock import patch

from postgres_case import PostgresCase


class EquipmentEventScopePipelineTests(PostgresCase):
    def test_equipped_source_observes_paid_cast_and_preserves_checkpoint_ownership(
        self,
    ):
        import test_equipment_null_carrier_pipeline as helpers
        from wakfu_server.combat_cost_payment_events import NativeCostPaymentEvents
        from wakfu_server.combat_effect_dispatch import EffectDispatcher
        from wakfu_server.combat_reproduction_state import encode_state, decode_state
        from wakfu_server.combat_server_spell import (
            prepare_server_spell,
            server_runtime,
        )
        from wakfu_server.combat_spell_commit import commit_spell_transaction
        from wakfu_server.fight_checkpoint_store import snapshot

        (
            char,
            monster,
            deck,
            rng,
            runtime,
            stats,
        ) = helpers.EquipmentNullCarrierPipelineTests._fixture(
            self,
            reference=29456,
            slot=17,
            level=245,
            breed=8,
            active_spells=[4780],
            select_elements=True,
        )
        owner = char["id"]
        fight = runtime.fight
        source = next(
            row
            for row in fight.native_owned_equipment_sources[str(owner)]["sources"]
            if row["source_reference"] == 29456
        )
        self.assertIs(source["_generic_operation_admission"], True)
        self.assertEqual(tuple(source["roots"]), (325487,))
        root = next(
            row
            for row in fight.actors[owner].state_ledger.entries
            if row.reference == 7106
        )
        self.assertEqual(
            sum(
                row.reference == 7106
                for row in fight.actors[owner].state_ledger.entries
            ),
            1,
        )
        self.assertFalse(
            any(
                row.reference == 7109
                for row in fight.actors[owner].state_ledger.entries
            )
        )
        # 1028 installs the 1001 listener; real owner start installs the paid
        # AP listener. Neither is created directly by this test.
        self.assertTrue(
            any(
                row.get("invocation", {}).get("reference") == 325377
                for row in fight.native_owned_group_effects.values()
            )
        )
        before, before_ap = snapshot(fight), fight.actors[owner].ap
        completed, paid_events = [], []
        execute, phase = EffectDispatcher.execute, NativeCostPaymentEvents.phase

        def observe_execute(dispatcher, invocation, **kwargs):
            result = execute(dispatcher, invocation, **kwargs)
            if result and invocation.reference in (325377, 325378, 325380):
                completed.append(invocation.reference)
            return result

        def observe_payment(events, effect, invocation, **kwargs):
            if effect.get("effect_class") == 30:
                paid_events.append(
                    (
                        kwargs["channel"],
                        tuple(kwargs["_event_ids"]),
                        dict(effect["native_costs"]),
                        kwargs["value"],
                    )
                )
            return phase(events, effect, invocation, **kwargs)

        target = fight.actors[-200]
        with patch.object(EffectDispatcher, "execute", observe_execute), patch.object(
            NativeCostPaymentEvents, "phase", observe_payment
        ):
            transaction = prepare_server_spell(
                struct.pack(">qqiih", owner, (owner << 32) | 4780, *target.position),
                char,
                {-200: monster},
                fight,
                char["account_id"],
                deck,
                action_id=runtime.action_id + 1,
                line_of_sight=lambda *_args: True,
                critical=False,
                rng=rng,
            )
        self.assertEqual(snapshot(fight), before)
        self.assertGreater(transaction.plan["costs"]["ap"], 0)
        self.assertEqual(
            transaction.fight.actors[owner].ap,
            before_ap - transaction.plan["costs"]["ap"],
        )
        self.assertEqual([row[0] for row in paid_events], [3, 4])
        self.assertTrue(all(2234 in row[1] for row in paid_events))
        costs = transaction.plan["costs"]
        packed = costs["ap"] | (costs["mp"] << 8) | (costs["wp"] << 16)
        self.assertTrue(all(row[3] == packed for row in paid_events))
        self.assertEqual(completed.count(325377), 1)
        # This listener is first registered during payment and later cloned
        # on1025; its child state application, rather than both execute calls,
        # is the exact once-only observable.
        self.assertIn(325378, completed)
        self.assertEqual(completed.count(325380), 1)
        packets = commit_spell_transaction(
            runtime,
            transaction,
            stats_serializer=lambda actor, preview: stats(actor, preview),
        )
        self.assertTrue(packets)
        stack = next(
            row
            for row in runtime.fight.actors[owner].state_ledger.entries
            if row.reference == 7109
        )
        self.assertEqual(stack.level, 1)
        checkpoint = snapshot(runtime.fight)
        restored = decode_state(encode_state(runtime.fight))
        self.assertEqual(snapshot(restored), checkpoint)
        self.assertEqual(
            [
                row.uid
                for row in restored.actors[owner].state_ledger.entries
                if row.reference == 7109
            ],
            [stack.uid],
        )

        # Native retained removal on a detached checkpoint instance retires
        # the source and its actual produced state without touching the live
        # committed fight or re-installing the equipment graph.
        preview = deepcopy(restored)
        factory, _ = server_runtime(
            char,
            {-200: monster},
            deck,
            action_id=runtime.action_id + 1,
            critical=False,
            rng=rng,
        )
        dispatcher, outbox = factory(
            preview, {"native_retained_container": {"present": False}}
        )
        retention = dispatcher.native_retention
        retention.removal(retention.view()).remove((root.uid,))
        retention.synchronize()
        self.assertFalse(
            any(
                row.get("state_uid") == root.uid
                for row in preview.native_owned_group_effects.values()
            )
        )
        if any(
            row.uid == stack.uid for row in preview.actors[owner].state_ledger.entries
        ):
            retention.removal(retention.view()).remove((stack.uid,))
            retention.synchronize()
        self.assertFalse(
            any(
                row.reference in (7106, 7109)
                for row in preview.actors[owner].state_ledger.entries
            )
        )
        self.assertTrue(any(opcode == 13560 for opcode, _body in outbox))
        self.assertEqual(snapshot(runtime.fight), checkpoint)
