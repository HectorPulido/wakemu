"""Current party actions on reviewed native pads, never sequential receipts.

The World and Position authorities own occupancy. Movement, a replacement
occupation, disconnect and native emote expiry invalidate a pad immediately;
there are no stale SQL occupancy leases to clean up. Only completion persists.
"""
from contextlib import ExitStack
from functools import lru_cache
from hashlib import sha256
import json
from pathlib import Path
import struct
import time

from psycopg.types.json import Jsonb

SOURCE = (
    Path(__file__).with_name("party_action_pad_profiles") / "whisper-organasm448.json"
)


def digest(value):
    return sha256(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode()
    ).hexdigest()


def validate(profile, geometry):
    fields = {
        "schema",
        "id",
        "map_id",
        "dungeon_definition_id",
        "template_id",
        "quest_id",
        "objective_id",
        "event_reference",
        "boss_references",
        "minimum_rooms",
        "provenance",
        "geometry_sha256",
        "scenario",
        "pads",
    }
    if (
        type(profile) is not dict
        or set(profile) != fields
        or profile["schema"] != "simultaneous-party-action-pads-v1"
    ):
        raise ValueError("Invalid simultaneous party pad profile")
    if any(
        type(profile[k]) is not int or profile[k] <= 0
        for k in (
            "map_id",
            "dungeon_definition_id",
            "template_id",
            "quest_id",
            "objective_id",
            "event_reference",
            "minimum_rooms",
        )
    ):
        raise ValueError("Invalid native party pad identity")
    if not profile["id"] or not profile["provenance"] or len(profile["id"]) > 128:
        raise ValueError("Missing reviewed party pad provenance")
    if (
        profile["map_id"] != geometry["map_id"]
        or digest(geometry) != profile["geometry_sha256"]
    ):
        raise ValueError("Party pad native floor differs from reviewed source")
    cells = {tuple(p) for p in geometry["cells"]}
    if (
        type(profile["boss_references"]) is not list
        or not profile["boss_references"]
        or any(type(v) is not int or v <= 0 for v in profile["boss_references"])
    ):
        raise ValueError("Missing frozen native boss identity")
    scenario = profile["scenario"]
    if (
        type(scenario) is not dict
        or set(scenario)
        != {
            "id",
            "lua_sha256",
            "event_signatures",
            "king_death_event",
            "destruction_event",
        }
        or scenario["id"] != profile["event_reference"]
    ):
        raise ValueError("Party pad native scenario is not pinned")
    signatures = scenario["event_signatures"]
    if signatures.get(str(scenario["king_death_event"])) != 1:
        raise ValueError("Party pad King event signature differs")
    pads = profile["pads"]
    if (
        type(pads) is not list
        or not 2 <= len(pads) <= 6
        or signatures.get(str(scenario["destruction_event"])) != len(pads)
    ):
        raise ValueError("Party pad native destruction arity differs")
    ids, positions, emotes = set(), set(), set()
    for pad in pads:
        if type(pad) is not dict or set(pad) != {
            "id",
            "position",
            "emote_id",
            "activation_event",
            "decrement_event",
            "aggro_event",
        }:
            raise ValueError("Invalid native action pad")
        position = tuple(pad["position"])
        if (
            not pad["id"]
            or pad["id"] in ids
            or position in positions
            or position not in cells
            or pad["emote_id"] in emotes
            or any(
                type(pad[k]) is not int or pad[k] <= 0
                for k in (
                    "emote_id",
                    "activation_event",
                    "decrement_event",
                    "aggro_event",
                )
            )
        ):
            raise ValueError("Action pads need distinct original native floors/emotes")
        if signatures.get(str(pad["activation_event"])) != 2 or any(
            signatures.get(str(pad[k])) != 1 for k in ("decrement_event", "aggro_event")
        ):
            raise ValueError("Action pad event signature differs from native Lua")
        ids.add(pad["id"])
        positions.add(position)
        emotes.add(pad["emote_id"])
    return profile


@lru_cache(maxsize=1)
def source():
    profile = json.loads(SOURCE.read_text())
    geometry = json.loads(SOURCE.with_suffix(".exploration.json").read_text())
    return validate(profile, geometry)


def active_emote(character, now):
    """Read only the trusted native occupation published by World authorization."""
    if character.get("_emote_until", 0) <= now:
        return None
    packet = character.get("_emote_packet")
    if (
        not isinstance(packet, (tuple, list))
        or len(packet) != 2
        or packet[0] != 12088
        or not isinstance(packet[1], bytes)
        or len(packet[1]) != 20
    ):
        return None
    status, kind, actor, size, emote, arguments = struct.unpack(">BhqIiB", packet[1])
    if (status, kind, actor, size, arguments) != (1, 20, character["id"], 5, 0):
        return None
    return emote


def occupied(profile, members, *, now):
    """Pure simultaneous selection; one member can never fill two pads."""
    chosen = []
    for pad in profile["pads"]:
        eligible = [
            member
            for member in members
            if tuple(member[k] for k in ("x", "y", "z")) == tuple(pad["position"])
            and member.get("map_id") == profile["map_id"]
            and active_emote(member, now) == pad["emote_id"]
        ]
        if len(eligible) != 1:
            return ()
        chosen.append(eligible[0])
    if len({member["id"] for member in chosen}) != len(profile["pads"]):
        return ()
    instances = {member.get("instance_id", 0) for member in chosen}
    if len(instances) != 1 or next(iter(instances)) <= 0:
        return ()
    return tuple(chosen)


def native_packet(profile, event, arguments):
    if profile["scenario"]["event_signatures"].get(str(event)) != len(arguments):
        raise ValueError("Party pad presentation differs from original native event")
    return 13411, struct.pack(
        ">BiiB", 0, event, profile["scenario"]["id"], len(arguments)
    ) + b"".join(struct.pack(">q", value) for value in arguments)


def king_outcome(db, profile, instance_id):
    """The final admitted original King roster and settled victory are mandatory."""
    row = db.execute(
        "SELECT i.instance_id,i.party_id,i.template_id,i.definition_id,i.start_map_id,"
        "r.rooms,r.status,e.fight_id,e.status AS encounter_status,e.result "
        "FROM dungeon_instances i JOIN dungeon_room_runs r USING(instance_id) "
        "JOIN dungeon_room_encounters e ON e.instance_id=i.instance_id "
        "AND e.room_order=jsonb_array_length(r.rooms) "
        "WHERE i.instance_id=%s AND e.status='victory' AND e.result->>'completed'='true' "
        "ORDER BY e.fight_id DESC LIMIT 1 FOR UPDATE OF i,r,e",
        (instance_id,),
    ).fetchone()
    if (
        row is None
        or row["definition_id"] != profile["dungeon_definition_id"]
        or row["template_id"] != profile["template_id"]
        or row["start_map_id"] != profile["map_id"]
        or row["status"] != "completed"
        or len(row["rooms"]) < profile["minimum_rooms"]
    ):
        return None
    final = row["rooms"][-1]
    roster = {m["ref_id"] for m in final["monsters"] if m.get("count", 0) > 0}
    if not set(profile["boss_references"]) <= roster:
        return None
    return row


def _enabled(db, profile):
    return (
        db.execute(
            "SELECT 1 FROM mission_toolkit_event_index i JOIN mission_toolkit_active a "
            "ON (a.profile_id,a.version)=(i.profile_id,i.version) "
            "WHERE i.kind='party_pad_completed' AND i.reference=%s LIMIT 1",
            (profile["event_reference"],),
        ).fetchone()
        is not None
    )


def settle_current(db, store, profile, members, *, now, validate_live):
    """Current membership/occupation proof and receipt share one transaction.

    The caller holds sorted Position account barriers and the native World
    scope reservation until this transaction commits. This also catches an
    accepted move that has not yet reached the World projection.
    """
    participants = occupied(profile, members, now=now)
    if not participants:
        return []
    instances = {m.get("instance_id", 0) for m in participants}
    if len(instances) != 1 or next(iter(instances)) <= 0 or not _enabled(db, profile):
        return []
    instance_id = next(iter(instances))
    for account in sorted({m["account_id"] for m in participants}):
        db.execute("SELECT id FROM accounts WHERE id=%s FOR UPDATE", (account,))
    for member in sorted(participants, key=lambda m: (m["account_id"], m["id"])):
        db.execute(
            "SELECT id FROM characters WHERE id=%s AND account_id=%s FOR UPDATE",
            (member["id"], member["account_id"]),
        )
    outcome = king_outcome(db, profile, instance_id)
    if outcome is None:
        return []
    db.execute(
        "SELECT id FROM player_parties WHERE id=%s FOR UPDATE", (outcome["party_id"],)
    )
    current = db.execute(
        "SELECT c.id,c.account_id,s.generation FROM dungeon_instance_members m "
        "JOIN characters c ON c.id=m.character_id "
        "JOIN player_party_members p ON p.character_id=c.id AND p.party_id=m.party_id "
        "JOIN sessions s ON s.account_id=c.account_id AND s.character_id=c.id "
        "AND s.generation=m.session_generation AND s.expires_at>%s "
        "WHERE m.instance_id=%s AND m.party_id=%s AND m.status='active' "
        "AND c.map_id=%s AND c.instance_id=%s AND c.deleted_at IS NULL",
        (store.now(), instance_id, outcome["party_id"], profile["map_id"], instance_id),
    ).fetchall()
    owned = {(row["id"], row["account_id"], row["generation"]) for row in current}
    if any(
        (m["id"], m["account_id"], m["_pad_generation"]) not in owned
        for m in participants
    ):
        return []
    if not validate_live(participants) or len(
        occupied(profile, participants, now=time.monotonic())
    ) != len(participants):
        return []
    pin = digest(profile)
    inserted = db.execute(
        "INSERT INTO simultaneous_party_pad_completions(instance_id,profile_id,profile_sha256,fight_id,participants) "
        "VALUES(%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING RETURNING instance_id",
        (
            instance_id,
            profile["id"],
            pin,
            outcome["fight_id"],
            Jsonb([m["id"] for m in participants]),
        ),
    ).fetchone()
    if inserted is None:
        return []
    from wakfu_server.achievements import mission_toolkit, tutorial_presentation_once

    deliveries = []
    arguments = [1] * len(participants)
    # Native destruction accepts earth,air,water,fire trigger counts, not actor
    # IDs. Every count is proven by a different simultaneous current member.
    presentation = native_packet(
        profile, profile["scenario"]["destruction_event"], arguments
    )
    for member in participants:
        stored = store.character(member["account_id"], member["id"], db)
        packets = mission_toolkit.settle(
            db,
            store,
            stored,
            token=f"party-pads:{profile['id']}:{instance_id}:{outcome['fight_id']}",
            kind="party_pad_completed",
            reference=profile["event_reference"],
        )
        presentation_packets = (
            [presentation]
            if tutorial_presentation_once.claim(
                db,
                member["id"],
                profile["scenario"]["id"],
                profile["scenario"]["destruction_event"],
            )
            else []
        )
        deliveries.append(
            (member["id"], member["_pad_generation"], [*presentation_packets, *packets])
        )
    return deliveries


def performed(runtime, character, emote_id):
    """Application adapter after actual authorized emote publication to World."""
    profile = source()
    if (
        character.get("map_id") != profile["map_id"]
        or character.get("instance_id", 0) <= 0
        or emote_id not in {p["emote_id"] for p in profile["pads"]}
    ):
        return []

    def snapshot():
        return [
            dict(c, _pad_generation=generation)
            for generation, _, c in runtime.WORLD.captured_players()
            if (c["map_id"], c.get("instance_id", 0))
            == (profile["map_id"], character["instance_id"])
        ]

    captured = snapshot()
    if not occupied(profile, captured, now=time.monotonic()):
        return []
    accounts = {m["account_id"] for m in captured}
    with ExitStack() as stack:
        for account in sorted(accounts):
            stack.enter_context(runtime.POSITIONS.account_barrier(account))
        stack.enter_context(
            runtime.WORLD.scope_barrier(profile["map_id"], character["instance_id"])
        )
        captured = snapshot()
        if any(
            member["account_id"] not in accounts
            for member in occupied(profile, captured, now=time.monotonic())
        ):
            return []

        def validate_live(participants):
            for member in participants:
                key = (member["account_id"], member["_pad_generation"], member["id"])
                state = runtime.POSITIONS.entry_state(key)
                if state is None or not runtime.POSITIONS.lease_active(*key):
                    return False
                current = state["current"]
                if any(
                    current.get(k) != member.get(k)
                    for k in ("map_id", "instance_id", "x", "y", "z")
                ):
                    return False
                if runtime.COMBAT_SESSIONS.lookup_character(member["id"]) is not None:
                    return False
            return True

        with runtime.STORE.connection() as db:
            return settle_current(
                db,
                runtime.STORE,
                profile,
                captured,
                now=time.monotonic(),
                validate_live=validate_live,
            )


def prepare_aggro(runtime, character, emote_id, generation):
    """An elemental pad before King death queues the real available final group.

    The ordinary encounter handler re-resolves and claims this frozen group;
    this helper creates no group, changes no room, and awards no outcome.
    """
    profile = source()
    if (
        character.get("map_id") != profile["map_id"]
        or character.get("instance_id", 0) <= 0
    ):
        return None
    pad = next(
        (
            p
            for p in profile["pads"]
            if p["emote_id"] == emote_id
            and tuple(p["position"]) == tuple(character[k] for k in ("x", "y", "z"))
        ),
        None,
    )
    if pad is None or active_emote(character, time.monotonic()) != emote_id:
        return None
    with runtime.STORE.connection() as db:
        if not _enabled(db, profile):
            return None
        row = db.execute(
            "SELECT i.party_id,r.rooms,g.members FROM dungeon_instances i "
            "JOIN dungeon_room_runs r USING(instance_id) "
            "JOIN dungeon_room_spawn_receipts p ON p.instance_id=i.instance_id AND p.room_order=r.current_room "
            "JOIN combat_groups g ON g.map_id=p.asset_map_id AND g.instance_id=p.instance_id AND g.group_id=p.group_id "
            "JOIN dungeon_instance_members m ON m.instance_id=i.instance_id AND m.party_id=i.party_id AND m.character_id=%s AND m.status='active' "
            "JOIN player_party_members party ON party.character_id=m.character_id AND party.party_id=i.party_id "
            "JOIN sessions s ON s.character_id=m.character_id AND s.generation=m.session_generation AND s.expires_at>%s "
            "WHERE i.instance_id=%s AND i.definition_id=%s AND i.template_id=%s AND i.start_map_id=%s "
            "AND i.status='active' AND r.status='active' AND r.current_room=jsonb_array_length(r.rooms) "
            "AND s.generation=%s AND g.status='available'",
            (
                character["id"],
                runtime.STORE.now(),
                character["instance_id"],
                profile["dungeon_definition_id"],
                profile["template_id"],
                profile["map_id"],
                generation,
            ),
        ).fetchone()
        if row is None or len(row["rooms"]) < profile["minimum_rooms"]:
            return None
        frozen = {
            m["ref_id"] for m in row["rooms"][-1]["monsters"] if m.get("count", 0) > 0
        }
        actual = [m for m in row["members"] if m["ref"] in profile["boss_references"]]
        if not set(profile["boss_references"]) <= frozen or len(actual) != len(
            profile["boss_references"]
        ):
            return None
        king = actual[0]
        return dict(
            attack_body=struct.pack(
                ">qiihB", king["id"], king["x"], king["y"], king["z"], 0
            ),
            packet=native_packet(profile, pad["aggro_event"], [0]),
        )
