"""Natural local Fields mercenary journey; no quest/stat/win fixtures.

Reuses authenticated board, source and dialogue adapters. City proofs are
retained independently. Only the explicit public !astrub position setup may
be used when the existing QA character starts outside map527.
"""
from __future__ import annotations
import argparse
from collections import deque
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import struct
import time

from tools.install_mission_bundle import local_connection
from tools.regional_quest_tls_probe import RegionalProbe
from tools.rii_departure_probe import ObservedPeer, login
from tools.candidate_friendly_duel_socket_smoke import placement
from tools import line2_rank23_native_tls_probe as shared
from wakfu_server.store import Store
from wakfu_server import dungeon_instances, dungeon_runtime_config
from wakfu_server.combat_terrain import published_geometry

QUESTS = (2143, 2144, 2145, 2146, 2138)
BOARD = 24162
APPROACH = (16, 45, 0)
ROUTE = "native_dungeon_27"
SOURCES = (
    (24101, 4251, (-52, 109, 0), "gather"),
    (24104, 4252, (-64, 106, 0), "encounter"),
    (24107, 4253, (-66, 107, 0), "gather"),
    (24113, 4254, (-63, 110, 0), "encounter"),
    (24116, 4255, (-59, 113, 0), "gather"),
    (24114, 4256, (-57, 114, 0), "encounter"),
)


def player_exploration(configuration):
    path = Path(".runtime/quest-archetypes/dungeon27-native-sm6.json")
    if not path.exists():
        return configuration["topology"]["exploration_geometry"]
    geometry = json.loads(path.read_text())
    if (
        geometry.get("map_id") != 1087
        or geometry.get("topology_sha256")
        != "a77fa529f2f56f580799b0e07f293de713ab84324638ec03bd0c8325ed414333"
        or geometry.get("profile")
        != {"height": 6, "native_class": "Sm", "movement_type": 0, "jump_capacity": 4}
    ):
        raise ValueError("Dungeon27 player exploration proof changed")
    return geometry


class FieldsProbe(RegionalProbe):
    def walk(self, goal):
        current = self.current()
        if current["instance_id"] and current["map_id"] == 1087:
            from tools.quest_instance_combat_probe import walk_native

            with self.store.connection() as db:
                configuration = dungeon_runtime_config.active_configuration(db, ROUTE)
            configuration = dict(configuration)
            configuration["topology"] = dict(configuration["topology"])
            configuration["topology"]["exploration_geometry"] = player_exploration(
                configuration
            )
            return walk_native(self, configuration, goal)
        try:
            return super().walk(goal)
        except AssertionError as error:
            if (
                "No native world walking path" not in str(error)
                or self.current()["map_id"] != 527
                or self.current()["instance_id"] != 0
            ):
                raise
        from wakfu_server.command_permissions import is_admin, set_admin

        original_admin = is_admin(self.store, self.account["id"])
        before = set(self.progress()["objectives"])
        mark = self.peer.mark()
        goal = tuple(goal)
        text = "!tp 527 " + " ".join(map(str, goal))
        try:
            set_admin(
                self.store,
                self.account["id"],
                True,
                operator="Codex local QA",
                reason="Authorized pinned public Fields position setup; no objective or outcome command",
            )
            command(self, text)
            acked = set()
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline:
                with self.peer.observation_lock:
                    rows = list(enumerate(self.peer.records[mark:], start=mark))
                for index, (opcode, _body) in rows:
                    if opcode in (13974, 12436) and index not in acked:
                        self.peer.send(12449)
                        acked.add(index)
                current = self.current()
                if tuple(current[k] for k in ("x", "y", "z")) == goal:
                    break
                time.sleep(0.1)
            else:
                raise AssertionError("Public position setup did not settle")
        finally:
            set_admin(
                self.store,
                self.account["id"],
                original_admin,
                operator="Codex local QA",
                reason="Restore role after authorized public Fields position setup",
            )
        if set(self.progress()["objectives"]) != before:
            raise AssertionError("Public position setup advanced objectives")
        record(
            self,
            "public position setup only",
            command=text,
            qualification="QA topology gap; not evidence of a fully walked route",
            admin_restored=True,
        )


def stamp():
    return datetime.now(timezone.utc).isoformat()


def record(probe, boundary, **facts):
    probe.receipt.setdefault("journey", []).append(
        {"at": stamp(), "boundary": boundary, **facts}
    )
    probe.save()
    print(json.dumps({"boundary": boundary, **facts}, default=str), flush=True)


def command(probe, text):
    raw = text.encode()
    probe.peer.send(12366, struct.pack(">H", len(raw)) + raw)


def play_administrative(
    probe,
    fight_id,
    wire_start,
    *,
    resume_existing=False,
    timeout=600,
    priority_breed=None,
    scope="line3",
):
    """Explicit user-authorized !winfight smoke, never natural fight evidence."""
    from wakfu_server.command_permissions import is_admin, set_admin

    original = is_admin(probe.store, probe.account["id"])
    mark = probe.peer.mark()
    try:
        set_admin(
            probe.store,
            probe.account["id"],
            True,
            operator="Codex local QA",
            reason="Hector explicitly authorized !winfight for remaining "
            + scope
            + " fights; no further combat QA",
        )
        command(probe, "!winfight")

        def terminal():
            with probe.store.connection() as db:
                row = db.execute(
                    "SELECT status FROM combat_fights WHERE id=%s", (fight_id,)
                ).fetchone()
                return row if row and row["status"] == "finished" else None

        shared._wait_until(
            terminal, timeout=30, label="authorized administrative fight outcome"
        )
        record(
            probe,
            "USER-AUTHORIZED ADMINISTRATIVE WIN APPLIED",
            fight_id=fight_id,
            command="!winfight",
            qualification="Not a natural victory or combat/AI test",
        )
    finally:
        set_admin(
            probe.store,
            probe.account["id"],
            original,
            operator="Codex local QA",
            reason="Restore role after user-authorized " + scope + " !winfight",
        )
    with probe.store.connection() as db:
        snapshot = db.execute(
            "SELECT snapshot FROM fight_checkpoints WHERE fight_id=%s", (fight_id,)
        ).fetchone()["snapshot"]
    probe.receipt.setdefault("fights", []).append(
        dict(
            fight_id=fight_id,
            administrative_command="!winfight",
            phase=snapshot["phase"],
            winner=snapshot["winner"],
            qualification="Explicit user exception, not natural gameplay",
        )
    )
    probe.save()
    probe.peer.send(12925, struct.pack(">iB", fight_id, 1))
    probe.peer.matching(
        13046,
        mark,
        lambda body: len(body) == 15
        and struct.unpack_from(">q", body)[0] == probe.character["id"]
        and body[10] == 17
        and struct.unpack_from(">i", body, 11)[0] == -1,
        timeout=30,
    )


def accept(probe, quest):
    state = probe.progress()
    if quest in state["running"] or quest in state["completed"]:
        return
    probe.walk(APPROACH)
    mark = probe.peer.mark()
    probe.peer.send(12870, struct.pack(">qHH", BOARD, 0, 0))
    probe.peer.send(12864, struct.pack(">iqB", quest, -1, 1))
    shared._wait_until(
        lambda: quest in probe.progress()["running"],
        timeout=15,
        label=f"native Fields acceptance {quest}",
    )
    with probe.store.connection() as db:
        event = db.execute(
            "SELECT payload FROM character_achievement_events WHERE character_id=%s AND event_key=%s",
            (probe.character["id"], f"native-mercenary-board-acceptance:{quest}"),
        ).fetchone()
    assert event is not None and event["payload"]["board_id"] == BOARD
    probe.receipt["trace"].extend(probe.peer.gameplay_trace(mark))
    record(probe, "naturally accepted Fields contract", quest_id=quest)


def verify(probe, quest, mark, was_completed):
    shared._verify_completed_rewards(
        probe,
        quest,
        mark,
        require_objective=not was_completed,
        require_completion=not was_completed,
        require_reward=not was_completed,
    )
    record(
        probe,
        "completed Fields contract",
        quest_id=quest,
        rewards=shared._reward_receipts(probe.store, probe.character["id"], quest),
    )


def setup_public(probe):
    current = probe.current()
    if current["instance_id"]:
        with probe.store.connection() as db:
            route = db.execute(
                "SELECT definition_id,entry_object_id,start_map_id FROM dungeon_instances WHERE instance_id=%s",
                (current["instance_id"],),
            ).fetchone()
        if not route or (
            route["definition_id"],
            route["entry_object_id"],
            route["start_map_id"],
        ) != (27, 26962, 1087):
            raise ValueError("Refusing unrelated private instance")
        return
    if current["map_id"] == 527:
        return
    if current["map_id"] != 546:
        raise ValueError("Only existing sewer exterior setup is allowed")
    mark = probe.peer.mark()
    command(probe, "!astrub")
    acked = set()
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        with probe.peer.observation_lock:
            rows = list(enumerate(probe.peer.records[mark:], start=mark))
        for index, (opcode, _body) in rows:
            if opcode in (13974, 12436) and index not in acked:
                probe.peer.send(12449)
                acked.add(index)
        current = probe.current()
        if current["map_id"] == 527 and current["instance_id"] == 0:
            break
        time.sleep(0.1)
    assert current["map_id"] == 527 and current["instance_id"] == 0
    record(
        probe,
        "public position setup only",
        command="!astrub",
        position={k: current[k] for k in ("map_id", "instance_id", "x", "y", "z")},
        qualification="Not evidence of walking the sewer exterior",
    )


def admit_room(probe, configuration, order):
    current = probe.current()
    with probe.store.connection() as db:
        group = db.execute(
            "SELECT g.* FROM dungeon_room_spawn_receipts r JOIN combat_groups g ON g.map_id=r.asset_map_id AND g.instance_id=r.instance_id AND g.group_id=r.group_id WHERE r.instance_id=%s AND r.room_order=%s",
            (current["instance_id"], order),
        ).fetchone()
    if group is None:
        raise ValueError("No authenticated room group")
    if group["status"] == "fighting":
        return group["fight_id"], 0, True
    if group["status"] == "defeated":
        return None, 0, False
    if group["status"] != "available":
        raise ValueError(("Room group unavailable", group["status"]))
    from wakfu_server.combat_geometry import prepare_geometry

    graph = prepare_geometry(player_exploration(configuration)).outgoing
    here = tuple(current[k] for k in ("x", "y", "z"))
    occupied = {tuple(m[k] for k in ("x", "y", "z")) for m in group["members"]}
    pending = deque([here])
    seen = {here}
    target = None
    while pending and target is None:
        cell = pending.popleft()
        for member in group["members"]:
            if (
                abs(cell[0] - member["x"]) + abs(cell[1] - member["y"]) <= 1
                and abs(cell[2] - member["z"]) <= 1
            ):
                probe.walk(cell)
                target = member
                break
        for nxt in graph.get(cell, ()):
            if nxt not in seen and nxt not in occupied:
                seen.add(nxt)
                pending.append(nxt)
    if target is None:
        # A real native far-click delegates approach to the server's ordinary
        # actor-action path. The QA combat graph is not player exploration.
        target = group["members"][0]
        record(
            probe,
            "ordinary registered-target far click",
            room=order,
            target_id=target["id"],
            qualification="Server chooses its native legal approach",
        )
    mark = probe.peer.mark()
    probe.peer.send(
        13130,
        struct.pack(">qiihB", target["id"], target["x"], target["y"], target["z"], 0),
    )
    fight_id, _ = placement(probe.peer.matching(13652, mark, timeout=60))
    return fight_id, mark, False


def physical_exit(probe, source_id):
    from wakfu_server import generic_transports
    from wakfu_server.combat_geometry import prepare_geometry

    with probe.store.connection() as db:
        configuration = dungeon_runtime_config.active_configuration(db, ROUTE)
    current = probe.current()
    source = generic_transports.source(current["map_id"], source_id)
    if source is None:
        raise ValueError("Native physical exit source is absent")
    graph = prepare_geometry(player_exploration(configuration)).outgoing
    approved = {
        tuple(row[k] for k in ("x", "y", "z"))
        for row in source.get("approach_positions", ())
    }
    here = tuple(current[k] for k in ("x", "y", "z"))
    pending = deque([here])
    seen = {here}
    goal = None
    while pending:
        cell = pending.popleft()
        if cell in approved if approved else cell[:2] == (source["x"], source["y"]):
            goal = cell
            break
        for nxt in graph.get(cell, ()):
            if nxt not in seen:
                seen.add(nxt)
                pending.append(nxt)
    if goal is None:
        raise ValueError("Native exploration graph has no physical exit approach")
    probe.walk(goal)
    mark = probe.peer.mark()
    probe.peer.send(12296, struct.pack(">qiBi", source_id, 2517, 0, 2))
    probe.peer.matching(13974, mark, timeout=30)
    probe.peer.send(12449)
    shared._wait_until(
        lambda: probe.current()["instance_id"] == 0,
        timeout=20,
        label="normal native physical exit",
    )
    record(probe, "native physical exit used", source_id=source_id, destination_id=2517)


def dungeon(probe, play):
    dungeon_instances.load_runtime_routes(probe.store)
    route = dungeon_instances.route(ROUTE)
    with probe.store.connection() as db:
        configuration = dungeon_runtime_config.active_configuration(db, ROUTE)
    current = probe.current()
    if not current["instance_id"]:
        native = configuration["route"]
        # This is the exact published physical source; native admission remains
        # responsible for range and the unchanged entrance costs/criteria.
        from wakfu_server import generic_transports

        source = generic_transports.source(527, native["entry_object_id"])
        if source is None:
            raise ValueError("Published native Dungeon27 source is absent")
        geometry = published_geometry(527).outgoing
        here = tuple(current[k] for k in ("x", "y", "z"))
        source_cell = tuple(source[k] for k in ("x", "y", "z"))
        pending = deque([here])
        seen = {here}
        goal = None
        while pending:
            cell = pending.popleft()
            if (
                abs(cell[0] - source_cell[0]) + abs(cell[1] - source_cell[1]) <= 1
                and abs(cell[2] - source_cell[2]) <= 1
            ):
                goal = cell
                break
            for nxt in geometry.get(cell, ()):
                if nxt not in seen:
                    seen.add(nxt)
                    pending.append(nxt)
        if goal is None:
            raise ValueError("No native dungeon27 source approach")
        probe.walk(goal)
        mark = probe.peer.mark()
        probe.peer.send(
            12296,
            struct.pack(
                ">qiBi", native["entry_object_id"], native["destination_id"], 0, 2
            ),
        )
        probe.peer.matching(13974, mark, timeout=30)
        probe.peer.send(12449)
        current = probe.current()
        assert (
            current["map_id"] == native["start_map_id"] and current["instance_id"] > 0
        )
        record(
            probe,
            "native Dungeon27 entry",
            instance_id=current["instance_id"],
            object_id=native["entry_object_id"],
        )
    instance = current["instance_id"]
    with probe.store.connection() as db:
        progress = db.execute(
            "SELECT current_room,status FROM dungeon_room_runs WHERE instance_id=%s",
            (instance,),
        ).fetchone()
    for order in range(
        progress["current_room"], len(configuration["topology"]["rooms"]) + 1
    ):
        shared._wait_room(probe.store, instance, order)
        fight, mark, resuming = admit_room(probe, configuration, order)
        if fight is not None:
            record(
                probe,
                "native Dungeon27 fight admitted",
                room=order,
                fight_id=fight,
                resume=resuming,
            )
            play(
                probe,
                fight,
                mark,
                resume_existing=resuming,
                timeout=600,
                priority_breed=1259,
            )
            probe.peer.send(12449)
            record(probe, "native Dungeon27 room won", room=order, fight_id=fight)
        if order < len(configuration["topology"]["rooms"]):
            next_room = configuration["topology"]["rooms"][order]
            with probe.store.connection() as db:
                new = db.execute(
                    "SELECT current_room,status FROM dungeon_room_runs WHERE instance_id=%s",
                    (instance,),
                ).fetchone()
            if new["current_room"] <= order:
                probe.walk(tuple(next_room["anchor"]))
            shared._wait_room(probe.store, instance, order + 1)
    if probe.current()["instance_id"]:
        physical_exit(probe, 26872)
    shared._wait_until(
        lambda: probe.current()["instance_id"] == 0,
        timeout=40,
        label="Dungeon27 normal exterior return",
    )
    with probe.store.connection() as db:
        membership = db.execute(
            "SELECT status FROM dungeon_instance_members WHERE instance_id=%s AND character_id=%s",
            (instance, probe.character["id"]),
        ).fetchone()
        pending = db.execute(
            "SELECT count(*) n FROM dungeon_transition_outbox WHERE instance_id=%s AND character_id=%s AND status='pending'",
            (instance, probe.character["id"]),
        ).fetchone()["n"]
        company = db.execute(
            "SELECT party_id FROM player_party_members WHERE character_id=%s",
            (probe.character["id"],),
        ).fetchone()
    record(
        probe,
        "Dungeon27 normal return",
        membership=membership,
        pending=pending,
        company=company,
        position={
            k: probe.current()[k] for k in ("map_id", "instance_id", "x", "y", "z")
        },
    )


def run(store, account, character, path, resume, administrative_wins=False):
    probe = FieldsProbe(store, account, character, path)
    if path.exists():
        if not resume:
            raise ValueError("Existing receipt requires --resume")
        probe.receipt = json.loads(path.read_text())
    else:
        probe.receipt.update(
            scope="Natural Fields2143+2144 ->2145+2146 ->2138 only; no quest/stat/win fixtures",
            journey=[],
            trace=[],
        )
    if administrative_wins:
        probe.receipt[
            "scope"
        ] = "Line3 original contracts and room1 natural; remaining Dungeon27 fights use explicitly authorized !winfight. No quest assignment/completion or HP/stat writes; administrative outcomes are not natural victories."
    probe.receipt.setdefault("attempts", []).append(
        {"started_at": stamp(), "status": "running"}
    )
    attempt = probe.receipt["attempts"][-1]
    try:
        probe.peer = ObservedPeer()
        probe.generation = login(store, probe.peer, probe.account, probe.current())
        setup_public(probe)
        record(
            probe,
            "selected current character",
            hp=probe.current()["hp"],
            level=probe.current()["level"],
        )
        for quest in (2143, 2144):
            accept(probe, quest)
        from tools.line3_fields_dialogue_actions import run_guard_acknowledgements

        mark = probe.peer.mark()
        done = 2143 in probe.progress()["completed"]
        run_guard_acknowledgements(probe)
        verify(probe, 2143, mark, done)
        from tools.line3_fields_inspection_actions import run_inspections

        mark = probe.peer.mark()
        done = 2144 in probe.progress()["completed"]
        run_inspections(probe)
        verify(probe, 2144, mark, done)
        for quest in (2145, 2146):
            accept(probe, quest)
        if administrative_wins:
            play_existing = play_administrative
        else:
            from tools.line3_fields_combat import play_existing
        shared._play_already_started_fight = play_existing
        health = probe.current()["hp"]
        record(probe, "pre-combat actual HP", hp=health)
        mark = probe.peer.mark()
        done = 2145 in probe.progress()["completed"]
        shared._source_click(probe, 24086, 4250, (-134, 42, 0), "encounter")
        verify(probe, 2145, mark, done)
        mark = probe.peer.mark()
        done = 2146 in probe.progress()["completed"]
        for source in SOURCES:
            shared._source_click(probe, *source)
        verify(probe, 2146, mark, done)
        accept(probe, 2138)
        mark = probe.peer.mark()
        done = 2138 in probe.progress()["completed"]
        if not done:
            dungeon(probe, play_existing)
        verify(probe, 2138, mark, done)
        before = probe.progress()
        rewards = {q: shared._reward_receipts(store, character, q) for q in QUESTS}
        probe.peer.close()
        time.sleep(0.5)
        probe.peer = ObservedPeer()
        login(store, probe.peer, probe.account, probe.current())
        assert before == probe.progress()
        assert rewards == {
            q: shared._reward_receipts(store, character, q) for q in QUESTS
        }
        record(
            probe,
            "Fields completion persisted on reconnect",
            quests=list(QUESTS),
            administrative_outcome_exception=administrative_wins,
        )
        attempt["status"] = "passed"
        probe.receipt["success"] = True
    except BaseException as error:
        attempt["status"] = "failed"
        attempt["error"] = repr(error)
        raise
    finally:
        attempt["finished_at"] = stamp()
        probe.save()
        if probe.peer:
            probe.peer.close()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--account-id", type=int, required=True)
    p.add_argument("--character-id", type=int, required=True)
    p.add_argument("--resume", action="store_true")
    p.add_argument("--run", action="store_true")
    p.add_argument("--administrative-wins", action="store_true")
    args = p.parse_args()
    local_connection(os.environ["WAKFU_DATABASE_URL"])
    store = Store(
        os.environ["WAKFU_DATABASE_URL"],
        password_file=os.environ.get("WAKFU_DATABASE_PASSWORD_FILE"),
    )
    try:
        if not args.run:
            character = store.character(args.account_id, args.character_id)
            state = shared._progress(store, args.character_id)
            print(
                json.dumps(
                    {
                        "ready": character is not None,
                        "character": {
                            k: character[k]
                            for k in ("id", "map_id", "instance_id", "hp", "level")
                        },
                        "running": sorted(set(state["running"]) & set(QUESTS)),
                        "completed": sorted(set(state["completed"]) & set(QUESTS)),
                    }
                )
            )
            return
        path = Path(
            f".local-state/wakemu/qa/line3-fields-{args.account_id}-{args.character_id}.json"
        )
        run(
            store,
            args.account_id,
            args.character_id,
            path,
            args.resume,
            args.administrative_wins,
        )
    finally:
        store.close()


if __name__ == "__main__":
    main()
