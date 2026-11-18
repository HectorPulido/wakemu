"""Natural2143 guard acknowledgements on the caller's existing local TLS peer.

No connection, quest/item setup or administrative command is created here. The
actual offered native nation root chooses its accredited supply acknowledgement;
these native type-seven choices require no supply-item payment.
"""
import struct
import time


# (native reference, actor UID, action, real approach, objective, offered roots)
GUARDS = (
    (1322, -2251799934991322, 102, (80, -1, 2), 4242, {2154: 6853, 2155: 6852}),
    (1324, -2251799934991324, 100, (88, -6, 2), 4243, {2156: 6858, 2157: 6857}),
    (1437, -2251799934991437, 117, (80, 18, 2), 4244, {2158: 6863, 2159: 6862}),
    (1592, -2251799934991592, 129, (73, 33, 2), 4245, {2160: 6866, 2161: 6864}),
)


def _await_progress(probe, predicate, *, timeout=15):
    deadline = time.monotonic() + timeout
    state = probe.progress()
    while not predicate(state):
        if time.monotonic() >= deadline:
            raise AssertionError(("Native2143 acknowledgement did not persist", state))
        time.sleep(0.05)
        state = probe.progress()
    return state


def run_guard_acknowledgements(probe):
    """Walk, open the actually offered branch and accept each missing guard."""
    state = probe.progress()
    if 2143 in state["completed"]:
        return state
    if 2143 not in state["running"]:
        raise ValueError("Naturally accept2143 from board24162 before visiting guards")
    here = probe.current()
    if here["map_id"] != 527 or here.get("instance_id", 0) != 0:
        raise ValueError("Guard acknowledgements require the original public Astrub527")
    journey = probe.receipt.setdefault("journey", [])
    trace = probe.receipt.setdefault("trace", [])
    character_id = probe.character["id"]
    for reference, actor, action, approach, objective, choices in GUARDS:
        state = probe.progress()
        if objective in state["objectives"]:
            continue  # Resume preserves all genuinely earned guard receipts.
        probe.walk(approach)
        start = probe.peer.mark()
        probe.peer.send(13222, struct.pack(">qq", actor, action))
        opened = probe.peer.matching(12969, start, timeout=20)
        if len(opened) != 13:
            raise AssertionError(
                ("Malformed native guard dialogue", reference, len(opened))
            )
        node, _speaker_type, speaker = struct.unpack(">ibq", opened)
        if speaker != actor or node not in choices:
            raise AssertionError(
                ("Unexpected offered guard branch", reference, actor, node, speaker)
            )
        choice = choices[node]
        before_choice = probe.peer.mark()
        probe.peer.send(12058, struct.pack(">ii", node, choice))
        closed = probe.peer.matching(12218, before_choice, timeout=15)
        if closed != struct.pack(">i", 0):
            raise AssertionError(
                ("Supply acknowledgement did not close native dialogue", node, choice)
            )
        probe.peer.matching(
            13832,
            before_choice,
            predicate=lambda body: body == struct.pack(">qi", character_id, objective),
            timeout=15,
        )
        state = _await_progress(probe, lambda value: objective in value["objectives"])
        if 2143 in state["completed"]:
            probe.peer.matching(
                13422,
                before_choice,
                predicate=lambda body: len(body) == 20
                and struct.unpack_from(">qi", body) == (character_id, 2143),
                timeout=15,
            )
            # The ordinary reward settlement can emit its inventory delta just
            # after completion; capture that immediate boundary without a reconnect.
            probe.peer.matching_any((12471, 13879), before_choice, timeout=15)
        journey.append(
            dict(
                kind="native_guard_supply_acknowledgement",
                quest_id=2143,
                native_reference=reference,
                actor_id=actor,
                action_id=action,
                approach=list(approach),
                offered_root=node,
                accepted_choice=choice,
                objective_id=objective,
                completed=2143 in state["completed"],
                item_payment=None,
                native_choice_type=7,
            )
        )
        trace.extend(probe.peer.gameplay_trace(before_choice))
        probe.receipt["2143_last_guard_mark"] = before_choice
        probe.save()
    final = probe.progress()
    if 2143 not in final["completed"]:
        raise AssertionError(
            ("Four native guard acknowledgements did not complete2143", final)
        )
    return final
