"""Private TC/Tu queue primitive; execution authority is required at delivery."""
from copy import deepcopy

SOURCE = "native.eZR.bbS.SU.TC.Tu.v1"


def short(value):
    return ((value + 32768) % 65536) - 32768


def fresh_queue():
    return dict(source=SOURCE, next_sequence=1, entries=[])


def validate(queue):
    if (
        not isinstance(queue, dict)
        or set(queue) != {"source", "next_sequence", "entries"}
        or queue["source"] != SOURCE
        or type(queue["next_sequence"]) is not int
        or queue["next_sequence"] < 1
        or not isinstance(queue["entries"], list)
    ):
        raise ValueError("Missing verified native delay queue")
    sequences = []
    for row in queue["entries"]:
        if (
            not isinstance(row, dict)
            or set(row)
            != {"sequence", "uid", "clock_id", "round", "phase", "invocation"}
            or any(
                type(row[k]) is not int
                for k in ("sequence", "uid", "clock_id", "round")
            )
            or row["uid"] <= 0
            or row["sequence"] <= 0
            or row["phase"] not in ("start", "end")
            or not isinstance(row["invocation"], dict)
        ):
            raise ValueError("Malformed actual Tu registration")
        sequences.append(row["sequence"])
    if (
        sequences != sorted(set(sequences))
        or sequences
        and sequences[-1] >= queue["next_sequence"]
    ):
        raise ValueError("Invalid native insertion order")


def enqueue(
    queue,
    *,
    uid,
    clock_id,
    delay,
    expire_at_end,
    current_round,
    on_clock_turn,
    clock_not_reached,
    invocation
):
    validate(queue)
    if (
        any(type(v) is not int for v in (uid, clock_id, delay, current_round))
        or uid <= 0
        or clock_id == 0
        or delay <= 0
        or any(
            type(v) is not bool
            for v in (expire_at_end, on_clock_turn, clock_not_reached)
        )
        or not isinstance(invocation, dict)
    ):
        raise ValueError("Missing actual native delayed runner authority")
    if any(row["uid"] == uid for row in queue["entries"]):
        raise ValueError("Duplicate actual Tu runner UID")
    baseline = short(
        max(current_round, 1) + int(not clock_not_reached and not on_clock_turn)
    )
    expiration = short(baseline + short(delay) - int(expire_at_end))
    expiration = short(max(baseline, expiration))
    row = dict(
        sequence=queue["next_sequence"],
        uid=uid,
        clock_id=clock_id,
        round=expiration,
        phase="end" if expire_at_end else "start",
        invocation=deepcopy(invocation),
    )
    queue["next_sequence"] += 1
    queue["entries"].append(row)
    return deepcopy(row)


def deliver(queue, *, clock_id, round_number, phase, execute, round_cleanup=False):
    validate(queue)
    if (
        type(clock_id) is not int
        or type(round_number) is not int
        or phase not in ("start", "end")
        or type(round_cleanup) is not bool
        or not callable(execute)
    ):
        raise ValueError("Missing actual native phase producer")
    # TC.a(short,SU) cleanup flushes prior-round leftovers, including dead clocks.
    candidates = [
        row
        for row in queue["entries"]
        if (
            row["round"] == short(round_number - 1)
            if round_cleanup
            else row["round"] == round_number
            and row["phase"] == phase
            and row["clock_id"] == clock_id
        )
    ]
    if round_cleanup:
        candidates.sort(key=lambda row: (row["phase"] == "end", row["sequence"]))
    outcomes = []
    for row in candidates:
        if row not in queue["entries"]:
            continue  # Native TC checks live-list membership after nested callbacks.
        queue["entries"].remove(row)  # fbX clears the handle before Qe.bbJ.
        outcomes.append(execute(deepcopy(row)))
    return tuple(outcomes)


def cancel(queue, uid):
    validate(queue)
    if type(uid) is not int or uid <= 0:
        raise ValueError("Invalid Tu cancellation UID")
    queue["entries"][:] = [row for row in queue["entries"] if row["uid"] != uid]
