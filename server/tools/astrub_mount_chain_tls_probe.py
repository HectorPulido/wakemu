"""One-QA, real TLS acceptance for the reconstructed Astrub mount chain.

Only level, profession, ordinary gear and crafting/turn-in materials are
initial fixtures. All quest progress, physical pickup, warehouse membership,
combat victory, crafting and dialogue payments use normal World operations.
"""
import json
import os
from pathlib import Path
import secrets
import struct
import time

from psycopg.conninfo import conninfo_to_dict
from psycopg.types.json import Jsonb

from tools.rii_departure_probe import ObservedPeer, login
from tools.quest_instance_combat_probe import fight_owned_room, walk_native
from wakfu_server.achievements import storage
from wakfu_server.progression import level_xp
from wakfu_server.store import Store
from wakfu_server.items.inventory import initialize

ROOT = Path(__file__).resolve().parents[1]
RECEIPT = Path(".runtime/astrub-mount-chain-tls-proof.json")
IMAGE = "wakemu-world:mount-fresco-archetypes-20261115"
SOURCE_SHA = "ec2813b218d4ecf07063865cde965447519229e6ce3b1135eab59cec4361b289"


class MountProbe:
    def __init__(self, store, resume=False):
        self.store, self.peer = store, None
        if resume:
            self.receipt = json.loads(RECEIPT.read_text())
            self.account = {"id": self.receipt["account_id"]}
            self.character = store.character(
                self.account["id"], self.receipt["character_id"]
            )
            self.receipt.pop("error", None)
            self.receipt.setdefault("resumptions", []).append(
                {
                    "time": time.time(),
                    "note": "resume same QA after assertion-only stop",
                }
            )
            self.save()
            return
        suffix = "".join(secrets.choice("abcdefghjkmnpqrstuvwxyz") for _ in range(9))
        self.account = store.register(
            "mount_chain_" + suffix, secrets.token_urlsafe(32)
        )
        self.character = store.create_character(
            self.account["id"], "Mount Chain " + suffix, breed=19
        )
        self.receipt = {
            "account_id": self.account["id"],
            "character_id": self.character["id"],
            "image": IMAGE,
            "source_sha256": SOURCE_SHA,
            "scope": "single local QA; initial level35, learned profession83, ordinary native gear and materials only; no quest completion, fake books, synthetic victory or admin teleport",
            "fixture": {},
            "events": [],
        }
        with store.connection() as db:
            db.execute(
                "UPDATE characters SET map_id=527,instance_id=0,x=-89,y=-58,z=0,level=35 WHERE id=%s AND account_id=%s",
                (self.character["id"], self.account["id"]),
            )
            db.execute(
                "UPDATE character_progression SET xp=%s WHERE character_id=%s",
                (level_xp(35), self.character["id"]),
            )
            db.execute(
                "INSERT INTO account_professions(account_id,profession_id,xp) VALUES(%s,83,0) ON CONFLICT DO NOTHING",
                (self.account["id"],),
            )
            initialize(db, self.character["id"])
            bag = db.execute(
                "SELECT uid FROM inventory_containers WHERE character_id=%s AND kind=0",
                (self.character["id"],),
            ).fetchone()["uid"]
            # Legitimate prepared recipe inputs and the exact later Missy payment.
            for slot, (ref, quantity) in enumerate(((1723, 25), (1732, 25), (8414, 5))):
                db.execute(
                    "INSERT INTO inventory_items(character_id,reference,quantity,container,slot) VALUES(%s,%s,%s,%s,%s)",
                    (self.character["id"], ref, quantity, bag, slot),
                )
            state = storage.load_locked(db, self.character["id"])
            if any(state[k] for k in ("running", "completed", "objectives")):
                raise AssertionError(("Fresh QA unexpectedly has quest state", state))
            self.receipt["fixture"] = {
                "level": 35,
                "profession_id": 83,
                "materials": {"1723": 25, "1732": 25, "8414": 5},
                "initial_quest_state_empty": True,
                "position": [-89, -58, 0],
            }
        self.character = self.current()
        self.save()

    def save(self):
        RECEIPT.parent.mkdir(parents=True, exist_ok=True)
        RECEIPT.write_text(json.dumps(self.receipt, indent=2, default=str))

    def current(self):
        return self.store.character(self.account["id"], self.character["id"])

    def progress(self):
        with self.store.connection() as db:
            return storage.load_locked(db, self.character["id"])

    def connect(self):
        if self.peer:
            self.peer.close()
            time.sleep(0.5)
        self.peer = ObservedPeer()
        login(self.store, self.peer, self.account, self.current())

    def mark(self):
        return self.peer.mark()

    def matching(self, opcode, start, timeout=15):
        return self.peer.matching(opcode, start, timeout=timeout)

    def open(self, actor, action, root):
        start = self.mark()
        self.peer.send(13222, struct.pack(">qq", actor, action))
        movement_due = getattr(self, "movement_due_at", 0.0)
        timeout = max(15, movement_due - time.monotonic() + 5)
        body = self.peer.matching(12969, start, timeout=timeout)
        self.movement_due_at = 0.0
        actual = struct.unpack_from(">i", body)[0]
        assert actual == root, (
            "unexpected dialogue root",
            actor,
            actual,
            root,
            body.hex(),
        )
        self.receipt["events"].append({"open": [actor, action, root]})

    def choose(self, node, choice, target=0):
        start = self.mark()
        self.peer.send(12058, struct.pack(">ii", node, choice))
        body = self.matching(12218, start)
        actual = struct.unpack_from(">i", body)[0]
        assert actual == target, (
            "unexpected dialogue destination",
            node,
            choice,
            actual,
            target,
            body.hex(),
        )
        self.receipt["events"].append({"choice": [node, choice, target]})
        self.save()

    def walk(self, cell):
        current = self.current()
        start = tuple(current[k] for k in ("x", "y", "z"))
        if start == tuple(cell):
            return
        from wakfu_server.combat_terrain import published_geometry
        from protocol_codec import DIRECTIONS
        from collections import deque

        graph = published_geometry(current["map_id"]).outgoing
        previous, pending = {start: None}, deque([start])
        while pending and tuple(cell) not in previous:
            point = pending.popleft()
            for nxt in graph.get(point, ()):
                if nxt not in previous:
                    previous[nxt] = point
                    pending.append(nxt)
        if tuple(cell) not in previous:
            raise AssertionError(("No native exterior path", start, cell))
        path, point = [], tuple(cell)
        while point != start:
            path.append(point)
            point = previous[point]
        path.reverse()
        directions = {(dx, dy): key for key, (_, dx, dy) in DIRECTIONS.items()}
        for offset in range(0, len(path), 255):
            chunk = path[offset : offset + 255]
            self.movement_due_at = max(
                getattr(self, "movement_due_at", 0.0),
                time.monotonic() + 0.5 * len(chunk) + 0.1,
            )
            point = tuple(self.current()[k] for k in ("x", "y", "z"))
            encoded = bytearray()
            for nxt in chunk:
                encoded.append(
                    (directions[(nxt[0] - point[0], nxt[1] - point[1])] << 5)
                    | ((nxt[2] - point[2]) & 31)
                )
                point = nxt
            self.peer.send(
                13331,
                struct.pack(
                    ">iiihB",
                    0,
                    *tuple(self.current()[k] for k in ("x", "y", "z")),
                    len(chunk),
                )
                + encoded,
            )
            deadline = time.monotonic() + max(5, len(chunk) * 0.3)
            while time.monotonic() < deadline:
                if tuple(self.current()[k] for k in ("x", "y", "z")) == chunk[-1]:
                    break
                time.sleep(0.1)
            else:
                raise AssertionError(
                    ("native walk did not settle", chunk[-1], self.current())
                )

    def qty(self, reference):
        with self.store.connection() as db:
            row = db.execute(
                "SELECT coalesce(sum(quantity),0) AS n FROM inventory_items WHERE character_id=%s AND reference=%s",
                (self.character["id"], reference),
            ).fetchone()
            quest = db.execute(
                "SELECT coalesce(sum(quantity),0) AS n FROM character_quest_items WHERE character_id=%s AND reference=%s",
                (self.character["id"], reference),
            ).fetchone()
        return int(row["n"] or 0) + int(quest["n"] or 0)

    def assert_state(self, *, complete=(), running=(), objectives=()):
        state = self.progress()
        for quest in complete:
            assert quest in state["completed"], ("quest incomplete", quest, state)
        for quest in running:
            assert quest in state["running"], ("quest not running", quest, state)
        for objective in objectives:
            assert objective in state["objectives"], (
                "objective incomplete",
                objective,
                state,
            )
        self.receipt["latest_progress"] = {
            "running": state["running"],
            "completed": state["completed"],
            "objectives": state["objectives"],
            "variables": state["variables"],
        }
        self.save()

    def transport(self, source, destination, expected_map, expected_position=None):
        start = self.mark()
        self.peer.send(12296, struct.pack(">qiBi", source, destination, 0, 2))
        self.peer.matching(13974, start, timeout=35)
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            now = self.current()
            if now["map_id"] == expected_map and (
                expected_position is None
                or tuple(now[k] for k in ("x", "y", "z")) == tuple(expected_position)
            ):
                self.receipt["events"].append(
                    {
                        "transport": [source, destination, expected_map],
                        "instance_id": now["instance_id"],
                    }
                )
                self.save()
                return
            time.sleep(0.1)
        raise AssertionError(
            ("native transport destination mismatch", expected_map, self.current())
        )

    def npc(self, actor, action, root, anchor):
        now = self.current()
        if now["map_id"] != 527 or now["instance_id"] != 0:
            raise AssertionError(("NPC outside exterior map", now))
        with self.store.connection() as db:
            placement = db.execute(
                "SELECT x,y,z,interaction_range FROM world_dialogue_npcs WHERE actor_id=%s AND enabled",
                (actor,),
            ).fetchone()
        if tuple(now[k] for k in ("x", "y", "z")) != tuple(anchor):
            self.walk(anchor)
        self.open(actor, action, root)


def main():
    assert (
        os.environ.get("WAKFU_MOUNT_CHAIN_TLS") == "1"
    ), "Set WAKFU_MOUNT_CHAIN_TLS=1 to create the one permitted QA fixture"
    cfg = conninfo_to_dict(os.environ["WAKFU_DATABASE_URL"])
    assert cfg.get("host") in ("postgres", "127.0.0.1", "localhost", "::1"), cfg.get(
        "host"
    )
    resume = RECEIPT.exists()
    if resume and os.environ.get("WAKFU_MOUNT_CHAIN_RESUME") != "1":
        raise ValueError(
            f"Receipt exists; set WAKFU_MOUNT_CHAIN_RESUME=1 to resume same QA at {RECEIPT}"
        )
    if not resume and os.environ.get("WAKFU_MOUNT_CHAIN_RESUME") == "1":
        raise ValueError("Cannot resume because the QA receipt is absent")
    store = Store(
        os.environ["WAKFU_DATABASE_URL"],
        password_file=os.environ["WAKFU_DATABASE_PASSWORD_FILE"],
    )
    p = MountProbe(store, resume=resume)
    try:
        p.connect()
        print("QA", p.character["id"], "level35 profession83", flush=True)

        # 2013 actual talk, then explicitly accept parent reading quest2015.
        state = p.progress()
        if 2013 not in state["completed"]:
            p.npc(-2251799934992013, 354, 2166, (-89, -58, 0))
            p.choose(2166, 6483, 2707)
            p.choose(2707, 6489, 2715)
            p.choose(2715, 6519, 0)
        p.assert_state(complete=(2013,))
        assert p.qty(18682) == 1
        if (
            2015 not in p.progress()["running"]
            and 2015 not in p.progress()["completed"]
        ):
            p.open(-2251799934992013, 354, 2166)
            p.choose(2166, 13311, 2708)
            p.choose(2708, 6492, 0)
        p.assert_state(complete=(2013,))

        # Jenry book quest: real acceptance, physical bag pickup, native handback.
        if 2048 not in p.progress()["completed"]:
            if 2048 not in p.progress()["running"]:
                p.npc(-2251799934992048, 436, 2315, (-145, 122, -3))
                p.choose(2315, 6497, 2709)
                p.choose(2709, 6498, 2721)
                p.choose(2721, 6532, 2722)
                p.choose(2722, 6533, 0)
            if p.qty(18689) == 0:
                p.walk((-120, 64, 0))
                pickup = p.mark()
                p.peer.send(12870, struct.pack(">qHH", 23033, 0, 0))
                p.matching(13879, pickup, timeout=15)
                p.matching(13832, pickup, timeout=15)
            assert p.qty(18689) == 1
            p.npc(-2251799934992048, 436, 2315, (-145, 122, -3))
            p.choose(2315, 6534, 0)
        p.assert_state(complete=(2013, 2048))
        assert p.qty(18689) == 0 and p.qty(18628) == 1

        # Genuine private warehouse membership and original native rat victory.
        if 2016 not in p.progress()["completed"]:
            if 2016 not in p.progress()["running"]:
                p.npc(-2251799934992016, 429, 2297, (25, -35, 4))
                p.choose(2297, 6499, 2710)
                p.choose(2710, 6500, 0)
            p.assert_state(running=(2015, 2016))
            if p.current()["instance_id"] == 0:
                p.walk((20, -34, 0))
                p.transport(23030, 1798, 891)
            config = json.loads(
                (
                    ROOT
                    / "wakfu_server/maps/quest_encounter_profiles/astrub-warehouse.configuration.json"
                ).read_text()
            )
            current = p.current()
            assert current["instance_id"] > 0
            p.receipt["warehouse_entry"] = {
                "map_id": current["map_id"],
                "instance_id": current["instance_id"],
                "position": [current[k] for k in ("x", "y", "z")],
            }
            p.assert_state(running=(2015, 2016), objectives=(4079,))
            if p.current()["y"] > -50:
                walk_native(p, config, (-4, -5, 0))
                p.transport(23180, 1801, 891, (-11, -159, 0))
            if 4084 not in p.progress()["objectives"]:
                p.receipt["rat_fight"] = fight_owned_room(p, config)
                p.assert_state(running=(2015, 2016), objectives=(4079, 4084))
        if p.current()["instance_id"] > 0:
            walk_native(p, config, (-15, -159, 12))
            p.transport(23031, 1802, 891, (-4, -4, 0))
            walk_native(p, config, (0, 0, 0))
            p.transport(23181, 1799, 527, (20, -34, 0))
        assert p.current()["instance_id"] == 0
        if 2016 not in p.progress()["completed"]:
            p.npc(-2251799934992016, 429, 2297, (25, -35, 4))
            p.choose(2297, 6541, 0)
        p.assert_state(complete=(2013, 2048, 2016))
        assert p.qty(18629) == 1

        # Native recipe 3599, real occupation batches 1+4, then exact five-item payment.
        if 2017 not in p.progress()["completed"]:
            if 2017 not in p.progress()["running"]:
                p.npc(-2251799934992017, 430, 2299, (4, 49, 0))
                p.choose(2299, 6502, 2711)
                p.choose(2711, 6503, 0)
        craft_count = p.progress()["variables"].get("451", 0)
        handles_before = (
            p.qty(18782)
            if 2017 in p.progress()["completed"]
            else p.qty(18782) - craft_count
        )
        for batches, expected in (
            ((1, 1), (4, 5))
            if craft_count == 0
            else (((4, 5),) if craft_count == 1 else ())
        ):
            offset = p.mark()
            p.peer.send(12231, struct.pack(">qii", 20332, 3599, batches))
            body = p.matching(13989, offset, timeout=20)
            table, recipe, mode, duration, extra = struct.unpack(">qibqq", body)
            assert (table, recipe) == (20332, 3599) and 0 < duration < 60000, body.hex()
            time.sleep(duration / 1000 + 0.15)
            p.peer.send(13429, struct.pack(">Bh", 2, 8))
            counter = struct.unpack(">qiq", p.matching(13295, offset, timeout=20))
            assert counter == (p.character["id"], 451, expected), counter
            p.matching(12470, offset, timeout=10)
            p.assert_state(
                running=(2015, 2017), objectives=(() if expected == 1 else (4082,))
            )
            assert p.qty(18782) == handles_before + expected
            p.receipt.setdefault("crafts", []).append(
                {"batches": batches, "counter13295": counter, "duration_ms": duration}
            )
        if 2017 not in p.progress()["completed"]:
            p.npc(-2251799934992017, 430, 2299, (4, 49, 0))
            offset = p.mark()
            p.choose(2299, 6504, 0)
            p.matching(13832, offset, timeout=10)
            p.matching(12470, offset, timeout=10)
            p.matching(13422, offset, timeout=10)
        p.assert_state(complete=(2013, 2048, 2016, 2017, 2015))
        assert p.qty(18782) == handles_before and p.qty(18630) == 1

        # Parent acknowledgment, three-stage Missy chain, and final Melmac talk.
        if 2018 not in p.progress()["completed"]:
            p.npc(-2251799934992013, 354, 2166, (-89, -58, 0))
            p.choose(2166, 6507, 2712)
            p.choose(2712, 6508, 0)
        p.assert_state(complete=(2018,), running=(2019,), objectives=(4086,))
        if 2019 not in p.progress()["completed"]:
            p.npc(-2251799934992019, 431, 2301, (-37, 2, 3))
            p.choose(2301, 6509, 2713)
            p.choose(2713, 6510, 0)
        p.assert_state(complete=(2019,), running=(2025,), objectives=(4087,))
        if 2025 not in p.progress()["completed"]:
            p.npc(-2251799934992019, 431, 2301, (-37, 2, 3))
            p.choose(2301, 6514, 0)
        p.assert_state(complete=(2019, 2025), running=(2026,), objectives=(4099,))
        assert p.qty(8414) == 0
        if 2026 not in p.progress()["completed"]:
            p.npc(-2251799934992019, 431, 2301, (-37, 2, 3))
            p.choose(2301, 6516, 2714)
            p.choose(2714, 6517, 0)
        p.assert_state(complete=(2019, 2025, 2026), objectives=(4101,))
        assert p.qty(18631) == 1
        p.npc(-2251799934992013, 354, 2166, (-89, -58, 0))
        p.choose(2166, 6518, 0)
        p.assert_state(complete=(2013, 2015, 2016, 2017, 2018, 2019, 2025, 2026, 2027))
        p.connect()
        p.assert_state(complete=(2013, 2015, 2016, 2017, 2018, 2019, 2025, 2026, 2027))
        assert (
            p.qty(18682)
            == p.qty(18628)
            == p.qty(18629)
            == p.qty(18630)
            == p.qty(18631)
            == 1
        )
        p.receipt["result"] = "passed"
        p.save()
        print(
            "PASS seven-quest native Astrub mount precursor chain",
            json.dumps(p.receipt, default=str),
            flush=True,
        )
    except BaseException as exc:
        p.receipt["error"] = repr(exc)
        p.receipt["latest_progress"] = p.progress()
        p.save()
        raise
    finally:
        if p.peer:
            p.peer.close()


if __name__ == "__main__":
    main()
