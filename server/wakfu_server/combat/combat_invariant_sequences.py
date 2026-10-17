"""Inspect existing runtime delivery/ACK facts without draining any queue."""


def check_runtime_sequences(runtime, ack, issue, unknown, checked):
    from .combat_ack_barrier import AckBarrier

    if runtime is None:
        return
    facts = vars(runtime)
    pending, turn = facts.get("pending"), facts.get("awaiting_ack")
    if turn is not None and (
        type(turn) is not int or not -(1 << 31) <= turn < (1 << 31)
    ):
        issue(
            "sequence.turn_ack",
            "runtime.awaiting_ack",
            "Pending turn ACK is not signed32",
        )
    if type(pending) is not list:
        issue(
            "sequence.pending",
            "runtime.pending",
            "Pending presentation is not an owned packet list",
        )
    elif len(pending) > 16384:
        unknown(
            "coverage.limit",
            "runtime.pending",
            "Pending packet inspection limit reached",
        )
    else:
        if pending and turn is None:
            issue(
                "sequence.pending",
                "runtime.pending",
                "Successor packets have no preceding ACK barrier",
            )
        size = 0
        for row in pending:
            if (
                type(row) not in (tuple, list)
                or len(row) != 2
                or type(row[0]) is not int
                or type(row[1]) is not bytes
            ):
                issue("sequence.pending", "runtime.pending", "Malformed pending packet")
                break
            size += len(row[1])
            if size > 32 * 1024 * 1024:
                unknown(
                    "coverage.limit",
                    "runtime.pending",
                    "Pending packet byte inspection limit reached",
                )
                break
        # These packets have not reached native ID allocation yet. Repeated
        # logical request IDs here are legitimate and must not be rejected.
        checked.append("sequence.pending")
    counter = facts.get("native_action_id")
    if type(counter) is not int or not 0 <= counter < (1 << 31):
        issue(
            "sequence.native_counter",
            "runtime.native_action_id",
            "Native allocator is outside signed32 range",
        )
    else:
        actions = facts.get("last_native_delivery")
        if type(actions) is not tuple:
            issue(
                "sequence.native_delivery",
                "runtime.last_native_delivery",
                "Native correlation ledger is not owned",
            )
        elif len(actions) > 16384:
            unknown(
                "coverage.limit",
                "runtime.last_native_delivery",
                "Correlation ledger inspection limit reached",
            )
        else:
            previous = 0
            for row in actions:
                uid = row.get("native_action_id") if type(row) is dict else None
                if type(uid) is not int or not previous < uid <= counter:
                    issue(
                        "sequence.native_delivery",
                        "runtime.last_native_delivery",
                        "Native action identities are duplicate, unordered or outside their allocator",
                    )
                    break
                previous = uid
            checked.append("sequence.native_delivery")
    checked.extend(("sequence.turn_ack", "sequence.native_counter"))
    if ack is None:
        unknown(
            "sequence.shared_ack",
            "shared.ack",
            "No staged shared barrier supplied at this boundary",
        )
        return
    if type(ack) is not AckBarrier:
        issue("sequence.shared_ack", "shared.ack", "Unsupported shared barrier owner")
        return
    barrier = vars(ack)
    expected, received, barrier_turn = (
        barrier.get(name) for name in ("expected", "received", "turn")
    )
    if type(expected) is not dict or type(received) is not set:
        issue(
            "sequence.shared_ack",
            "shared.ack",
            "Missing exact participant generation/receipt populations",
        )
        return
    if len(expected) > 4096 or len(received) > 4096:
        unknown(
            "coverage.limit", "shared.ack", "ACK population inspection limit reached"
        )
        return
    if any(
        type(account) is not int or account <= 0 or type(generation) is not str
        for account, generation in dict.items(expected)
    ) or any(
        type(account) is not int or account not in expected for account in received
    ):
        issue(
            "sequence.shared_ack",
            "shared.ack",
            "Receipt or generation has no expected participant",
        )
    if barrier_turn != turn:
        issue(
            "sequence.shared_ack",
            "shared.ack.turn",
            "Staged shared turn differs from runtime pending ACK",
        )
    if barrier_turn is None:
        if expected or received:
            issue(
                "sequence.shared_ack",
                "shared.ack",
                "Cleared barrier retains participant receipts",
            )
    elif (
        type(barrier_turn) is not int
        or not 0 <= barrier_turn < (1 << 31)
        or not expected
    ):
        issue(
            "sequence.shared_ack",
            "shared.ack",
            "Armed barrier lacks valid turn or participants",
        )
    checked.append("sequence.shared_ack")
