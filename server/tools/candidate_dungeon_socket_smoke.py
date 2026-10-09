"""Selected dungeon TLS acceptance on a disposable database, never a live DB.

Default scope: native party invitation, approved world approach, native entry,
private map/context hydration, frozen room roster and reconnect.
This script does not manufacture victories or bypass source interaction guards.
``--phase full`` additionally runs three normal shared room fights, verifies
automatic whole-party room advancement after victory, exits both owners
and reconnects outside. No containers or services are started here.
"""
from collections import deque
import argparse
import json
import os
from pathlib import Path
import struct
import time

from psycopg.conninfo import conninfo_to_dict
from protocol_codec import DIRECTIONS
from wakfu_server import generic_transports, proto_dungeon
from wakfu_server.maps.dungeon_runtime_config import active_configuration
from wakfu_server.store import Store
from candidate_shared_combat_push_smoke import (
    Peer as BasePeer,
    login,
    stop_test_session_heartbeats,
    _walk_edges,
)
from candidate_shared_combat_three_peer_smoke import (
    create_character,
    wait_sql,
    command_text,
)


class Peer(BasePeer):
    """Report a background TLS reader failure before the next native action."""

    def send(self, opcode, body=b""):
        with self.events.mutex:
            failures = [packet[1] for packet in self.events.queue if packet[0] is None]
        failures.extend(packet[1] for packet in self.pending if packet[0] is None)
        if failures:
            error = failures[0]
            raise AssertionError(
                f"TLS reader failed before sending opcode {opcode}: "
                f"{type(error).__name__}: {error}"
            ) from error
        return super().send(opcode, body)


def world_context(body):
    blocks, offset = [], 0
    for _ in range(4):
        size = struct.unpack_from(">H", body, offset)[0]
        offset += 2
        blocks.append(body[offset : offset + size])
        offset += size
    if offset != len(body) or len(blocks[0]) != struct.calcsize(">BqBqiihqBBiihq"):
        raise AssertionError("Native map bootstrap block layout changed")
    fields = struct.unpack(">BqBqiihqBBiihq", blocks[0])
    return fields[7], proto_dungeon.decode(blocks[3])


def await_room_bootstrap(peer, initial, map_id, cells):
    """Accept an already-consumed return only if it hydrates the next room."""
    deadline = time.monotonic() + 40
    body = initial
    while True:
        actual_map, _ = world_context(body)
        entity_size = struct.unpack_from(">H", body)[0]
        fields = struct.unpack(">BqBqiihqBBiihq", body[2 : 2 + entity_size])
        if actual_map == map_id and tuple(fields[4:7]) in cells:
            return
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise AssertionError(
                "Native bootstrap did not hydrate the automatic next room"
            )
        body, _ = peer.wait(13974, timeout=remaining)


def native_path(map_id, start, goal):
    if start == goal:
        return []
    graph = _walk_edges(map_id)
    queue, previous = deque([start]), {start: None}
    while queue:
        cell = queue.popleft()
        for neighbor in graph.get(cell, ()):
            if neighbor in previous:
                continue
            previous[neighbor] = cell
            if neighbor == goal:
                path = [goal]
                while previous[path[-1]] != start:
                    path.append(previous[path[-1]])
                return list(reversed(path))
            queue.append(neighbor)
    raise AssertionError("No approved native path reaches the selected approach")


def walk(peer, observer, character_id, map_id, start, destination):
    path = native_path(map_id, start, destination)
    if not path:
        return
    if len(path) > 255:
        raise AssertionError("Acceptance path exceeds native byte count")
    directions = {(dx, dy): identity for identity, (_, dx, dy) in DIRECTIONS.items()}
    current, steps = start, bytearray()
    for cell in path:
        dz = cell[2] - current[2]
        if not -16 <= dz <= 15:
            raise AssertionError("Native altitude delta cannot be encoded")
        steps.append(
            (directions[(cell[0] - current[0], cell[1] - current[1])] << 5) | (dz & 31)
        )
        current = cell
    peer.send(13331, struct.pack(">iiihB", 0, *start, len(steps)) + steps)
    # Peer publication proves that the server approved the actual path. The
    # owning client animates locally and deliberately receives no path echo.
    body, _ = observer.wait(13852, timeout=15)
    while len(body) < 8 or struct.unpack_from(">q", body)[0] != character_id:
        body, _ = observer.wait(13852, timeout=15)


def character_position(store, identity):
    with store.connection() as db:
        row = db.execute(
            "SELECT map_id,instance_id,x,y,z FROM characters WHERE id=%s", (identity,)
        ).fetchone()
    return row, (row["x"], row["y"], row["z"])


def approach_source(store, actor, observer, identity, map_id, source):
    row, start = character_position(store, identity)
    if row["map_id"] != map_id:
        raise AssertionError("Approach starts on a different native asset")
    graph = _walk_edges(map_id)
    mask = source.get("approach_mask", 0)
    if type(mask) is not int or not 0 <= mask <= 32767:
        raise AssertionError("Native interactive approach mask is malformed")
    if mask == 0:
        # Verified bEm zero-mask callback compares the raw source X/Y on the
        # approved path. This wire gate does not prove a client menu exists.
        if source["x"] != int(source["x"]) or source["y"] != int(source["y"]):
            raise AssertionError("Native zero-mask source position is non-integral")
        candidates = [
            cell for cell in graph if cell[:2] == (int(source["x"]), int(source["y"]))
        ]
    else:
        candidates = [
            tuple(point[key] for key in ("x", "y", "z"))
            for point in source.get("approach_positions", ())
        ]
    candidates = [cell for cell in candidates if cell in graph]
    if not candidates:
        raise AssertionError(
            "Native interactive exposes no verified walkable approach; no proximity fallback"
        )
    candidates.sort(key=lambda cell: (abs(cell[2] - source["z"]), cell))
    goal = next((cell for cell in candidates if cell == start), candidates[0])
    walk(actor, observer, identity, map_id, start, goal)


def room_state(store, instance_id):
    """Read durable progression and groups without altering acceptance state."""
    with store.connection() as db:
        run = db.execute(
            "SELECT * FROM dungeon_room_runs WHERE instance_id=%s", (instance_id,)
        ).fetchone()
        groups = db.execute(
            "SELECT * FROM combat_groups WHERE instance_id=%s ORDER BY group_id",
            (instance_id,),
        ).fetchall()
    return run, groups


def door_request(store, peers, identities, map_id, door, *, expect_rejection=False):
    source = generic_transports.source(map_id, door["source_id"])
    approach_source(store, peers[0], peers[1], identities[0], map_id, source)
    before = [character_position(store, identity)[0] for identity in identities]
    prior_room_state = (
        room_state(store, before[0]["instance_id"]) if expect_rejection else None
    )
    peers[0].send(
        12296, struct.pack(">qiBi", door["source_id"], door["destination_id"], 0, 2)
    )
    if expect_rejection:
        # Native transport rejection rehydrates the owner's current asset;
        # the dispatcher records the reason server-side, without opcode 674.
        drain_bootstrap(peers[0], map_id)
        after = [character_position(store, identity)[0] for identity in identities]
        if after != before:
            raise AssertionError("Rejected forward door moved a dungeon member")
        if room_state(store, before[0]["instance_id"]) != prior_room_state:
            raise AssertionError(
                "Rejected forward door changed dungeon progression or groups"
            )
    else:
        for peer in peers:
            drain_bootstrap(peer, map_id)


def full_room_cycle(store, peers, identities, config, instance_id):
    from dungeon_combat_harness import fight_room

    map_id = config["route"]["start_map_id"]
    reports = []
    for room in config["compiled_plan"]["rooms"]:
        order = room["order"]
        has_next = order < len(config["compiled_plan"]["rooms"])
        with store.connection() as db:
            receipt = db.execute(
                "SELECT group_id FROM dungeon_room_spawn_receipts WHERE instance_id=%s AND room_order=%s",
                (instance_id, order),
            ).fetchone()
            if receipt is None:
                raise AssertionError("Current room has no durable native group receipt")
            group = db.execute(
                "SELECT * FROM combat_groups WHERE map_id=%s AND instance_id=%s AND group_id=%s",
                (map_id, instance_id, receipt["group_id"]),
            ).fetchone()
        count = sum(monster["count"] for monster in room["monsters"])
        if group is None or len(group["members"]) != count:
            raise AssertionError("Room native group count differs from reviewed JSON")
        report = fight_room(
            store,
            dict(zip(identities, peers)),
            identities,
            map_id,
            instance_id,
            group,
            timeout=90,
        )
        return_bootstraps = report.pop("return_bootstraps")
        if len(return_bootstraps) != len(peers):
            raise AssertionError("Native combat returns omitted a participating owner")
        report["native_report_sizes"] = [
            len(body) for body in report.pop("victory_reports")
        ]
        with store.connection() as db:
            rewards = db.execute(
                "SELECT character_id,xp,kamas FROM fight_rewards WHERE fight_id=%s ORDER BY character_id",
                (report["fight_id"],),
            ).fetchall()
            if len(rewards) != len(identities) or {
                row["character_id"] for row in rewards
            } != set(identities):
                raise AssertionError(
                    "Shared dungeon rewards do not exactly match participating owners"
                )
        report["rewards"] = [dict(row) for row in rewards]
        reports.append(report)
        wait_sql(
            store,
            "SELECT status,current_room FROM dungeon_room_runs WHERE instance_id=%s",
            (instance_id,),
            lambda row: row is not None
            and (
                row["current_room"] == order + 1
                if has_next
                else row["status"] == "completed"
            ),
            "Native fight victory did not advance the frozen room progression",
        )
        if has_next:
            next_room = config["topology"]["rooms"][order]
            cells = set(map(tuple, next_room["cells"]))
            for identity in identities:
                wait_sql(
                    store,
                    "SELECT map_id,instance_id,x,y,z FROM characters WHERE id=%s",
                    (identity,),
                    lambda row: row is not None
                    and row["map_id"] == map_id
                    and row["instance_id"] == instance_id
                    and (row["x"], row["y"], row["z"]) in cells,
                    "Victory did not automatically move every participating party member",
                )
            with store.connection() as db:
                receipts = db.execute(
                    "SELECT group_id FROM dungeon_room_spawn_receipts "
                    "WHERE instance_id=%s AND room_order=%s",
                    (instance_id, order + 1),
                ).fetchall()
            if len(receipts) != 1:
                raise AssertionError(
                    "Automatic room advancement did not spawn exactly one next group"
                )
            for peer, initial in zip(peers, return_bootstraps):
                await_room_bootstrap(peer, initial, map_id, cells)
            report["automatic_party_advance_verified"] = True
    if config["topology"].get("policy") == "local_accessible_anchor_policy":
        destination = config["topology"].get("completion_destination")
        if not isinstance(destination, dict):
            raise AssertionError("Automatic completion destination is absent")
        target = tuple(destination[key] for key in ("x", "y", "z"))
        for identity, peer, initial in zip(identities, peers, return_bootstraps):
            wait_sql(
                store,
                "SELECT map_id,instance_id,x,y,z FROM characters WHERE id=%s",
                (identity,),
                lambda row: row is not None
                and row["instance_id"] == 0
                and row["map_id"] == destination["map_id"]
                and (row["x"], row["y"], row["z"]) == target,
                "Final victory did not return every party member to the exterior",
            )
            await_room_bootstrap(peer, initial, destination["map_id"], {target})
        wait_sql(
            store,
            "SELECT status FROM dungeon_instances WHERE instance_id=%s",
            (instance_id,),
            lambda row: row["status"] == "closed",
            "Automatic final return did not close the dungeon instance",
        )
        reports[-1]["automatic_party_exit_verified"] = True
        return reports
    catalog = json.loads(
        (
            Path(__file__).parents[1] / "protocol/native-generic-teleporters.json"
        ).read_text()
    )
    final_room_cells = set(map(tuple, config["topology"]["rooms"][-1]["cells"]))
    exits = [
        (source, destination)
        for source in catalog
        if source["map_id"] == map_id
        and (int(source["x"]), int(source["y"]), int(source["z"])) in final_room_cells
        for destination in source["destinations"]
        if destination["map_id"] == config["route"]["entry_map_id"]
        and not destination["criterion"].strip()
        and destination["cyZ"] < 0
    ]
    if len(exits) != 1:
        raise AssertionError("Native exterior exit is absent or ambiguous")
    source, destination = exits[0]
    # Both owners approach while they still share the same world instance.
    for actor_index in (0, 1):
        approach_source(
            store,
            peers[actor_index],
            peers[1 - actor_index],
            identities[actor_index],
            map_id,
            source,
        )
    for actor_index, peer in enumerate(peers):
        peer.send(
            12296,
            struct.pack(">qiBi", source["id"], destination["destination_id"], 0, 2),
        )
        drain_bootstrap(peer, config["route"]["entry_map_id"])
        wait_sql(
            store,
            "SELECT instance_id FROM characters WHERE id=%s",
            (identities[actor_index],),
            lambda row: row["instance_id"] == 0,
            "Native exit did not return the member to the exterior",
        )
    wait_sql(
        store,
        "SELECT status FROM dungeon_instances WHERE instance_id=%s",
        (instance_id,),
        lambda row: row["status"] == "closed",
        "Final member departure did not close the run",
    )
    return reports


def drain_bootstrap(peer, expected_map):
    deadline = time.monotonic() + 30
    observed_maps, notices = [], []
    while time.monotonic() < deadline:
        try:
            (opcode, body), _ = peer.wait_any(
                (13974, 674), timeout=max(0.01, deadline - time.monotonic())
            )
        except AssertionError as error:
            raise AssertionError(
                f"No bootstrap for asset {expected_map}; observed assets={observed_maps}, "
                f"notices={notices}: {error}"
            ) from error
        if opcode == 674:
            notices.append(command_text(body))
            continue
        map_id, context = world_context(body)
        observed_maps.append(map_id)
        if map_id == expected_map:
            return context
        # Login and owned movement synchronization can leave exterior map
        # bootstraps queued. Keep the connection alive until the requested
        # native transition actually arrives; an old map is not a rejection.
        print(
            json.dumps(
                {"bootstrap_waiting_for": expected_map, "prior_asset_observed": map_id}
            ),
            flush=True,
        )
    raise AssertionError(
        f"No bootstrap for asset {expected_map}; "
        f"observed assets={observed_maps}, notices={notices}"
    )


def initial_reconnect_enabled(phase):
    if phase not in ("entry", "full"):
        raise ValueError("Unknown dungeon acceptance phase")
    # Full mode isolates normal party combat from the separately observed
    # peer-disconnection boundary during an in-dungeon leader reselection.
    return phase == "entry"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", choices=("entry", "full"), default="entry")
    parser.add_argument("--route-key", default="jalato_normal")
    args = parser.parse_args()
    phase = args.phase
    dbname = conninfo_to_dict(os.environ["WAKFU_DATABASE_URL"]).get("dbname", "")
    if not dbname.startswith("wakemu_candidate_smoke_"):
        raise ValueError("Requires disposable wakemu_candidate_smoke_* database")
    store = Store(
        os.environ["WAKFU_DATABASE_URL"],
        password_file=os.environ["WAKFU_DATABASE_PASSWORD_FILE"],
    )
    peers = []
    try:
        with store.connection() as db:
            config = active_configuration(db, args.route_key)
        route = config["route"]
        source = generic_transports.source(
            route["entry_map_id"], route["entry_object_id"]
        )
        graph = _walk_edges(route["entry_map_id"])
        approaches = [
            tuple(point[key] for key in ("x", "y", "z"))
            for point in source.get("approach_positions", ())
        ]
        if not approaches or any(cell not in graph for cell in approaches):
            raise AssertionError("Native entrance has no verified walkable approach")
        goal = approaches[0]
        adjacent = next((cell for cell in graph if goal in graph[cell]), None)
        if adjacent is None:
            raise AssertionError(
                "Native entrance approach has no incoming walkable edge"
            )
        owners = [create_character(store, role) for role in ("dungeona", "dungeonb")]
        for account, character in owners:
            # Isolated setup only; all entry/party/path requests use actual TLS.
            with store.connection() as db:
                db.execute(
                    "UPDATE characters SET map_id=%s,instance_id=0,x=%s,y=%s,z=%s WHERE id=%s",
                    (route["entry_map_id"], *adjacent, character["id"]),
                )
            character.update(
                map_id=route["entry_map_id"],
                instance_id=0,
                x=adjacent[0],
                y=adjacent[1],
                z=adjacent[2],
            )
            peer = Peer()
            peers.append(peer)
            login(store, peer, account, character, "dungeon")
            drain_bootstrap(peer, route["entry_map_id"])
            # The existing owned progression command refreshes native health,
            # XP and level together. No arbitrary player-stat SQL is used.
            command = b"!nivel 40"
            peer.send(12366, struct.pack(">H", len(command)) + command)
            reply, _ = peer.wait(674, timeout=20)
            if "Nivel 40 guardado" not in command_text(reply):
                raise AssertionError(
                    "Native level-40 fixture progression command failed"
                )
            peer.close()
            replacement = Peer()
            peers[-1] = replacement
            login(store, replacement, account, character, "dungeon-level-40-reselect")
            drain_bootstrap(replacement, route["entry_map_id"])
            with store.connection() as db:
                fresh = store.character(account["id"], character["id"], db)
                if fresh["level"] != 40 or fresh["hp"] != fresh["max_hp"]:
                    raise AssertionError(
                        "Level fixture did not refresh native level and health"
                    )
        first, second = peers
        a, b = owners[0][1], owners[1][1]
        first.send(1156, b"\x01" + struct.pack(">qqBq", 0, 0, 1, b["id"]))
        second.wait(1072, timeout=15)
        name = a["name"].encode()
        second.send(
            1031,
            b"\x01\x01"
            + bytes([len(name)])
            + name
            + b"\x00"
            + struct.pack(">q", a["id"]),
        )
        wait_sql(
            store,
            "SELECT party_id FROM player_party_members WHERE character_id=%s",
            (a["id"],),
            lambda row: row is not None,
            "Native party creation failed",
        )
        walk(first, second, a["id"], route["entry_map_id"], adjacent, goal)
        first.send(
            12296,
            struct.pack(
                ">qiBi", route["entry_object_id"], route["destination_id"], 0, 2
            ),
        )
        contexts = [drain_bootstrap(peer, route["start_map_id"]) for peer in peers]
        for context in contexts:
            expected = {
                key: value
                for key, value in config["context_policy"].items()
                if key in context
            }
            expected["allowed_ids"] = tuple(expected["allowed_ids"])
            if any(context[key] != value for key, value in expected.items()):
                raise AssertionError(
                    "Native dungeon context differs from frozen policy"
                )
        with store.connection() as db:
            positions = db.execute(
                "SELECT id,map_id,instance_id FROM characters WHERE id=ANY(%s) ORDER BY id",
                ([a["id"], b["id"]],),
            ).fetchall()
            instance_ids = {row["instance_id"] for row in positions}
            if len(instance_ids) != 1 or next(iter(instance_ids)) <= 0:
                raise AssertionError(
                    "Dungeon party does not share one private instance"
                )
            instance_id = next(iter(instance_ids))
            receipt = db.execute(
                "SELECT * FROM dungeon_room_spawn_receipts WHERE instance_id=%s AND room_order=1",
                (instance_id,),
            ).fetchone()
            if receipt is None:
                raise AssertionError("Native entry did not initialize the first room")
            group = db.execute(
                "SELECT members FROM combat_groups WHERE map_id=%s AND instance_id=%s AND group_id=%s",
                (route["start_map_id"], instance_id, receipt["group_id"]),
            ).fetchone()
            expected_count = sum(
                monster["count"]
                for monster in config["compiled_plan"]["rooms"][0]["monsters"]
            )
            if group is None or len(group["members"]) != expected_count:
                raise AssertionError("First room has the wrong native monster count")
        if initial_reconnect_enabled(phase):
            first.close()
            first = Peer()
            peers[0] = first
            login(store, first, owners[0][0], a, "dungeon-reconnect")
            drain_bootstrap(first, route["start_map_id"])
            with store.connection() as db:
                current = db.execute(
                    "SELECT instance_id FROM characters WHERE id=%s", (a["id"],)
                ).fetchone()
                if current["instance_id"] != instance_id:
                    raise AssertionError(
                        "Reconnect created or selected another dungeon run"
                    )
                replay = db.execute(
                    "SELECT group_id FROM dungeon_room_spawn_receipts WHERE instance_id=%s AND room_order=1",
                    (instance_id,),
                ).fetchall()
                if len(replay) != 1 or replay[0]["group_id"] != receipt["group_id"]:
                    raise AssertionError(
                        "Reconnect duplicated or replaced the first room spawn receipt"
                    )
        reports = []
        if phase == "full":
            reports = full_room_cycle(
                store, peers, [a["id"], b["id"]], config, instance_id
            )
            for index, peer in enumerate(list(peers)):
                peer.close()
                replacement = Peer()
                peers[index] = replacement
                login(
                    store,
                    replacement,
                    owners[index][0],
                    owners[index][1],
                    "dungeon-exterior-reconnect",
                )
                drain_bootstrap(replacement, route["entry_map_id"])
                if (
                    character_position(store, owners[index][1]["id"])[0]["instance_id"]
                    != 0
                ):
                    raise AssertionError(
                        "Exterior reconnect revived the completed private run"
                    )
            with store.connection() as db:
                for report in reports:
                    rewards = db.execute(
                        "SELECT character_id,xp,kamas FROM fight_rewards WHERE fight_id=%s ORDER BY character_id",
                        (report["fight_id"],),
                    ).fetchall()
                    if [dict(row) for row in rewards] != report["rewards"]:
                        raise AssertionError(
                            "Dungeon reward receipts changed during exterior reconnect"
                        )
        print(
            json.dumps(
                {
                    "passed": True,
                    "scope": phase,
                    "full_room_victory_progression_verified": phase == "full",
                    "initial_dungeon_reconnect_verified": phase == "entry",
                    "in_combat_reselect_verified": False,
                    "instance_id": instance_id,
                    "first_room_monsters": expected_count,
                    "room_reports": reports,
                }
            )
        )
    finally:
        for peer in peers:
            peer.close()
        stop_test_session_heartbeats()
        store.close()


if __name__ == "__main__":
    main()
