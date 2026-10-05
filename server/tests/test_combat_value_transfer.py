from wakfu_server.combat_value_transfer import transferred_value, capture_child_value
from wakfu_server.combat_value_transfer import (
    ValueTransferSpecification,
    execute_value_transfer,
)
from wakfu_server.combat_value_transfer import value_transfer_specification


def test_native_group_parameter_defaults_and_nonzero_target_selector():
    assert value_transfer_specification([]) == ValueTransferSpecification()
    assert value_transfer_specification([50]) == ValueTransferSpecification(percent=50)
    assert value_transfer_specification(
        [50, -10, -7, 9, 999]
    ) == ValueTransferSpecification(50, -10, True, 9)


def test_signed_fraction_uses_native_stochastic_probability():
    seen = []

    def draw(p):
        seen.append(p)
        return True

    assert transferred_value(-3, 50, -100, 0, probability=draw) == -1
    assert seen == [0.5]
    assert transferred_value(-3, 50, -100, 9, probability=lambda p: False) == -2


def test_overflow_precedes_float_and_minimum():
    assert transferred_value(2147483647, 100, -100, -1, probability=None) == -1
    assert transferred_value(3, 50, 0, -1, probability=None) == 1
    assert transferred_value(3, 50, 0, 1, probability=None) == 2
    assert transferred_value(-3, 50, 5, 1, probability=None) == 5


def test_zero_callback_does_not_replace_existing_value():
    assert capture_child_value(7, 0) == 7
    assert capture_child_value(7, -3) == -3


def test_group_uses_callback_value_independently_of_child_success():
    calls = []

    def first(capture):
        capture(-3)
        return False

    def second(value, original):
        calls.append((value, original))
        return True

    assert execute_value_transfer(
        ValueTransferSpecification(50, -100, True, -1),
        execute_first=first,
        execute_second=second,
        probability=None,
        skip_second=False,
    )
    assert calls == [(-2, True)]


def test_success_without_nonzero_runner_value_does_not_execute_second():
    def second(*args):
        raise AssertionError("zero runner must omit second child")

    assert not execute_value_transfer(
        ValueTransferSpecification(),
        execute_first=lambda capture: True,
        execute_second=second,
        probability=None,
        skip_second=False,
    )


def test_native_exception_still_executes_first_but_omits_second():
    calls = []

    def first(capture):
        calls.append("first")
        capture(5)

    assert not execute_value_transfer(
        ValueTransferSpecification(),
        execute_first=first,
        execute_second=lambda *args: calls.append("second"),
        probability=None,
        skip_second=True,
    )
    assert calls == ["first"]


def test_transfer_observer_cannot_capture_later_unrelated_runner():
    import pytest

    observers = []
    execute_value_transfer(
        ValueTransferSpecification(),
        execute_first=lambda capture: observers.append(capture),
        execute_second=lambda *args: True,
        probability=None,
        skip_second=False,
    )
    with pytest.raises(ValueError, match="escaped"):
        observers[0](7)


def test_sq_value_preserves_sp_level_and_no_duplicate_fields():
    from wakfu_server.combat_value_transfer import transfer_value_context
    from wakfu_server.combat_effects import _integer
    from wakfu_server.wire import proto_fields

    original = b"".join(
        _integer(k, v)
        for k, v in ((1, 0), (2, 0), (4, 20), (5, 1), (6, 0), (7, 0), (8, 0), (9, 0))
    )
    result = dict(proto_fields(transfer_value_context(original, 17)))
    assert result == {8: 0, 16: 0, 32: 20, 40: 0, 48: 17, 56: 0, 64: 0, 72: 1}


def test_forced_value_is_applied_after_calculation():
    from wakfu_server.combat_value_transfer import (
        apply_context_value,
        transfer_value_context,
    )
    from wakfu_server.combat_effects import _integer

    assert apply_context_value(99, None) == 99
    assert apply_context_value(99, transfer_value_context(b"", -3)) == -3
    assert apply_context_value(3, _integer(6, 50) + _integer(9, 2)) == 1
    assert apply_context_value(-3, _integer(6, 50) + _integer(9, 2)) == 1
