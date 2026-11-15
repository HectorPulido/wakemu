"""Local TLS acceptance of quest5568's owned three-room cat story.

Only the new QA character's initial entry prerequisites are fixtures. All room
wins use ordinary combat with native ally AI and real player turn-end requests.
No synthetic wins, damage writes or subsequent progress fixtures are permitted.
Protocol/state evidence does not verify graphical cinematic rendering.
"""

import json
import os
from pathlib import Path
import secrets
import struct
import time
from collections import deque

from psycopg.conninfo import conninfo_to_dict
from psycopg.types.json import Jsonb

from tools.rii_departure_probe import Probe, ObservedPeer, login, map_id
from tools.candidate_friendly_duel_socket_smoke import placement
from wakfu_server.achievements import storage
from wakfu_server.combat_terrain import published_geometry
from wakfu_server.progression import level_xp
from wakfu_server.store import Store


class CatProbe(Probe):
    def __init__(self, store, *, resume=None):
        self.store, self.peer = store, None
        if resume is not None:
            self.receipt = json.loads(Path(resume).read_text())
            self.account = {"id": self.receipt["account_id"]}
            self.character = store.character(
                self.account["id"], self.receipt["character_id"]
            )
            assert self.character["id"] != 352 and self.character["name"].startswith(
                "Cat Story "
            )
            if "error" in self.receipt:
                self.receipt.setdefault("prior_errors", []).append(
                    self.receipt.pop("error")
                )
            self.instance = self.receipt.get("instance_id")
            self.map_seen = 0
            return
        suffix = "".join(secrets.choice("abcdefghjkmnpqrstuvwxyz") for _ in range(9))
        self.account = store.register("astrub_cat_" + suffix, secrets.token_urlsafe(24))
        self.character = store.create_character(
            self.account["id"], "Cat Story " + suffix, breed=19
        )
        assert self.character["id"] != 352
        with store.connection() as db:
            db.execute(
                "UPDATE characters SET map_id=527,instance_id=0,x=-29,y=120,z=0,level=6 WHERE id=%s AND account_id=%s",
                (self.character["id"], self.account["id"]),
            )
            db.execute(
                "UPDATE character_progression SET xp=%s WHERE character_id=%s",
                (level_xp(6), self.character["id"]),
            )
            state = storage.load_locked(db, self.character["id"])
            state.update(
                running=[5568],
                tracking=[5568],
                completed=[5160, 5161],
                objectives=[11508, 11509, 11510],
            )
            storage.store(db, self.character["id"], state)
            db.execute(
                "INSERT INTO character_achievement_authority(character_id,snapshot,revision,provenance) VALUES(%s,%s,1,'astrub-cat-initial-fixture') ON CONFLICT(character_id) DO UPDATE SET snapshot=EXCLUDED.snapshot,revision=character_achievement_authority.revision+1",
                (
                    self.character["id"],
                    Jsonb(
                        {k: state[k] for k in ("running", "completed", "objectives")}
                    ),
                ),
            )
        self.receipt = dict(
            account_id=self.account["id"],
            character_id=self.character["id"],
            checks=[],
            fights=[],
            scope="local TLS/state; only initial prerequisites are fixtures; rendering not verified",
        )
        self.map_seen = 0
        self.instance = None

    def checkpoint(self, fight_id):
        with self.store.connection() as db:
            row = db.execute(
                "SELECT snapshot FROM fight_checkpoints WHERE fight_id=%s", (fight_id,)
            ).fetchone()
        return None if row is None else row["snapshot"]

    def callback_done(self, event):
        with self.store.connection() as db:
            return (
                db.execute(
                    "SELECT 1 FROM character_achievement_events WHERE character_id=%s AND event_key=%s",
                    (
                        self.character["id"],
                        "astrub-cat-story:%s:callback:%s" % (self.instance, event),
                    ),
                ).fetchone()
                is not None
            )

    def ack_maps(self):
        with self.peer.observation_lock:
            count = sum(op == 13974 for op, _ in self.peer.records)
        while self.map_seen < count:
            self.peer.send(12449)
            self.map_seen += 1

    def group(self, room):
        deadline = time.monotonic() + 20
        stable, stable_since = None, time.monotonic()
        while time.monotonic() < deadline:
            self.ack_maps()
            current = self.current()
            with self.store.connection() as db:
                row = db.execute(
                    "SELECT g.members,g.group_id,g.status FROM dungeon_room_spawn_receipts r JOIN combat_groups g ON g.map_id=r.asset_map_id AND g.instance_id=r.instance_id AND g.group_id=r.group_id JOIN dungeon_room_runs d ON d.instance_id=r.instance_id WHERE r.instance_id=%s AND r.room_order=%s AND d.current_room=%s",
                    (self.instance, room, room),
                ).fetchone()
            with self.store.connection() as db:
                transitioning = db.execute(
                    "SELECT 1 FROM dungeon_transition_outbox WHERE character_id=%s AND status='pending' LIMIT 1",
                    (self.character["id"],),
                ).fetchone()
            location = tuple(
                current[k] for k in ("map_id", "instance_id", "x", "y", "z")
            ) + (self.map_seen,)
            if location != stable or transitioning:
                stable, stable_since = location, time.monotonic()
            if (
                row
                and row["status"] == "available"
                and current["map_id"] == 312
                and not transitioning
                and time.monotonic() - stable_since > 1
            ):
                return row
            time.sleep(0.1)
        raise AssertionError(("Owned room group unavailable", room, current))

    def approach(self, members):
        current = self.current()
        start = tuple(current[k] for k in ("x", "y", "z"))
        graph = published_geometry(312).outgoing
        pending, seen = deque([start]), {start}
        occupied = {tuple(m[k] for k in ("x", "y", "z")) for m in members}
        while pending:
            cell = pending.popleft()
            for member in members:
                target = tuple(member[k] for k in ("x", "y", "z"))
                if (
                    abs(cell[0] - target[0]) + abs(cell[1] - target[1]) <= 1
                    and abs(cell[2] - target[2]) <= 1
                ):
                    self.walk(cell)
                    return member
            for nxt in graph.get(cell, ()):
                if nxt not in seen and nxt not in occupied:
                    seen.add(nxt)
                    pending.append(nxt)
        raise AssertionError(("No native room approach", start))

    def fight(self, room):
        prior = next(
            (row for row in reversed(self.receipt["fights"]) if row["room"] == room),
            None,
        )
        previous = None if prior is None else self.checkpoint(prior["fight_id"])
        resuming = previous is not None and previous["phase"] in ("active", "finished")
        if resuming:
            fight_id, start, evidence = prior["fight_id"], 0, prior
            evidence["normal_native_recovery"] = True
            if previous["phase"] == "active":
                self.peer.send(13332, struct.pack(">i", fight_id))
        else:
            group = self.group(room)
            target = self.approach(group["members"])
            start = self.peer.mark()
            self.peer.send(
                13130,
                struct.pack(
                    ">qiihB", target["id"], target["x"], target["y"], target["z"], 0
                ),
            )
            fight_id, positions = placement(
                self.peer.matching(13652, start, timeout=30)
            )
            deadline = time.monotonic() + 10
            snap = self.checkpoint(fight_id)
            while (
                snap is None or not snap.get("native_scene_helper_manifest")
            ) and time.monotonic() < deadline:
                time.sleep(0.05)
                snap = self.checkpoint(fight_id)
            manifest = snap["native_scene_helper_manifest"]["source"]
            helper_row = next(
                row for row in manifest["helpers"] if row["reference"] == 4691
            )
            helper_id = helper_row["actor_id"]
            helper = snap["actors"][str(helper_id)]
            player = snap["actors"][str(self.character["id"])]
            assert (
                helper_row["controller_role"] == "self"
                and helper_row["team_role"] == "player"
            )
            assert (
                helper["team"] == player["team"]
                and helper["controlled"] is False
                and helper["native_controlled_by_ai"] is True
            )
            assert (
                helper["max_hp"],
                helper["max_ap"],
                helper["max_mp"],
                helper["initiative"],
                helper["effective_level"],
            ) == (200, 8, 4, 6, 6), helper
            assert helper["effect_stats"]["3"] == 4
            from wakfu_server.monsters import native_abilities

            native_spells = sorted(row["spell_id"] for row in native_abilities(4691, 6))
            assert native_spells == [6402, 6403, 6404]
            evidence = dict(
                room=room,
                fight_id=fight_id,
                helper_id=helper_id,
                helper=helper_row,
                initial_stats={
                    k: helper.get(k)
                    for k in (
                        "hp",
                        "max_hp",
                        "ap",
                        "max_ap",
                        "mp",
                        "max_mp",
                        "initiative",
                        "effective_level",
                        "native_controlled_by_ai",
                        "effect_stats",
                    )
                },
                native_spells=native_spells,
            )
            self.receipt["fights"].append(evidence)
            self.check(
                "room%d native4691 player-team/self-AI and original stats/book" % room
            )
        from tools.rii_lessons_complete_probe import Run

        class NativeRun(Run):
            def ready_for_input(driver):
                deadline = time.monotonic() + 180
                while time.monotonic() < deadline:
                    with driver.peer.observation_lock:
                        messages = driver.peer.records[driver.wire_cursor :]
                        driver.wire_cursor = len(driver.peer.records)
                    for opcode, body in messages:
                        if (
                            len(body) < 4
                            or struct.unpack_from(">i", body)[0] != driver.fight_id
                        ):
                            continue
                        if opcode == 12053 and len(body) >= 30:
                            # Native SU is inside the original fg/fh field envelope.
                            # Its global cursor survives KO, skipped actors and recovery.
                            driver.native_global_turn = struct.unpack_from(
                                ">i", body, 17
                            )[0]
                        elif opcode == 13482 and len(body) >= 28:
                            driver.native_global_turn += 1
                        elif opcode == 12502 and len(body) >= 28:
                            driver.peer.send(
                                13510, struct.pack(">i", driver.native_global_turn)
                            )
                    value = driver.checkpoint()
                    if value and (
                        value["phase"] == "finished"
                        or (
                            value["phase"] == "active"
                            and value["order"][value["turn_index"]] == driver.char["id"]
                        )
                    ):
                        return value
                    time.sleep(0.05)
                latest = driver.checkpoint()
                raise AssertionError(
                    (
                        "No native owned input turn",
                        driver.fight_id,
                        (
                            None
                            if latest is None
                            else {
                                "phase": latest["phase"],
                                "actors": {
                                    k: {f: a.get(f) for f in ("hp", "position", "team")}
                                    for k, a in latest["actors"].items()
                                },
                            }
                        ),
                    )
                )

        runner = NativeRun(self.store, self.account, self.character, self.receipt)
        runner.wire_cursor, runner.native_global_turn = (
            0 if resuming else self.peer.mark()
        ), 0
        runner.peer, runner.fight_id = self.peer, fight_id
        player_turns = 0
        if not resuming:
            self.peer.send(12523, b"\x01")
        deadline = time.monotonic() + 180
        while time.monotonic() < deadline:
            snap = runner.ready_for_input()
            if snap["phase"] == "finished":
                break
            hero = snap["actors"][str(self.character["id"])]
            if hero["ap"] < 2:
                player_turns += 1
                runner.end_turn()
                continue
            enemies = [
                actor
                for actor in snap["actors"].values()
                if actor["team"] != hero["team"] and actor["hp"] > 0
            ]
            here = tuple(hero["position"])
            occupied = {
                tuple(actor["position"])
                for identity, actor in snap["actors"].items()
                if int(identity) != self.character["id"] and actor["hp"] > 0
            }
            graph = {}
            for left, right in snap["edges"]:
                graph.setdefault(tuple(left), []).append(tuple(right))
            previous, pending = {here: None}, deque([here])
            while pending:
                point = pending.popleft()
                for nxt in graph.get(point, ()):
                    if nxt not in occupied and nxt not in previous:
                        previous[nxt] = point
                        pending.append(nxt)
            options = []
            for enemy in enemies:
                cell = tuple(enemy["position"])
                for point in previous:
                    if abs(point[0] - cell[0]) + abs(point[1] - cell[1]) != 1:
                        continue
                    path, cursor = [], point
                    while cursor != here:
                        path.append(cursor)
                        cursor = previous[cursor]
                    options.append((len(path), cell, list(reversed(path))))
            assert options, ("No natural player attack route", room, here)
            _, target_cell, path = min(options)
            if path:
                if hero["mp"] <= 0:
                    player_turns += 1
                    runner.end_turn()
                    continue
                segment = path[: hero["mp"]]
                runner.action(
                    12161,
                    struct.pack(">q", self.character["id"])
                    + b"".join(struct.pack(">iih", *point) for point in segment),
                    label="ordinary cat-story movement",
                )
            else:
                runner.cast(5562, target_cell, class_spell=True)
        snap = self.checkpoint(fight_id)
        assert snap and snap["phase"] == "finished", (
            "Native fight timed out",
            room,
            snap.get("round"),
            snap.get("runtime"),
        )
        assert snap["winner"] == snap["actors"][str(self.character["id"])]["team"], (
            "Native cat defeat",
            room,
            snap,
        )
        evidence.update(
            winner=snap["winner"],
            player_turns=player_turns,
            final_hp={k: a["hp"] for k, a in snap["actors"].items()},
        )
        self.peer.matching(12755, start)
        returned = self.peer.mark()
        self.peer.send(12925, struct.pack(">iB", fight_id, 1))
        event = {1: 23922, 2: 23924, 3: 23926}[room]
        scene = self.peer.scenario(event, returned)
        if event == 23924:
            ids = struct.unpack_from(">qqq", scene, 10)
            with self.peer.observation_lock:
                prior = self.peer.records[:]
            stop = next(
                index
                for index, (op, body) in enumerate(prior)
                if op == 13411 and body == scene
            )
            missing = [
                identity
                for identity in ids
                if not any(
                    op == 12608 and struct.pack(">q", identity) in body
                    for op, body in prior[:stop]
                )
            ]
            assert not missing, (
                "Boss scene23924 preceded actual actor publication",
                missing,
            )
            evidence["boss_scene_actor_ids_published_before_scene"] = list(ids)
        assert {1: 11511, 2: 11512, 3: 11513}[room] in self.progress()["objectives"]
        self.check(
            "room%d natural AI victory and authenticated scene%d" % (room, event)
        )
        self.callback(event, 23927 if room == 3 else {1: 23923, 2: 23925}[room])

    def rewards(self):
        with self.store.connection() as db:
            xp = db.execute(
                "SELECT xp FROM character_progression WHERE character_id=%s",
                (self.character["id"],),
            ).fetchone()["xp"]
            count = db.execute(
                "SELECT count(*) AS n FROM character_achievement_reward_outbox WHERE character_id=%s",
                (self.character["id"],),
            ).fetchone()["n"]
        return xp, count

    def fight_count(self):
        with self.store.connection() as db:
            return db.execute(
                "SELECT count(*) AS n FROM combat_fight_participants WHERE character_id=%s",
                (self.character["id"],),
            ).fetchone()["n"]

    def run(self):
        self.connect()
        self.map_seen = sum(op == 13974 for op, _ in self.peer.records)
        if self.current()["map_id"] == 527 and self.instance is None:
            start = self.peer.mark()
            self.peer.send(12296, struct.pack(">qiBi", 18736, 713, 0, 2))
            self.peer.matching(13974, start, lambda b: map_id(b) == 312, timeout=25)
            self.ack_maps()
            self.instance = self.current()["instance_id"]
            assert self.instance > 0
            self.receipt["instance_id"] = self.instance
            bootstrap = self.peer.scenario(10021, start)
            assert bootstrap[9] == 12
            self.peer.scenario(23920, start)
            self.check("owned private312 entry and native twelve-actor story bootstrap")
        if not self.callback_done(23920):
            self.callback(23920, 23921)
        for room in (1, 2, 3):
            event = {1: 23922, 2: 23924, 3: 23926}[room]
            if self.callback_done(event):
                continue
            if {1: 11511, 2: 11512, 3: 11513}[room] in self.progress()["objectives"]:
                self.peer.scenario(event)
                self.callback(event, 23927 if room == 3 else {1: 23923, 2: 23925}[room])
            else:
                self.fight(room)
        before = self.peer.mark()
        fights_before_nekark = self.fight_count()
        if not self.callback_done(23927):
            self.callback(23927, 23928)
        assert 11514 in self.progress()["objectives"]
        current = self.current()
        assert (
            current["map_id"],
            current["instance_id"],
            current["x"],
            current["y"],
            current["z"],
        ) == (312, self.instance, 149, 125, 0)
        if not self.callback_done(23928):
            scene = self.peer.scenario(23928)
            assert scene[9] == 5
        self.check("private exterior Nekark presentation with five native actors")
        start = 0
        if not self.callback_done(23928):
            start = self.callback(23928, 23929)
        if self.current()["map_id"] != 527:
            self.peer.matching(13974, start, lambda b: map_id(b) == 527, timeout=25)
        self.ack_maps()
        assert (
            11515 in self.progress()["objectives"]
            and self.current()["instance_id"] == 0
        )
        with self.store.connection() as db:
            active = db.execute(
                "SELECT count(*) AS n FROM dungeon_instance_members WHERE character_id=%s AND instance_id=%s AND status='active'",
                (self.character["id"], self.instance),
            ).fetchone()["n"]
            fights = db.execute(
                "SELECT count(*) AS n FROM dungeon_room_encounters WHERE instance_id=%s AND status='victory'",
                (self.instance,),
            ).fetchone()["n"]
        assert active == 0 and fights == 3
        assert self.fight_count() == fights_before_nekark
        self.receipt["fights_before_and_after_nekark"] = fights_before_nekark
        self.check(
            "Nekark callback without fourth fight, three victories and complete private exit"
        )
        self.walk((10, 155, 0))
        start = self.peer.mark()
        self.peer.send(13222, struct.pack(">qq", -1776810790485981, 969))
        assert struct.unpack_from(">i", self.peer.matching(12969, start))[0] == 7129
        for node, choice, target in (
            (7129, 15226, 7130),
            (7130, 15228, 7131),
            (7131, 15229, 7132),
            (7132, 15230, 7133),
            (7133, 15231, 7134),
            (7134, 15232, 7135),
            (7135, 15234, 7136),
            (7136, 15235, 7137),
            (7137, 15236, 0),
        ):
            start = self.peer.mark()
            self.peer.send(12058, struct.pack(">ii", node, choice))
            assert (
                struct.unpack_from(">i", self.peer.matching(12218, start))[0] == target
            )
        state = self.progress()
        assert 5568 in state["completed"] and 11544 in state["objectives"]
        self.check("native Gultar return completes11544 and quest5568")
        reward = self.rewards()
        start = self.peer.mark()
        self.peer.send(13222, struct.pack(">qq", -1776810790485981, 969))
        assert struct.unpack_from(">i", self.peer.matching(12969, start))[0] == 7137
        self.connect()
        assert self.rewards() == reward
        assert 5568 in self.progress()["completed"]
        self.check(
            "completed return dialogue/reconnect neither replays reward nor loses progress"
        )
        self.receipt["progress"] = self.progress()
        self.receipt["reward_snapshot"] = reward
        return self.receipt


def main():
    dsn = os.environ["WAKFU_DATABASE_URL"]
    if conninfo_to_dict(dsn).get("host") not in ("127.0.0.1", "localhost"):
        raise ValueError("This gameplay probe is local only")
    store = Store(dsn, password_file=os.environ["WAKFU_DATABASE_PASSWORD_FILE"])
    path = Path(
        os.environ.get(
            "WAKFU_ASTRUB_CAT_RECEIPT",
            ".local-state/wakemu/qa/astrub-cat-story-probe.json",
        )
    )
    probe = CatProbe(store, resume=os.environ.get("WAKFU_ASTRUB_CAT_RESUME"))
    try:
        probe.run()
    except Exception as error:
        probe.receipt["error"] = repr(error)
        raise
    finally:
        if probe.peer is not None:
            probe.peer.close()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(probe.receipt, indent=2))


if __name__ == "__main__":
    main()
