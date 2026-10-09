import unittest
import struct
from wakfu_server.combat_observation_delivery import (
    observation_registers,
    retained_delivery_opcode,
    choose_delivery,
    evaluated_application_from_observation,
)


class ObservationDeliveryTests(unittest.TestCase):
    def test_conversion_preserves_full_original_proto_and_action_identity(self):
        from wakfu_server.combat_effects import _integer

        proto = (
            b"".join(
                _integer(k, v)
                for k, v in (
                    (1, 81),
                    (2, 70),
                    (3, 150327),
                    (4, 20),
                    (6, 7),
                    (7, -8),
                    (9, 1),
                    (10, (3442 << 16) | 20),
                )
            )
            + b"\x5a\x02\x28\x01"
        )
        body = struct.pack(">iiiih", 3, 9, -1, 400, len(proto)) + proto
        converted = evaluated_application_from_observation(body)
        self.assertEqual(converted[:12], body[:12])
        self.assertEqual(converted[12], 0)
        self.assertEqual(converted[13:], body[12:])
        self.assertEqual(converted[19:], proto)
        executed = evaluated_application_from_observation(body, execute=True)
        self.assertEqual(executed[12], 1)
        self.assertEqual(executed[:12] + executed[13:], body)
        with self.assertRaises(ValueError):
            evaluated_application_from_observation(body, execute=1)
        for invalid in (body[:-1], body + b"\x00", b"", bytearray(body)):
            with self.assertRaises(ValueError):
                evaluated_application_from_observation(invalid)

    def test_evaluated_mutation_selects_execution_from_actual_retention(self):
        from wakfu_server.combat_stat_effects import (
            owned_effect_payload,
            evaluated_effect_delivery,
        )

        proto = owned_effect_payload(
            uid=81,
            base_uid=None,
            generic_effect=150327,
            caster_id=7,
            target_id=7,
            value=-3,
        )
        for retained in (False, True):
            opcode, body = evaluated_effect_delivery(
                3,
                9,
                retained=retained,
                effect_class=193,
                target_id=7,
                uid=81,
                running_effect_payload=proto,
            )
            self.assertEqual(opcode, 12613)
            self.assertEqual(body[12], int(not retained))
            self.assertEqual(body[19:], proto)
        with self.assertRaises(ValueError):
            evaluated_effect_delivery(
                3,
                9,
                retained=None,
                effect_class=193,
                target_id=7,
                uid=81,
                running_effect_payload=proto,
            )

    def test_delivery_checks_actual_manager_for_each_action(self):
        args = dict(
            native_ty=True,
            subscribed=True,
            native_delayed=False,
            manager_id=-7,
            observation_owner=7,
            full_owner=-7,
        )
        self.assertEqual(choose_delivery(**args), 12613)
        self.assertEqual(choose_delivery(**dict(args, observation_owner=-7)), 13497)
        with self.assertRaises(ValueError):
            choose_delivery(**dict(args, full_owner=7))
        with self.assertRaises(ValueError):
            choose_delivery(**dict(args, manager_id=True))

    def test_original_guard_truth_table(self):
        for persistent in (False, True):
            for delayed in (False, True):
                for masks in (False, True):
                    for manager in (False, True):
                        with self.subTest(
                            Ty=persistent, bbW=delayed, aZN=masks, manager=manager
                        ):
                            self.assertEqual(
                                observation_registers(
                                    persistent=persistent,
                                    delayed=delayed,
                                    has_event_masks=masks,
                                    manager_present=manager,
                                ),
                                manager
                                and (persistent or delayed)
                                and (masks or delayed),
                            )

    def test_original_state_children_have_different_contracts(self):
        common = dict(persistent=True, delayed=False, manager_present=True)
        self.assertEqual(
            retained_delivery_opcode(**common, has_event_masks=False), 12613
        )
        self.assertEqual(
            retained_delivery_opcode(**common, has_event_masks=True), 13497
        )

    def test_delay_subscription_keeps_observation_message(self):
        self.assertEqual(
            retained_delivery_opcode(
                persistent=False,
                delayed=True,
                has_event_masks=False,
                manager_present=True,
            ),
            13497,
        )

    def test_unresolved_manager_or_nonretained_runner_is_not_hidden(self):
        for values in ((True, False, False, False), (False, False, True, True)):
            with self.assertRaises(ValueError):
                retained_delivery_opcode(
                    **dict(
                        zip(
                            (
                                "persistent",
                                "delayed",
                                "has_event_masks",
                                "manager_present",
                            ),
                            values,
                        )
                    )
                )
        with self.assertRaises(ValueError):
            observation_registers(
                persistent=1, delayed=False, has_event_masks=False, manager_present=True
            )
