"""Native eWj/eWk1070: ordered, reversible characteristic subscriptions.

The listener stores only plain state, so transaction cloning/checkpoints keep
ownership and accumulated actual contributions without retaining actor objects.
"""
from .combat_casting_range import int32
from .combat_parameters import parameter_value

SOURCE = "eWj.eWa.eWk.PA.aZk"


def transfer_parameters(parameters, level):
    if len(parameters) not in (4, 6, 8, 10, 12):
        raise ValueError("Unsupported native eWj parameter count")
    values = [
        parameter_value(parameters, index, level)
        for index in range(len(parameters) // 2)
    ]
    source, destination = [((value + 128) % 256) - 128 for value in values[:2]]
    divisor = values[3] if len(values) > 3 else 1
    if divisor == 0:
        raise ValueError("Native eWj division by zero")
    return dict(
        source_stat=source,
        destination_stat=destination,
        caster_to_target=len(values) > 2 and values[2] == 1,
        divisor=divisor,
        maximum=values[4] if len(values) > 4 else -(1 << 31),
        # Fresh eWj.C writes rAF twice; rAG stays JVM-default zero.
        minimum=values[5] if len(values) > 5 else 0,
    )


def transfer_amount(current, *, divisor, maximum, minimum):
    if (
        any(
            type(value) is not int or not -(1 << 31) <= value < (1 << 31)
            for value in (current, divisor, maximum, minimum)
        )
        or divisor == 0
    ):
        raise ValueError("Missing native eWk int operands")
    value = int32(
        (abs(current) // abs(divisor)) * (-1 if (current < 0) != (divisor < 0) else 1)
    )
    if maximum > 0:
        value = min(maximum, value)
    if minimum > -(1 << 31):
        value = max(minimum, value)
    return value


def update_transfer(row, *, current, shift):
    """eWk.a: remove previous actual, read source NOW, clamp, add actual."""
    shift(row["actual"], True)
    value = transfer_amount(
        current(),
        divisor=row["divisor"],
        maximum=row["maximum"],
        minimum=row["minimum"],
    )
    row["actual"] = shift(value, False)


def transfer_additional_payload(specification):
    from .combat_effects import _integer, _varint

    additional = b"".join(
        _integer(field, value)
        for field, value in (
            (10, specification["maximum"]),
            (12, specification["destination_stat"]),
            (17, int(specification["caster_to_target"])),
            (19, specification["divisor"]),
            (20, specification["minimum"]),
        )
    )
    return _varint(8 << 3 | 2) + _varint(len(additional)) + additional


def _rows(fight):
    rows = getattr(fight, "native_characteristic_transfers", [])
    if not isinstance(rows, list) or any(
        not isinstance(row, dict) or row.get("source") != SOURCE for row in rows
    ):
        raise ValueError("Missing actual native eWk listener authority")
    return rows


def transfer_operations(fight, actor, source_id, stat):
    """Use existing exact reversible nonexpandable PA setters, never assignment."""
    from .combat_stat_handler import _current, _bounds, _write
    from .combat_character_copy_metadata import native_copy_characteristics

    definition = native_copy_characteristics()["fresh_characteristics"].get(str(stat))
    if not isinstance(definition, dict):
        raise ValueError("Unknown native eWj characteristic")
    if (
        definition.get("expandable") is not False
        or definition.get("over_max_current") is not False
        or stat in (1, 2, 3, 4, 14, 20, 111)
    ):
        raise ValueError("Native eWj destination requires nonexpandable PA authority")
    minimum, maximum = _bounds(actor, stat)
    if not minimum <= _current(actor, stat) <= maximum:
        raise ValueError("Invalid native eWj destination PA snapshot")
    if stat in actor.effect_frozen:
        return lambda: _current(actor, stat), lambda amount, subtract: 0

    def shift(amount, subtract):
        if getattr(actor, "native_copy_pa_source", None) is not None:
            from .combat_copied_pa import shift_copied_current

            return shift_copied_current(fight, actor, stat, amount, subtract=subtract)
        before = _current(actor, stat)
        minimum, maximum = _bounds(actor, stat)
        # fff.nG/oo compare a Java-long distance BEFORE wrapping int arithmetic.
        requested = (
            (minimum if amount > before - minimum else int32(before - amount))
            if subtract
            else (maximum if amount > maximum - before else int32(before + amount))
        )
        after = max(minimum, min(maximum, requested))
        _write(fight, source_id, actor, stat, after)
        return int32(before - after if subtract else after - before)

    return lambda: _current(actor, stat), shift


def attach_transfer(fight, *, uid, source_id, destination_id, caster_id, specification):
    from .combat_stat_handler import _current, _bounds

    rows = _rows(fight)
    if any(row["uid"] == uid for row in rows):
        raise ValueError("Duplicate native eWk UID")
    source = fight.actors[source_id]
    destination = fight.actors[destination_id]
    _bounds(source, specification["source_stat"])
    from .combat_character_copy_metadata import native_copy_characteristics

    source_definition = native_copy_characteristics()["fresh_characteristics"].get(
        str(specification["source_stat"])
    )
    if (
        not isinstance(source_definition, dict)
        or source_definition.get("expandable") is not False
        or specification["source_stat"] in (1, 2, 3, 4, 14, 20, 111)
    ):
        raise ValueError(
            "Native eWj source requires complete nonresource PA setter authority"
        )
    if specification["source_stat"] in source.effect_frozen:
        raise ValueError("Observed frozen source requires hidden raw-current authority")
    if getattr(fight, "native_characteristic_links", {}):
        raise ValueError("Mixed eWh/eWj native listener order unsupported")
    _, shift = transfer_operations(
        fight, destination, caster_id, specification["destination_stat"]
    )
    origin = (source_id, specification["source_stat"])
    target = (destination_id, specification["destination_stat"])
    edges = {}
    for row in rows:
        edges.setdefault((row["source_id"], row["source_stat"]), []).append(
            (row["destination_id"], row["destination_stat"])
        )
    pending = [target]
    seen = set()
    while pending:
        item = pending.pop()
        if item == origin:
            raise ValueError("Native eWk recursive characteristic cycle unsupported")
        if item not in seen:
            seen.add(item)
            pending.extend(edges.get(item, ()))
    row = dict(
        specification,
        source=SOURCE,
        uid=uid,
        source_id=source_id,
        destination_id=destination_id,
        caster_id=caster_id,
        actual=0,
    )
    if not hasattr(fight, "native_characteristic_transfers"):
        fight.native_characteristic_transfers = []
    fight.native_characteristic_transfers.append(row)
    update_transfer(
        row, current=lambda: _current(source, row["source_stat"]), shift=shift
    )
    return row


def notify_characteristic_transfers(
    fight, actor, stat, *, before_current=None, maximum=False
):
    from .combat_stat_handler import _current

    matches = [
        row
        for row in _rows(fight)
        if row["source_id"] == actor.id and row["source_stat"] == stat
    ]
    if not matches:
        return
    if not maximum:
        if type(before_current) is not int:
            raise ValueError("Missing native eWk setter preimage")
        if before_current == _current(actor, stat):
            return
    for row in tuple(matches):
        destination = fight.actors[row["destination_id"]]
        _, shift = transfer_operations(
            fight, destination, row["caster_id"], row["destination_stat"]
        )
        update_transfer(row, current=lambda: _current(actor, stat), shift=shift)


def detach_transfer(fight, uid):
    rows = _rows(fight)
    matches = [row for row in rows if row["uid"] == uid]
    if len(matches) != 1:
        raise ValueError("Missing native eWk listener for removal")
    row = matches[0]
    destination = fight.actors[row["destination_id"]]
    _, shift = transfer_operations(
        fight, destination, row["caster_id"], row["destination_stat"]
    )
    # Native eWa.bbR orders cancel() before bLM() observer detachment.
    shift(row["actual"], True)
    rows.remove(row)
    return row


def observed_fixed_assignment(
    fight, actor, stat, *, source_id, requested, raw_maximum, maximum, maximum_step
):
    """eWZ/eYO ordinary PA.or THEN PA.on, with one notification per setter.

    Existing callers retain their previous path when no1070 source observes
    this PA. Resource and copied-raw setters already own their own notifications.
    """
    if not any(
        row["source_id"] == actor.id and row["source_stat"] == stat
        for row in _rows(fight)
    ):
        return False
    from .combat_stat_handler import _current, _write
    from .combat_parameter_maximum import _write as maximum_write

    if stat in actor.effect_frozen:
        raise ValueError(
            "Observed frozen ordinary PA requires hidden raw-current authority"
        )
    if maximum_step:
        before = _current(actor, stat)
        intermediate = max(actor.effect_minima[stat], min(maximum, before))
        maximum_write(actor, stat, intermediate, raw_maximum, maximum)
        notify_characteristic_transfers(
            fight, actor, stat, before_current=before, maximum=True
        )
    after = max(actor.effect_minima[stat], min(actor.effect_maxima[stat], requested))
    _write(fight, source_id, actor, stat, after)
    return True
