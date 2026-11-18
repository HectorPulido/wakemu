"""Qualify regional/family kill events from actual owned victory/drop receipts.

This reviewed reconstruction uses each defeated original monster's frozen world
position, never the selected character's post-fight location. The owned admission
scene is still required; an owner standing across a territory boundary does not
invalidate a monster defeated in the declared region. Native callback recovery
is not claimed. No fight, kill, region or family fact comes from a client event.
"""

from functools import lru_cache
from hashlib import sha256
import json
from pathlib import Path

from . import mission_toolkit, native_effective_eligibility, storage

EVENT_KIND = "scoped_monster_defeat"
POLICY = "wakemu.original-monster-region-family-v1"
SOURCE = Path(__file__).with_name("combat_scope_profiles") / "regional-world-v1.json"


@lru_cache(maxsize=1)
def declarations():
    """Read the small reviewed scope index once; unknown shapes fail closed."""
    document = json.loads(SOURCE.read_text())
    if document.get("schema") != POLICY or not isinstance(document.get("scopes"), list):
        raise ValueError("Unsupported regional combat mission declarations")
    seen = set()
    for row in document["scopes"]:
        if (
            set(row)
            != {
                "reference",
                "quest_id",
                "objective_id",
                "variable_id",
                "maps",
                "regions",
                "families",
                "native_definition_sha256",
                "evidence",
            }
            or any(
                type(row.get(key)) is not int or row[key] <= 0
                for key in ("reference", "quest_id", "objective_id", "variable_id")
            )
            or row["reference"] in seen
            or not isinstance(row["evidence"], str)
            or not row["evidence"].strip()
        ):
            raise ValueError("Invalid regional combat mission declaration")
        for key in ("maps", "regions", "families"):
            values = row[key]
            if (
                not isinstance(values, list)
                or not values
                or any(type(value) is not int or value <= 0 for value in values)
                or len(set(values)) != len(values)
            ):
                raise ValueError("Invalid regional combat scope")
        seen.add(row["reference"])
    return document


def qualifying_kills(
    scope, original_monsters, defeated_pairs, source_scene, *, region_at, family_of
):
    """Select only exact original dead actors with known native world regions."""
    if (
        source_scene.get("map_id") not in scope["maps"]
        or source_scene.get("instance_id") != 0
    ):
        return ()
    original = {}
    for monster in original_monsters:
        identity, breed = monster.get("id"), monster.get("ref")
        if (
            type(identity) is not int
            or type(breed) is not int
            or breed <= 0
            or identity in original
        ):
            raise ValueError("Invalid regional original monster roster")
        original[identity] = monster
    selected = []
    for identity, breed in defeated_pairs:
        monster = original.get(identity)
        if monster is None or monster["ref"] != breed:
            raise ValueError("Regional victory differs from its original encounter")
        if any(type(monster.get(key)) is not int for key in ("x", "y")):
            continue
        if family_of(breed) not in scope["families"]:
            continue
        try:
            region = region_at(source_scene["map_id"], monster["x"], monster["y"])
        except ValueError:
            continue
        if region in scope["regions"]:
            selected.append((identity, breed))
    return tuple(selected)


def _drop_source(db, character, fight_id, event):
    row = db.execute(
        "SELECT snapshot,snapshot_sha256 FROM fight_drop_awards "
        "WHERE fight_id=%s AND character_id=%s AND account_id=%s",
        (fight_id, character["id"], character["account_id"]),
    ).fetchone()
    if row is None:
        return False
    snapshot = row["snapshot"]
    encoded = json.dumps(
        snapshot, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode()
    if sha256(encoded).hexdigest() != row["snapshot_sha256"]:
        raise ValueError("Regional combat drop source digest changed")
    if any(
        snapshot.get(key) != value
        for key, value in (
            ("account_id", character["account_id"]),
            ("character_id", character["id"]),
            ("fight_id", fight_id),
            ("can_loot", True),
        )
    ):
        raise ValueError("Regional combat drop source belongs to another winner")
    context = snapshot.get("fight_context", {})
    if (
        context.get("in_dungeon") is not False
        or context.get("in_infinite_waves") is not False
    ):
        return False
    monsters = snapshot.get("monsters")
    if not isinstance(monsters, list) or any(
        not isinstance(row, dict) for row in monsters
    ):
        raise ValueError("Missing original drop source identities")
    pairs = [(row.get("actor_id"), row.get("reference")) for row in monsters]
    if len(set(pairs)) != len(pairs) or not set(
        map(tuple, event["original_monsters"])
    ) <= set(pairs):
        raise ValueError("Regional victory does not match its original drop source")
    return True


def _admission(db, character, fight_id, original_monsters, scene):
    """Bind frozen owned admission to the durably settled original world group."""
    regions = scene.get("admission_regions")
    if not isinstance(regions, dict):
        return False
    region = regions.get(character["account_id"])
    if type(region) is not int or region <= 0 or scene.get("instance_id") != 0:
        return False
    lease = scene.get("group_lease")
    if not isinstance(lease, (tuple, list)) or len(lease) != 4:
        return False
    key, generation, original_fight, revision = lease
    if (
        not isinstance(key, (tuple, list))
        or len(key) != 3
        or any(type(value) is not int for value in key)
        or tuple(key[:2]) != (scene.get("map_id"), 0)
        or not isinstance(generation, str)
        or not generation
        or type(original_fight) is not int
        or original_fight != fight_id
        or type(revision) is not int
        or revision <= 0
    ):
        return False
    row = db.execute(
        "SELECT members,status,revision FROM combat_groups "
        "WHERE map_id=%s AND instance_id=%s AND group_id=%s FOR SHARE",
        tuple(key),
    ).fetchone()
    if row is None or row["status"] != "defeated" or row["revision"] != revision + 1:
        return False
    by_id = {monster["id"]: monster for monster in row["members"]}
    for monster in original_monsters:
        current = by_id.get(monster["id"])
        if current is None or any(
            current.get(key) != monster.get(key) for key in ("ref", "x", "y", "z")
        ):
            raise ValueError(
                "Regional origin differs from its durable defeated world group"
            )
    return True


def _eligible(db, store, character, scope, native_revision):
    from wakfu_server import dungeon_criteria
    from wakfu_server.dungeon_achievement_authority import queries_from_state

    state = storage.load_locked(db, character["id"])
    if (
        scope["quest_id"] not in state["running"]
        or scope["objective_id"] in state["objectives"]
    ):
        return False
    row = db.execute(
        "SELECT data FROM native_quest_metadata_definitions WHERE revision=%s AND definition_id=%s",
        (native_revision, scope["quest_id"]),
    ).fetchone()
    if row is None:
        raise ValueError("Missing regional combat native quest definition")
    definition = row["data"]["native"]
    digest = sha256(
        json.dumps(
            definition, sort_keys=True, separators=(",", ":"), ensure_ascii=True
        ).encode()
    ).hexdigest()
    if digest != scope["native_definition_sha256"]:
        raise ValueError("Regional combat native definition changed")
    objective = next(
        (obj for obj in definition["cjJ"] if obj["d"] == scope["objective_id"]), None
    )
    if objective is None:
        raise ValueError("Regional combat native objective is missing")
    authority = queries_from_state(state)
    try:
        return all(
            dungeon_criteria.evaluate(
                store, criterion, character=character, queries=authority
            )
            for criterion in (
                native_effective_eligibility.criterion(definition),
                objective["ckc"],
                objective["cke"],
            )
        )
    except (ValueError, NotImplementedError, KeyError):
        return False


def _digest(value):
    return sha256(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=True
        ).encode()
    ).hexdigest()


def _profile(db, character, scope):
    """A trusted scoped event may target only its declared native objective."""
    event = {"kind": EVENT_KIND, "reference": scope["reference"], "quantity": 1}
    selected = mission_toolkit._event_profiles(db, event, character, ())
    found = False
    for profile, _ in selected:
        for binding in profile["bindings"]:
            if (
                binding["quest_id"],
                binding["objective_id"],
                binding.get("variable_id"),
                binding["count"],
            ) != (
                scope["quest_id"],
                scope["objective_id"],
                scope["variable_id"],
                "quantity",
            ):
                raise ValueError(
                    "Regional combat event targets another native objective"
                )
            found = True
    return found


def stage(
    db,
    store,
    character,
    fight,
    original_monsters,
    defeated_monsters,
    source_scene,
    *,
    fresh,
):
    """Freeze eligible assigned work with the original fresh fight transaction."""
    if fresh is not True or not isinstance(source_scene, dict):
        return 0
    active = {
        row["reference"]
        for row in db.execute(
            "SELECT DISTINCT i.reference FROM mission_toolkit_event_index i "
            "JOIN mission_toolkit_active a USING(profile_id,version) WHERE i.kind=%s",
            (EVENT_KIND,),
        ).fetchall()
    }
    if not active:
        return 0
    from .service import _event, _owner
    from wakfu_server import monsters, native_catalog, territory_cells

    _owner(db, character)
    if not _admission(db, character, fight.id, original_monsters, source_scene):
        return 0
    event = _event(db, character, fight, defeated_monsters)
    receipt = db.execute(
        "SELECT payload FROM character_achievement_events WHERE character_id=%s AND event_key=%s",
        (character["id"], f"fight:{fight.id}"),
    ).fetchone()
    if receipt is None or receipt["payload"] != event:
        raise ValueError("Missing owned fresh regional combat victory receipt")
    if not _drop_source(db, character, fight.id, event):
        return 0
    document = declarations()
    from wakfu_server.native_catalog_compatibility import require_source_revision

    require_source_revision(
        document["native_catalog_revision"],
        ("monsters.json", "territory-map-cells.json"),
    )
    actor = fight.actors[character["id"]]
    scoped_character = dict(
        character,
        map_id=source_scene["map_id"],
        instance_id=0,
        effective_level=actor.effective_level,
    )
    staged = 0
    for scope in document["scopes"]:
        if scope["reference"] not in active:
            continue
        killed = qualifying_kills(
            scope,
            original_monsters,
            event["original_monsters"],
            source_scene,
            region_at=territory_cells.region_at,
            family_of=lambda breed: monsters.REFERENCES.get(breed, {}).get("family_id"),
        )
        if not killed or not _eligible(
            db, store, scoped_character, scope, document["native_metadata_revision"]
        ):
            continue
        if not _profile(db, scoped_character, scope):
            continue
        key = f"regional-mission-pending:{fight.id}:{scope['reference']}"
        payload = {
            "kind": "regional_mission_pending_v1",
            "account_id": character["account_id"],
            "character_id": character["id"],
            "fight_id": fight.id,
            "scope": scope["reference"],
            "scope_sha256": _digest(scope),
            "native_metadata_revision": document["native_metadata_revision"],
            "event": event,
            "quantity": len(killed),
            "qualified_monsters": [list(pair) for pair in killed],
            "assigned_quest": scope["quest_id"],
            "objective": scope["objective_id"],
            "map_id": source_scene["map_id"],
            "instance_id": 0,
            "effective_level": actor.effective_level,
        }
        staged += storage.record_event(db, character["id"], key, payload)
    return staged


def process(db, store, character, fight_id):
    """Retry existing pending work; never discover jobs from historical victories."""
    from .service import _owner

    _owner(db, character)
    if type(fight_id) is not int or fight_id <= 0:
        raise ValueError("Invalid pending regional fight identity")
    rows = db.execute(
        "SELECT event_key,payload,signature FROM character_achievement_events "
        "WHERE character_id=%s AND event_key LIKE %s FOR UPDATE",
        (character["id"], f"regional-mission-pending:{fight_id}:%"),
    ).fetchall()
    packets = []
    for row in rows:
        payload = row["payload"]
        if payload.get("kind") != "regional_mission_pending_v1":
            continue
        if sha256(storage._json(payload).encode()).hexdigest() != row["signature"]:
            raise ValueError("Pending regional mission receipt digest changed")
        if (
            payload.get("account_id"),
            payload.get("character_id"),
            payload.get("fight_id"),
        ) != (character["account_id"], character["id"], fight_id):
            raise ValueError("Pending regional mission belongs to another owner")
        completed_key = row["event_key"] + ":done"
        completed_payload = {
            "kind": "regional_mission_completed_v1",
            "pending_sha256": row["signature"],
        }
        completed = db.execute(
            "SELECT payload FROM character_achievement_events WHERE character_id=%s AND event_key=%s",
            (character["id"], completed_key),
        ).fetchone()
        if completed is not None:
            if completed["payload"] != completed_payload:
                raise ValueError(
                    "Regional completion receipt differs from pending work"
                )
            continue
        document = declarations()
        scope = next(
            (
                rule
                for rule in document["scopes"]
                if rule["reference"] == payload.get("scope")
            ),
            None,
        )
        if (
            scope is None
            or _digest(scope) != payload.get("scope_sha256")
            or document["native_metadata_revision"]
            != payload.get("native_metadata_revision")
        ):
            raise ValueError("Pending regional scope publication changed")
        if (payload.get("assigned_quest"), payload.get("objective")) != (
            scope["quest_id"],
            scope["objective_id"],
        ):
            raise ValueError("Pending regional assignment changed")
        quantity = payload.get("quantity")
        if (
            type(quantity) is not int
            or not 0 < quantity <= 32767
            or quantity != len(payload.get("qualified_monsters", ()))
        ):
            raise ValueError("Invalid pending regional defeated quantity")
        event = db.execute(
            "SELECT payload FROM character_achievement_events WHERE character_id=%s AND event_key=%s",
            (character["id"], f"fight:{fight_id}"),
        ).fetchone()
        if event is None or event["payload"] != payload.get("event"):
            raise ValueError("Pending regional victory source changed")
        if not _drop_source(db, character, fight_id, event["payload"]):
            raise ValueError("Pending regional drop source is unavailable")
        state = storage.load_locked(db, character["id"])
        if (
            scope["objective_id"] in state["objectives"]
            or scope["quest_id"] in state["completed"]
        ):
            storage.record_event(db, character["id"], completed_key, completed_payload)
            continue
        if scope["quest_id"] not in state["running"]:
            continue
        scoped_character = dict(
            character,
            map_id=payload["map_id"],
            instance_id=payload["instance_id"],
            effective_level=payload["effective_level"],
        )
        if not _profile(db, scoped_character, scope):
            raise ValueError("Pending regional mission profile is unavailable")
        token = f"fight:{fight_id}:scope:{scope['reference']}"
        packets.extend(
            mission_toolkit.settle(
                db,
                store,
                scoped_character,
                token,
                EVENT_KIND,
                scope["reference"],
                quantity,
            )
        )
        event_key = (
            f"mission-toolkit:{EVENT_KIND}:{scope['reference']}:"
            + sha256(token.encode()).hexdigest()
        )
        applied = db.execute(
            "SELECT 1 FROM character_achievement_events WHERE character_id=%s AND event_key=%s",
            (character["id"], event_key),
        ).fetchone()
        if applied is None:
            raise ValueError("Pending regional count was not durably settled")
        storage.record_event(db, character["id"], completed_key, completed_payload)
    return packets


def settle(
    db,
    store,
    character,
    fight,
    original_monsters,
    defeated_monsters,
    source_scene,
    *,
    fresh,
):
    """Convenience adapter; callers isolate staging and processing separately."""
    if fresh is True:
        stage(
            db,
            store,
            character,
            fight,
            original_monsters,
            defeated_monsters,
            source_scene,
            fresh=True,
        )
    return process(db, store, character, fight.id)
