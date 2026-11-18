"""Play a regional mercenary contract through native board and wild combat TLS.

Uses an explicitly supplied isolated local QA character already eligible for the
board. It never creates monsters, changes HP/stats, assigns/completes quests,
overrides regions, rewrites progress or fabricates victories. The default plan is
read-only; --run walks the real world and fights actually available native groups.
"""

import argparse
from collections import deque
import json
import os
from pathlib import Path
import struct
import time

from tools.install_mission_bundle import local_connection
from tools.rii_departure_probe import ObservedPeer, Probe, login
from tools.hunter_archetype_tls_probe import NativeRun
from tools.candidate_friendly_duel_socket_smoke import placement
from wakfu_server.achievements import scoped_combat_missions, storage
from wakfu_server.combat_terrain import published_geometry
from wakfu_server.store import Store


def targets(store, scope):
    """Inspect actual available ordinary groups; never restore defeated groups."""
    from wakfu_server import territory_cells, monsters

    with store.connection() as db:
        groups = db.execute(
            "SELECT map_id,instance_id,group_id,members,revision FROM combat_groups "
            "WHERE map_id=ANY(%s) AND instance_id=0 AND status='available' ORDER BY group_id",
            (scope["maps"],),
        ).fetchall()
    found = []
    for group in groups:
        scene = {"map_id": group["map_id"], "instance_id": 0}
        pairs = [(m["id"], m["ref"]) for m in group["members"]]
        selected = scoped_combat_missions.qualifying_kills(
            scope,
            group["members"],
            pairs,
            scene,
            region_at=territory_cells.region_at,
            family_of=lambda breed: monsters.REFERENCES.get(breed, {}).get("family_id"),
        )
        if selected:
            found.append(dict(group, qualifying=len(selected)))
    return sorted(
        found,
        key=lambda group: (
            -group["qualifying"],
            len(group["members"]),
            group["group_id"],
        ),
    )


class RegionalProbe(Probe):
    def __init__(self, store, account_id, character_id, path):
        self.store, self.peer, self.path = store, None, path
        self.account = {"id": account_id}
        self.character = store.character(account_id, character_id)
        if self.character is None:
            raise ValueError("Missing owned local QA character")
        if character_id in (348, 352):
            raise ValueError("Human test characters are excluded")
        if self.character["breed"] != 19:
            raise ValueError(
                "This native melee driver currently requires an isolated Huppermage QA character"
            )
        self.receipt = {
            "account_id": account_id,
            "character_id": character_id,
            "scope": "native mercenary offer/selection and genuine original wild combat; no quest/world/stat fixtures",
            "fights": [],
            "checks": [],
        }

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.receipt, indent=2, default=str) + "\n")

    def walk(self, goal):
        goal = tuple(goal)
        here = tuple(self.current()[key] for key in ("x", "y", "z"))
        graph = published_geometry(self.current()["map_id"]).outgoing
        # Reuse the established native walk helper, splitting long paths into
        # nearby graph waypoints so its native unsigned-byte count stays valid.
        previous, pending = {here: None}, deque([here])
        while pending and goal not in previous:
            point = pending.popleft()
            for nxt in graph.get(point, ()):
                if nxt not in previous:
                    previous[nxt] = point
                    pending.append(nxt)
        if goal not in previous:
            raise AssertionError(("No native world walking path", here, goal))
        path, point = [], goal
        while point != here:
            path.append(point)
            point = previous[point]
        path.reverse()
        for index in range(0, len(path), 60):
            waypoint = path[min(index + 59, len(path) - 1)]
            super().walk(waypoint)
            deadline = time.monotonic() + 20
            while time.monotonic() < deadline:
                if tuple(self.current()[key] for key in ("x", "y", "z")) == waypoint:
                    break
                time.sleep(0.1)
            else:
                raise AssertionError(
                    ("Native world movement did not settle", waypoint, self.current())
                )

    def approach(self, group):
        graph = published_geometry(group["map_id"])
        here = tuple(self.current()[key] for key in ("x", "y", "z"))
        previous, pending = {here: None}, deque([here])
        while pending:
            point = pending.popleft()
            for monster in group["members"]:
                if (
                    abs(point[0] - monster["x"]) + abs(point[1] - monster["y"]) <= 1
                    and abs(point[2] - monster["z"]) <= 1
                ):
                    self.walk(point)
                    return monster
            for nxt in graph.outgoing.get(point, ()):
                if nxt not in previous:
                    previous[nxt] = point
                    pending.append(nxt)
        raise AssertionError("No real native approach to the available wild group")

    def fight(self, group):
        target = self.approach(group)
        with self.store.connection() as db:
            current = db.execute(
                "SELECT members,status FROM combat_groups WHERE map_id=%s AND instance_id=0 AND group_id=%s",
                (group["map_id"], group["group_id"]),
            ).fetchone()
        if current is None or current["status"] != "available":
            raise ValueError("The ordinary world group is no longer available")
        # Wandering may move a legitimate group while this player approaches.
        if current["members"] != group["members"]:
            group = dict(group, members=current["members"])
            target = self.approach(group)
        start = self.peer.mark()
        self.peer.send(
            13130,
            struct.pack(
                ">qiihB", target["id"], target["x"], target["y"], target["z"], 0
            ),
        )
        fight_id, _ = placement(self.peer.matching(13652, start, timeout=30))
        runner = NativeRun(self.store, self.account, self.character, self.receipt)
        runner.peer, runner.fight_id = self.peer, fight_id
        runner.wire_cursor, runner.native_global_turn = start, 0
        self.peer.send(12523, b"\x01")
        casts, deadline = 0, time.monotonic() + 180
        while time.monotonic() < deadline:
            snap = runner.ready_for_input()
            if snap["phase"] == "finished":
                break
            hero = snap["actors"][str(self.character["id"])]
            enemies = [
                a
                for a in snap["actors"].values()
                if a["team"] != hero["team"] and a["hp"] > 0
            ]
            if not enemies:
                break
            here = tuple(hero["position"])
            enemy = min(
                enemies,
                key=lambda a: abs(a["position"][0] - here[0])
                + abs(a["position"][1] - here[1]),
            )
            target_cell = tuple(enemy["position"])
            if hero["ap"] < 2:
                runner.end_turn()
                continue
            if abs(here[0] - target_cell[0]) + abs(here[1] - target_cell[1]) == 1:
                try:
                    runner.cast(5562, target_cell, class_spell=True)
                except AssertionError as error:
                    if "maximum casts per turn" not in str(error):
                        raise
                    runner.end_turn()
                else:
                    casts += 1
                continue
            graph = {}
            for a, b in snap["edges"]:
                graph.setdefault(tuple(a), []).append(tuple(b))
            occupied = {
                tuple(a["position"])
                for a in snap["actors"].values()
                if a["hp"] > 0 and tuple(a["position"]) != here
            }
            previous, pending, goal = {here: None}, deque([here]), None
            while pending:
                point = pending.popleft()
                if abs(point[0] - target_cell[0]) + abs(point[1] - target_cell[1]) == 1:
                    goal = point
                    break
                for nxt in graph.get(point, ()):
                    if nxt not in previous and nxt not in occupied:
                        previous[nxt] = point
                        pending.append(nxt)
            if goal is None:
                raise AssertionError("No native reachable melee position")
            path = []
            while goal != here:
                path.append(goal)
                goal = previous[goal]
            path.reverse()
            if hero["mp"] <= 0:
                runner.end_turn()
            else:
                runner.action(
                    12161,
                    struct.pack(">q", self.character["id"])
                    + b"".join(
                        struct.pack(">iih", *point) for point in path[: hero["mp"]]
                    ),
                    label="native wild encounter movement",
                )
        snap = runner.checkpoint()
        if (
            snap["phase"] != "finished"
            or snap["winner"] != snap["actors"][str(self.character["id"])]["team"]
        ):
            raise AssertionError("The authentic wild encounter was not won")
        start = self.peer.mark()
        self.peer.send(12925, struct.pack(">iB", fight_id, 1))
        self.peer.matching(
            13046,
            start,
            lambda body: len(body) == 15
            and struct.unpack_from(">q", body)[0] == self.character["id"]
            and body[10] == 17
            and struct.unpack_from(">i", body, 11)[0] == -1,
            timeout=30,
        )
        self.receipt["fights"].append(
            {"fight_id": fight_id, "casts": casts, "original_group": group}
        )
        self.save()

    def run(self, scope, *, maximum_fights=5):
        if not targets(self.store, scope):
            raise ValueError(
                "No naturally available qualifying wild group; no population or quest fixture was created"
            )
        if self.current()["map_id"] != 527 or self.current()["instance_id"] != 0:
            raise ValueError(
                "Move the isolated eligible QA character to public Astrub before this probe"
            )
        state = self.progress()
        if scope["quest_id"] in state["completed"]:
            raise ValueError(
                "Use an isolated character that has not completed this contract"
            )
        self.peer = ObservedPeer()
        login(self.store, self.peer, self.account, self.character)
        if scope["quest_id"] not in state["running"]:
            self.walk((18, 45, 0))
            self.peer.send(12870, struct.pack(">qHH", 23865, 0, 0))
            self.peer.send(12864, struct.pack(">iqB", scope["quest_id"], -1, 1))
            deadline = time.monotonic() + 10
            while scope["quest_id"] not in self.progress()["running"]:
                if time.monotonic() > deadline:
                    raise AssertionError(
                        "Native board selection did not accept the contract"
                    )
                time.sleep(0.1)
        self.receipt["checks"].append(
            "native board admission earned without quest-state fixture"
        )
        for _ in range(maximum_fights):
            before = self.progress()
            if scope["quest_id"] in before["completed"]:
                break
            available = targets(self.store, scope)
            if not available:
                raise ValueError(
                    "Qualifying wild population exhausted before completion"
                )
            self.fight(available[0])
            after = self.progress()
            if after["variables"].get(str(scope["variable_id"]), 0) <= before[
                "variables"
            ].get(str(scope["variable_id"]), 0):
                raise AssertionError(
                    "Genuine regional victory did not advance the native counter"
                )
            self.receipt["checks"].append(
                {"native_counter": after["variables"].get(str(scope["variable_id"]))}
            )
        final = self.progress()
        if scope["quest_id"] not in final["completed"]:
            raise AssertionError(
                "Regional contract did not complete through natural victories"
            )
        with self.store.connection() as db:
            rewards = db.execute(
                "SELECT reward_key FROM character_achievement_reward_outbox WHERE character_id=%s AND achievement_id=%s",
                (self.character["id"], scope["quest_id"]),
            ).fetchall()
        if len(rewards) != 2:
            raise AssertionError(
                ("Expected two native one-time reward entitlements", rewards)
            )
        self.receipt.update(
            success=True,
            final_native_counter=final["variables"][str(scope["variable_id"])],
            native_rewards=len(rewards),
        )
        self.save()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="store_true")
    parser.add_argument("--account-id", type=int)
    parser.add_argument("--character-id", type=int)
    parser.add_argument(
        "--receipt",
        type=Path,
        default=Path(".local-state/wakemu/qa/regional-contract.json"),
    )
    args = parser.parse_args()
    local_connection(os.environ.get("WAKFU_DATABASE_URL", ""))
    store = Store(
        os.environ["WAKFU_DATABASE_URL"],
        password_file=os.environ.get("WAKFU_DATABASE_PASSWORD_FILE"),
    )
    probe = None
    try:
        scope = scoped_combat_missions.declarations()["scopes"][0]
        if not args.run:
            print(
                json.dumps(
                    {"scope": scope, "available_targets": targets(store, scope)},
                    default=str,
                )
            )
            return
        if args.account_id is None or args.character_id is None:
            parser.error(
                "--run requires an explicitly isolated --account-id and --character-id"
            )
        probe = RegionalProbe(store, args.account_id, args.character_id, args.receipt)
        probe.run(scope)
        print(json.dumps(probe.receipt, default=str))
    except BaseException as error:
        if probe is not None:
            probe.receipt["error"] = repr(error)
            probe.save()
        raise
    finally:
        if probe is not None and probe.peer is not None:
            probe.peer.close()
        store.close()


if __name__ == "__main__":
    main()
