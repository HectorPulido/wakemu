"""Committed movement receipts and source-bearing eWf publication boundaries."""
from copy import deepcopy
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from wakfu_server.combat_state import Actor, Fight
from wakfu_server.combat_movement_payment_events import (
    committed_step_payment,
    consume_step_payment,
    replay_movement_payment,
    valid_movement_descriptor,
)
from wakfu_server.combat_cost_payment_events import PaidAbilityPolicy, payment_event_ids


class MovementPaymentTests(unittest.TestCase):
    def fixture(self):
        actor = Actor(7, 0, (0, 0, 0), 100, 6, 4, 20, 60, 3, True)
        enemy = Actor(8, 1, (4, 0, 0), 100, 6, 4, 10, 60)
        fight = Fight(
            2,
            [actor, enemy],
            {(x, 0, 0) for x in range(5)},
            {0: {actor.position}, 1: {enemy.position}},
        )
        fight.ready(3)
        return fight

    def test_actual_two_step_producer_publishes_exact_paid_receipts_once(self):
        fight = self.fixture()
        rows = []
        policies = []

        def callback(current, actor, origin, cell):
            policy = consume_step_payment(
                current, actor_id=7, origin=origin, path=[cell]
            )
            with self.assertRaisesRegex(ValueError, "does not own"):
                consume_step_payment(current, actor_id=7, origin=origin, path=[cell])
            with self.assertRaisesRegex(ValueError, "differs"):
                replay_movement_payment(
                    SimpleNamespace(native_retention=SimpleNamespace(fight=current)),
                    policy,
                )
            foreign = deepcopy(current)
            foreign.id += 1
            with self.assertRaisesRegex(ValueError, "differs"):
                replay_movement_payment(
                    SimpleNamespace(native_retention=SimpleNamespace(fight=foreign)),
                    policy,
                )
            preview = deepcopy(current)

            def phase(definition, invocation, **kwargs):
                rows.append((definition, invocation, kwargs))
                return ()

            dispatcher = SimpleNamespace(
                native_retention=SimpleNamespace(fight=preview),
                native_cost_payment_events_factory=lambda: SimpleNamespace(phase=phase),
            )
            before = (preview.current.ap, preview.current.mp, preview.current.hp)
            replay_movement_payment(dispatcher, policy)
            self.assertEqual(
                (preview.current.ap, preview.current.mp, preview.current.hp), before
            )
            with self.assertRaisesRegex(ValueError, "differs"):
                replay_movement_payment(dispatcher, policy)
            policies.append(policy)

        result = fight.move(3, 7, [(1, 0, 0), (2, 0, 0)], step_callback=callback)
        self.assertEqual(result["cost"], 2)
        self.assertEqual(fight.actors[7].mp, 2)
        self.assertEqual([p.receipt["index"] for p in policies], [0, 1])
        self.assertEqual([p.receipt["mp_paid"] for p in policies], [1, 1])
        self.assertEqual([row[2]["channel"] for row in rows], [3, 4, 3, 4])
        for definition, invocation, fields in rows:
            self.assertEqual(fields["_event_ids"], (0, 65, 74))
            self.assertEqual(fields["value"], 256)
            self.assertEqual((invocation.caster_id, invocation.target_id), (7, 7))
            descriptor = definition["native_movement_payment_policy"].descriptor(
                definition["native_costs"]
            )
            self.assertTrue(
                valid_movement_descriptor(descriptor, caster_id=7, target_id=7)
            )
            self.assertFalse(
                valid_movement_descriptor(descriptor, caster_id=8, target_id=8)
            )
        self.assertIsNone(
            consume_step_payment(fight, actor_id=7, origin=(0, 0, 0), path=[(1, 0, 0)])
        )

    def test_foreign_owner_failed_move_has_no_receipt_or_resource_spend(self):
        fight = self.fixture()
        before = (fight.actors[7].position, fight.actors[7].mp)
        calls = []
        with self.assertRaises(ValueError):
            fight.move(
                4, 7, [(1, 0, 0)], step_callback=lambda *args: calls.append(args)
            )
        with self.assertRaises(ValueError):
            fight.move(
                3, 7, [(4, 0, 0)], step_callback=lambda *args: calls.append(args)
            )
        self.assertEqual(calls, [])
        self.assertEqual((fight.actors[7].position, fight.actors[7].mp), before)
        self.assertIsNone(
            consume_step_payment(fight, actor_id=7, origin=(0, 0, 0), path=[(1, 0, 0)])
        )

    def test_forced_position_change_without_payment_cannot_publish(self):
        from wakfu_server.combat_qi_fight import move_registered_actor

        fight = self.fixture()
        actor = fight.actors[7]
        before_mp = actor.mp
        move_registered_actor(fight, actor, (1, 0, 0))
        self.assertEqual(actor.mp, before_mp)
        self.assertIsNone(
            consume_step_payment(
                fight, actor_id=7, origin=(0, 0, 0), path=[actor.position]
            )
        )
        self.assertEqual(replay_movement_payment(None, None), ())

    def test_exception_resets_receipt_and_clone_cannot_consume_source_authority(self):
        fight = self.fixture()

        def callback(current, actor, origin, cell):
            with self.assertRaisesRegex(ValueError, "does not own"):
                consume_step_payment(
                    deepcopy(current), actor_id=7, origin=origin, path=[cell]
                )
            raise RuntimeError("unpublished callback")

        with self.assertRaisesRegex(RuntimeError, "unpublished"):
            fight.move(3, 7, [(1, 0, 0)], step_callback=callback)
        self.assertIsNone(
            consume_step_payment(fight, actor_id=7, origin=(0, 0, 0), path=[(1, 0, 0)])
        )

    def test_frozen_or_free_committed_step_keeps_movement_flag_but_spell_does_not(self):
        fight = self.fixture()
        actor = fight.actors[7]
        from wakfu_server.combat_qi_fight import move_registered_actor

        origin = actor.position
        move_registered_actor(fight, actor, (1, 0, 0))
        with committed_step_payment(
            fight,
            actor,
            origin=origin,
            destination=actor.position,
            index=0,
            ap_before=actor.ap,
            mp_before=actor.mp,
            ap_paid=0,
            mp_paid=0,
        ):
            policy = consume_step_payment(
                fight, actor_id=7, origin=origin, path=[actor.position]
            )
            rows = []
            dispatcher = SimpleNamespace(
                native_retention=SimpleNamespace(fight=deepcopy(fight)),
                native_cost_payment_events_factory=lambda: SimpleNamespace(
                    phase=lambda *args, **kwargs: rows.append(kwargs)
                ),
            )
            replay_movement_payment(dispatcher, policy)
            self.assertEqual([row["_event_ids"] for row in rows], [(0, 74), (0, 74)])
            self.assertEqual([row["value"] for row in rows], [0, 0])
        costs = dict(ap=2, mp=1, wp=0)
        self.assertNotIn(74, payment_event_ids(costs, special=True))
        self.assertEqual(
            PaidAbilityPolicy(7).descriptor(costs)["paid_ability_policy"],
            dict(payer_id=7, mi=True, mh=False),
        )

    def test_callback_failure_rolls_back_complete_unpublished_client_movement(self):
        import struct
        from wakfu_server.combat_runtime_messages import RuntimeMessages
        from wakfu_server.combat_movement_runtime import apply_client

        fight = self.fixture()
        runtime = RuntimeMessages(fight)
        before = (fight.actors[7].position, fight.actors[7].mp, fight.actors[7].hp)
        seen = []

        def provider(current, **boundary):
            policy = consume_step_payment(
                current,
                actor_id=boundary["actor_id"],
                origin=boundary["origin"],
                path=boundary["path"],
            )
            seen.append(policy.receipt["mp_paid"])
            raise RuntimeError("transaction rejected")

        with self.assertRaisesRegex(RuntimeError, "transaction rejected"):
            apply_client(
                runtime,
                3,
                struct.pack(">qiih", 7, 1, 0, 0),
                lambda actor: b"owned",
                area_provider=provider,
            )
        self.assertEqual(seen, [1])
        self.assertIs(runtime.fight, fight)
        self.assertEqual(
            (fight.actors[7].position, fight.actors[7].mp, fight.actors[7].hp), before
        )
        self.assertIsNone(
            consume_step_payment(fight, actor_id=7, origin=(0, 0, 0), path=[(1, 0, 0)])
        )

    def test_frozen_and_hidden_raw_pa_preserve_existing_movement_and_exact_debit(self):
        from unittest.mock import patch
        from test_combat_resource_pa_notifications import ResourcePANotificationTests

        for frozen in (False, True):
            with self.subTest(frozen=frozen):
                fight = self.fixture()
                _, native = ResourcePANotificationTests().fixture()
                actor = fight.actors[7]
                # Reuse the authoritative PA unit fixture; isolate PA movement
                # from unrelated tackle authority in both differential paths.
                for name, value in vars(native).items():
                    if name != "id":
                        setattr(actor, name, deepcopy(value))
                actor.effect_resource_raw_currents[3] = 5
                actor.effect_frozen = frozenset({3}) if frozen else frozenset()
                baseline = deepcopy(fight)
                policies = []

                def callback(current, mover, origin, cell):
                    policies.append(
                        consume_step_payment(
                            current, actor_id=7, origin=origin, path=[cell]
                        )
                    )

                with patch(
                    "wakfu_server.combat_tackle_movement.movement_tackle_cost",
                    return_value=(0, 0),
                ):
                    expected = baseline.move(3, 7, [(1, 0, 0)])
                    actual = fight.move(3, 7, [(1, 0, 0)], step_callback=callback)
                self.assertEqual(actual, expected)
                for name in (
                    "position",
                    "ap",
                    "mp",
                    "effect_resource_raw_currents",
                    "effect_stats",
                ):
                    self.assertEqual(
                        getattr(actor, name), getattr(baseline.actors[7], name)
                    )
                self.assertEqual(actor.mp, 3)
                # Native non-expandable MP setter clamps hidden raw5 to max3.
                self.assertEqual(policies[0].receipt["mp_paid"], 0 if frozen else 2)
                self.assertEqual(policies[0].receipt["mp_before"], 5)
                self.assertEqual(policies[0].receipt["mp_after"], 5 if frozen else 3)
                wrong_raw = deepcopy(fight)
                wrong_raw.actors[7].effect_resource_raw_currents[3] += 1
                self.assertEqual(wrong_raw.actors[7].mp, actor.mp)
                with self.assertRaisesRegex(ValueError, "differs"):
                    replay_movement_payment(
                        SimpleNamespace(
                            native_retention=SimpleNamespace(fight=wrong_raw)
                        ),
                        policies[0],
                    )
                costs = dict(ap=0, mp=policies[0].receipt["mp_paid"], wp=0)
                self.assertTrue(
                    valid_movement_descriptor(
                        policies[0].descriptor(costs), caster_id=7, target_id=7
                    )
                )

    def test_forged_hour_wp_after_value_is_rejected_before_receipt_publication(self):
        fight = self.fixture()
        actor = fight.actors[7]
        actor.effect_stats = {4: 12}
        with patch(
            "wakfu_server.combat_tackle_movement.movement_tackle_cost",
            return_value=(0, 0),
        ):
            fight.move(3, 7, [(1, 0, 0)])
        with self.assertRaisesRegex(ValueError, "committed movement WP payment"):
            with committed_step_payment(
                fight,
                actor,
                origin=(0, 0, 0),
                destination=(1, 0, 0),
                index=0,
                ap_before=actor.ap,
                mp_before=4,
                ap_paid=0,
                mp_paid=1,
                wp_before=12,
                wp_after=11,
                wp_paid=1,
            ):
                self.fail("A claimed WP debit cannot differ from actual WP")
        self.assertIsNone(
            consume_step_payment(fight, actor_id=7, origin=(0, 0, 0), path=[(1, 0, 0)])
        )
