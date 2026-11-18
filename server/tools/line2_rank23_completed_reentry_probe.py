"""Verify native Dungeon 65 reentry after completed quest 2139 without fights.

This probe uses an existing QA character only. It never changes quest state,
inventory, combat statistics or dungeon progress. Each pass enters through the
reviewed native source and leaves through the normal ``!exitdungeon`` command,
which uses the pinned dungeon-owned exterior return transaction.

Run after the rank23 journey has genuinely completed 2139 and returned to map
546. Do not start it while another journey or dungeon session is active.
"""

import argparse
import json
import os
from pathlib import Path
import struct
import time

from tools.install_mission_bundle import local_connection
from tools.rii_departure_probe import ObservedPeer, login
from protocol_codec import DIRECTIONS
from wakfu_server import dungeon_instances, dungeon_runtime_config
from wakfu_server.combat_terrain import published_geometry
from wakfu_server.store import Store


ROUTE_KEY = "native_dungeon_65"
ENTRY_MAP = 546
ENTRY_OBJECT = 24026
ENTRY_DESTINATION = 2053
ENTRY_APPROACH = (-49, 16, -1)
EXTERIOR_MAP = 546
QUEST_ID = 2139
OBJECTIVE_ID = 4231
EXIT_COMMAND = b"!exitdungeon"
RECEIPT_ROOT = Path(".local-state/wakemu/qa")


def _wait_until(read, predicate, label, timeout=30):
    deadline = time.monotonic() + timeout
    latest = None
    while time.monotonic() < deadline:
        latest = read()
        if predicate(latest):
            return latest
        time.sleep(0.1)
    raise AssertionError(("Timed out waiting for " + label, latest))


def _progress(store, character_id):
    with store.connection() as db:
        row = db.execute(
            "SELECT state FROM character_achievement_progress WHERE character_id=%s",
            (character_id,),
        ).fetchone()
    if row is None or not isinstance(row["state"], dict):
        raise ValueError("The QA character has no persisted achievement progress")
    return row["state"]


def _reward_rows(store, character_id):
    with store.connection() as db:
        return db.execute(
            "SELECT achievement_id,cycle_key,reward_key,payload,delivered_at IS NOT NULL AS delivered "
            "FROM character_achievement_reward_outbox WHERE character_id=%s "
            "AND achievement_id=ANY(%s) ORDER BY achievement_id,cycle_key,reward_key",
            (character_id, [2150, 2151, QUEST_ID]),
        ).fetchall()


def preflight(store, account_id, character_id):
    character = store.character(account_id, character_id)
    if character is None:
        raise ValueError("The supplied QA character does not exist")
    if character.get("map_id") != EXTERIOR_MAP or character.get("instance_id") != 0:
        raise ValueError("The character must be outside Dungeon 65 on public map 546")
    state = _progress(store, character_id)
    if QUEST_ID not in set(state.get("completed", ())):
        raise ValueError("Quest 2139 must already be naturally completed")
    if OBJECTIVE_ID not in set(state.get("objectives", ())):
        raise ValueError("Completed quest 2139 lacks durable objective 4231")
    with store.connection() as db:
        company = db.execute(
            "SELECT party_id FROM player_party_members WHERE character_id=%s",
            (character_id,),
        ).fetchone()
        active_membership = db.execute(
            "SELECT m.instance_id FROM dungeon_instance_members m "
            "JOIN dungeon_instances i USING(instance_id) "
            "WHERE m.character_id=%s AND m.status='active' AND i.status='active'",
            (character_id,),
        ).fetchone()
    if company is not None:
        raise ValueError("Use a solo QA character with no existing party membership")
    if active_membership is not None:
        raise ValueError("The character already belongs to an active dungeon run")

    dungeon_instances.load_runtime_routes(store)
    route = dungeon_instances.route(ROUTE_KEY)
    if (
        route.entry_map_id != ENTRY_MAP
        or route.entry_object_id != ENTRY_OBJECT
        or route.destination_id != ENTRY_DESTINATION
    ):
        raise ValueError(
            "The active Dungeon 65 native route differs from the reviewed entrance"
        )
    with store.connection() as db:
        configuration = dungeon_runtime_config.active_configuration(db, ROUTE_KEY)
        exits = configuration["topology"].get("physical_exit_objects", ())
        if configuration["topology"].get(
            "policy"
        ) != "local_accessible_anchor_policy" or not configuration["topology"].get(
            "completion_destination"
        ):
            raise ValueError(
                "Dungeon 65 no longer has the reviewed owned exterior return"
            )
    rewards = _reward_rows(store, character_id)
    if any(not row["delivered"] for row in rewards):
        raise ValueError("A rank23 native reward is still pending delivery")
    return {
        "character": character,
        "route": route,
        "configuration": configuration,
        "progress": state,
        "rewards": rewards,
        "physical_room1_exits": len(
            [row for row in exits if row.get("room_order") == 1]
        ),
    }


def _walk_to_entry(store, peer, account_id, character_id, goal):
    geometry = published_geometry(ENTRY_MAP)
    current = store.character(account_id, character_id)
    start = tuple(current[key] for key in ("x", "y", "z"))
    goal = tuple(goal)
    previous, pending = {start: None}, [start]
    for point in pending:
        if point == goal:
            break
        for target in geometry.outgoing.get(point, ()):
            if target not in previous:
                previous[target] = point
                pending.append(target)
    if goal not in previous:
        raise AssertionError(("No native walk to the dungeon entrance", start, goal))
    path, point = [], goal
    while point != start:
        path.append(point)
        point = previous[point]
    path.reverse()
    directions = {(dx, dy): key for key, (_, dx, dy) in DIRECTIONS.items()}
    for offset in range(0, len(path), 60):
        segment = path[offset : offset + 60]
        here = tuple(
            store.character(account_id, character_id)[k] for k in ("x", "y", "z")
        )
        encoded = bytearray()
        for cell in segment:
            encoded.append(
                (directions[(cell[0] - here[0], cell[1] - here[1])] << 5)
                | ((cell[2] - here[2]) & 31)
            )
            here = cell
        start_cell = tuple(
            store.character(account_id, character_id)[k] for k in ("x", "y", "z")
        )
        peer.send(13331, struct.pack(">iiihB", 0, *start_cell, len(segment)) + encoded)
        target = segment[-1]
        _wait_until(
            lambda: store.character(account_id, character_id),
            lambda row: tuple(row[k] for k in ("x", "y", "z")) == target,
            f"native exterior walk to {target}",
            timeout=20,
        )


def _enter(store, peer, account_id, character_id, previous_instance):
    _walk_to_entry(store, peer, account_id, character_id, ENTRY_APPROACH)
    mark = peer.mark()
    peer.send(
        12296,
        struct.pack(">qiBi", ENTRY_OBJECT, ENTRY_DESTINATION, 0, 2),
    )
    peer.matching(13974, mark, timeout=30)
    peer.send(12449)
    current = _wait_until(
        lambda: store.character(account_id, character_id),
        lambda row: row["map_id"] == 902 and row["instance_id"] > 0,
        "native dungeon entry commit",
        timeout=30,
    )
    instance_id = current["instance_id"]
    if instance_id == previous_instance:
        raise AssertionError("Reentry reused the prior closed dungeon instance")
    with store.connection() as db:
        room = db.execute(
            "SELECT current_room,status FROM dungeon_room_runs WHERE instance_id=%s",
            (instance_id,),
        ).fetchone()
    if room != {"current_room": 1, "status": "active"}:
        raise AssertionError(("Reentry did not start at room 1", room))
    return instance_id


def _normal_exit(
    store, peer, account_id, character_id, instance_id, expected_destination
):
    peer.send(12366, struct.pack(">H", len(EXIT_COMMAND)) + EXIT_COMMAND)
    exterior = _wait_until(
        lambda: store.character(account_id, character_id),
        lambda row: row["map_id"] == EXTERIOR_MAP and row["instance_id"] == 0,
        "normal owned dungeon exit",
        timeout=40,
    )

    def current_exit_state():
        with store.connection() as db:
            membership = db.execute(
                "SELECT status FROM dungeon_instance_members WHERE instance_id=%s AND character_id=%s",
                (instance_id, character_id),
            ).fetchone()
            run = db.execute(
                "SELECT status FROM dungeon_instances WHERE instance_id=%s",
                (instance_id,),
            ).fetchone()
            pending = db.execute(
                "SELECT count(*) AS count FROM dungeon_transition_outbox "
                "WHERE instance_id=%s AND character_id=%s AND status='pending'",
                (instance_id, character_id),
            ).fetchone()["count"]
            company = db.execute(
                "SELECT party_id FROM player_party_members WHERE character_id=%s",
                (character_id,),
            ).fetchone()
        return membership, run, pending, company

    membership, run, pending, company = _wait_until(
        current_exit_state,
        lambda value: value[0] is not None
        and value[0]["status"] == "returned"
        and value[1] is not None
        and value[1]["status"] == "closed"
        and value[2] == 0
        and value[3] is None,
        "membership, transition and solo company cleanup",
        timeout=30,
    )
    if membership is None or membership["status"] != "returned":
        raise AssertionError(
            ("Normal exit did not return dungeon membership", membership)
        )
    if run is None or run["status"] != "closed":
        raise AssertionError(("Normal exit did not close the run", run))
    if pending:
        raise AssertionError(("Normal exit transition remains pending", pending))
    if company is not None:
        raise AssertionError(
            ("Solo dungeon company membership remained after exit", company)
        )
    position = {key: exterior[key] for key in ("map_id", "instance_id", "x", "y", "z")}
    expected_position = {
        **{key: expected_destination[key] for key in ("map_id", "x", "y", "z")},
        "instance_id": 0,
    }
    if position != expected_position:
        raise AssertionError(
            (
                "Normal exit differs from the pinned owned destination",
                expected_position,
                position,
            )
        )
    return position


def run(store, account_id, character_id, receipt_path):
    ready = preflight(store, account_id, character_id)
    resolved_path = receipt_path.resolve()
    private_root = RECEIPT_ROOT.resolve()
    if resolved_path != private_root and private_root not in resolved_path.parents:
        raise ValueError("QA receipts must remain under .local-state/wakemu/qa")
    if receipt_path.exists():
        raise ValueError("Refusing to overwrite an existing private QA receipt")
    account = {"id": account_id}
    peer = ObservedPeer()
    result = {
        "account_id": account_id,
        "character_id": character_id,
        "scope": "completed 2139 native Dungeon 65 entry, normal owned exit, reentry, normal exit; no combat or quest writes",
        "prior_2139_completed": True,
        "room1_physical_exit_objects": ready["physical_room1_exits"],
        "journey": [],
    }
    instance_id = 0
    try:
        login(store, peer, account, ready["character"])
        first = _enter(store, peer, account_id, character_id, 0)
        instance_id = first
        result["journey"].append({"entry": 1, "instance_id": first})
        result["journey"].append(
            {
                "exit": 1,
                "position": _normal_exit(
                    store,
                    peer,
                    account_id,
                    character_id,
                    first,
                    ready["configuration"]["topology"]["completion_destination"],
                ),
            }
        )
        instance_id = 0
        if (
            _progress(store, character_id) != ready["progress"]
            or _reward_rows(store, character_id) != ready["rewards"]
        ):
            raise AssertionError(
                "Completed quest state or rewards changed after the first reentry exit"
            )
        second = _enter(store, peer, account_id, character_id, first)
        instance_id = second
        result["journey"].append({"entry": 2, "instance_id": second})
        result["journey"].append(
            {
                "exit": 2,
                "position": _normal_exit(
                    store,
                    peer,
                    account_id,
                    character_id,
                    second,
                    ready["configuration"]["topology"]["completion_destination"],
                ),
            }
        )
        instance_id = 0

        progress_before = ready["progress"]
        rewards_before = ready["rewards"]
        peer.close()
        peer = ObservedPeer()
        generation = login(
            store, peer, account, store.character(account_id, character_id)
        )
        progress_after = _progress(store, character_id)
        rewards_after = _reward_rows(store, character_id)
        if progress_after != progress_before:
            raise AssertionError("Completed quest state changed across dungeon reentry")
        if rewards_after != rewards_before:
            raise AssertionError(
                "Completed quest reward receipts changed across reentry"
            )
        result.update(
            generation=str(generation),
            quest_completed=True,
            reward_receipts_unchanged=True,
            next_character_selection=True,
            success=True,
        )
        receipt_path.parent.mkdir(parents=True, exist_ok=True)
        receipt_path.write_text(json.dumps(result, indent=2, default=str) + "\n")
        return result
    except BaseException as error:
        result["error"] = repr(error)
        current = store.character(account_id, character_id)
        if current is not None and current.get("instance_id", 0) > 0:
            instance_id = current["instance_id"]
        if (
            instance_id
            and current is not None
            and current.get("instance_id") == instance_id
            and not peer.closed.is_set()
        ):
            try:
                result["cleanup_exit"] = _normal_exit(
                    store,
                    peer,
                    account_id,
                    character_id,
                    instance_id,
                    ready["configuration"]["topology"]["completion_destination"],
                )
            except BaseException as cleanup_error:
                result["cleanup_error"] = repr(cleanup_error)
        receipt_path.parent.mkdir(parents=True, exist_ok=True)
        receipt_path.write_text(json.dumps(result, indent=2, default=str) + "\n")
        raise
    finally:
        peer.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--account-id", type=int, required=True)
    parser.add_argument("--character-id", type=int, required=True)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--preflight", action="store_true")
    mode.add_argument("--run", action="store_true")
    parser.add_argument("--receipt", type=Path)
    args = parser.parse_args()
    local_connection(os.environ.get("WAKFU_DATABASE_URL", ""))
    store = Store(
        os.environ["WAKFU_DATABASE_URL"],
        password_file=os.environ.get("WAKFU_DATABASE_PASSWORD_FILE"),
    )
    try:
        checked = preflight(store, args.account_id, args.character_id)
        if args.preflight:
            print(
                json.dumps(
                    {
                        "ready": True,
                        "route": ROUTE_KEY,
                        "room1_physical_exit_objects": checked["physical_room1_exits"],
                        "completed_objective": OBJECTIVE_ID,
                    }
                )
            )
            return
        receipt = args.receipt or (
            RECEIPT_ROOT
            / f"line2-rank23-reentry-{args.account_id}-{args.character_id}.json"
        )
        print(
            json.dumps(
                run(store, args.account_id, args.character_id, receipt),
                indent=2,
                default=str,
            )
        )
    finally:
        store.close()


if __name__ == "__main__":
    main()
