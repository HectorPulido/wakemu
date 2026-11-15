"""Native Rii occupations for a real already connected character.

No character, quest, profession, inventory or location fixtures are written.
The caller walks to legitimate native interaction cells and owns the connection.
"""

import struct
import time
from wakfu_server.wire import proto_field


def _record_start(peer):
    if hasattr(peer, "observation_lock"):
        with peer.observation_lock:
            return len(peer.records)
    return None


def _owned(peer, opcode, character_id, actor_offset, *, timeout=25, start=None):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if start is not None:
            with peer.observation_lock:
                records = list(peer.records[start:])
            for received, body in records:
                if received in (349, 674):
                    raise AssertionError(
                        (
                            "Native occupation rejected",
                            received,
                            body.decode("utf-8", errors="replace"),
                        )
                    )
                if (
                    received == opcode
                    and struct.unpack_from(">q", body, actor_offset)[0] == character_id
                ):
                    return body
            time.sleep(0.03)
            continue
        body, _ = peer.wait(opcode, timeout=max(0.1, deadline - time.monotonic()))
        if struct.unpack_from(">q", body, actor_offset)[0] == character_id:
            return body
    raise AssertionError(("No owned native occupation started", opcode))


def harvest_monster(peer, character_id, monster_id, *, action_id=5097):
    start = _record_start(peer)
    peer.send(
        13481, proto_field(8, action_id) + proto_field(16, monster_id % (1 << 64))
    )
    body = _owned(peer, 13597, character_id, 3, start=start)
    time.sleep(struct.unpack_from(">q", body, 11)[0] / 1000 + 0.15)
    peer.send(13429, struct.pack(">Bh", 2, 6))


def harvest_flower(peer, character_id, x, y, *, action_id):
    # 2269 = seed at stage3;2270 = cut stage3;2271 = cut stage4.
    start = _record_start(peer)
    peer.send(
        12995,
        b"".join(
            proto_field(tag, value % (1 << 64))
            for tag, value in ((8, action_id), (16, x), (24, y))
        ),
    )
    body = _owned(peer, 12230, character_id, 3, start=start)
    time.sleep(struct.unpack_from(">q", body, 11)[0] / 1000 + 0.15)
    peer.send(13429, struct.pack(">Bh", 2, 3))


def plant(peer, character_id, item_uid, x, y, *, item_reference):
    action = {30927: 13427, 31007: 13500}[item_reference]
    start = _record_start(peer)
    peer.send(13220, struct.pack(">iqii", action, item_uid, x, y))
    body = _owned(peer, 12815, character_id, 3, start=start)
    time.sleep(struct.unpack_from(">i", body, 15)[0] / 1000 + 0.15)
    peer.send(13429, struct.pack(">Bh", 2, 2))


def craft(peer, *, count=3):
    """Caller must stand on native workshop interaction cell(19,18,1)."""
    peer.send(12231, struct.pack(">qii", 34659, 9445, count))
    body, _ = peer.wait(13989, timeout=25)
    table, recipe, _, duration, _ = struct.unpack(">qibqq", body)
    assert (table, recipe) == (34659, 9445), (table, recipe)
    time.sleep(duration / 1000 + 0.15)
    peer.send(13429, struct.pack(">Bh", 2, 8))


def progress(store, character_id):
    from wakfu_server.achievements import storage

    with store.connection() as db:
        return storage.load_locked(db, character_id)


def wait_counter(store, character_id, variable, expected, *, timeout=15):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        state = progress(store, character_id)
        if state["variables"].get(str(variable), 0) >= expected:
            return state
        time.sleep(0.1)
    raise AssertionError(
        ("Native occupation did not advance counter", variable, expected, state)
    )


def inventory_item(store, character_id, reference):
    with store.connection() as db:
        return db.execute(
            "SELECT * FROM inventory_items WHERE character_id=%s AND reference=%s AND quantity>0 ORDER BY uid LIMIT 1",
            (character_id, reference),
        ).fetchone()


def monsters(store, character):
    """Read actual available Wodents; exclude retired or unrelated training actors."""
    with store.connection() as db:
        rows = db.execute(
            "SELECT members FROM combat_groups WHERE map_id=%s AND instance_id=%s AND status='available'",
            (character["map_id"], character["instance_id"]),
        ).fetchall()
    return sorted(
        [m for row in rows for m in row["members"] if m["ref"] == 5455],
        key=lambda m: abs(m["x"] - character["x"]) + abs(m["y"] - character["y"]),
    )


def flowers(store, character):
    with store.connection() as db:
        rows = db.execute(
            "SELECT * FROM planted_resources WHERE map_id=%s AND instance_id=%s AND resource_reference=825 ORDER BY resource_uid",
            (character["map_id"], character["instance_id"]),
        ).fetchall()
    return sorted(
        rows, key=lambda m: abs(m["x"] - character["x"]) + abs(m["y"] - character["y"])
    )


def empty_soil(store, character, graph):
    """Yield reachable native single-height surfaces adjacent to the walk graph.

    Neither occupancy nor native geometry is fabricated. The server retains final
    species suitability and transaction validation when the request is submitted.
    """
    from wakfu_server.planting_cells import cells

    surfaces = cells(character["map_id"])
    with store.connection() as db:
        occupied = {
            (r["x"], r["y"])
            for r in db.execute(
                "SELECT x,y FROM planted_resources WHERE map_id=%s AND instance_id=%s",
                (character["map_id"], character["instance_id"]),
            ).fetchall()
        }
    reachable = set(graph)
    result = []
    for (x, y), rows in surfaces.items():
        if len(rows) != 1 or (x, y) in occupied:
            continue
        z = rows[0]["z"]
        approaches = [
            (x + dx, y + dy, z)
            for dx, dy in ((0, 1), (1, 0), (0, -1), (-1, 0))
            if (x + dx, y + dy, z) in reachable
        ]
        if approaches:
            result.append(dict(x=x, y=y, z=z, approaches=approaches))
    return sorted(
        result,
        key=lambda m: abs(m["x"] - character["x"]) + abs(m["y"] - character["y"]),
    )


def run_flower_objectives(
    peer, store, account, character_id, goto, graph, save_progress
):
    """Complete actual resource actions from current natural progress; no fixture writes."""

    def current():
        return store.character(account["id"], character_id)

    for variable, action in ((760, "plant"), (759, "seed"), (758, "cut")):
        deadline = time.monotonic() + 240
        while progress(store, character_id)["variables"].get(str(variable), 0) < 3:
            before = progress(store, character_id)["variables"].get(str(variable), 0)
            actor = current()
            if action == "plant":
                item = inventory_item(store, character_id, 31007)
                if item is None:
                    raise AssertionError("Natural flower seed supply exhausted")
                candidates = empty_soil(store, actor, graph)
                for target in candidates:
                    try:
                        goto(target["approaches"][0])
                    except ValueError:
                        continue
                    plant(
                        peer,
                        character_id,
                        item["uid"],
                        target["x"],
                        target["y"],
                        item_reference=31007,
                    )
                    break
                else:
                    raise AssertionError("No reachable unoccupied native planting cell")
            else:
                candidates = [
                    v
                    for v in flowers(store, actor)
                    if v["stage"] == 3 or (action == "cut" and v["stage"] == 4)
                ]
                for target in candidates:
                    approaches = [
                        (target["x"] + dx, target["y"] + dy, target["z"])
                        for dx, dy in ((0, 1), (1, 0), (0, -1), (-1, 0))
                    ]
                    for cell in approaches:
                        try:
                            goto(cell)
                            break
                        except ValueError:
                            continue
                    else:
                        continue
                    harvest_flower(
                        peer,
                        character_id,
                        target["x"],
                        target["y"],
                        action_id=(
                            2269
                            if action == "seed"
                            else (2270 if target["stage"] == 3 else 2271)
                        ),
                    )
                    break
                else:
                    if time.monotonic() > deadline:
                        raise AssertionError(
                            ("No naturally mature reachable flower", action)
                        )
                    time.sleep(1)
                    continue
            wait_counter(store, character_id, variable, before + 1)
            save_progress()


def run_ecology(peer, store, account, char, goto, approach, kill, checkpoint):
    """Run active ecology quests through actual native packets only.

    The caller opens Kheperalia's conversations between subquests. This function
    handles whichever of5145,5155,5156 is active, and never activates quests.
    """
    from wakfu_server.combat_terrain import published_geometry

    character_id = char["id"]

    def current():
        return store.character(account["id"], character_id)

    def mark(label):
        checkpoint(label)

    state = progress(store, character_id)
    if 5145 in state["running"]:
        # Harvest before killing: a legitimate seed-bearing Wodent must survive
        # the occupation. Cooldowns belong to each actual monster globally.
        seed_deadline = time.monotonic() + 180
        while progress(store, character_id)["variables"].get("756", 0) < 3:
            before = progress(store, character_id)["variables"].get("756", 0)
            with store.connection() as db:
                cooling = {
                    r["monster_id"]
                    for r in db.execute(
                        "SELECT monster_id FROM monster_harvest_receipts WHERE map_id=1385 AND instance_id=0 AND regenerates_until>%s",
                        (store.now(),),
                    ).fetchall()
                }
            candidates = [
                m for m in monsters(store, current()) if m["id"] not in cooling
            ]
            if not candidates:
                if time.monotonic() > seed_deadline:
                    raise AssertionError(
                        "No naturally regenerated Wodent seed source within180seconds"
                    )
                time.sleep(1)
                continue
            for monster in candidates:
                try:
                    approach(
                        dict(
                            monster,
                            actor_id=monster["id"],
                            map_id=1385,
                            instance_id=0,
                            interaction_range=1,
                        )
                    )
                except ValueError:
                    continue
                harvest_monster(peer, character_id, monster["id"])
                wait_counter(store, character_id, 756, before + 1)
                mark("wodent-seed-" + str(before + 1))
                break
            else:
                raise AssertionError("No reachable naturally harvestable Wodent")
        graph = published_geometry(1385).outgoing
        while progress(store, character_id)["variables"].get("757", 0) < 2:
            before = progress(store, character_id)["variables"].get("757", 0)
            item = inventory_item(store, character_id, 30927)
            if item is None:
                raise AssertionError("No naturally collected Wodent seed")
            for target in empty_soil(store, current(), graph):
                try:
                    goto(target["approaches"][0])
                except ValueError:
                    continue
                plant(
                    peer,
                    character_id,
                    item["uid"],
                    target["x"],
                    target["y"],
                    item_reference=30927,
                )
                wait_counter(store, character_id, 757, before + 1)
                mark("wodent-plant-" + str(before + 1))
                break
            else:
                raise AssertionError("No reachable native Wodent planting surface")
        while progress(store, character_id)["variables"].get("755", 0) < 3:
            before = progress(store, character_id)["variables"].get("755", 0)
            for monster in monsters(store, current()):
                try:
                    approach(
                        dict(
                            monster,
                            actor_id=monster["id"],
                            map_id=1385,
                            instance_id=0,
                            interaction_range=1,
                        )
                    )
                except ValueError:
                    continue
                kill(monster)
                wait_counter(store, character_id, 755, before + 1)
                mark("wodent-kill-" + str(before + 1))
                break
            else:
                raise AssertionError("No reachable native Wodent to fight")
    state = progress(store, character_id)
    if 5155 in state["running"]:
        run_flower_objectives(
            peer,
            store,
            account,
            character_id,
            goto,
            published_geometry(1385).outgoing,
            lambda: mark("flower-native-action"),
        )
    state = progress(store, character_id)
    if 5156 in state["running"]:
        for reference in (31006, 31158):
            item = inventory_item(store, character_id, reference)
            if item is None or item["quantity"] < 3:
                raise AssertionError(
                    ("Natural crafting materials missing", reference, item)
                )
        goto((19, 18, 1))
        craft(peer, count=3)
        deadline = time.monotonic() + 15
        while 10602 not in progress(store, character_id)["objectives"]:
            if time.monotonic() > deadline:
                raise AssertionError("Native crafting objective10602 did not complete")
            time.sleep(0.1)
        mark("craft-3-native")
