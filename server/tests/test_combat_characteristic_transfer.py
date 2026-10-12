import copy
import unittest
from wakfu_server.combat_characteristic_transfer import (
    transfer_amount,
    transfer_parameters,
    transfer_additional_payload,
    update_transfer,
)


class NativeCharacteristicTransferPrimitiveTests(unittest.TestCase):
    def test_java_signed_division_and_ordered_caps(self):
        for source, divisor, expected in (
            (7, 3, 2),
            (-7, 3, -2),
            (7, -3, -2),
            (-7, -3, 2),
        ):
            self.assertEqual(
                transfer_amount(source, divisor=divisor, maximum=5, minimum=-4),
                expected,
            )
        self.assertEqual(transfer_amount(100, divisor=1, maximum=5, minimum=8), 8)
        self.assertEqual(
            transfer_amount(-(1 << 31), divisor=-1, maximum=0, minimum=-(1 << 31)),
            -(1 << 31),
        )

    def test_owned_tyra_nis_native_parameters_and_default_field(self):
        spec = transfer_parameters([35, 0, 8, 0, 1, 0, 1, 0, 100, 200], 95)
        self.assertEqual(
            spec,
            dict(
                source_stat=35,
                destination_stat=8,
                caster_to_target=True,
                divisor=1,
                maximum=19100,
                minimum=0,
            ),
        )
        self.assertEqual(transfer_parameters([35, 0, 52, 0], 1)["minimum"], 0)
        with self.assertRaises(ValueError):
            transfer_parameters([35, 0, 8, 0, 1, 0, 0, 0], 1)

    def fixture(
        self, current=7, divisor=3, destination=20, minimum=-1000, maximum=1000
    ):
        state = dict(source=current, destination=destination, events=[])
        row = dict(actual=0, divisor=divisor, minimum=-4, maximum=5)

        def shift(amount, subtract):
            state["events"].append(("subtract" if subtract else "add", amount))
            before = state["destination"]
            state["destination"] = max(
                minimum, min(maximum, before - amount if subtract else before + amount)
            )
            return (
                before - state["destination"]
                if subtract
                else state["destination"] - before
            )

        return state, row, shift

    def test_native_oracle_repeated_update_and_cancel_contribution(self):
        # Installed Java eWk/fff oracle: input7 divisor3 gives22, update11 gives23,
        # cancel restores20. Previous contribution is removed before source read.
        state, row, shift = self.fixture()
        update_transfer(row, current=lambda: state["source"], shift=shift)
        self.assertEqual((state["destination"], row["actual"]), (22, 2))
        state["source"] = 11
        update_transfer(row, current=lambda: state["source"], shift=shift)
        self.assertEqual((state["destination"], row["actual"]), (23, 3))
        shift(row["actual"], True)
        self.assertEqual(state["destination"], 20)
        self.assertEqual(
            state["events"],
            [("subtract", 0), ("add", 2), ("subtract", 2), ("add", 3), ("subtract", 3)],
        )

    def test_destination_clamping_tracks_actual_not_requested(self):
        state, row, shift = self.fixture(current=100, divisor=1, destination=999)
        update_transfer(row, current=lambda: state["source"], shift=shift)
        self.assertEqual((state["destination"], row["actual"]), (1000, 1))
        shift(row["actual"], True)
        self.assertEqual(state["destination"], 999)

    def test_source_is_read_after_remove_not_captured_before(self):
        state, row, shift = self.fixture()
        row["actual"] = 2

        def mutate_then_shift(amount, subtract):
            actual = shift(amount, subtract)
            if subtract:
                state["source"] = 12
            return actual

        update_transfer(row, current=lambda: state["source"], shift=mutate_then_shift)
        self.assertEqual(row["actual"], 4)

    def test_plain_listener_preview_rollback_does_not_mutate_original(self):
        original = dict(actual=2, divisor=3, minimum=-4, maximum=5)
        preview = copy.deepcopy(original)

        def failing_shift(amount, subtract):
            if not subtract:
                raise RuntimeError("injected setter failure")
            return amount

        with self.assertRaises(RuntimeError):
            update_transfer(preview, current=lambda: 11, shift=failing_shift)
        self.assertEqual(original, dict(actual=2, divisor=3, minimum=-4, maximum=5))

    def test_wire_additional_matches_installed_java(self):
        spec = dict(
            maximum=5, destination_stat=0, caster_to_target=False, divisor=3, minimum=-4
        )
        self.assertEqual(
            transfer_additional_payload(spec).hex(),
            "421650056000880100980103a001fcffffffffffffffff01",
        )

    def test_native_division_by_zero_rejected(self):
        with self.assertRaises(ValueError):
            transfer_amount(8, divisor=0, maximum=0, minimum=0)
