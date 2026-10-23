"""Real saved Turquoise source observes completed owned critical damage hits."""
from copy import deepcopy
from random import Random
import struct
from unittest.mock import patch

from postgres_case import PostgresCase


class _MinimumRandom(Random):
    """Legal minimum native draws make the actual owned critical roll stable."""

    def randint(self, low, high):
        return low


class EquipmentTurquoisePipelineTests(PostgresCase):
    def test_saved_source_paid_critical_hit_preview_rollback_and_checkpoint(self):
        import test_equipment_null_carrier_pipeline as helpers
        from wakfu_server.combat_critical import prepare_with_critical
        from wakfu_server import combat_critical_hit_events as critical_events
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
            _fixture_rng,
            runtime,
            stats,
        ) = helpers.EquipmentNullCarrierPipelineTests._fixture(
            self,
            reference=28417,
            slot=17,
            level=245,
            breed=8,
            active_spells=[4780],
            select_elements=True,
        )
        owner = char["id"]
        source = next(
            row
            for row in runtime.fight.native_owned_equipment_sources[str(owner)][
                "sources"
            ]
            if row["source_reference"] == 28417
        )
        self.assertIs(source["_generic_operation_admission"], True)
        self.assertTrue(
            any(
                state.reference == 6731
                for state in runtime.fight.actors[owner].state_ledger.entries
            )
        )
        self.assertTrue(
            any(
                row.get("invocation", {}).get("reference") == 311729
                for row in runtime.fight.native_owned_group_effects.values()
            )
        )

        def level(fight, reference):
            return sum(
                state.level
                for state in fight.actors[owner].state_ledger.entries
                if state.reference == reference
            )

        self.assertEqual(level(runtime.fight, 6733), 0)
        baseline = snapshot(runtime.fight)
        target = runtime.fight.actors[-200]
        rng = _MinimumRandom(28417)

        def prepare(*, critical, rng):
            return prepare_server_spell(
                struct.pack(">qqiih", owner, (owner << 32) | 4780, *target.position),
                char,
                {-200: monster},
                runtime.fight,
                char["account_id"],
                deck,
                action_id=runtime.action_id + 1,
                line_of_sight=lambda *_args: True,
                critical=critical,
                rng=rng,
            )

        # A real noncritical damage transaction pays its normal native cost
        # and leaves the critical-only item state unchanged. It is not adopted.
        normal_decision, normal = prepare_with_critical(
            runtime.fight.actors[owner],
            rng=rng,
            prepare=prepare,
            mode="normal",
        )
        self.assertFalse(normal_decision.critical)
        self.assertGreater(normal.plan["costs"]["ap"], 0)
        self.assertEqual(level(normal.fight, 6733), 0)
        self.assertEqual(level(normal.fight, 6732), 0)
        self.assertLess(normal.fight.actors[-200].hp, target.hp)
        self.assertEqual(snapshot(runtime.fight), baseline)

        original = critical_events.deliver_completed_critical_hit
        rejected_hits = []

        def fail_after_actual_application(handler, effect, invocation, **boundary):
            result = original(handler, effect, invocation, **boundary)
            rejected_hits.append((boundary["uid"], invocation.target_id))
            self.assertGreater(level(handler.fight, 6733), 0)
            raise ValueError(
                "qualification failure after actual critical item application"
            )

        random_before = rng.getstate()
        with patch.object(
            critical_events,
            "deliver_completed_critical_hit",
            fail_after_actual_application,
        ):
            with self.assertRaisesRegex(ValueError, "qualification failure"):
                prepare_with_critical(
                    runtime.fight.actors[owner], rng=rng, prepare=prepare
                )
        self.assertTrue(rejected_hits)
        self.assertEqual(rng.getstate(), random_before)
        self.assertEqual(snapshot(runtime.fight), baseline)

        hits = []

        def observe(handler, effect, invocation, **boundary):
            context = boundary["context"]
            self.assertIs(context.critical, True)
            self.assertEqual(invocation.caster_id, owner)
            self.assertEqual(invocation.target_id, -200)
            # Exercise the absent-caster eligibility fence using the ACTUAL
            # callback objects. This is a temporary post-L4 membership probe,
            # not a claim to play a detached constructor source to completion.
            before = snapshot(handler.fight)
            outbox_length = len(handler.packets)
            actual_actor = handler.fight.actors.pop(owner)
            try:
                self.assertEqual(original(handler, effect, invocation, **boundary), ())
                self.assertEqual(len(handler.packets), outbox_length)
            finally:
                handler.fight.actors[owner] = actual_actor
            self.assertEqual(snapshot(handler.fight), before)
            result = original(handler, effect, invocation, **boundary)
            hits.append(
                (boundary["uid"], invocation.target_id, boundary["result"]["value"])
            )
            return result

        with patch.object(critical_events, "deliver_completed_critical_hit", observe):
            decision, transaction = prepare_with_critical(
                runtime.fight.actors[owner],
                rng=rng,
                prepare=prepare,
            )
        self.assertTrue(decision.critical)
        self.assertEqual(decision.mode, "auto")
        self.assertGreater(transaction.plan["costs"]["ap"], 0)
        self.assertLess(
            transaction.fight.actors[owner].ap, runtime.fight.actors[owner].ap
        )
        self.assertLess(transaction.fight.actors[-200].hp, target.hp)
        self.assertTrue(hits)
        self.assertEqual(
            len({(uid, recipient) for uid, recipient, _value in hits}), len(hits)
        )
        self.assertEqual(level(transaction.fight, 6733), len(hits))
        self.assertEqual(level(transaction.fight, 6732), len(hits))
        self.assertEqual(snapshot(runtime.fight), baseline)
        packets = commit_spell_transaction(
            runtime,
            transaction,
            stats_serializer=lambda actor, preview: stats(actor, preview),
        )
        self.assertTrue(packets)
        self.assertEqual(level(runtime.fight, 6733), len(hits))
        self.assertEqual(level(runtime.fight, 6732), len(hits))
        stable = snapshot(runtime.fight)
        restored = decode_state(encode_state(runtime.fight))
        self.assertEqual(snapshot(restored), stable)
        self.assertEqual(level(restored, 6733), len(hits))
        # Remove the actual permanent item carrier in an independent preview.
        # The native state machinery, not this policy, owns descendant timers.
        preview = deepcopy(restored)
        root = next(
            state
            for state in preview.actors[owner].state_ledger.entries
            if state.reference == 6731
        )
        factory, _ = server_runtime(
            char,
            {-200: monster},
            deck,
            action_id=runtime.action_id + 1,
            critical=False,
            rng=rng,
        )
        dispatcher, _outbox = factory(
            preview, {"native_retained_container": {"present": False}}
        )
        retained = dispatcher.native_retention
        retained.removal(retained.view()).remove((root.uid,))
        retained.synchronize()
        self.assertFalse(
            any(
                row.get("invocation", {}).get("reference") == 311729
                for row in preview.native_owned_group_effects.values()
            )
        )
        self.assertEqual(snapshot(runtime.fight), stable)
        owned = self.store.character(char["account_id"], owner)
        self.assertTrue(
            any(
                item["reference"] == 28417 and item["quantity"] == 1
                for item in owned["inventory_items"]
            )
        )
