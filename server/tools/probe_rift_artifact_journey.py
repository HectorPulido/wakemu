"""Opt-in live TLS artifact/wave/reconnect probe, using one NEW local QA owner.

The declared level245 Cra build/equipment is a pre-fight fixture premise, not
earned progress. After login all gameplay uses real World packets. Installed
policy, roster, RNG, AI, costs, artifacts and rewards are never replaced. Turn
ACKs derive only from received native timeline/boundary packets. A normal
surrender ends the bounded journey; this is not a complete forty-turn victory.

Run with PYTHONPATH=server:server/tests and the serving local Store environment.
Never run against production or a pre-existing player identity.
"""
import argparse
from collections import defaultdict, deque
from copy import deepcopy
import json
import os
from pathlib import Path
import secrets
import select
import struct
import time

from tools import probe_rift_native_ready as entry
from tools import verify_clean_install as access
from wakfu_server.combat_geometry import published_geometry
from wakfu_server.store import Store


class TimelinePeer:
    """Minimal original SU consumer: recovery, begin, table, and end ACK."""

    def __init__(self, peer, events):
        self.peer, self.events = peer, events
        self.round = self.turn = self.actor = self.fight_id = None
        self.acks = []
        self.opcodes = []
        self.packet_records = []

    def receive(self, opcode, body):
        self.opcodes.append(opcode)
        self.packet_records.append(
            dict(opcode=opcode, length=len(body), payload_prefix_hex=body[:256].hex())
        )
        if opcode == 12233:
            # Ordinary fresh fights initialize SU at zero and publish
            # 13477/13337/13482.12053 is only needed for a replacement timeline.
            if len(body) != 4:
                raise ValueError("Invalid native placement-end identity")
            self.fight_id = struct.unpack(">i", body)[0]
            self.round = self.turn = 0
            self.actor = None
        elif opcode == 12053:
            fight_id, length = struct.unpack_from(">ih", body)
            if len(body) != length + 6 or body[6:13] != struct.pack(
                ">BBiB", 1, 0, 6, 0
            ):
                raise ValueError("Unexpected original timeline field envelope")
            size = struct.unpack_from(">h", body, 13)[0]
            if size != len(body) - 15:
                raise ValueError("Truncated original timeline recovery")
            self.round, self.turn, phase = struct.unpack_from(">hiB", body, 15)
            position = 30  # envelope15 + SU round2/turn4/phase1/deadline8
            orders = []
            for _ in range(2):
                count = struct.unpack_from(">b", body, position)[0]
                position += 1
                if count < 1:
                    raise ValueError("Missing native timeline order")
                orders.append(struct.unpack_from(">" + "q" * count, body, position))
                position += count * 8
            progress = struct.unpack_from(">b", body, position)[0]
            position += 1 + progress * 10
            cursor = struct.unpack_from(">b", body, position)[0]
            self.actor = orders[0][cursor] if phase == 1 else None
            self.fight_id = fight_id
            self.events.append(
                dict(
                    kind="wire_recovery",
                    fight_id=fight_id,
                    turn=self.turn,
                    round=self.round,
                    phase=phase,
                )
            )
        elif opcode == 13477:
            self.round = struct.unpack_from(">h", body, 12)[0]
        elif opcode == 13482:
            if self.turn is None:
                raise ValueError("Native begin arrived before timeline recovery")
            self.actor = struct.unpack_from(">q", body, 12)[0]
            self.turn += 1
            self.events.append(
                dict(
                    kind="wire_begin",
                    actor=self.actor,
                    turn=self.turn,
                    round=self.round,
                )
            )
        elif opcode == 12502:
            ended = struct.unpack_from(">q", body, 12)[0]
            if self.turn is None or ended != self.actor:
                raise ValueError("Turn end does not match received native begin")
            # SU global turn came from cvn12053/eE13482, never awaiting_ack,
            # database writes, runtime monkeypatches or manufactured success.
            self.peer.send(13510, struct.pack(">i", self.turn))
            self.acks.append(self.turn)
            self.events.append(dict(kind="wire_ack", actor=ended, turn=self.turn))
            self.actor = None

    def drain(self, seconds=0.12):
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            if (
                not self.peer.connection.pending()
                and not select.select(
                    [self.peer.connection],
                    [],
                    [],
                    min(0.05, max(0, deadline - time.monotonic())),
                )[0]
            ):
                continue
            length = struct.unpack(">I", self.peer.exact(4))[0]
            if not 6 <= length <= 327670:
                raise ValueError("Invalid World frame length")
            payload = self.peer.exact(length - 4)
            self.receive(struct.unpack_from(">H", payload)[0], payload[2:])


def build():
    from native_paid_party_fixture import NativePartyBuild, NativeGear

    return NativePartyBuild(
        breed=9,
        level=245,
        active_spells=(4769, 4816),
        aptitudes=(
            (1, 50),
            (23, 50),
            (37, 20),
            (2, 1),
            (3, 1),
            (4, 1),
            (8, 1),
            (20, 20),
            (19, 10),
        ),
        gear=tuple(
            NativeGear(reference, slot, damage_mask=26)
            for reference, slot in (
                (20722, 3),
                (20723, 5),
                (20724, 13),
                (20725, 0),
                (20726, 12),
                (20727, 4),
                (20728, 7),
                (20729, 15),
                (20730, 8),
            )
        ),
    )


def walk_to_native_exit(peer, geometry, start, source):
    """Use bEG/bEm's actual published approach, not an invented radius."""
    from protocol_codec import DIRECTIONS

    if source.get("approach_mask", 0):
        goals = {
            tuple(int(point[k]) for k in ("x", "y", "z"))
            for point in source["approach_positions"]
        }
    else:
        goals = {
            cell
            for cell in geometry.cells
            if cell[:2] == (int(source["x"]), int(source["y"]))
        }
    path = entry.path_to(geometry, start, goals)
    if len(path) > 255:
        raise ValueError("Native exit path exceeds its wire length")
    directions = {(x, y): key for key, (_, x, y) in DIRECTIONS.items()}
    steps, current = bytearray(), start
    for cell in path:
        dz = cell[2] - current[2]
        if not -16 <= dz <= 15:
            raise ValueError("Native exit altitude delta is not encodable")
        steps.append(
            (directions[(cell[0] - current[0], cell[1] - current[1])] << 5) | (dz & 31)
        )
        current = cell
    if steps:
        peer.send(13331, struct.pack(">iiihB", 0, *start, len(steps)) + steps)
    return current


def existing_qa(store, name, *, continue_fight=None):
    """Reuse only an explicitly named complete fixture; never regrant or heal."""
    from wakfu_server.equipment_stats import bonuses

    if not name.startswith("artifactqa") or len(name) != 22 or not name.isalpha():
        raise ValueError("Only this probe's explicitly named QA identities may resume")
    account = store.authenticate(name, "isolated-party-test-password")
    if account is None:
        raise ValueError("Dedicated QA authentication failed")
    with store.connection() as db:
        rows = db.execute(
            "SELECT id FROM characters WHERE account_id=%s AND name=%s AND deleted_at IS NULL",
            (account["id"], name),
        ).fetchall()
        if len(rows) != 1:
            raise ValueError("Dedicated QA character identity is ambiguous")
        identity = rows[0]["id"]
        active = db.execute(
            "SELECT f.id FROM combat_fight_participants p JOIN combat_fights f ON f.id=p.fight_id "
            "WHERE p.character_id=%s AND f.status IN ('active','placement')",
            (identity,),
        ).fetchall()
        if continue_fight is not None:
            assert [row["id"] for row in active] == [
                continue_fight
            ], "Explicit continued fight differs from owned active fight"
        elif active:
            raise ValueError(
                "Dedicated QA still has an active fight; do not overwrite it"
            )
    character = store.character(account["id"], identity)
    expected = build()
    assert character["breed"] == expected.breed and character["level"] == expected.level
    equipped = set(bonuses(character)["equipped_uids"])
    items = [row for row in character["inventory_items"] if row["uid"] in equipped]
    assert sorted(row["reference"] for row in items) == sorted(
        row.reference for row in expected.gear
    )
    slots = {row.reference: row.slot for row in expected.gear}
    return character, [
        dict(uid=row["uid"], reference=row["reference"], slot=slots[row["reference"]])
        for row in items
    ]


def leave_native_rift(store, wire, character, geometry, source, destination):
    current = store.character(character["account_id"], character["id"])
    assert current["map_id"] == source["map_id"]
    target = walk_to_native_exit(
        wire.peer, geometry, tuple(current[k] for k in ("x", "y", "z")), source
    )
    entry.wait_for(
        lambda: tuple(
            store.character(character["account_id"], character["id"])[k]
            for k in ("x", "y", "z")
        )
        == target
    )
    wire.peer.send(
        12296, struct.pack(">qiBi", source["id"], destination["destination_id"], 0, 2)
    )
    wire.peer.until(13974)
    wire.peer.send(14689)
    exterior = store.character(character["account_id"], character["id"])
    assert exterior["map_id"] == destination["map_id"] and exterior["instance_id"] == 0
    return {k: exterior[k] for k in ("map_id", "instance_id", "x", "y", "z")}


def checkpoint(store, owner):
    with store.connection() as db:
        row = db.execute(
            "SELECT r.instance_id,r.fight_id,r.status AS run_status,r.wave,"
            "f.status AS fight_status,c.revision,c.snapshot FROM rift_instances r "
            "JOIN combat_fights f ON f.id=r.fight_id "
            "LEFT JOIN fight_checkpoints c ON c.fight_id=f.id "
            "WHERE r.owner_character_id=%s ORDER BY r.created_at DESC LIMIT 1",
            (owner,),
        ).fetchone()
    if row is None or not row["snapshot"]:
        return None
    state = row["snapshot"]
    if isinstance(state, str):
        state = json.loads(state)
    return dict(row, snapshot=state)


def observed(state, owner):
    actor = state["actors"][str(owner)]
    rift = state["rift_wave_state"]
    return dict(
        wave=rift["wave"],
        phase=state["phase"],
        turn=state["turn_id"],
        position=actor["position"],
        hp=actor["hp"],
        ap=actor["ap"],
        mp=actor["mp"],
        groups=deepcopy(rift.get("native_artifact_groups", {})),
        live_area_ids=sorted(int(uid) for uid in state.get("native_effect_areas", {})),
    )


def validate_groups(state, previous):
    """Public ledger/lifetime invariants, independent of recovery implementation."""
    groups = state["rift_wave_state"].get("native_artifact_groups", {})
    all_original = []
    for wave, group in groups.items():
        originals = set(map(int, group["original"]))
        all_original.extend(originals)
        assert len(group["remaining"]) == len(set(group["remaining"]))
        assert set(group["remaining"]) <= originals
        assert 0 <= group["choices_made"] <= group["choices_allowed"]
        receipts = group.get("assignments", [])
        consumed = [row["opponent"] for row in receipts]
        consumed += [row["collected"] for row in receipts]
        assert len(consumed) == len(set(consumed)), "Duplicate artifact assignment"
        assert not set(consumed) & set(group["remaining"])
        activations = state.get("native_artifact_activation_receipts", {})
        for uid in consumed:
            assert str(uid) in activations and activations[str(uid)]["complete"] is True
            assert str(uid) not in state.get(
                "native_effect_areas", {}
            ), "Consumed Qq remains live"
        old = previous.get(wave)
        if old is not None:
            assert old["original"] == group["original"], "Artifact IDs regenerated"
            assert receipts[: len(old.get("assignments", []))] == old.get(
                "assignments", []
            )
            assert set(group["remaining"]) <= set(
                old["remaining"]
            ), "Consumed artifact resurrected"
    assert len(all_original) == len(
        set(all_original)
    ), "Artifact UID reused across waves"
    return deepcopy(groups)


def shortest(state, start, goals, owner):
    cells = set(map(tuple, state["walkable"]))
    occupied = {
        tuple(a["position"])
        for a in state["actors"].values()
        if a["id"] != owner and a["hp"] > 0
    }
    cells -= occupied
    edges = defaultdict(list)
    for first, second in state.get("edges") or ():
        first, second = tuple(first), tuple(second)
        if first in cells and second in cells:
            edges[first].append(second)
    if not edges:
        for x, y, z in cells:
            edges[x, y, z] = [
                (x + dx, y + dy, z)
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))
                if (x + dx, y + dy, z) in cells
            ]
    pending, previous = deque([start]), {start: None}
    while pending:
        current = pending.popleft()
        if current in goals:
            path = []
            while previous[current] is not None:
                path.append(current)
                current = previous[current]
            return list(reversed(path))
        for cell in sorted(edges[current]):
            if cell not in previous:
                previous[cell] = current
                pending.append(cell)
    return []


def login_peer(username, character, events, *, reconnect=False):
    login = access.post(
        "/login", dict(username=username, password="isolated-party-test-password")
    )
    if not reconnect:
        return TimelinePeer(entry.selected(login, character), events)
    ticket, _ = access.dispatcher_ticket(login["game_token"])
    peer = access.Peer(access.ACCESS["world_port"])
    peer.send(426, access.text(ticket) + access.text("rift-artifact-journey"))
    peer.until(13873)
    peer.send(
        23664, struct.pack(">q", character["id"]) + access.text(character["name"])
    )
    wire = TimelinePeer(peer, events)
    # The original client loads the selected scene. World attaches a surviving
    # fight only after this normal request sets loaded=True; selection alone
    # deliberately does not publish an actionable fight onto an unloaded map.
    peer.send(14689)
    deadline = time.monotonic() + 40
    try:
        while 12053 not in wire.opcodes and time.monotonic() < deadline:
            wire.drain(0.2)
    finally:
        events.append(dict(kind="reconnect_packets", packets=wire.packet_records))
    assert (
        12847 in wire.opcodes and 12053 in wire.opcodes
    ), "Real reconnect bootstrap absent"
    return wire


def admit_new_rift(store, wire, character, outside, inside, portal, altar):
    owner = character["id"]
    exterior = store.character(character["account_id"], owner)
    portal_approach = entry.walk(
        wire.peer, outside, tuple(exterior[k] for k in ("x", "y", "z")), portal
    )
    entry.wait_for(
        lambda: tuple(
            store.character(character["account_id"], owner)[k] for k in ("x", "y", "z")
        )
        == portal_approach
    )
    wire.peer.send(12870, struct.pack(">qHH", portal["object_id"], 11, 0))
    bootstrap = wire.peer.until(13974)
    size = struct.unpack_from(">H", bootstrap)[0]
    fields = struct.unpack(">BqBqiihqBBiihq", bootstrap[2 : 2 + size])
    assert fields[1] == owner and fields[7] == altar["map_id"]
    wire.peer.send(14689)
    destination = entry.walk(wire.peer, inside, tuple(fields[4:7]), altar)
    entry.wait_for(
        lambda: tuple(
            store.character(character["account_id"], owner)[k] for k in ("x", "y", "z")
        )
        == destination
    )
    wire.peer.send(12870, struct.pack(">qHH", altar["id"], 0, 0))
    wire.peer.until(12847)
    wire.peer.send(12523, b"\x01")
    initial_deadline = time.monotonic() + 40
    while wire.actor is None and time.monotonic() < initial_deadline:
        wire.drain(0.2)
    assert wire.actor is not None, "Native first turn was not published"


def run(
    store,
    receipt,
    *,
    seconds,
    reuse_dedicated_qa=None,
    continue_fight=None,
    continue_receipt=None
):
    from native_paid_party_fixture import persisted_party_character

    with store.connection() as db:
        catalog = db.execute(
            "SELECT value FROM settings WHERE name='rift_catalog'"
        ).fetchone()["value"]["3"]
    assert catalog["type"] == "INFINITE_WAVE" and catalog["map_id"] == 1314
    portal = catalog["entrances"][0]
    outside, inside = published_geometry(portal["map_id"]), published_geometry(
        catalog["map_id"]
    )
    approach = entry.nearby(outside, portal)[0]
    altar = next(
        row
        for row in catalog["objects"]
        if row["type"] == "GenericActivableInteractiveElement"
    )
    from wakfu_server.generic_transports import source as transport_source

    exit_object = next(row for row in catalog["objects"] if row["type"] == "Teleporter")
    exit_source = transport_source(catalog["map_id"], exit_object["id"])
    exits = [
        row for row in exit_source["destinations"] if row["map_id"] != catalog["map_id"]
    ]
    assert len(exits) == 1, "Probe needs the unique original Rift exit destination"
    exit_destination = exits[0]
    username = reuse_dedicated_qa or "artifactqa" + "".join(
        secrets.choice("abcdefghijklmnopqrstuvwxyz") for _ in range(12)
    )
    # The helper creates a brand-new account itself. Its only non-gameplay
    # writes establish the declared build before the first real HTTP login.
    if reuse_dedicated_qa is None:
        character, _, _, _, admitted = persisted_party_character(
            store, build(), name=username, map_id=portal["map_id"], position=approach
        )
    else:
        character, admitted = existing_qa(
            store, username, continue_fight=continue_fight
        )
    owner = character["id"]
    receipt.update(
        account_id=character["account_id"],
        character_id=owner,
        setup=dict(
            level=245,
            breed=9,
            active_spells=[4769, 4816],
            gear=admitted,
            reused_existing_qa=reuse_dedicated_qa is not None,
            scope="new QA only; pre-fight build premise; no earned acquisition claim",
        ),
    )
    events = receipt.setdefault("events", [])
    prior, baseline = None, None
    if continue_fight is not None:
        prior = json.loads(continue_receipt.read_text())
        assert (prior["account_id"], prior["character_id"], prior["fight_id"]) == (
            character["account_id"],
            owner,
            continue_fight,
        )
        baseline = checkpoint(store, owner)
        assert baseline["fight_id"] == continue_fight
        receipt["continued_from"] = str(continue_receipt)
    wire = login_peer(username, character, events, reconnect=continue_fight is not None)
    before_login_position = {
        k: character[k] for k in ("map_id", "instance_id", "x", "y", "z")
    }
    character = store.character(character["account_id"], owner)
    after_login_position = {k: character[k] for k in before_login_position}
    if after_login_position != before_login_position:
        receipt["login_location_recovery"] = dict(
            before=before_login_position, after=after_login_position
        )
    receipt["cleanup"] = "not_started"
    try:
        if continue_fight is not None:
            first = checkpoint(store, owner)
            assert first["fight_id"] == continue_fight
            assert (
                first["snapshot"]["rift_wave_state"]["native_artifact_groups"]
                == baseline["snapshot"]["rift_wave_state"]["native_artifact_groups"]
            ), "Reconnect changed artifact ownership"
            assert first["snapshot"].get(
                "native_artifact_activation_receipts"
            ) == baseline["snapshot"].get(
                "native_artifact_activation_receipts"
            ), "Reconnect changed native activation receipts"
            before_owner = baseline["snapshot"]["actors"][str(owner)]
            after_owner = first["snapshot"]["actors"][str(owner)]
            for key in ("ap", "mp", "state_ledger"):
                assert (
                    after_owner[key] == before_owner[key]
                ), "Reconnect changed earned effects or action costs"
            receipt["reconnect"] = dict(
                status="PASS",
                fight_id=continue_fight,
                preserved_groups=deepcopy(
                    first["snapshot"]["rift_wave_state"]["native_artifact_groups"]
                ),
            )
        elif character["instance_id"]:
            assert character["map_id"] == catalog["map_id"]
            receipt["prior_attempt_native_exit"] = leave_native_rift(
                store, wire, character, inside, exit_source, exit_destination
            )
        elif continue_fight is None:
            assert character["map_id"] == portal["map_id"]
        if continue_fight is None:
            admit_new_rift(store, wire, character, outside, inside, portal, altar)
        first = entry.wait_for(lambda: checkpoint(store, owner))
        receipt.update(
            fight_id=first["fight_id"],
            instance_id=first["instance_id"],
            frozen_policy=first["snapshot"]["rift_wave_state"]["policy"],
        )
        deadline = time.monotonic() + seconds
        previous, attempted, reconnect_done, paid_casts, contact_done = (
            {},
            set(),
            continue_fight is not None,
            [],
            False,
        )
        if prior is not None:
            receipt["native_contact_cost"] = prior["native_contact_cost"]
            for event in prior["events"]:
                if (
                    event.get("kind") == "paid_input"
                    and event["opcode"] == 13260
                    and event["after"]["ap"] < event["before"]["ap"]
                ):
                    paid_casts.append(
                        dict(
                            wave=event["before"]["wave"],
                            ap_before=event["before"]["ap"],
                            ap_after=event["after"]["ap"],
                            source_receipt=str(continue_receipt),
                        )
                    )
        last_wave = None
        while time.monotonic() < deadline:
            wire.drain()
            row = checkpoint(store, owner)
            state = row["snapshot"]
            now = observed(state, owner)
            previous = validate_groups(state, previous)
            if now["wave"] != last_wave:
                events.append(dict(kind="durable_wave", **now))
                last_wave = now["wave"]
            if state["phase"] != "active" or row["fight_status"] != "active":
                raise AssertionError("Fight ended before repeated artifact journey")
            actor = state["actors"][str(owner)]
            assert actor["hp"] > 0, "QA owner died before artifact journey completed"
            current = state["order"][state["turn_index"]]
            if (
                current != owner
                or wire.actor != owner
                or state["runtime"]["awaiting_ack"] is not None
            ):
                continue
            groups = now["groups"]
            contact_done |= groups.get("1", {}).get("choices_made", 0) > 0
            if contact_done and now["wave"] >= 2 and not reconnect_done:
                before = deepcopy(groups)
                budget = (actor["ap"], actor["mp"])
                earned = deepcopy(actor["state_ledger"])
                activations = deepcopy(
                    state.get("native_artifact_activation_receipts", {})
                )
                identity = row["fight_id"]
                wire.peer.close()
                wire = login_peer(username, character, events, reconnect=True)
                after = entry.wait_for(lambda: checkpoint(store, owner))
                assert after["fight_id"] == identity
                assert (
                    after["snapshot"]["rift_wave_state"]["native_artifact_groups"]
                    == before
                )
                resumed = after["snapshot"]["actors"][str(owner)]
                assert (
                    resumed["ap"],
                    resumed["mp"],
                ) == budget, "Reconnect recharged or repaid action costs"
                assert (
                    resumed["state_ledger"] == earned
                ), "Reconnect changed earned native states"
                assert (
                    after["snapshot"].get("native_artifact_activation_receipts", {})
                    == activations
                )
                receipt["reconnect"] = dict(
                    status="PASS", fight_id=identity, preserved_groups=before
                )
                reconnect_done = True
                continue
            if (
                now["wave"] >= 3
                and reconnect_done
                and any(c["wave"] >= 3 for c in paid_casts)
            ):
                assert groups["1"]["choices_made"] >= 1
                assert groups["2"][
                    "assignments"
                ], "Second ordinary artifact group never assigned"
                receipt.update(
                    status="PASS_BOUNDED_LIVE_JOURNEY", final=now, paid_casts=paid_casts
                )
                break
            move_path = []
            # Earn the first choice by actual movement/contact. Leave the next
            # group unclaimed to exercise automatic assignment on wave3.
            if not contact_done and actor["mp"] > 0:
                remaining = groups.get("1", {}).get("remaining", [])
                goals = {
                    tuple(state["native_effect_areas"][str(uid)]["cell"])
                    for uid in remaining
                    if str(uid) in state["native_effect_areas"]
                }
                move_path = shortest(state, tuple(actor["position"]), goals, owner)[
                    : actor["mp"]
                ]
            enemies = [
                a
                for a in state["actors"].values()
                if not a["controlled"] and a["hp"] > 0 and a["team"] != actor["team"]
            ]
            enemies.sort(
                key=lambda a: (
                    abs(a["position"][0] - actor["position"][0])
                    + abs(a["position"][1] - actor["position"][1]),
                    a["id"],
                )
            )
            action = None
            if move_path:
                action = (
                    12161,
                    struct.pack(">q", owner)
                    + b"".join(struct.pack(">iih", *cell) for cell in move_path),
                )
            elif contact_done:
                for enemy in enemies:
                    for spell in (4769, 4816):
                        key = (
                            state["turn_id"],
                            actor["ap"],
                            tuple(actor["position"]),
                            enemy["id"],
                            enemy["hp"],
                            spell,
                        )
                        if key in attempted or actor["ap"] <= 0:
                            continue
                        attempted.add(key)
                        action = (
                            13260,
                            struct.pack(
                                ">qqiih",
                                owner,
                                (owner << 32) | spell,
                                *enemy["position"]
                            ),
                        )
                        break
                    if action:
                        break
                if action is None and actor["mp"] > 0 and enemies:
                    goals = {
                        tuple(cell)
                        for cell in state["walkable"]
                        if any(
                            2
                            <= abs(cell[0] - a["position"][0])
                            + abs(cell[1] - a["position"][1])
                            <= 4
                            for a in enemies
                        )
                    }
                    move_path = shortest(state, tuple(actor["position"]), goals, owner)[
                        : actor["mp"]
                    ]
                    if move_path:
                        action = (
                            12161,
                            struct.pack(">q", owner)
                            + b"".join(
                                struct.pack(">iih", *cell) for cell in move_path
                            ),
                        )
            if action is None:
                wire.peer.send(12403, struct.pack(">qh", owner, wire.round))
                wire.drain(0.3)
                continue
            wire.peer.send(*action)
            changed = row
            until = time.monotonic() + 1.5
            while time.monotonic() < until:
                wire.drain(0.08)
                changed = checkpoint(store, owner)
                if changed["revision"] != row["revision"]:
                    break
            after = observed(changed["snapshot"], owner)
            events.append(
                dict(kind="paid_input", opcode=action[0], before=now, after=after)
            )
            if action[0] == 12161 and after["groups"].get("1", {}).get(
                "choices_made", 0
            ) > now["groups"].get("1", {}).get("choices_made", 0):
                assert (
                    after["mp"] == 0
                ), "Native contact did not pay its original whole-MP toll"
                receipt["native_contact_cost"] = dict(
                    mp_before=now["mp"],
                    mp_after=after["mp"],
                    before=now["position"],
                    after=after["position"],
                )
            if action[0] == 13260 and after["ap"] < now["ap"]:
                paid_casts.append(
                    dict(
                        wave=now["wave"],
                        ap_before=now["ap"],
                        ap_after=after["ap"],
                        spell=struct.unpack_from(">q", action[1], 8)[0] & 0xFFFFFFFF,
                    )
                )
            if action[0] == 12161 and after["position"] == now["position"]:
                raise AssertionError(
                    "Planned native path was rejected; no movement override used"
                )
        else:
            receipt.update(
                status="INCOMPLETE_TIME_BUDGET", final=now, paid_casts=paid_casts
            )
        receipt["wire_ack_count"] = sum(e["kind"] == "wire_ack" for e in events)
    finally:
        try:
            current = checkpoint(store, owner)
            if current is not None and current["fight_status"] == "active":
                wire.peer.send(13952)
                wire.peer.until(12238)
                wire.peer.send(12925, struct.pack(">iB", current["fight_id"], 0))
                wire.peer.until(13974)
                wire.peer.send(14689)
                receipt["cleanup"] = "native_surrender_and_return"
                receipt["native_exit"] = leave_native_rift(
                    store, wire, character, inside, exit_source, exit_destination
                )
            else:
                receipt["cleanup"] = "already_terminal"
        except Exception as error:
            receipt["cleanup"] = (
                "NOT_VERIFIED:" + type(error).__name__ + ":" + str(error)
            )
        wire.peer.close()
    if receipt.get("status") == "PASS_BOUNDED_LIVE_JOURNEY":
        assert receipt["cleanup"] == "native_surrender_and_return"

        def settlement():
            with store.connection() as db:
                terminal = db.execute(
                    "SELECT r.status AS rift_status,f.status AS fight_status "
                    "FROM rift_instances r JOIN combat_fights f ON f.id=r.fight_id "
                    "WHERE r.instance_id=%s",
                    (receipt["instance_id"],),
                ).fetchone()
                waves = db.execute(
                    "SELECT wave,actor_ids,defeated_monsters FROM rift_wave_receipts "
                    "WHERE instance_id=%s ORDER BY wave",
                    (receipt["instance_id"],),
                ).fetchall()
                outcome = db.execute(
                    "SELECT outcome,result FROM rift_settlement_receipts WHERE instance_id=%s",
                    (receipt["instance_id"],),
                ).fetchone()
                rewards = db.execute(
                    "SELECT character_id,fight_id,eligibility_snapshot FROM rift_item_reward_receipts "
                    "WHERE instance_id=%s ORDER BY character_id",
                    (receipt["instance_id"],),
                ).fetchall()
                inventory = db.execute(
                    "SELECT uid,reference,quantity FROM inventory_items WHERE character_id=%s ORDER BY uid",
                    (owner,),
                ).fetchall()
            return dict(
                waves=waves,
                outcome=outcome,
                rewards=rewards,
                inventory=inventory,
                terminal=terminal,
            )

        # 13952 is voluntary abandonment, not ordinary all-player KO. Its
        # generic abort preserves earned progress receipts but does not enter
        # the KO settlement path. Do not invent rewards or wait for a receipt
        # that this native outcome does not produce.
        settled = settlement()
        assert settled["terminal"] == dict(rift_status="closed", fight_status="aborted")
        assert settled["outcome"] is None and not settled["rewards"]
        assert {1, 2} <= {row["wave"] for row in settled["waves"]}
        resumed = login_peer(username, character, events)
        resumed.peer.close()
        after = store.character(character["account_id"], owner)
        assert {k: after[k] for k in receipt["native_exit"]} == receipt["native_exit"]
        assert (
            settlement() == settled
        ), "Post-return login duplicated rewards or wave settlement"
        receipt["post_return_login"] = "PASS_NATIVE_WORLD_JOIN"
        receipt[
            "outcome_policy"
        ] = "voluntary_native_abort; ordinary_KO_rewards_not_exercised"
        receipt["durable_settlement"] = settled


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--http-url", required=True)
    parser.add_argument("--world-host", default="127.0.0.1")
    parser.add_argument("--dispatcher-port", type=int, default=15558)
    parser.add_argument("--world-port", type=int, default=15556)
    parser.add_argument("--seconds", type=int, default=360)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--execute-new-local-qa", action="store_true")
    parser.add_argument(
        "--reuse-dedicated-qa",
        help="Explicit previously created artifactqa name; validates gear and never regrants",
    )
    parser.add_argument(
        "--continue-fight",
        type=int,
        help="Reconnect only to this exact existing owned active fight; do not enter again",
    )
    parser.add_argument(
        "--continue-receipt",
        type=Path,
        help="Original receipt proving prior paid actions in the same continued fight",
    )
    args = parser.parse_args()
    if not args.execute_new_local_qa or args.world_host not in (
        "127.0.0.1",
        "localhost",
    ):
        parser.error("Explicit new-local-QA opt-in and loopback World required")
    if args.continue_fight is not None and (
        not args.reuse_dedicated_qa or not args.continue_receipt
    ):
        parser.error(
            "Continuing requires the named existing QA and its exact prior receipt"
        )
    access.ACCESS.update(
        http_url=args.http_url.rstrip("/"),
        world_host=args.world_host,
        dispatcher_port=args.dispatcher_port,
        world_port=args.world_port,
    )
    receipt = dict(
        status="NOT_STARTED",
        resolution="NOT_CONFIRMED_FIXED",
        scope="Paid classic Rift3 artifact contact, repeat waves, real socket reconnect, normal surrender; no full forty-turn victory",
    )
    store = Store(
        os.environ["WAKFU_DATABASE_URL"],
        password_file=os.environ["WAKFU_DATABASE_PASSWORD_FILE"],
    )
    try:
        run(
            store,
            receipt,
            seconds=args.seconds,
            reuse_dedicated_qa=args.reuse_dedicated_qa,
            continue_fight=args.continue_fight,
            continue_receipt=args.continue_receipt,
        )
    except BaseException as error:
        receipt.update(status="FAIL", error_type=type(error).__name__, error=str(error))
        raise
    finally:
        args.receipt.parent.mkdir(parents=True, exist_ok=True)
        args.receipt.write_text(json.dumps(receipt, indent=2, default=str) + "\n")
        store.close()
    return 0 if receipt["status"] == "PASS_BOUNDED_LIVE_JOURNEY" else 2


if __name__ == "__main__":
    raise SystemExit(main())
