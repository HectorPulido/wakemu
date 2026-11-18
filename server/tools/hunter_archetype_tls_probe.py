"""Local native TLS acceptance for reconstructed Hunter IV/V and X dialogue.

Two isolated QA characters receive initial prior-quest/kill/item fixtures. The
default delivery scope declares all prior boss kills initially and exercises
only actual conversations/payments. Optional combat scope attempts a native
scaled boss fight; optional one-shot separately verifies a fresh victory. No
quest-complete, fake victory or post-start progress writes are used.
"""

import argparse
from collections import deque
import json
import os
from pathlib import Path
import secrets
import struct
import time

from psycopg.conninfo import conninfo_to_dict
from psycopg.types.json import Jsonb

from tools.rii_departure_probe import Probe, ObservedPeer, login
from tools.candidate_friendly_duel_socket_smoke import placement
from tools.candidate_combat_socket_reward_smoke import _spawned_actor
from tools.rii_lessons_complete_probe import Run
from wakfu_server.achievements import storage
from wakfu_server.command_permissions import set_admin
from wakfu_server.combat_terrain import published_geometry
from wakfu_server.progression import level_xp
from wakfu_server.store import Store

ACTOR = -2251799934991695
ACTION = 466
IV = {3269: 5114, 5793: 3587, 5791: 1786, 5795: 3735}
REMAINING_OBJECTIVE = 5795
BOSS = IV[REMAINING_OBJECTIVE]
V_KILLS = [3283, 3285, 3287, 3281]


class NativeRun(Run):
    """Acknowledge actual global native turns, including NPC-only turns."""

    def ready_for_input(self):
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            with self.peer.observation_lock:
                messages = self.peer.records[self.wire_cursor :]
                self.wire_cursor = len(self.peer.records)
            for opcode, body in messages:
                if len(body) < 4 or struct.unpack_from(">i", body)[0] != self.fight_id:
                    continue
                if opcode == 12053 and len(body) >= 30:
                    self.native_global_turn = struct.unpack_from(">i", body, 17)[0]
                elif opcode == 13482 and len(body) >= 28:
                    self.native_global_turn += 1
                elif opcode == 12502 and len(body) >= 28:
                    self.peer.send(13510, struct.pack(">i", self.native_global_turn))
            snap = self.checkpoint()
            if snap and (
                snap["phase"] == "finished"
                or (
                    snap["phase"] == "active"
                    and snap["order"][snap["turn_index"]] == self.char["id"]
                )
            ):
                return snap
            time.sleep(0.05)
        raise AssertionError(("No owned native input turn", self.fight_id))


class HunterProbe(Probe):
    def __init__(self, store, *, stage, path):
        self.store, self.peer, self.path = store, None, path
        if path.exists():
            self.receipt = json.loads(path.read_text())
            self.account = {"id": self.receipt["account_id"]}
            self.character = store.character(
                self.account["id"], self.receipt["character_id"]
            )
            if "error" in self.receipt:
                self.receipt.setdefault("prior_errors", []).append(
                    self.receipt.pop("error")
                )
            return
        suffix = "".join(secrets.choice("abcdefghjkmnpqrstuvwxyz") for _ in range(9))
        self.account = store.register(
            "hunter_flow_" + suffix, secrets.token_urlsafe(24)
        )
        self.character = store.create_character(
            self.account["id"], "Hunter Flow " + suffix, breed=19
        )
        set_admin(
            store,
            self.account["id"],
            True,
            operator="local-hunter-archetype-acceptance",
            reason="isolated native scaled-boss spawn; never administrative wins or quest completion",
        )
        document = json.loads(
            (
                Path(__file__).resolve().parents[1]
                / "wakfu_server/maps/native_quest_conversation_contracts.json"
            ).read_text()
        )
        self.receipt = dict(
            account_id=self.account["id"],
            character_id=self.character["id"],
            stage=stage,
            checks=[],
            scope=(
                "local TLS; all IV/V boss kills are initial fixture; actual native dialogue and inventory debits; no boss kill proof"
                if stage == "iv-v-delivery"
                else "local TLS; initial prior quest/kill/item fixtures; actual native dialogue and inventory debits; optional combat tracked separately"
            ),
        )
        row = next(
            p["row"] for p in document["placements"] if p["row"]["actor_id"] == ACTOR
        )
        graph = published_geometry(527)
        candidates = [
            cell
            for cell in graph.cells
            if cell[2] == row["z"]
            and abs(cell[0] - row["x"]) + abs(cell[1] - row["y"]) <= 2
        ]
        assert candidates, "No walkable native approach to the published disciple"
        cell = min(
            candidates, key=lambda p: (abs(p[0] - row["x"]) + abs(p[1] - row["y"]), p)
        )
        self.receipt["npc_approach"] = list(cell)
        with store.connection() as db:
            db.execute(
                "UPDATE characters SET map_id=527,instance_id=0,x=%s,y=%s,z=%s,level=230 WHERE id=%s AND account_id=%s",
                (*cell, self.character["id"], self.account["id"]),
            )
            db.execute(
                "UPDATE character_progression SET xp=%s WHERE character_id=%s",
                (level_xp(230), self.character["id"]),
            )
            state = storage.load_locked(db, self.character["id"])
            completed = [1695, 1708, 1715]
            objectives = [
                identity
                for identity in IV
                if stage == "iv-v-delivery" or identity != REMAINING_OBJECTIVE
            ] + V_KILLS
            if stage == "x":
                completed += [1717, 1719, 2869, 2870, 2871, 2872]
                state.update(
                    running=[4733], tracking=[4733], completed=completed, objectives=[]
                )
            else:
                state.update(
                    running=[], tracking=[], completed=completed, objectives=objectives
                )
            state["completion_dates"].update(
                {
                    str(identity): int(store.now().timestamp() * 1000)
                    for identity in completed
                }
            )
            storage.store(db, self.character["id"], state)
            db.execute(
                "INSERT INTO character_achievement_authority(character_id,snapshot,revision,provenance) VALUES(%s,%s,1,'hunter-archetype-initial-fixture') ON CONFLICT(character_id) DO UPDATE SET snapshot=EXCLUDED.snapshot,revision=character_achievement_authority.revision+1",
                (
                    self.character["id"],
                    Jsonb(
                        {k: state[k] for k in ("running", "completed", "objectives")}
                    ),
                ),
            )
            if stage in ("iv-v", "iv-v-delivery"):
                from wakfu_server.inventory import initialize

                initialize(db, self.character["id"])
                bag = db.execute(
                    "SELECT uid FROM inventory_containers WHERE character_id=%s AND kind=0",
                    (self.character["id"],),
                ).fetchone()
                payments = [
                    r for r in document["turnins"] if r["node_id"] in (2422, 2424)
                ]
                for slot, payment in enumerate(payments):
                    db.execute(
                        "INSERT INTO inventory_items(character_id,reference,quantity,container,slot) VALUES(%s,%s,%s,%s,%s)",
                        (
                            self.character["id"],
                            payment["item_reference"],
                            payment["quantity"],
                            bag["uid"],
                            slot,
                        ),
                    )
        self.character = self.current()
        self.save()

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.receipt, indent=2, default=str))

    def check(self, label):
        if label not in self.receipt["checks"]:
            super().check(label)
        self.receipt["progress"] = self.progress()
        self.save()

    def open(self, expected):
        start = self.peer.mark()
        self.peer.send(13222, struct.pack(">qq", ACTOR, ACTION))
        body = self.peer.matching(12969, start)
        assert struct.unpack_from(">i", body)[0] == expected, (
            "Unexpected disciple root",
            body.hex(),
            expected,
        )

    def choose(self, node, choice, expected=0):
        start = self.peer.mark()
        self.peer.send(12058, struct.pack(">ii", node, choice))
        body = self.peer.matching(12218, start)
        assert struct.unpack_from(">i", body)[0] == expected, (
            "Unexpected disciple transition",
            body.hex(),
            expected,
        )

    def quantity(self, reference):
        with self.store.connection() as db:
            return db.execute(
                "SELECT coalesce(sum(quantity),0) AS quantity FROM inventory_items WHERE character_id=%s AND reference=%s",
                (self.character["id"], reference),
            ).fetchone()["quantity"]

    def relocate(self, cell):
        """Use the native authorized movement command for QA travel only."""
        command = "!teleport 527 %s %s %s" % tuple(cell)
        start = self.peer.mark()
        self.peer.send(12366, struct.pack(">H", len(command)) + command.encode())
        self.peer.matching(13974, start, timeout=25)
        self.peer.send(12449)
        self.receipt.setdefault("qa_travel", []).append(
            dict(command=command, scope="owned QA movement only")
        )
        self.connect()

    def retire_pending_fight(self):
        """Clean up only this isolated QA owner's interrupted attempt normally."""
        with self.store.connection() as db:
            row = db.execute(
                "SELECT f.id,c.snapshot FROM combat_fights f "
                "JOIN combat_fight_participants p ON p.fight_id=f.id "
                "JOIN fight_checkpoints c ON c.fight_id=f.id "
                "WHERE p.character_id=%s AND f.status IN ('placement','active') ORDER BY f.id DESC LIMIT 1",
                (self.character["id"],),
            ).fetchone()
        if row is None:
            return
        start = self.peer.mark()
        self.peer.send(13952)
        self.peer.matching(12238, start, timeout=20)
        self.peer.send(12925, struct.pack(">iB", row["id"], 0))
        self.receipt.setdefault("abandoned_attempts", []).append(row["id"])
        self.connect()

    def reward_receipts(self):
        with self.store.connection() as db:
            return [
                dict(row)
                for row in db.execute(
                    "SELECT achievement_id,reward_key,delivered_at IS NOT NULL AS delivered "
                    "FROM character_achievement_reward_outbox WHERE character_id=%s "
                    "AND achievement_id=ANY(%s) ORDER BY achievement_id,reward_key",
                    (self.character["id"], [1717, 1719]),
                ).fetchall()
            ]

    def aggregate_receipts(self, identity):
        with self.store.connection() as db:
            return [
                dict(row)
                for row in db.execute(
                    "SELECT achievement_id,reward_key,delivered_at IS NOT NULL AS delivered "
                    "FROM character_achievement_reward_outbox WHERE character_id=%s AND achievement_id=%s "
                    "ORDER BY reward_key",
                    (self.character["id"], identity),
                ).fetchall()
            ]

    def aggregate_recovery(self):
        """Reconcile the same earned QA state through native selection twice."""
        before = self.quantity(29725)
        earned = 1707 in self.progress()["completed"]
        self.connect()
        self.retire_pending_fight()
        expected = tuple(self.receipt["npc_approach"])
        if tuple(self.current()[key] for key in ("x", "y", "z")) != expected:
            self.relocate(expected)
        assert (
            1707 in self.progress()["completed"]
        ), "Completed first five quests must earn native aggregate1707"
        assert 3226 in self.progress()["objectives"]
        first = self.quantity(29725)
        assert first >= 1 and (earned or first == before + 1)
        receipts = self.aggregate_receipts(1707)
        assert len(receipts) == 2 and all(row["delivered"] for row in receipts)
        from wakfu_server.cosmetic_store import load as cosmetics

        with self.store.connection() as db:
            owned = cosmetics(db, self.account["id"])
        assert sum(row[:2] == (7, 269) for row in owned.items) == 1
        if self.receipt["stage"] == "x":
            assert 9843 in self.progress()["objectives"]
            assert 2873 not in self.progress()["completed"]
            assert not self.aggregate_receipts(2873)
            self.open(4814)
            self.choose(4814, 11778)
        else:
            self.open(2429)
            assert 2869 in self.progress()["running"]
            self.choose(2429, 5884)
        self.connect()
        assert self.quantity(29725) == first
        assert self.aggregate_receipts(1707) == receipts
        if self.receipt["stage"] == "x":
            assert 2873 not in self.progress()["completed"]
            self.open(4814)
            self.choose(4814, 11778)
            self.check(
                "v4 HunterX preserves actual9843/root4814; first-five1707 earned, all-ten2873 remains unearned"
            )
        else:
            self.open(2429)
            self.choose(2429, 5884)
            self.check(
                "v4 reconnect earned1707/title269/item29725 once; existing first-five facts unlockedVI on NPC reopening"
            )
        self.receipt["v4_aggregate_1707"] = dict(
            item_reference=29725,
            quantity=first,
            title=269,
            reward_receipts=receipts,
            initial_item_quantity=before,
        )
        self.save()

    def fight(self, *, reference=BOSS, objective=REMAINING_OBJECTIVE):
        if objective in self.progress()["objectives"]:
            return
        self.relocate((0, 32, 0))
        from wakfu_server.monsters import reference as monster_reference, statistics

        # Some native ffC curves go below zero far beneath a species' minimum.
        # Pick the smallest living native scaling, never overwrite fighter HP.
        native = monster_reference(reference)
        level = next(
            level
            for level in range(1, native["min_level"] + 1)
            if (
                lambda stats: stats["HP"] > 0
                and all(stats[key] >= 0 for key in ("AP", "MP", "WP"))
            )(statistics(reference, level))
        )
        command = f"!monster {reference} {level} 1"
        start = self.peer.mark()
        self.peer.send(12366, struct.pack(">H", len(command)) + command.encode())
        raw = self.peer.matching(
            12608, start, lambda body: body[:2] == b"\x00\x01", timeout=30
        )
        monster = _spawned_actor(raw)
        assert monster["reference"] == reference, monster
        start = self.peer.mark()
        self.peer.send(
            13130, struct.pack(">qiihB", monster["id"], *monster["position"], 0)
        )
        fight_id, _ = placement(self.peer.matching(13652, start, timeout=30))
        runner = NativeRun(self.store, self.account, self.character, self.receipt)
        runner.peer, runner.fight_id = self.peer, fight_id
        runner.wire_cursor, runner.native_global_turn = self.peer.mark(), 0
        self.receipt["fight_id"] = fight_id
        self.receipt.setdefault("fights", []).append(
            dict(
                fight_id=fight_id, reference=reference, level=level, objective=objective
            )
        )
        self.save()
        self.peer.send(12523, b"\x01")
        deadline = time.monotonic() + 180
        while time.monotonic() < deadline:
            snap = runner.ready_for_input()
            if snap["phase"] == "finished":
                break
            hero = snap["actors"][str(self.character["id"])]
            enemies = [
                (int(identity), actor)
                for identity, actor in snap["actors"].items()
                if actor["team"] != hero["team"] and actor["hp"] > 0
            ]
            assert enemies, ("Active native fight has no living enemy", fight_id)
            enemy = min(
                enemies, key=lambda row: (row[0] != monster["id"], row[1]["hp"])
            )[1]
            here, target = tuple(hero["position"]), tuple(enemy["position"])
            if hero["ap"] < 2:
                runner.end_turn()
                continue
            if abs(here[0] - target[0]) + abs(here[1] - target[1]) == 1:
                runner.cast(5562, target, class_spell=True)
                continue
            graph = {}
            for left, right in snap["edges"]:
                graph.setdefault(tuple(left), []).append(tuple(right))
            previous, pending = {here: None}, deque([here])
            goal = None
            occupied = {
                tuple(a["position"])
                for a in snap["actors"].values()
                if a["hp"] > 0 and tuple(a["position"]) != here
            }
            while pending:
                point = pending.popleft()
                if abs(point[0] - target[0]) + abs(point[1] - target[1]) == 1:
                    goal = point
                    break
                for nxt in graph.get(point, ()):
                    if nxt not in previous and nxt not in occupied:
                        previous[nxt] = point
                        pending.append(nxt)
            assert goal is not None, ("No natural boss approach", here, target)
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
                    + b"".join(struct.pack(">iih", *p) for p in path[: hero["mp"]]),
                    label="ordinary scaled-boss approach",
                )
        snap = runner.checkpoint()
        assert (
            snap["phase"] == "finished"
            and snap["winner"] == snap["actors"][str(self.character["id"])]["team"]
        ), ("Native boss fight failed", fight_id)
        start = self.peer.mark()
        self.peer.send(12925, struct.pack(">iB", fight_id, 1))
        self.peer.matching(
            13046,
            start,
            lambda body: (
                len(body) == 15
                and struct.unpack_from(">q", body)[0] == self.character["id"]
                and body[10:] == b"\x11\xff\xff\xff\xff"
            ),
            timeout=20,
        )
        until = time.monotonic() + 10
        while (
            objective not in self.progress()["objectives"] and time.monotonic() < until
        ):
            time.sleep(0.1)
        assert objective in self.progress()["objectives"]
        self.check(
            f"actual native breed{reference} victory credited objective{objective}"
        )
        self.connect()
        self.relocate(tuple(self.receipt["npc_approach"]))

    def run(self, *, include_one_shot=False):
        self.connect()
        self.retire_pending_fight()
        if self.receipt["stage"] == "x":
            if 9843 not in self.progress()["objectives"]:
                self.open(3451)
                self.choose(3451, 11776, 4813)
                assert 9843 in self.progress()["objectives"]
                self.choose(4813, 11777)
                self.check("HunterX native offered talk actually settled9843")
            self.connect()
            self.open(4814)
            self.choose(4814, 11778)
            self.check(
                "HunterX reconnect selected delivery stage4814 from real objective9843"
            )
            return
        if 1717 not in self.progress()["completed"]:
            self.open(2422)
            assert 1717 in self.progress()["running"]
            self.choose(2422, 5869)
            self.check("NPC opening activated HunterIV through earned predecessor")
            if self.receipt["stage"] == "iv-v":
                self.fight()
            else:
                assert set(IV) <= set(self.progress()["objectives"])
                self.check(
                    "delivery-only initial fixture declares all prior IV/V boss kills; no kill proof claimed"
                )
        document = json.loads(
            (
                Path(__file__).resolve().parents[1]
                / "wakfu_server/maps/native_quest_conversation_contracts.json"
            ).read_text()
        )
        for root, quest in ((2422, 1717), (2424, 1719)):
            if quest in self.progress()["completed"]:
                continue
            for payment in (r for r in document["turnins"] if r["node_id"] == root):
                current = self.progress()
                binding = next(
                    b
                    for b in document["bindings"]
                    if b["node_id"] == root and b["choice_id"] == payment["choice_id"]
                )
                if binding["objective_id"] in current["objectives"]:
                    continue
                self.open(root)
                before = self.quantity(payment["item_reference"])
                start = self.peer.mark()
                self.choose(root, payment["choice_id"])
                assert (
                    self.quantity(payment["item_reference"])
                    == before - payment["quantity"]
                )
                assert binding["objective_id"] in self.progress()["objectives"]
                with self.peer.observation_lock:
                    opcodes = [op for op, _ in self.peer.records[start:]]
                    objectives = [
                        struct.unpack_from(">qi", body)[1]
                        for op, body in self.peer.records[start:]
                        if op == 13832 and len(body) == 12
                    ]
                assert 12470 in opcodes, (
                    "Missing native inventory debit packet",
                    opcodes,
                )
                assert binding["objective_id"] in objectives, (
                    "Missing immediate native objective packet",
                    binding["objective_id"],
                    opcodes,
                )
                self.receipt.setdefault("payments", []).append(
                    dict(
                        objective_id=binding["objective_id"],
                        reference=payment["item_reference"],
                        quantity=payment["quantity"],
                        opcodes=opcodes,
                    )
                )
                self.check(
                    f"paid native objective{binding['objective_id']} with exact inventory debit"
                )
            assert quest in self.progress()["completed"]
            self.check(f"Hunter{quest} completed through actual item delivery")
        assert 1707 in self.progress()["completed"]
        rewards_before = self.reward_receipts()
        expected_rewards = sum(
            len(d["cjK"]) for d in document["definitions"] if d["d"] in (1717, 1719)
        )
        assert len(rewards_before) == expected_rewards and all(
            row["delivered"] for row in rewards_before
        )
        self.connect()
        self.open(2429)
        self.choose(2429, 5884)
        assert {1717, 1719} <= set(self.progress()["completed"])
        assert 2869 in self.progress()["running"]
        assert self.reward_receipts() == rewards_before
        self.receipt["reward_receipts"] = rewards_before
        self.check(
            "HunterV stayed completed after reconnect; native first-five1707 unlockedVI"
        )
        if include_one_shot and 3970 not in self.progress()["completed"]:
            assert 3970 not in self.progress()["running"]
            self.fight(reference=4097, objective=8461)
            assert 3970 in self.progress()["completed"]
            with self.store.connection() as db:
                receipts = db.execute(
                    "SELECT reward_key,delivered_at IS NOT NULL AS delivered FROM character_achievement_reward_outbox "
                    "WHERE character_id=%s AND achievement_id=3970 ORDER BY reward_key",
                    (self.character["id"],),
                ).fetchall()
            assert len(receipts) == 2 and all(row["delivered"] for row in receipts)
            self.receipt["one_shot_3970_rewards"] = [dict(row) for row in receipts]
            self.check(
                "one-shot3970 accepted and completed from actual native4097 victory; both rewards delivered"
            )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--receipt-dir", type=Path, default=Path(".local-state/wakemu/qa")
    )
    parser.add_argument(
        "--scope", choices=("deliveries", "combat"), default="deliveries"
    )
    parser.add_argument("--include-one-shot", action="store_true")
    parser.add_argument(
        "--aggregate-recovery",
        action="store_true",
        help="Only verify v4 aggregate recovery on existing receipts; do not create/reset QA fixtures",
    )
    args = parser.parse_args()
    url = os.environ["WAKFU_DATABASE_URL"]
    config = conninfo_to_dict(url)
    if config.get("host") not in ("127.0.0.1", "localhost", "::1"):
        raise ValueError("This acceptance probe may only use local PostgreSQL")
    store = Store(url, password_file=os.environ["WAKFU_DATABASE_PASSWORD_FILE"])
    first = "iv-v-delivery" if args.scope == "deliveries" else "iv-v"
    for stage in (first, "x"):
        path = args.receipt_dir / f"hunter-archetype-{stage}.json"
        if args.aggregate_recovery and not path.exists():
            raise ValueError(
                "Aggregate recovery requires existing isolated QA receipts"
            )
        probe = HunterProbe(store, stage=stage, path=path)
        try:
            if args.aggregate_recovery:
                probe.aggregate_recovery()
            else:
                probe.run(include_one_shot=args.include_one_shot)
        except BaseException as error:
            probe.receipt["error"] = repr(error)
            probe.save()
            raise
        finally:
            if probe.peer is not None:
                probe.peer.close()
    print(
        "PASS Hunter IV/V native payment flow, deferred VI and HunterX talk-stage recovery",
        flush=True,
    )


if __name__ == "__main__":
    main()
