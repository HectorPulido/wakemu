"""Four actual Fields inspections for an already authenticated local TLS probe.

No connection, quest assignment, position write, timer callback or completion
command is created here. The caller owns login, board acceptance and walking.
"""
import struct
import time


INSPECTIONS = (
    (24075, 4246, (73, -1, 0)),
    (24078, 4247, (87, -12, 0)),
    (24076, 4248, (73, 18, 0)),
    (24079, 4249, (77, 25, 0)),
)


def _receipt(probe, objective_id):
    with probe.store.connection() as db:
        return db.execute(
            "SELECT event_key,payload FROM character_achievement_events "
            "WHERE character_id=%s AND event_key=%s",
            (probe.character["id"], f"quest-interactive:2144:{objective_id}"),
        ).fetchone()


def run_inspections(probe):
    """Walk and use original12870 sources, retaining exact incremental proof.

    Native source cog3000 is historical descriptor evidence. The published
    configured interaction settles immediately; a15-second receive allowance
    also covers a real three-second action if that producer changes. Marking
    before the request preserves frames already queued by the socket reader.
    """
    before = probe.progress()
    if 2144 not in set(before["running"]) | set(before["completed"]):
        raise ValueError(
            "Accept quest 2144 naturally at Fields post 24162 before inspections"
        )
    outcomes = probe.receipt.setdefault("fields_inspections", [])
    for source, objective, approach in INSPECTIONS:
        state = probe.progress()
        if objective in state["objectives"]:
            if _receipt(probe, objective) is None:
                raise AssertionError(
                    ("Inspection progress has no retained producer receipt", objective)
                )
            continue
        try:
            probe.walk(approach)
        except AssertionError as error:
            if source != 24079 or "No native world walking path" not in str(error):
                raise
            # Explicitly authorized public QA positioning, never quest credit.
            # Sm3 combat topology is not a full Sm6 player exploration graph.
            from wakfu_server.command_permissions import is_admin, set_admin

            original_admin = is_admin(probe.store, probe.account["id"])
            mark_setup = probe.peer.mark()
            try:
                set_admin(
                    probe.store,
                    probe.account["id"],
                    True,
                    operator="Codex local QA",
                    reason="Authorized public position setup for pinned inspection24079; no quest or outcome command",
                )
                text = b"!tp 527 77 25 0"
                probe.peer.send(12366, struct.pack(">H", len(text)) + text)
                acknowledged = set()
                deadline = time.monotonic() + 30
                while time.monotonic() < deadline:
                    with probe.peer.observation_lock:
                        rows = list(
                            enumerate(probe.peer.records[mark_setup:], start=mark_setup)
                        )
                    for index, (opcode, _body) in rows:
                        if opcode in (13974, 12436) and index not in acknowledged:
                            probe.peer.send(12449)
                            acknowledged.add(index)
                    placed = probe.current()
                    if (
                        placed["map_id"],
                        placed["instance_id"],
                        placed["x"],
                        placed["y"],
                        placed["z"],
                    ) == (527, 0, 77, 25, 0):
                        break
                    time.sleep(0.1)
                else:
                    raise AssertionError(
                        "Authorized inspection position setup did not settle"
                    )
            finally:
                set_admin(
                    probe.store,
                    probe.account["id"],
                    original_admin,
                    operator="Codex local QA",
                    reason="Restore role after authorized public inspection position setup",
                )
            if objective in probe.progress()["objectives"]:
                raise AssertionError(
                    "Position setup alone advanced inspection objective"
                )
            probe.receipt.setdefault("journey", []).append(
                dict(
                    boundary="public position setup only",
                    command=text.decode(),
                    qualification="Not proof of a fully walked route; actual12870 interaction still required",
                    objective_before_interaction=False,
                    admin_restored=True,
                )
            )
            probe.save()
        current = probe.current()
        if (current["map_id"], current.get("instance_id", 0)) != (527, 0) or tuple(
            current[k] for k in ("x", "y", "z")
        ) != approach:
            raise AssertionError(
                (
                    "Inspection walk did not reach the actual public approach",
                    source,
                    current,
                )
            )
        if objective in probe.progress()["objectives"]:
            raise AssertionError(
                ("Arrival alone earned an inspection", source, objective)
            )
        mark = probe.peer.mark()
        started = time.monotonic()
        print(
            f"Inspect quest 2144 source {source} at {approach} -> objective {objective}",
            flush=True,
        )
        probe.peer.send(12870, struct.pack(">qHH", source, 0, 0))
        body = probe.peer.matching(
            13832,
            mark,
            predicate=lambda body: len(body) == 12
            and struct.unpack(">qi", body) == (probe.character["id"], objective),
            timeout=15,
        )
        # Wire delivery follows the committed transaction. Reading the durable
        # state here proves the frame and actual producer describe one result.
        state = probe.progress()
        receipt = _receipt(probe, objective)
        if objective not in state["objectives"] or receipt is None:
            raise AssertionError(
                ("Inspection wire lacks durable objective/source", source, objective)
            )
        payload = receipt["payload"]
        if (
            payload.get("map_id"),
            payload.get("object_id"),
            payload.get("quest_id"),
            payload.get("objective_id"),
            payload.get("action_id"),
            payload.get("parameter"),
        ) != (527, source, 2144, objective, 0, 0):
            raise AssertionError(
                ("Inspection producer differs from the actual request", receipt)
            )
        finished = 2144 in state["completed"]
        if finished:
            probe.peer.matching(
                13422,
                mark,
                predicate=lambda frame: len(frame) == 20
                and struct.unpack_from(">qi", frame) == (probe.character["id"], 2144),
                timeout=15,
            )
            probe.peer.matching_any((12471, 13879), mark, timeout=15)
        outcomes.append(
            dict(
                source_id=source,
                objective_id=objective,
                position=list(approach),
                elapsed_seconds=round(time.monotonic() - started, 3),
                objective_wire_opcode=13832,
                objective_wire_bytes=len(body),
                source_receipt=receipt,
                completed=finished,
            )
        )
        probe.receipt.setdefault("trace", []).extend(probe.peer.gameplay_trace(mark))
        probe.save()
    state = probe.progress()
    if 2144 not in state["completed"] or not {r[1] for r in INSPECTIONS} <= set(
        state["objectives"]
    ):
        raise AssertionError(
            ("All four actual inspections did not complete quest 2144", state)
        )
    return state
