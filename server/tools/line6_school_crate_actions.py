"""Literal published crate witnesses on the owner's existing native QA peer.

No TLS session, solver, fixture, actor movement override or outcome is created.
Uppercase is one ordinary paid step. Lowercase is raw native Push5589 followed
by that ordinary step, unless the push has already finished the real puzzle.
"""
import json
from pathlib import Path
import struct
import time


BOARDS = (
    Path(__file__).resolve().parents[1]
    / "wakfu_server/maps/owned_story_profiles/huppermage-sokoban-1019.boards.json"
)
DIRECTIONS = {"N": (0, -1), "S": (0, 1), "E": (1, 0), "W": (-1, 0)}


def _board(source_id):
    matches = [
        row
        for row in json.loads(BOARDS.read_text())["boards"]
        if row["source_id"] == source_id
    ]
    if len(matches) != 1:
        raise ValueError("Use one actual26322/26324/26323 board source")
    return matches[0]


def _snapshot(runner):
    # A terminal checkpoint must never enter a fresh native input/ACK wait.
    current = runner.checkpoint()
    if current and current["phase"] == "finished":
        return current
    return runner.ready_for_input()


def _prefix_state(board, index):
    """Replay only the supplied literal prefix; this performs no search."""
    hero = tuple(board["hero"])
    boxes = set(map(tuple, board["boxes"]))
    goals = set(map(tuple, board["goals"]))
    for symbol in board["reviewed_solution"]["path"][:index]:
        dx, dy = DIRECTIONS[symbol.upper()]
        target = (hero[0] + dx, hero[1] + dy, hero[2])
        if symbol.islower():
            beyond = (target[0] + dx, target[1] + dy, target[2])
            if target not in boxes or beyond in boxes:
                raise ValueError("Published witness prefix has an invalid push")
            boxes.remove(target)
            boxes.add(beyond)
            if boxes == goals:
                continue  # The final native push ends before the vacated step.
        elif target in boxes:
            raise ValueError("Published witness prefix walks into a crate")
        hero = target
    return hero, boxes


def play_existing(
    probe,
    source_id,
    fight_id,
    wire_start=0,
    *,
    resume_existing=False,
    timeout=240,
    max_operations=512,
    start_index=0,
    resume_index=None
):
    from tools.line2_rank23_native_tls_probe import Rank23NativeRun

    board = _board(source_id)
    if resume_index is not None:
        if start_index not in (0, resume_index):
            raise ValueError("Conflicting literal witness resume indexes")
        start_index = resume_index
    if type(start_index) is not int or not 0 <= start_index <= len(
        board["reviewed_solution"]["path"]
    ):
        raise ValueError("Invalid literal witness resume index")
    expected_hero, expected_boxes = _prefix_state(board, start_index)
    current = probe.current()
    if current["map_id"] != 1019 or current.get("instance_id", 0) <= 0:
        raise ValueError("Enter the actual owned native crate board first")
    expected = "huppermage-sokoban-" + board["name"] + "-1019"
    if (
        probe.configuration()["topology"].get("owned_story_controller", {}).get("id")
        != expected
    ):
        raise ValueError(
            "The requested witness differs from the pinned crate controller"
        )
    with probe.store.connection() as db:
        groups = db.execute(
            "SELECT members FROM combat_groups WHERE fight_id=%s", (fight_id,)
        ).fetchall()
    if (
        len(groups) != 1
        or len(groups[0]["members"]) != len(board["boxes"])
        or any(member["ref"] != 3889 for member in groups[0]["members"])
    ):
        raise ValueError("The actual fight lacks its original native crate roster")
    original_ids = {str(member["id"]) for member in groups[0]["members"]}
    runner = Rank23NativeRun(probe.store, probe.account, probe.character, probe.receipt)
    runner.peer, runner.fight_id = probe.peer, fight_id
    runner.wire_cursor = 0 if resume_existing else wire_start
    runner.native_global_turn, runner.native_turn_actor = 0, None
    runner.native_timeline_phase, runner.native_timeline_members = None, frozenset()
    runner.last_begin_identity = runner.last_acked_turn = None
    before = runner.checkpoint()
    if before is None or before["phase"] == "placement":
        probe.peer.send(12523, b"\x01")
    elif before["phase"] != "finished":
        probe.peer.send(13332, struct.pack(">i", fight_id))
    deadline = time.monotonic() + timeout
    operations = []

    def ready():
        if len(operations) >= max_operations or time.monotonic() >= deadline:
            raise AssertionError(
                ("Literal crate witness bound exhausted", source_id, operations)
            )
        return _snapshot(runner)

    def step(symbol):
        while True:
            snapshot = ready()
            if snapshot["phase"] == "finished":
                return snapshot
            hero = snapshot["actors"][str(probe.character["id"])]
            if hero["mp"] > 0:
                break
            runner.end_turn()
            operations.append(dict(kind="normal_end_turn"))
        dx, dy = DIRECTIONS[symbol.upper()]
        target = (
            hero["position"][0] + dx,
            hero["position"][1] + dy,
            hero["position"][2],
        )
        if (tuple(hero["position"]), target) not in {
            tuple(map(tuple, edge)) for edge in snapshot["edges"]
        }:
            raise AssertionError(
                (
                    "Witness step lacks an actual native edge",
                    symbol,
                    hero["position"],
                    target,
                )
            )
        after = runner.action(
            12161,
            struct.pack(">q", hero["id"]) + struct.pack(">iih", *target),
            label="literal School crate paid step " + symbol,
        )
        operations.append(dict(kind="paid_native_move", cell=list(target)))
        if (
            after["phase"] != "finished"
            and tuple(after["actors"][str(hero["id"])]["position"]) != target
        ):
            raise AssertionError(
                ("Actual crate step did not reach its literal cell", target)
            )
        return after

    first = ready()
    if first["phase"] != "finished":
        actual_boxes = {
            tuple(first["actors"][identity]["position"]) for identity in original_ids
        }
        if (
            tuple(first["actors"][str(probe.character["id"])]["position"])
            != expected_hero
            or actual_boxes != expected_boxes
        ):
            raise ValueError(
                (
                    "Actual hero/crates differ from literal witness prefix",
                    start_index,
                    expected_hero,
                    sorted(expected_boxes),
                )
            )
    for index, symbol in enumerate(
        board["reviewed_solution"]["path"][start_index:], start_index
    ):
        snapshot = ready()
        if snapshot["phase"] == "finished":
            break
        if symbol.islower():
            hero = snapshot["actors"][str(probe.character["id"])]
            dx, dy = DIRECTIONS[symbol.upper()]
            target = (
                hero["position"][0] + dx,
                hero["position"][1] + dy,
                hero["position"][2],
            )
            boxes = [
                actor
                for identity, actor in snapshot["actors"].items()
                if identity in original_ids
                and tuple(actor["position"]) == target
                and actor["hp"] > 0
            ]
            if len(boxes) != 1:
                raise AssertionError(
                    ("Literal native push has no original crate", index, target)
                )
            runner.cast(5589, target, class_spell=False)
            operations.append(
                dict(kind="native_push", casting_uid=5589, target=list(target))
            )
            snapshot = runner.checkpoint()
            if snapshot and snapshot["phase"] == "finished":
                break
        snapshot = step(symbol)
        if snapshot["phase"] == "finished":
            break
    terminal = runner.checkpoint()
    hero = terminal["actors"][str(probe.character["id"])]
    if terminal["phase"] != "finished" or terminal.get("winner") != hero["team"]:
        raise AssertionError(
            (
                "Literal native crate witness did not finish",
                source_id,
                terminal["phase"],
            )
        )
    if any(
        event.get("kind") == "administrative_outcome"
        for event in terminal.get("events", ())
    ):
        raise AssertionError("An administrative outcome cannot prove crate completion")
    close_mark = probe.peer.mark()
    probe.peer.send(12925, struct.pack(">iB", fight_id, 1))
    probe.ack_loads(close_mark, timeout=10)
    settle_deadline = time.monotonic() + 5
    while True:
        with probe.store.connection() as db:
            progress = db.execute(
                "SELECT state FROM character_achievement_progress WHERE character_id=%s",
                (probe.character["id"],),
            ).fetchone()
        if (
            progress is not None
            and board["objective_id"] in progress["state"].get("objectives", ())
            and probe.current().get("instance_id", 0) == 0
        ):
            break
        if time.monotonic() >= settle_deadline:
            raise AssertionError(
                (
                    "Native crate outcome did not publish its objective",
                    board["objective_id"],
                )
            )
        probe.ack_loads(close_mark, timeout=0.2)
        time.sleep(0.1)
    result = dict(
        source_id=source_id,
        objective_id=board["objective_id"],
        fight_id=fight_id,
        start_index=start_index,
        witness=board["reviewed_solution"]["path"],
        operations=operations,
        winner=terminal["winner"],
        returned={
            key: probe.current().get(key)
            for key in ("map_id", "instance_id", "x", "y", "z")
        },
        qualification="Literal paid native moves and rawPush5589; no administrative outcome",
    )
    probe.receipt.setdefault("school_crate_witnesses", []).append(result)
    probe.note(
        "actual literal School crate witness completed",
        source_id=source_id,
        objective_id=board["objective_id"],
        fight_id=fight_id,
        operations=len(operations),
    )
    return result


def play_trial(probe, source_id, wire_start=0, *, admission_timeout=15, **kwargs):
    """Wait only for the existing scene's authentic automatic admission."""
    board = _board(source_id)
    deadline = time.monotonic() + admission_timeout
    while time.monotonic() < deadline:
        current = probe.current()
        with probe.store.connection() as db:
            row = db.execute(
                "SELECT g.fight_id,g.status FROM dungeon_room_spawn_receipts r "
                "JOIN combat_groups g ON g.map_id=r.asset_map_id AND g.instance_id=r.instance_id "
                "AND g.group_id=r.group_id WHERE r.instance_id=%s AND r.room_order=1",
                (current["instance_id"],),
            ).fetchone()
        if row and row["status"] == "fighting" and row.get("fight_id"):
            return play_existing(
                probe, board["source_id"], row["fight_id"], wire_start, **kwargs
            )
        probe.ack_loads(wire_start, timeout=0.2)
        time.sleep(0.1)
    raise AssertionError(
        "Actual crate bootstrap/autostart has not admitted a fight; no client substitute sent"
    )
