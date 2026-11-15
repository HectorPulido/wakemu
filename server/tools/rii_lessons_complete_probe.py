"""Play seven Rii lessons over local TLS with one persistent QA character.

Only the initial arrival prerequisites are fixtures. Every subsequent objective
and reward must be earned by native dialogue, movement, casts and turn events.
Private receipts include packet evidence and progress before/after reconnect.
"""

import copy
import json
import os
from pathlib import Path
import queue
import secrets
import struct
import threading
import time
from collections import deque
from datetime import datetime, timezone

from psycopg.conninfo import conninfo_to_dict
from psycopg.types.json import Jsonb

from tools.rii_lesson_parity_probe import LocalPeer, OBJECTIVES
from tools.candidate_friendly_duel_socket_smoke import login, placement
from wakfu_server.achievements import storage
from wakfu_server.combat_protocol_reconstruction import decode_packet
from wakfu_server.combat_effect_targets import area_offsets
from wakfu_server.progression import level_xp
from wakfu_server.rii_lesson_spell_catalog import catalog
from wakfu_server.store import Store
from wakfu_server.spells import owned_spell_records, spell_inventory

AIRYNA = -1706442046308339
GUIDES = (22409, 22494, 22495, 22507, 22508, 22516, 22517)
SUCCESS_GUIDES = tuple(range(22540, 22547))


class ObservedPeer(LocalPeer):
    def __init__(self):
        self.observation_lock = threading.Lock()
        self.records = []
        self.states = {}
        self.areas = {}
        self.stats = {}
        super().__init__()

    def _read(self):
        try:
            while not self.closed.is_set():
                size = struct.unpack(">I", self._exact(4))[0]
                if not 6 <= size <= 327670:
                    raise AssertionError("Invalid server frame size %s" % size)
                raw = self._exact(size - 4)
                opcode, body = struct.unpack_from(">H", raw)[0], raw[2:]
                self.observe(opcode, body)
                self.events.put((opcode, body))
        except Exception as error:
            if not self.closed.is_set():
                self.events.put((None, error))

    def observe(self, opcode, body):
        with self.observation_lock:
            self.records.append((opcode, body))
            if opcode == 13726 and len(body) == 20:
                self.areas.pop(struct.unpack_from(">q", body, 12)[0], None)
            if opcode in (12613, 13497, 13560):
                try:
                    data = decode_packet(opcode, body)
                    effect = data.get("effect", {})
                    if effect.get("family") == 310:
                        if opcode == 13560:
                            self.states.pop(effect["uid"], None)
                        else:
                            self.states[effect["uid"]] = effect
                    if effect.get("family") in (308, 315) and opcode != 13560:
                        self.areas[effect["area_uid"]] = effect
                except ValueError:
                    pass
            if opcode in (12873, 13912) and len(body) > 15:
                identity = struct.unpack_from(">q", body, 4)[0]
                offset = 14 if opcode == 12873 else 16
                state = body[offset:]
                if not state:
                    return
                start = {2: 1 + 20 + 10, 3: 1 + 8 + 20 + 10, 40: 1}.get(state[0])
                if start is None or len(state) < start + 2:
                    return
                count = struct.unpack_from(">H", state, start)[0]
                if start + 2 + 17 * count > len(state):
                    return
                values = {}
                for i in range(count):
                    pc, current, minimum, maximum, percentage = struct.unpack_from(
                        ">Biiii", state, start + 2 + i * 17
                    )
                    values[pc] = current
                self.stats[identity] = values

    def view(self):
        with self.observation_lock:
            return copy.deepcopy((self.states, self.areas, self.stats))

    def reset_fight(self):
        with self.observation_lock:
            self.states.clear()
            self.areas.clear()
            self.stats.clear()


class Run:
    def __init__(self, store, account, char, receipt):
        self.store, self.account, self.char, self.receipt = (
            store,
            account,
            char,
            receipt,
        )
        self.peer = None
        self.fight_id = None
        self.targets = []
        self.index = None

    def connect(self):
        self.peer = ObservedPeer()
        self.generation = login(
            self.store, self.peer, self.account, self.char, "rii-continuous"
        )

    def checkpoint(self):
        with self.store.connection() as db:
            row = db.execute(
                "SELECT snapshot FROM fight_checkpoints WHERE fight_id=%s",
                (self.fight_id,),
            ).fetchone()
        return row["snapshot"] if row else None

    def progress(self):
        with self.store.connection() as db:
            return storage.load_locked(db, self.char["id"])

    def poll(self, predicate, *, timeout=12, label="state"):
        deadline = time.monotonic() + timeout
        last = None
        while time.monotonic() < deadline:
            last = self.checkpoint()
            if last and predicate(last):
                return last
            time.sleep(0.07)
        raise AssertionError("Timeout %s; last=%s" % (label, last))

    def ready_for_input(self):
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            snap = self.checkpoint()
            if not snap:
                time.sleep(0.07)
                continue
            if snap["phase"] == "finished":
                return snap
            runtime = snap.get("runtime", {})
            ack = runtime.get("awaiting_ack")
            if ack is not None:
                self.peer.send(13510, struct.pack(">i", ack))
                time.sleep(0.1)
                continue
            if (
                snap["phase"] == "active"
                and snap["order"][snap["turn_index"]] == self.char["id"]
            ):
                return snap
            time.sleep(0.07)
        raise AssertionError("No owned input turn")

    def action(self, opcode, body, *, label):
        before = self.ready_for_input()
        if before["phase"] == "finished":
            return before
        prior = before.get("runtime", {}).get("action_id", 0)
        prior_native = before.get("runtime", {}).get("native_action_id", 0)
        with self.peer.observation_lock:
            wire_start = len(self.peer.records)
        self.peer.send(opcode, body)
        deadline = time.monotonic() + 6
        while time.monotonic() < deadline:
            after = self.checkpoint()
            if after and (
                after["phase"] == "finished"
                or after.get("runtime", {}).get("action_id", 0) > prior
                or after.get("runtime", {}).get("native_action_id", 0) > prior_native
                or after.get("actors") != before.get("actors")
            ):
                time.sleep(0.08)
                return after
            with self.peer.observation_lock:
                rejected = [
                    raw for op, raw in self.peer.records[wire_start:] if op == 674
                ]
            if rejected:
                raise AssertionError(
                    "Action rejected %s: %s"
                    % (label, rejected[-1].decode("utf8", "replace"))
                )
            time.sleep(0.07)
        messages = []
        with self.peer.observation_lock:
            for op, raw in self.peer.records[-12:]:
                if op in (674, 349):
                    messages.append(raw.hex())
        raise AssertionError("Action rejected %s; messages=%s" % (label, messages))

    def cast(self, spell, cell, *, class_spell=False):
        uid = (self.char["id"] << 32) | spell if class_spell else spell
        return self.action(
            13260,
            struct.pack(">qqiih", self.char["id"], uid, *cell),
            label="cast %s %s" % (spell, cell),
        )

    def end_turn(self):
        snap = self.ready_for_input()
        if snap["phase"] == "finished":
            return snap
        self.peer.send(
            12403,
            struct.pack(">qh", self.char["id"], snap.get("native_timeline_round", 1)),
        )
        self.poll(
            lambda value: value["phase"] == "finished"
            or value.get("runtime", {}).get("awaiting_ack") is not None,
            label="turn end",
        )
        return self.ready_for_input()

    def move(self, goal):
        goal = tuple(goal)
        for _ in range(8):
            snap = self.ready_for_input()
            if snap["phase"] == "finished":
                return snap
            hero = snap["actors"][str(self.char["id"])]
            here = tuple(hero["position"])
            if here == goal:
                return snap
            occupied = {
                tuple(a["position"])
                for k, a in snap["actors"].items()
                if int(k) != self.char["id"] and a["hp"] > 0
            }
            _, areas, _ = self.peer.view()
            occupied.update(
                tuple(a["cell"]) for a in areas.values() if a.get("prototype") == 1808
            )
            graph = {}
            for left, right in snap["edges"]:
                graph.setdefault(tuple(left), []).append(tuple(right))
            previous = {here: None}
            todo = deque([here])
            while todo and goal not in previous:
                left = todo.popleft()
                for right in graph.get(left, ()):
                    if right not in occupied and right not in previous:
                        previous[right] = left
                        todo.append(right)
            if goal not in previous:
                raise AssertionError("No path %s -> %s" % (here, goal))
            path, point = [], goal
            while point != here:
                path.append(point)
                point = previous[point]
            path.reverse()
            count = min(len(path), hero["mp"])
            if count == 0:
                self.end_turn()
                continue
            segment = path[:count]
            self.action(
                12161,
                struct.pack(">q", self.char["id"])
                + b"".join(struct.pack(">iih", *point) for point in segment),
                label="move %s" % (segment,),
            )
        raise AssertionError("Movement budget exhausted")

    def start(self, index):
        self.index = index
        with self.peer.observation_lock:
            self.start_wire_index = len(self.peer.records)
        self.peer.reset_fight()
        if index == 0:
            self.peer.send(13222, struct.pack(">qq", AIRYNA, 1390))
            body, _ = self.peer.wait(12969, timeout=12)
            assert struct.unpack_from(">i", body)[0] == 5755
            self.peer.send(12058, struct.pack(">ii", 5755, 13258))
            self.peer.wait(12218, timeout=12)
            self.peer.send(12058, struct.pack(">ii", 5756, 13260))
        else:
            self.peer.send(13222, struct.pack(">qq", AIRYNA, 1389))
            body, _ = self.peer.wait(12969, timeout=12)
            assert struct.unpack_from(">i", body)[0] == 5787
            self.peer.send(12058, struct.pack(">ii", 5787, 13322 + index))
        completed_fights = {row["fight_id"] for row in self.receipt["lessons"]}
        while True:
            body, _ = self.peer.wait(13652, timeout=45)
            self.fight_id, positions = placement(body)
            if self.fight_id not in completed_fights:
                break
        self.targets = [
            identity for identity in positions if identity != self.char["id"]
        ]
        with self.peer.observation_lock:
            admission = list(self.peer.records[self.start_wire_index :])
        seen_descriptors = set()
        for opcode, payload in admission:
            if opcode == 13652 and placement(payload)[0] == self.fight_id:
                break
            if opcode != 12608:
                continue
            offset = 2
            for _ in range(payload[1]):
                actor_type, identity, size = struct.unpack_from(">BqH", payload, offset)
                offset += 11
                descriptor = payload[offset : offset + size]
                assert len(descriptor) == size
                if actor_type == 1 and identity in self.targets:
                    assert descriptor[0] == 11
                    assert struct.unpack_from(">q", descriptor, 1)[0] == identity
                    seen_descriptors.add(identity)
                offset += size
        assert set(self.targets) <= seen_descriptors, (
            "Native target descriptors missing before placement",
            self.targets,
            sorted(seen_descriptors),
        )
        self.receipt.setdefault("target_descriptors_before_placement", []).append(
            {"fight_id": self.fight_id, "actor_ids": sorted(seen_descriptors)}
        )
        while True:
            guide, _ = self.peer.wait(13411, timeout=15)
            if struct.unpack_from(">i", guide, 1)[0] == GUIDES[self.index]:
                break
        with self.peer.observation_lock:
            published = self.peer.records[self.start_wire_index :]
            placement_index = next(
                i
                for i, (opcode, payload) in enumerate(published)
                if opcode == 13652 and placement(payload)[0] == self.fight_id
            )
            guide_index = next(
                i
                for i, (opcode, payload) in enumerate(published)
                if opcode == 13411
                and struct.unpack_from(">i", payload, 1)[0] == GUIDES[self.index]
            )
            assert guide_index > placement_index, "Guide preceded admitted placement"
        self.start_xp = self.store.character(self.account["id"], self.char["id"])["xp"]
        self.receipt["pending_xp"] = {"fight_id": self.fight_id, "xp": self.start_xp}
        self.peer.send(12523, b"\x01")
        while True:
            body, _ = self.peer.wait(13482, timeout=45)
            if struct.unpack_from(">i", body)[0] == self.fight_id:
                break
        self.ready_for_input()
        print("START", index, self.fight_id, positions, flush=True)

    def solve(self):
        if self.index == 0:
            self.move((0, -14, 0))
            self.cast(5562, (0, -13, 0), class_spell=True)
            return
        for attempt in range(40):
            snap = self.ready_for_input()
            if snap["phase"] == "finished":
                return
            target = snap["actors"][str(self.targets[0])]
            target_cell = tuple(target["position"])
            states, areas, stats = self.peer.view()
            if self.index == 1:
                values = stats.get(self.targets[0], {})
                resists = {pc: values[pc] for pc in (28, 29, 30, 31) if pc in values}
                assert len(resists) == 4, ("No resistance snapshot", values)
                self.cast(
                    {28: 7963, 29: 7964, 30: 7965, 31: 7966}[
                        min(resists, key=resists.get)
                    ],
                    target_cell,
                )
            elif self.index == 2:
                count = (100 - target["hp"]) // 25
                self.move(
                    (target_cell[0], target_cell[1] + (2 if count % 2 == 0 else 3), 0)
                )
                self.cast(7967, target_cell)
            elif self.index == 3:
                self.solve_los(snap, target_cell)
            elif self.index == 4:
                living = {
                    tuple(row["position"])
                    for identity, row in snap["actors"].items()
                    if int(identity) in self.targets and row["hp"] > 0
                }
                choices = []
                hero = snap["actors"][str(self.char["id"])]["position"]
                for spell, ref in ((7969, 367103), (7970, 367142), (7971, 367145)):
                    offsets = set(area_offsets(catalog()["effects"][str(ref)]))
                    for cell in map(tuple, snap["walkable"]):
                        if 2 <= abs(cell[0] - hero[0]) + abs(
                            cell[1] - hero[1]
                        ) <= 16 and living <= {
                            (cell[0] + dx, cell[1] + dy, cell[2]) for dx, dy in offsets
                        }:
                            choices.append((spell, cell))
                assert choices, living
                self.cast(*choices[0])
            elif self.index == 5:
                self.solve_movement(snap, target_cell, states, areas)
            else:
                target_states = {
                    e["state_id"]
                    for e in states.values()
                    if e.get("target") == self.targets[0]
                } & {8013, 8014, 8015, 8016}
                assert len(target_states) == 1, target_states
                state = next(iter(target_states))
                if state in (8015, 8016):
                    reference = 1103 if state == 8015 else 1102
                    cell = next(
                        tuple(a["cell"])
                        for a in areas.values()
                        if a.get("prototype") == reference
                    )
                    self.move(cell)
                    self.cast(7967, target_cell)
                else:
                    distance = 1 if state == 8013 else 6
                    cell = next(
                        tuple(cell)
                        for cell in snap["walkable"]
                        if abs(cell[0] - target_cell[0]) + abs(cell[1] - target_cell[1])
                        == distance
                    )
                    self.move(cell)
                    self.end_turn()
        raise AssertionError("Lesson did not complete")

    def solve_los(self, snap, target):
        from wakfu_server.combat_native_los_ray import cast_rays

        hero = tuple(snap["actors"][str(self.char["id"])]["position"])
        blocks = {
            (row["position"][0] + dx, row["position"][1] + dy)
            for row in snap.get("native_qi_slots", ())
            if row and row.get("indexed") and row["identity"][0] == "effect_area"
            for dx in range(-row["radius"], row["radius"] + 1)
            for dy in range(-row["radius"], row["radius"] + 1)
        }
        candidates = [
            tuple(cell)
            for cell in snap["walkable"]
            if 4 <= abs(cell[0] - target[0]) + abs(cell[1] - target[1]) <= 16
            and tuple(cell) not in blocks
        ]
        candidates.sort(
            key=lambda cell: abs(cell[0] - hero[0]) + abs(cell[1] - hero[1])
        )
        for cell in candidates:
            if (cell[0], cell[1]) in blocks:
                continue
            if not any(
                clear and not (set(probes) & blocks)
                for clear, probes in cast_rays(
                    1388, cell, target, source_height=6, target_height=4
                )
            ):
                continue
            try:
                self.move(cell)
                before = self.ready_for_input()
                after = self.cast(7968, target)
                print(
                    "LOS_NATIVE_CAST",
                    cell,
                    before["actors"][str(self.targets[0])]["hp"],
                    after["actors"][str(self.targets[0])]["hp"],
                    "QK",
                    len(blocks),
                    flush=True,
                )
                return
            except AssertionError as error:
                print("LOS_PROBE_REJECTED", cell, str(error)[:120], flush=True)
        raise AssertionError("No clear native shooting cell")

    def solve_movement(self, snap, target, states, areas):
        marker = next(
            tuple(a["cell"]) for a in areas.values() if a.get("prototype") == 1807
        )
        level = next(
            e["level"]
            for e in states.values()
            if e.get("target") == self.targets[0] and e.get("state_id") == 8011
        )
        hero = tuple(snap["actors"][str(self.char["id"])]["position"])

        def teleport(cell):
            nonlocal hero
            from wakfu_server.combat_native_los_ray import cast_rays

            for _ in range(8):
                current = self.ready_for_input()
                hero = tuple(current["actors"][str(self.char["id"])]["position"])
                if hero == cell:
                    return
                occupied = {
                    (a["position"][0], a["position"][1])
                    for identity, a in current["actors"].items()
                    if int(identity) != self.char["id"] and a["hp"] > 0
                }
                distance = abs(hero[0] - cell[0]) + abs(hero[1] - cell[1])
                candidates = [
                    tuple(point)
                    for point in current["walkable"]
                    if (point[0], point[1]) not in occupied
                    and 0 < abs(point[0] - hero[0]) + abs(point[1] - hero[1]) <= 4
                    and abs(point[0] - cell[0]) + abs(point[1] - cell[1]) < distance
                ]
                candidates.sort(
                    key=lambda point: abs(point[0] - cell[0]) + abs(point[1] - cell[1])
                )
                options = [
                    point
                    for point in candidates
                    if any(
                        clear and not (set(probes) & occupied)
                        for clear, probes in cast_rays(
                            1388, hero, point, source_height=6, target_height=0
                        )
                    )
                ]
                assert options, ("No native teleport path", hero, cell)
                waypoint = options[0]
                self.cast(7974, waypoint)
                self.poll(
                    lambda state: tuple(
                        state["actors"][str(self.char["id"])]["position"]
                    )
                    == waypoint,
                    label="teleport position",
                )
            raise AssertionError("Teleport route exhausted")

        if level == 4:
            teleport(marker)
            self.cast(7975, target)
            return
        dx = 0 if target[0] == marker[0] else (1 if marker[0] > target[0] else -1)
        dy = 0 if dx else (1 if marker[1] > target[1] else -1)
        if level == 1:
            self.cast(7973, target)
        elif level == 2:
            self.cast(7972, target)
        else:
            teleport((target[0] - dx, target[1] - dy, target[2]))
            self.cast(7973, target)

    def finish(self):
        snap = self.poll(lambda state: state["phase"] == "finished", label="victory")
        assert snap["winner"] == snap["actors"][str(self.char["id"])]["team"], snap[
            "winner"
        ]
        self.peer.wait(12755, timeout=15)
        self.peer.wait(12238, timeout=15)
        progress = self.progress()
        assert OBJECTIVES[self.index] in progress["objectives"], progress
        with self.peer.observation_lock:
            before_return = self.peer.records[getattr(self, "start_wire_index", 0) :]
            assert not any(
                opcode == 13832
                and len(body) == 12
                and struct.unpack(">qi", body)[1] == OBJECTIVES[self.index]
                for opcode, body in before_return
            ), "Objective notification preceded native cleanup acknowledgement"
        self.peer.send(12925, struct.pack(">iB", self.fight_id, 0))
        while True:
            guide, _ = self.peer.wait(13411, timeout=15)
            if struct.unpack_from(">i", guide, 1)[0] == SUCCESS_GUIDES[self.index]:
                break
        self.peer.wait(13974, timeout=15)
        with self.peer.observation_lock:
            messages = self.peer.records[getattr(self, "start_wire_index", 0) :]
            guide_events = [
                struct.unpack_from(">i", body, 1)[0]
                for op, body in messages
                if op == 13411
            ]
        objective_notifications = [
            body
            for opcode, body in messages
            if opcode == 13832
            and len(body) == 12
            and struct.unpack(">qi", body)[1] == OBJECTIVES[self.index]
        ]
        assert len(objective_notifications) == 1, objective_notifications
        # Resumed fights can have started in an earlier process; a fresh run
        # must observe both native guide publications exactly once.
        if not os.environ.get("WAKFU_RII_RESUME"):
            assert guide_events.count(GUIDES[self.index]) == 1, guide_events
            assert guide_events.count(SUCCESS_GUIDES[self.index]) == 1, guide_events
        current = self.store.character(self.account["id"], self.char["id"])
        with self.store.connection() as db:
            reward = db.execute(
                "SELECT xp,kamas,start_xp,end_xp FROM fight_rewards WHERE fight_id=%s AND character_id=%s",
                (self.fight_id, self.char["id"]),
            ).fetchone()
            assert reward is not None, "Missing battle reward receipt"
            quest_xp = db.execute(
                "SELECT awarded_xp FROM achievement_flat_xp_rates WHERE character_id=%s AND achievement_id=5143 AND reward_key='9712'",
                (self.char["id"],),
            ).fetchone()
        if os.environ.get("WAKFU_RII_VERIFY_REWARDS", "1") == "1":
            assert reward["xp"] == 0, (
                "Tutorial battle granted ordinary combat XP",
                reward,
            )
            assert reward["kamas"] == 0, (
                "Tutorial battle granted ordinary combat kamas",
                reward,
            )
            start = getattr(self, "start_xp", None)
            if start is not None:
                expected_xp = quest_xp["awarded_xp"] if self.index == 6 else 0
                assert current["xp"] - start == expected_xp, (
                    start,
                    current["xp"],
                    expected_xp,
                )
        permanent = {ref for _, ref, _ in owned_spell_records(current)}
        assert 5562 in permanent and not permanent.intersection(
            range(7963, 7976)
        ), permanent
        row = {
            "index": self.index,
            "objective": OBJECTIVES[self.index],
            "fight_id": self.fight_id,
            "winner": snap["winner"],
            "completed_objectives": progress["objectives"],
            "guide_events": guide_events,
            "class_book_references_after_return": sorted(permanent),
            "combat_reward": reward,
            "end_xp": current["xp"],
        }
        self.receipt["lessons"].append(row)
        print("VICTORY", row, flush=True)
        self.fight_id = None
        # A reconnect can have left its old admission packets pending. The
        # terminal/world-return fence has consumed that fight completely.
        self.peer.pending.clear()
        while True:
            try:
                self.peer.events.get_nowait()
            except queue.Empty:
                break


def main():
    dsn = os.environ["WAKFU_DATABASE_URL"]
    if conninfo_to_dict(dsn).get("host") not in ("127.0.0.1", "localhost"):
        raise ValueError("Local probe only")
    store = Store(dsn, password_file=os.environ["WAKFU_DATABASE_PASSWORD_FILE"])
    resume = os.environ.get("WAKFU_RII_RESUME")
    if resume:
        receipt = json.loads(Path(resume).read_text())
        account = {"id": receipt["account_id"]}
        char = store.character(account["id"], receipt["character_id"])
        if not char["name"].startswith("Rii Path "):
            raise ValueError("Refusing to resume a non-QA character")
        suffix = char["name"][9:]
        receipt.pop("error", None)
        if "wire" in receipt:
            receipt.setdefault("previous_wire_runs", []).append(receipt.pop("wire"))
    else:
        suffix = "".join(secrets.choice("abcdefghjkmnpqrstuvwxyz") for _ in range(9))
        account = store.register("rii_continuous_" + suffix, secrets.token_urlsafe(24))
        char = store.create_character(account["id"], "Rii Path " + suffix, breed=19)
        receipt = {
            "account_id": account["id"],
            "character_id": char["id"],
            "lessons": [],
            "started": datetime.now(timezone.utc).isoformat(),
        }
        with store.connection() as db:
            db.execute(
                "UPDATE characters SET map_id=1388,instance_id=0,x=0,y=-18,z=0,level=6 WHERE id=%s",
                (char["id"],),
            )
            db.execute(
                "UPDATE character_progression SET xp=%s WHERE character_id=%s",
                (level_xp(6), char["id"]),
            )
            state = storage.load_locked(db, char["id"])
            state.update(
                running=[5154, 5160],
                tracking=[5160],
                objectives=[10595, 10596, 10607, 10612, 10613, 10615],
                completed=[],
            )
            storage.store(db, char["id"], state)
            db.execute(
                "INSERT INTO character_achievement_authority(character_id,snapshot,revision,provenance) VALUES(%s,%s,1,'rii-continuous-fixture') ON CONFLICT(character_id) DO UPDATE SET snapshot=EXCLUDED.snapshot,revision=character_achievement_authority.revision+1",
                (
                    char["id"],
                    Jsonb(
                        {
                            key: state[key]
                            for key in ("running", "completed", "objectives")
                        }
                    ),
                ),
            )
    run = Run(store, account, char, receipt)
    try:
        run.connect()
        for index in range(len(receipt["lessons"]), 7):
            active = None
            if resume:
                with store.connection() as db:
                    active = db.execute(
                        "SELECT f.id FROM combat_fights f JOIN combat_fight_participants p ON p.fight_id=f.id WHERE p.character_id=%s AND f.status IN ('placement','active') ORDER BY f.id DESC LIMIT 1",
                        (char["id"],),
                    ).fetchone()
            if active:
                run.index, run.fight_id = index, active["id"]
                pending_xp = receipt.get("pending_xp", {})
                if pending_xp.get("fight_id") == run.fight_id:
                    run.start_xp = pending_xp["xp"]
                snap = run.checkpoint()
                run.targets = [
                    int(identity)
                    for identity in snap["actors"]
                    if int(identity) != char["id"]
                ]
                if snap["phase"] == "placement":
                    run.peer.send(12523, b"\x01")
                run.ready_for_input()
                print("RESUME", index, run.fight_id, flush=True)
            else:
                run.start(index)
            run.solve()
            run.finish()
        before = run.progress()
        assert 5143 in before["completed"] and 10616 in before["objectives"], before
        with run.peer.observation_lock:
            receipt.setdefault("previous_wire_runs", []).append(
                [(opcode, body.hex()) for opcode, body in run.peer.records]
            )
        all_wire = [
            packet for batch in receipt["previous_wire_runs"] for packet in batch
        ]
        all_guides = [
            struct.unpack_from(">i", bytes.fromhex(body), 1)[0]
            for opcode, body in all_wire
            if opcode == 13411
        ]
        for expected in (*GUIDES, *SUCCESS_GUIDES):
            assert all_guides.count(expected) == 1, (expected, all_guides)
        receipt["observed_guide_events"] = all_guides
        with store.connection() as db:
            rows = db.execute(
                "SELECT achievement_id,reward_key,delivered_at FROM character_achievement_reward_outbox WHERE character_id=%s AND achievement_id=5143 ORDER BY reward_key",
                (char["id"],),
            ).fetchall()
            native = db.execute(
                "SELECT data FROM native_quest_metadata_definitions WHERE revision=(SELECT revision FROM native_quest_metadata_releases ORDER BY imported_at DESC LIMIT 1) AND definition_id=5143"
            ).fetchone()["data"]["native"]
            expected_rewards = {str(row["d"]) for row in native["cjK"]}
            assert {str(row["reward_key"]) for row in rows} == expected_rewards, rows
            assert all(row["delivered_at"] is not None for row in rows), rows
            receipt["delivered_rewards"] = [
                {**row, "delivered_at": row["delivered_at"].isoformat()} for row in rows
            ]
        run.peer.close()
        run.peer = None
        time.sleep(0.2)
        run.connect()
        after = run.progress()
        assert all(objective in after["objectives"] for objective in OBJECTIVES)
        assert 5143 in after["completed"] and 10616 in after["objectives"]
        current = store.character(account["id"], char["id"])
        expected_book = spell_inventory(current)
        with run.peer.observation_lock:
            book_packets = [
                op for op, body in run.peer.records if expected_book in body
            ]
        assert (
            book_packets
        ), "Reconnected client did not receive the permanent class spell inventory"
        with store.connection() as db:
            after_rows = db.execute(
                "SELECT achievement_id,reward_key,delivered_at FROM character_achievement_reward_outbox WHERE character_id=%s AND achievement_id=5143 ORDER BY reward_key",
                (char["id"],),
            ).fetchall()
            assert after_rows == rows, "Reconnection changed delivered reward receipts"
            active = db.execute(
                "SELECT f.id FROM combat_fights f JOIN combat_fight_participants p ON p.fight_id=f.id WHERE p.character_id=%s AND f.status IN ('active','placement')",
                (char["id"],),
            ).fetchall()
            assert not active, active
            loot = db.execute(
                "SELECT fight_id FROM fight_drop_awards WHERE character_id=%s AND fight_id=ANY(%s)",
                (char["id"], [lesson["fight_id"] for lesson in receipt["lessons"]]),
            ).fetchall()
            assert not loot, ("Tutorial battles granted ordinary loot", loot)
        receipt["permanent_book_reconnect_opcodes"] = book_packets
        receipt.update(
            progress_before_reconnect=before,
            progress_after_reconnect=after,
            success=True,
        )
    except Exception as error:
        receipt["error"] = repr(error)
        raise
    finally:
        if run.peer is not None:
            receipt["wire"] = [
                (opcode, body.hex()) for opcode, body in run.peer.records
            ]
            run.peer.close()
        output = Path(
            os.environ.get(
                "WAKFU_RII_COMPLETE_RECEIPT",
                ".local-state/wakemu/qa/rii-complete-" + suffix + ".json",
            )
        )
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(receipt, indent=2) + "\n")
        print("RECEIPT", output, flush=True)
        store.close()


if __name__ == "__main__":
    main()
