"""Native version5 state section and absolute achievement notifications."""

import struct
import zlib
from .storage import _state


def section(state, *, activation_dates=None, preview_active=(), preview_completed=()):
    _state(state)
    activation_dates = {} if activation_dates is None else activation_dates
    if not isinstance(activation_dates, dict) or any(
        type(key) is not int
        or key <= 0
        or type(value) is not int
        or not 0 <= value < 2**63
        for key, value in activation_dates.items()
    ):
        raise ValueError("Invalid native achievement activation dates")
    preview_active, preview_completed = set(preview_active), set(preview_completed)
    if not preview_active <= set(state["completed"]) or any(
        type(i) is not int or not 0 < i < 2**31 for i in preview_completed
    ):
        raise ValueError("Invalid mission journal preview")
    from .lifecycle import active_ids

    active = set(active_ids(state))
    recent = state["recent"][-255:]
    body = struct.pack(">iB", 5, len(recent))
    body += b"".join(struct.pack(">iq", row["id"], row["date_ms"]) for row in recent)
    variables = sorted((int(key), value) for key, value in state["variables"].items())
    body += struct.pack(">i", len(variables))
    body += b"".join(struct.pack(">iq", key, value) for key, value in variables)
    identities = sorted(active | set(state["completed"]) | preview_completed)
    body += struct.pack(">i", len(identities))
    for identity in identities:
        # Original bdD.cCN sets ddP at activation; loader date2 calls hl.
        # Date1 is a distinct cooldown clock and remains absent here.
        activated_at = activation_dates.get(identity)
        body += struct.pack(
            ">iBBBB",
            identity,
            identity in active or identity in preview_active,
            identity in state["completed"] or identity in preview_completed,
            0,
            activated_at is not None,
        )
        if activated_at is not None:
            body += struct.pack(">q", activated_at)
        body += b"\x00"  # Opaque native flagV5.
    body += struct.pack(">i", len(state["objectives"]))
    body += b"".join(struct.pack(">i", identity) for identity in state["objectives"])
    body += struct.pack(">B", len(state["tracking"]))
    body += b"".join(struct.pack(">i", identity) for identity in state["tracking"])
    compressed = False
    if len(body) > 65535:
        body, compressed = zlib.compress(body), True
    if len(body) > 65535:
        raise ValueError("Achievement state exceeds native section capacity")
    return struct.pack(">H", len(body)) + body + bytes([compressed])


def _safe_initial_reset(identity, before, definition):
    """Only reset when native objective/counter progress is known to be empty."""
    if definition is None:
        return False
    if definition.get("d") != identity or not isinstance(definition.get("cjJ"), list):
        return False
    objective_ids, variable_ids = set(), set()
    for objective in definition["cjJ"]:
        if type(objective.get("d")) is not int or not isinstance(
            objective.get("ckf"), list
        ):
            return False
        objective_ids.add(objective["d"])
        for variable in objective["ckf"]:
            sources = variable.get("ckn") if isinstance(variable, dict) else None
            if not isinstance(sources, list) or any(
                type(source) is not int for source in sources
            ):
                return False
            variable_ids.update(sources)
    return not (objective_ids & set(before.get("objectives", ()))) and not any(
        before.get("variables", {}).get(str(variable), 0) for variable in variable_ids
    )


def changes(
    character_id,
    before,
    after,
    new_objectives,
    new_completed,
    now_ms,
    *,
    definitions=None,
    already_reset=()
):
    packets = []
    newly_active = sorted(
        set(after["running"]) - set(before["running"]) - set(before["completed"])
    )
    newly_tracked = set(after["tracking"]) - set(before["tracking"])
    recent_ids = {row["id"] for row in before.get("recent", ())}
    definitions = {} if definitions is None else dict(definitions)
    already_reset = set(already_reset)
    # Official journal batches are ordered per producer mission: counter facts
    # of an already active mission, then its objective and completion marks,
    # then a newly activated mission together with the zero initialisation of
    # its own counters (2026-11-12 capture: ctv 10615/10607, three ctA zeros,
    # then ctx/ctq/ctu 5145; and ctA=3 immediately before ctv 10597).
    activation_variables = set()
    for identity in sorted(
        set(after["running"]) - set(before["running"]) - set(before["completed"])
    ):
        for objective in (definitions.get(identity) or {}).get("cjJ", ()) or ():
            for condition in objective.get("ckf") or ():
                activation_variables.update(
                    str(value)
                    for value in (condition.get("ckn") or [])
                    if type(value) is int
                )
    activation_variables = {}
    for identity in newly_active:
        for objective in (definitions.get(identity) or {}).get("cjJ") or ():
            for condition in objective.get("ckf") or ():
                for source in condition.get("ckn") or ():
                    if type(source) is int:
                        activation_variables.setdefault(str(source), identity)
    changed_variables = set()
    counters = []
    for key, value in sorted(after["variables"].items(), key=lambda row: int(row[0])):
        if before["variables"].get(key) == value:
            continue
        changed_variables.add(int(key))
        if key not in activation_variables:
            counters.append((13295, struct.pack(">qiq", character_id, int(key), value)))
    packets.extend(counters)
    packets.extend(
        (13832, struct.pack(">qi", character_id, identity))
        for identity in new_objectives
    )
    packets.extend(
        (13422, struct.pack(">qiq", character_id, identity, now_ms))
        for identity in new_completed
    )
    for identity in sorted(set(before["tracking"]) - set(after["tracking"])):
        packets.append((13371, struct.pack(">qiB", character_id, identity, 0)))
    for identity in newly_active:
        for key, owner in sorted(
            activation_variables.items(), key=lambda row: int(row[0])
        ):
            if owner != identity or before["variables"].get(key) == after[
                "variables"
            ].get(key):
                continue
            packets.append(
                (
                    13295,
                    struct.pack(
                        ">qiq", character_id, int(key), after["variables"][key]
                    ),
                )
            )
        if (
            identity not in recent_ids
            and identity not in already_reset
            and _safe_initial_reset(identity, before, definitions.get(identity))
        ):
            packets.append((13205, struct.pack(">qi", character_id, identity)))
        # Native cto/cEC13312 activates bdD.NO. ctv/cEJ13205 instead resets
        # that flag and completed objectives; it cannot announce a mission alone.
        packets.append((13312, struct.pack(">qi", character_id, identity)))
        if identity in newly_tracked:
            packets.append((13371, struct.pack(">qiB", character_id, identity, 1)))
    for identity in sorted(newly_tracked - set(newly_active)):
        packets.append((13371, struct.pack(">qiB", character_id, identity, 1)))
    # The native client can retain a stale tracker row after processing an
    # objective even though its underlying mission state is correct. Rebinding
    # the affected, already-followed mission refreshes its HUD row. Restrict
    # this to authoritative definitions and the client's four-pin capacity;
    # unrelated, completed, newly pinned and untracked missions are untouched.
    stable_tracking = set(before["tracking"]) & set(after["tracking"])
    if (
        (new_objectives or changed_variables)
        and len(before["tracking"]) <= 4
        and len(after["tracking"]) <= 4
    ):
        for identity in sorted(stable_tracking & set(after["running"])):
            definition = definitions.get(identity)
            if not isinstance(definition, dict) or definition.get("d") != identity:
                continue
            objectives = definition.get("cjJ")
            if not isinstance(objectives, list):
                continue
            objective_ids = {
                row.get("d") for row in objectives if isinstance(row, dict)
            }
            variable_ids = {
                source
                for row in objectives
                if isinstance(row, dict)
                for variable in (row.get("ckf") or [])
                if isinstance(variable, dict)
                for source in (variable.get("ckn") or [])
                if type(source) is int
            }
            if not (
                objective_ids.intersection(new_objectives)
                or variable_ids.intersection(changed_variables)
            ):
                continue
            packets.extend(
                (
                    (13371, struct.pack(">qiB", character_id, identity, 0)),
                    (13371, struct.pack(">qiB", character_id, identity, 1)),
                )
            )
    return packets
