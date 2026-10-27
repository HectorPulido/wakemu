"""Exact state-application ancestry, separate from native removal ownership.

Qe base UID may be its own UID, and a state PL encodes only state/grade. Neither
recovers the applying state object's identity. Capture that real UID while the
native application scope exists. These plain source facts survive retirement,
checkpointing and private-preview copies; they never alter native owner_uid,
wire fields, removal cascades, clocks or execution order.
"""
from collections.abc import Mapping
from types import MappingProxyType

POLICY = "wakemu.actual-state-source-uid.v1"
_CONTAINER = (
    "container_present",
    "container_type",
    "container_id",
    "container_kind",
    "container_is_spell",
    "spell_protected",
)
_FIELDS = frozenset(
    (
        "uid",
        "parent_state_uid",
        "parent_known",
        "container_known",
        "state_reference",
        "state_level",
        "caster_id",
        "target_id",
        "retained",
        "source",
        *_CONTAINER,
    )
)


def _signed(value):
    return value - (1 << 64) if value >= (1 << 63) else value


def _record(state, parent_uid, container, *, source, parent_known, container_known):
    return dict(
        uid=state.uid,
        parent_state_uid=parent_uid,
        parent_known=parent_known,
        container_known=container_known,
        state_reference=state.reference,
        state_level=state.level,
        caster_id=state.caster_id,
        target_id=state.target_id,
        retained=state.retained,
        source=source,
        **{key: container.get(key) for key in _CONTAINER}
    )


def _validate_record(row):
    if (
        not isinstance(row, Mapping)
        or set(row) != _FIELDS
        or type(row["uid"]) is not int
        or not 0 < row["uid"] < (1 << 63)
        or type(row["state_reference"]) is not int
        or not 0 < row["state_reference"] <= 32767
        or type(row["state_level"]) is not int
        or not -32768 <= row["state_level"] <= 32767
        or any(
            type(row[key]) is not int
            or row[key] == 0
            or not -(1 << 63) <= row[key] < (1 << 63)
            for key in ("caster_id", "target_id")
        )
        or any(
            type(row[key]) is not bool
            for key in ("parent_known", "container_known", "retained")
        )
        or row["source"] not in ("captured_application", "legacy_observed")
    ):
        raise ValueError("Invalid actual state source provenance")
    parent = row["parent_state_uid"]
    if (
        parent is not None
        and (type(parent) is not int or not 0 < parent < (1 << 63))
        or parent == row["uid"]
        or not row["parent_known"]
        and parent is not None
    ):
        raise ValueError("Invalid actual state source parent UID")
    if row["source"] == "captured_application" and parent is None:
        expected_known = not (
            row["container_known"]
            and row["container_present"] is True
            and row["container_type"] == 1
        )
        if row["parent_known"] is not expected_known:
            raise ValueError("Captured state PL has contradictory parent knowledge")
    if not row["container_known"]:
        if row["source"] != "legacy_observed" or any(
            row[key] is not None for key in _CONTAINER
        ):
            raise ValueError("Unknown legacy PL must remain explicitly unknown")
    elif row["container_present"] is False:
        if any(
            row[key] is not None for key in _CONTAINER if key != "container_present"
        ):
            raise ValueError("Null state source PL has invented metadata")
    elif row["container_present"] is True:
        if (
            type(row["container_type"]) is not int
            or type(row["container_id"]) is not int
            or not -(1 << 63) <= row["container_id"] < (1 << 63)
            or row["container_kind"] is not None
            and type(row["container_kind"]) is not str
            or type(row["container_is_spell"]) is not bool
            or row["spell_protected"] is not None
            and type(row["spell_protected"]) is not bool
        ):
            raise ValueError("Invalid captured state source PL")
    else:
        raise ValueError("Missing captured state source PL presence")


def _verify_wire_payload(payload, row):
    from .combat_effect_removal import _identity_fields
    from .combat_state_parameters import pack_state_identity

    if type(payload) is not str:
        raise ValueError("State source provenance lacks its actual carrier wire")
    fields = _identity_fields(
        bytes.fromhex(payload), integer_fields=(1, 2, 3, 4, 6, 7, 9, 10)
    )
    if (
        fields.get(1) != row["uid"]
        or fields.get(4)
        != pack_state_identity(row["state_reference"], row["state_level"])
        or _signed(fields.get(6, 0)) != row["caster_id"]
        or _signed(fields.get(7, 0)) != row["target_id"]
    ):
        raise ValueError("State source provenance differs from actual carrier identity")
    if row["container_known"]:
        if row["container_present"]:
            if (
                fields.get(9) != row["container_type"]
                or _signed(fields.get(10, 0)) != row["container_id"]
            ):
                raise ValueError(
                    "State source provenance differs from actual carrier PL"
                )
        elif 9 in fields or 10 in fields:
            raise ValueError(
                "Null state source provenance contradicts actual carrier PL"
            )


def _verify_wire(fight, state, row):
    from .combat_native_container import resolve_state_wire_payload

    payload = resolve_state_wire_payload(fight, state.uid)
    if not state.retained and payload is None:
        return
    _verify_wire_payload(payload, row)


def capture_state_source(fight, state, invocation, container):
    """Capture only the real applied RunningState and applying invocation."""
    from .combat_state_ledger import RunningState
    from .combat_native_container import resolve_state_container

    if not isinstance(state, RunningState):
        raise ValueError("Actual applied state source required")
    ledger = getattr(fight, "native_state_source_provenance", None)
    if ledger is None:
        ledger = fight.native_state_source_provenance = dict(policy=POLICY, entries={})
    if (
        type(ledger) is not dict
        or set(ledger) != {"policy", "entries"}
        or ledger["policy"] != POLICY
        or type(ledger["entries"]) is not dict
    ):
        raise ValueError("Invalid state source provenance ledger")
    records = ledger["entries"]
    parent_uid = invocation.state_uid
    # An explicitly supplied state PL without its actual fyW UID remains
    # unknown ancestry. It is not a root merely because state_uid is absent.
    parent_known = parent_uid is not None or not (
        container.get("container_present") is True
        and container.get("container_type") == 1
    )
    row = _record(
        state,
        parent_uid,
        container,
        source="captured_application",
        parent_known=parent_known,
        container_known=True,
    )
    _validate_record(row)
    _verify_wire(fight, state, row)
    if parent_uid is not None and str(parent_uid) not in records:
        # Legacy parents have real state/wire authority but may have no source
        # ledger. Preserve their actual PL and explicitly unknown older ancestry.
        parent = resolve_state_container(fight, parent_uid)
        if not isinstance(parent, RunningState) or parent.uid != parent_uid:
            raise ValueError("Missing actual parent state source UID")
        retained = getattr(fight, "native_retained_records", {}).get(parent_uid)
        known = isinstance(retained, Mapping) and (
            retained.get("container_present") is False
            or retained.get("container_present") is True
            and type(retained.get("container_is_spell")) is bool
        )
        anchor = _record(
            parent,
            None,
            retained if known else {},
            source="legacy_observed",
            parent_known=False,
            container_known=known,
        )
        _validate_record(anchor)
        _verify_wire(fight, parent, anchor)
        records[str(parent_uid)] = anchor
    previous = records.get(str(state.uid))
    if previous is not None and previous != row:
        raise ValueError("State source UID provenance changed after capture")
    records[str(state.uid)] = row


def state_source_provenance(fight):
    """Return verified immutable source facts, including retired ancestors.

    A legacy fight with no ledger yields no invented facts. Consumers decide
    conservatively whether existing direct PL authority is sufficient; unknown
    state-PL ancestry must not become an NPC-source admission shortcut.
    """
    ledger = getattr(fight, "native_state_source_provenance", None)
    if ledger is None:
        return MappingProxyType({})
    if (
        type(ledger) is not dict
        or set(ledger) != {"policy", "entries"}
        or ledger["policy"] != POLICY
        or type(ledger["entries"]) is not dict
    ):
        raise ValueError("Invalid state source provenance ledger")
    result = {}
    for key, row in ledger["entries"].items():
        _validate_record(row)
        if type(key) is not str or key != str(row["uid"]):
            raise ValueError("State source UID key differs from captured identity")
        payload = getattr(fight, "state_wire_payloads", {}).get(row["uid"])
        if payload is not None:
            _verify_wire_payload(payload, row)
        result[row["uid"]] = dict(row)
    from .combat_state_parameters import pack_state_identity

    for row in result.values():
        parent_uid = row["parent_state_uid"]
        if parent_uid is None:
            continue
        parent = result.get(parent_uid)
        if parent is None:
            raise ValueError("Unknown state source parent UID")
        if (
            not row["container_known"]
            or row["container_present"] is not True
            or row["container_type"] != 1
            or row["container_id"]
            != pack_state_identity(parent["state_reference"], parent["state_level"])
        ):
            raise ValueError("State source parent UID contradicts its actual native PL")
    complete = set()
    for uid in result:
        visiting, current = set(), uid
        while current not in complete:
            if current not in result:
                raise ValueError("Unknown state source parent UID")
            if current in visiting:
                raise ValueError("Cyclic state source UID ancestry")
            visiting.add(current)
            parent = result[current]["parent_state_uid"]
            if parent is None:
                break
            current = parent
        complete.update(visiting)
    return MappingProxyType({uid: MappingProxyType(row) for uid, row in result.items()})
