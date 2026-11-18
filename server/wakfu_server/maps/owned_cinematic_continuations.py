"""Once-only cinematic stages reached through reviewed owned story exits.

The caller owns its account position barrier, SQL transaction and bootstrap
delivery. These stages never fabricate companions, combat wins or quest admission.
They retain the ordinary exit cleanup and durable transition outbox on both legs.
V1 is presentation only; explicit V2 may settle its earned native final objective.
"""

from copy import deepcopy
from functools import lru_cache
from hashlib import sha256
import json
from pathlib import Path
import struct

from wakfu_server.achievements import storage

SCHEMA = "owned-cinematic-continuation-v1"
SCHEMA_V2 = "owned-cinematic-continuation-v2"
ROOT = Path(__file__).with_name("owned_story_continuations")
ARRIVAL_PREFIX = "owned-cinematic-arrival:"


@lru_cache(maxsize=1)
def stage_maps():
    """Cheap map routing only; an owned pinned arrival still authorizes a scene."""
    result = set()
    for path in ROOT.glob("*.json"):
        document = json.loads(path.read_text())
        stage = document.get("stage", {})
        if (
            document.get("schema") not in (SCHEMA, SCHEMA_V2)
            or type(stage.get("map_id")) is not int
            or stage["map_id"] <= 0
        ):
            raise ValueError("Invalid reviewed cinematic routing source")
        result.add(stage["map_id"])
    return frozenset(result)


def _digest(value):
    return sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def stage_instance_id(character_id):
    """Reuse the existing private introductory namespace, scoped by native map."""
    from wakfu_server.intro_cinematic import private_instance_id

    return private_instance_id(character_id)


def owns_stage(character):
    """Cheap scene routing, not a replacement for its durable arrival receipt."""
    if character.get("map_id") not in stage_maps():
        return False
    try:
        return character.get("instance_id") == stage_instance_id(character.get("id"))
    except ValueError:
        return False


def validate(document, source_lookup):
    """Authenticate native endpoints while retaining reviewed scene associations."""
    if (
        type(document) is not dict
        or document.get("schema") not in (SCHEMA, SCHEMA_V2)
        or not isinstance(document.get("id"), str)
        or not 1 <= len(document["id"]) <= 80
        or any(
            type(document.get(k)) is not int or document[k] <= 0
            for k in ("source_map_id", "quest_id")
        )
        or not document.get("provenance")
        or not isinstance(document.get("required_story_steps"), list)
        or not document["required_story_steps"]
        or any(
            not isinstance(s, str) or not s for s in document["required_story_steps"]
        )
    ):
        raise ValueError("Invalid owned cinematic continuation policy")
    version2 = document["schema"] == SCHEMA_V2
    if version2:
        admission, completion = document.get("admission"), document.get("completion")
        if (
            not isinstance(admission, dict)
            or set(admission) != {"quest_id", "required_objectives"}
            or admission["quest_id"] != document["quest_id"]
            or not isinstance(admission["required_objectives"], list)
            or not admission["required_objectives"]
            or any(
                type(v) is not int or v <= 0 for v in admission["required_objectives"]
            )
            or len(set(admission["required_objectives"]))
            != len(admission["required_objectives"])
            or not isinstance(completion, dict)
            or set(completion) != {"quest_id", "objective_id"}
            or completion["quest_id"] != document["quest_id"]
            or type(completion["objective_id"]) is not int
            or completion["objective_id"] <= 0
            or completion["objective_id"] in admission["required_objectives"]
            or not isinstance(document.get("native_arrival"), dict)
            or set(document["native_arrival"]) != {"map_id", "x", "y", "z"}
            or any(type(v) is not int for v in document["native_arrival"].values())
            or document["native_arrival"]["map_id"] <= 0
        ):
            raise ValueError("Cinematic v2 lacks exact earned admission/completion")
    stage = document.get("stage")
    anchor = document.get("return_anchor")
    presentation = document.get("presentation")
    if (
        type(stage) is not dict
        or set(stage) != {"map_id", "x", "y", "z"}
        or any(type(v) is not int for v in stage.values())
        or stage["map_id"] <= 0
        or type(anchor) is not dict
        or set(anchor)
        != {"source_id", "destination_id", "map_id", "x", "y", "z"}
        | ({"source_map_id"} if version2 else set())
        or any(type(v) is not int for v in anchor.values())
        or anchor["map_id"] <= 0
        or (not version2 and anchor["map_id"] == stage["map_id"])
        or type(presentation) is not dict
        or set(presentation)
        != {"scenario", "event", "finish_event", "duration_ms", "lua_sha256"}
        | ({"argument_count"} if version2 else set())
        or any(
            type(presentation[k]) is not int or presentation[k] <= 0
            for k in ("scenario", "event", "finish_event", "duration_ms")
        )
        or presentation["duration_ms"] > 600000
        or not isinstance(presentation["lua_sha256"], str)
        or len(presentation["lua_sha256"]) != 64
        or any(c not in "0123456789abcdef" for c in presentation["lua_sha256"])
    ):
        raise ValueError("Cinematic stage lacks exact presentation/return identities")
    if version2:
        if type(presentation["argument_count"]) is not int or presentation[
            "argument_count"
        ] not in (0, 1):
            raise ValueError("Cinematic v2 has unsupported native scene arguments")
        from wakfu_server.combat_geometry import published_geometry

        if (
            tuple(stage[k] for k in ("x", "y", "z"))
            not in published_geometry(stage["map_id"]).cells
        ):
            raise ValueError("Cinematic v2 stage has no actual native floor")
    entries = document.get("entries")
    if not isinstance(entries, list) or not entries:
        raise ValueError("Cinematic stage has no actual native entrance")
    seen = set()
    for entry in entries:
        if (
            type(entry) is not dict
            or set(entry) != {"source_id", "destination_id"}
            or any(type(v) is not int or v <= 0 for v in entry.values())
            or (entry.get("source_id"), entry.get("destination_id")) in seen
        ):
            raise ValueError("Invalid or repeated cinematic native exit")
        seen.add((entry["source_id"], entry["destination_id"]))
        target = _native_target(source_lookup, document["source_map_id"], entry)
        if any(
            target[k] != v
            for k, v in (document["native_arrival"] if version2 else stage).items()
        ) or (
            not version2
            and target.get("criterion")
            != f"IsAchievementComplete({document['quest_id']})"
        ):
            raise ValueError(
                "Cinematic stage differs from its native completed-quest exit"
            )
    target = _native_target(
        source_lookup, anchor.get("source_map_id", document["source_map_id"]), anchor
    )
    if any(target[k] != anchor[k] for k in ("map_id", "x", "y", "z")):
        raise ValueError("Cinematic return anchor differs from its native endpoint")
    return document


def _native_target(lookup, map_id, binding):
    source = lookup(map_id, binding["source_id"])
    targets = (
        []
        if source is None
        else [
            row
            for row in source["destinations"]
            if row["destination_id"] == binding["destination_id"]
        ]
    )
    if len(targets) != 1:
        raise ValueError("Cinematic native endpoint is missing or ambiguous")
    target = targets[0]
    if (
        target.get("native_altitude_walkable") is not True
        or target.get("cyZ", 0) >= 0
        or target.get("cyX", -1) != 0
        or target.get("cyW", -1) != 0
    ):
        raise ValueError("Cinematic endpoint is not a free verified native surface")
    return target


@lru_cache(maxsize=16)
def _load(path, digest):
    from wakfu_server import generic_transports

    if Path(path).name != path or not path.endswith(".json"):
        raise ValueError(
            "Cinematic source must remain in the reviewed profile directory"
        )
    raw = (ROOT / path).read_bytes()
    if sha256(raw).hexdigest() != digest:
        raise ValueError("Cinematic source attestation changed")
    return validate(json.loads(raw), generic_transports.source)


def policy(selected):
    pointer = selected.get("cinematic_continuation")
    if pointer is None:
        return None
    if (
        type(pointer) is not dict
        or set(pointer) != {"path", "sha256"}
        or not isinstance(pointer["path"], str)
        or not isinstance(pointer["sha256"], str)
        or len(pointer["sha256"]) != 64
        or any(c not in "0123456789abcdef" for c in pointer["sha256"])
    ):
        raise ValueError("Missing pinned cinematic continuation source")
    return deepcopy(_load(pointer["path"], pointer["sha256"]))


def packet(document, event, owner):
    presentation = document["presentation"]
    if type(owner) is not int or not 0 < owner < 2**63:
        raise ValueError("Cinematic presentation requires its real player identity")
    if event == presentation["event"]:
        arguments = () if presentation.get("argument_count", 1) == 0 else (owner,)
    elif event == presentation["finish_event"]:
        arguments = ()
    else:
        raise ValueError("Unqualified owned cinematic event")
    return 13411, struct.pack(
        ">BiiB", 0, event, presentation["scenario"], len(arguments)
    ) + b"".join(struct.pack(">q", value) for value in arguments)


def recognizes(selected, body):
    """Classify only; native source and owned completion still require begin()."""
    document = policy(selected)
    if document is None or len(body) != 17:
        return False
    source, destination, flag, mode = struct.unpack(">qiBi", body)
    return (
        flag == 0
        and mode == 2
        and dict(source_id=source, destination_id=destination) in document["entries"]
    )


def _event(db, owner, key):
    row = db.execute(
        "SELECT payload FROM character_achievement_events WHERE character_id=%s AND event_key=%s",
        (owner, key),
    ).fetchone()
    return None if row is None else row["payload"]


def _key(document, suffix):
    return "owned-cinematic-" + suffix + ":" + document["id"]


def eligible(document, state):
    """Physical visits can bypass this optional continuation without quest fiction."""
    if document["schema"] == SCHEMA:
        return document["quest_id"] in state["completed"]
    if document["schema"] != SCHEMA_V2:
        raise ValueError("Unknown cinematic continuation admission")
    quest = document["admission"]["quest_id"]
    if quest not in state["running"] or quest in state["completed"]:
        return False
    from wakfu_server.dungeon_achievement_authority import queries_from_state

    try:
        running = queries_from_state(state)["IsAchievementRunning"](quest)
    except ValueError:
        return False
    return (
        running
        and set(document["admission"]["required_objectives"])
        <= set(state["objectives"])
        and document["completion"]["objective_id"] not in state["objectives"]
    )


def begin(
    db, store, account_id, generation, character_id, body, *, source_allowed, in_fight
):
    """Leave the real completed private story through its selected native exit."""
    from wakfu_server import dungeon_exit, owned_story_exits

    if not callable(source_allowed) or not callable(in_fight):
        raise ValueError(
            "Cinematic exit requires authoritative interaction/combat guards"
        )
    store.lock_character(db, account_id, generation, character_id)
    character = store.character(account_id, character_id, db)
    authenticated = owned_story_exits.authenticate_exit(
        db, store, character, body, source_allowed=source_allowed
    )
    selected = authenticated["controller"]
    completed = authenticated["completed_steps"]
    document = policy(selected)
    if document is None:
        raise ValueError("Owned story has no reviewed cinematic continuation")
    if len(body) != 17:
        raise ValueError("Invalid cinematic native exit request")
    source_id, target_id, flag, mode = struct.unpack(">qiBi", body)
    if (
        flag != 0
        or mode != 2
        or character["map_id"] != document["source_map_id"]
        or {"source_id": source_id, "destination_id": target_id}
        not in document["entries"]
        or not eligible(document, storage.load_locked(db, character_id))
    ):
        raise ValueError("Cinematic exit lacks its actual completed owned story")
    arrival = _event(db, character_id, _key(document, "arrival"))
    if arrival is not None:
        _validate_arrival(document, arrival, character)
        finished = _event(db, character_id, _key(document, "finished"))
        if finished is not None:
            if finished.get("owner") != character_id or finished.get(
                "policy_sha256"
            ) != _digest(document):
                raise ValueError("Conflicting once-only cinematic completion")
            # The original native gate is completion-only. A later genuine
            # visit must retain its exit without replaying an earned scene.
            destination = {
                k: document["return_anchor"][k] for k in ("map_id", "x", "y", "z")
            }
        else:
            # Preserve the original presentation/deadline, including a visit
            # after an administrative departure from its unfinished stage.
            destination = dict(
                document["stage"], instance_id=stage_instance_id(character_id)
            )
            storage.record_event(
                db,
                character_id,
                _key(document, "resume") + ":" + str(character["instance_id"]),
                dict(
                    owner=character_id,
                    original_instance_id=arrival["source_instance_id"],
                    resumed_from_instance_id=character["instance_id"],
                    policy_sha256=_digest(document),
                ),
            )
        return dungeon_exit._leave(
            store,
            account_id,
            generation,
            character_id,
            in_fight=in_fight,
            destination_for=lambda *_: destination,
            _db=db,
        )
    if not set(document["required_story_steps"]) <= completed:
        raise ValueError("Cinematic exit lacks its actual owned boss sequence")
    receipt = dict(
        schema=document["schema"],
        owner=character_id,
        account_id=account_id,
        source_instance_id=character["instance_id"],
        policy_sha256=_digest(document),
        profile_id=document["id"],
        profile_pointer=selected["cinematic_continuation"],
        stage_map_id=document["stage"]["map_id"],
        stage_instance_id=stage_instance_id(character_id),
    )
    if not storage.record_event(db, character_id, _key(document, "arrival"), receipt):
        raise ValueError("Cinematic entrance raced another transition")
    return dungeon_exit._leave(
        store,
        account_id,
        generation,
        character_id,
        in_fight=in_fight,
        destination_for=lambda *_: dict(
            document["stage"], instance_id=stage_instance_id(character_id)
        ),
        _db=db,
    )


def _validate_arrival(document, receipt, character):
    if (
        type(receipt) is not dict
        or receipt.get("schema") != document["schema"]
        or receipt.get("owner") != character["id"]
        or receipt.get("account_id") != character["account_id"]
        or receipt.get("policy_sha256") != _digest(document)
        or receipt.get("stage_instance_id") != stage_instance_id(character["id"])
        or receipt.get("stage_map_id") != document["stage"]["map_id"]
        or type(receipt.get("source_instance_id")) is not int
        or receipt["source_instance_id"] <= 0
    ):
        raise ValueError("Cinematic arrival differs from its original owner/policy")


def pending(db, store, character):
    """Find this owner's pending scene, never authorize by map number alone."""
    rows = db.execute(
        "SELECT payload FROM character_achievement_events WHERE character_id=%s "
        "AND left(event_key,%s)=%s AND payload->>'stage_map_id'=%s",
        (
            character["id"],
            len(ARRIVAL_PREFIX),
            ARRIVAL_PREFIX,
            str(character["map_id"]),
        ),
    ).fetchall()
    candidates = []
    for row in rows:
        receipt = row["payload"]
        if (
            type(receipt) is not dict
            or receipt.get("schema") not in (SCHEMA, SCHEMA_V2)
            or receipt.get("owner") != character["id"]
            or receipt.get("account_id") != character["account_id"]
            or type(receipt.get("profile_pointer")) is not dict
        ):
            raise ValueError("Pending cinematic lacks its owned original receipt")
        document = policy({"cinematic_continuation": receipt["profile_pointer"]})
        _validate_arrival(document, receipt, character)
        finished = _event(db, character["id"], _key(document, "finished"))
        if finished is not None:
            if finished.get("owner") != character["id"] or finished.get(
                "policy_sha256"
            ) != _digest(document):
                raise ValueError("Conflicting once-only cinematic completion")
            # V2 can return publicly to the same asset used by its private
            # stage. Closed receipts remain history, not a pending-stage claim.
            continue
        if (
            receipt.get("schema") != document["schema"]
            or receipt.get("owner") != character["id"]
            or receipt.get("account_id") != character["account_id"]
            or receipt.get("policy_sha256") != _digest(document)
            or not owns_stage(character)
            or receipt.get("stage_instance_id") != character["instance_id"]
            or any(character[k] != v for k, v in document["stage"].items())
        ):
            raise ValueError("Pending cinematic owner or original stage changed")
        candidates.append((document, receipt))
    if len(candidates) > 1:
        raise ValueError("Ambiguous owned cinematic continuation")
    return candidates[0] if candidates else None


def ready(db, store, account_id, generation, character_id):
    """Publish the original scene once; reconnects keep its durable deadline."""
    store.lock_character(db, account_id, generation, character_id)
    character = store.character(account_id, character_id, db)
    current = pending(db, store, character)
    if current is None:
        return None
    document, _ = current
    key = _key(document, "started")
    started = _event(db, character_id, key)
    packets = []
    if started is None:
        suppressed = False
        if document["schema"] == SCHEMA_V2:
            from wakfu_server.achievements import tutorial_presentation_once

            suppressed = not tutorial_presentation_once.claim(
                db,
                character_id,
                document["presentation"]["scenario"],
                document["presentation"]["event"],
            )
        started = dict(
            owner=character_id,
            generation=generation,
            due_ms=int(store.now().timestamp() * 1000)
            + (0 if suppressed else document["presentation"]["duration_ms"]),
            **({"presentation_suppressed": True} if suppressed else {}),
        )
        if not storage.record_event(db, character_id, key, started):
            raise ValueError("Cinematic presentation raced")
        if not suppressed:
            packets.append(
                packet(document, document["presentation"]["event"], character_id)
            )
    due_ms = started["due_ms"]
    if document["schema"] == SCHEMA_V2 and started["generation"] != generation:
        # This connection has no live movie/actors. Keep the once-only start
        # receipt, while acknowledging the skipped presentation mechanically.
        due_ms = int(store.now().timestamp() * 1000)
    return dict(packets=packets, due_ms=due_ms)


def finish(db, store, account_id, generation, character_id):
    """Finish by the native timeline, atomically retaining ordinary exit delivery."""
    store.lock_character(db, account_id, generation, character_id)
    source = store.character(account_id, character_id, db)
    current = pending(db, store, source)
    if current is None:
        return None
    document, arrival = current
    started = _event(db, character_id, _key(document, "started"))
    skipped_reconnect = (
        document["schema"] == SCHEMA_V2
        and started is not None
        and started["generation"] != generation
    )
    if started is None or (
        int(store.now().timestamp() * 1000) < started["due_ms"]
        and not skipped_reconnect
    ):
        return None
    run = db.execute(
        "SELECT * FROM dungeon_instances WHERE instance_id=%s FOR UPDATE",
        (arrival["source_instance_id"],),
    ).fetchone()
    member = db.execute(
        "SELECT status FROM dungeon_instance_members WHERE instance_id=%s AND character_id=%s FOR UPDATE",
        (arrival["source_instance_id"], character_id),
    ).fetchone()
    if (
        run is None
        or run["status"] != "closed"
        or member is None
        or member["status"] != "returned"
    ):
        raise ValueError("Cinematic return lost its ordinary completed exit membership")
    objective_packets = []
    if document["schema"] == SCHEMA_V2 and eligible(
        document, storage.load_locked(db, character_id)
    ):
        from wakfu_server.achievements.owned_quest_encounters import _advance

        completion = document["completion"]
        objective_packets = _advance(
            db,
            store,
            source,
            completion,
            completion["objective_id"],
            _key(document, "objective"),
            dict(
                source_instance_id=arrival["source_instance_id"],
                stage_instance_id=source["instance_id"],
                scenario=document["presentation"]["scenario"],
                finish_event=document["presentation"]["finish_event"],
            ),
        )
    destination = {k: document["return_anchor"][k] for k in ("map_id", "x", "y", "z")}
    saved = store.transition_map_in_transaction(
        db,
        account_id,
        generation,
        character_id,
        source,
        dict(destination, instance_id=0),
    )
    revision = run["revision"] + 1
    db.execute(
        "UPDATE dungeon_instances SET revision=%s WHERE instance_id=%s",
        (revision, run["instance_id"]),
    )
    db.execute(
        "UPDATE dungeon_instance_members SET session_generation=%s WHERE instance_id=%s AND character_id=%s AND status='returned'",
        (generation, run["instance_id"], character_id),
    )
    db.execute(
        "UPDATE dungeon_transition_outbox SET status='superseded',superseded_at=%s WHERE character_id=%s AND status='pending'",
        (store.now(), character_id),
    )
    db.execute(
        "INSERT INTO dungeon_transition_outbox(instance_id,party_id,transition_revision,character_id,session_generation,"
        "source_map_id,source_instance_id,source_x,source_y,source_z,destination_map_id,destination_instance_id,"
        "destination_x,destination_y,destination_z,transition_kind) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,0,%s,%s,%s,'exit')",
        (
            run["instance_id"],
            run["party_id"],
            revision,
            character_id,
            generation,
            source["map_id"],
            source["instance_id"],
            source["x"],
            source["y"],
            source["z"],
            destination["map_id"],
            destination["x"],
            destination["y"],
            destination["z"],
        ),
    )
    if not storage.record_event(
        db,
        character_id,
        _key(document, "finished"),
        dict(
            owner=character_id, policy_sha256=_digest(document), destination=destination
        ),
    ):
        raise ValueError("Cinematic completion raced another return")
    packets = []
    if started["generation"] == generation and not started.get(
        "presentation_suppressed", False
    ):
        packets.append(
            packet(document, document["presentation"]["finish_event"], character_id)
        )
    packets.extend(objective_packets)
    return dict(
        destination,
        instance_id=0,
        transition_kind="exit",
        character=saved,
        before_transition_packets=packets,
    )
