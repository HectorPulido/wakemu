"""Durable party-owned dungeon sessions; not connected to native transport yet.

The entry callback is intentionally mandatory: it must validate the installed
server's native criterion, source interaction/proximity, and configured route.
This module owns session creation and party authorization, not room composition,
map movement, combat, or reward policy.
"""
from __future__ import annotations

from dataclasses import dataclass
import json

from wakfu_server import player_parties
from wakfu_server.paths import DATA_ROOT


@dataclass(frozen=True)
class EntryRoute:
    key: str
    template_id: int
    definition_id: int
    entry_map_id: int
    entry_object_id: int
    destination_id: int
    start_map_id: int
    criterion: str


# These are catalog identities, not permission to enter. The native
# `not IsNeoServer()` criterion and approach check still need a caller-owned,
# source-verified callback before this API can be wired to the dispatcher.
def _load_routes():
    """Load server-owned mappings; native criteria are never evaluated here."""
    rows = json.loads(
        (DATA_ROOT / "dungeon-entry-routes.json").read_text(encoding="utf8")
    )
    native_rows = json.loads(
        (DATA_ROOT / "native-generic-teleporters.json").read_text(encoding="utf8")
    )
    native_sources = {(row["map_id"], row["id"]): row for row in native_rows}
    if not isinstance(rows, list) or not rows:
        raise RuntimeError("Dungeon entry route configuration is empty")
    result = {}
    required = {
        "key",
        "template_id",
        "definition_id",
        "entry_map_id",
        "entry_object_id",
        "destination_id",
        "start_map_id",
        "criterion",
    }
    for raw in rows:
        if not isinstance(raw, dict) or set(raw) != required:
            raise RuntimeError("Invalid dungeon entry route configuration")
        if (
            not isinstance(raw["key"], str)
            or not raw["key"]
            or not isinstance(raw["criterion"], str)
        ):
            raise RuntimeError("Invalid dungeon route identity or criterion")
        for field in required - {"key", "criterion"}:
            if type(raw[field]) is not int or raw[field] <= 0:
                raise RuntimeError("Invalid dungeon route numeric field")
        if raw["key"] in result:
            raise RuntimeError("Duplicate dungeon entry route key")
        source = native_sources.get((raw["entry_map_id"], raw["entry_object_id"]))
        destination = (
            None
            if source is None
            else next(
                (
                    item
                    for item in source["destinations"]
                    if item["destination_id"] == raw["destination_id"]
                ),
                None,
            )
        )
        if (
            destination is None
            or destination["map_id"] != raw["start_map_id"]
            or destination["cyZ"] != raw["template_id"]
            or destination["criterion"] != raw["criterion"]
        ):
            raise RuntimeError(
                "Dungeon route no longer matches the native teleporter catalog"
            )
        result[raw["key"]] = EntryRoute(**raw)
    return result


_ROUTES = _load_routes()


def _positive_int(value, field):
    if type(value) is not int or not 0 < value < 2**63:
        raise ValueError(f"Invalid dungeon {field}")


def route(key):
    if not isinstance(key, str) or key not in _ROUTES:
        raise ValueError("Unknown configured dungeon route")
    return _ROUTES[key]


def route_for_entry(entry_map_id, entry_object_id, destination_id):
    """Resolve an exact server-configured native route identity."""
    for configured in _ROUTES.values():
        if (
            configured.entry_map_id == entry_map_id
            and configured.entry_object_id == entry_object_id
            and configured.destination_id == destination_id
        ):
            return configured
    return None


def create_or_reuse(
    store,
    account_id,
    generation,
    character_id,
    route_key,
    *,
    authorize_entry,
    transition_destination=None,
):
    """Create/reuse the party's durable run after a server-owned entry check.

    `authorize_entry(character, route)` must be a trusted server callback and
    return exactly True. When a native destination is supplied, run creation
    and party-wide location updates commit in the same transaction. The
    destination accepts no instance ID; that comes from the durable run row.
    """
    for value, field in (
        (account_id, "account"),
        (character_id, "character"),
    ):
        _positive_int(value, field)
    if not isinstance(generation, str) or not generation:
        raise ValueError("Invalid dungeon session generation")
    selected_route = route(route_key)
    if not callable(authorize_entry):
        raise ValueError("Authoritative dungeon entry check required")

    with store.connection() as db:
        initial = db.execute(
            "SELECT p.id,p.leader_id,p.revision FROM player_parties p "
            "JOIN player_party_members m ON m.party_id=p.id "
            "WHERE m.character_id=%s",
            (character_id,),
        ).fetchone()
        if initial is None:
            raise ValueError("Character is not in a player party")
        initial_members = db.execute(
            "SELECT character_id FROM player_party_members WHERE party_id=%s "
            "ORDER BY character_id",
            (initial["id"],),
        ).fetchall()
        member_ids = [row["character_id"] for row in initial_members]
        player_parties._lock_members(db, member_ids)

        # Match party mutations' lock order: member advisory locks, session and
        # character rows in stable character order, then the party row.
        live_rows = db.execute(
            "SELECT c.id,c.account_id,c.map_id,c.instance_id,c.x,c.y,c.z,"
            "s.generation,s.character_id AS selected_character_id,s.expires_at "
            "FROM player_party_members m JOIN characters c ON c.id=m.character_id "
            "JOIN sessions s ON s.account_id=c.account_id "
            "WHERE m.party_id=%s AND c.deleted_at IS NULL "
            "ORDER BY c.id FOR UPDATE OF s,c",
            (initial["id"],),
        ).fetchall()
        party = db.execute(
            "SELECT id,leader_id,revision FROM player_parties WHERE id=%s FOR UPDATE",
            (initial["id"],),
        ).fetchone()
        current_members = [row["id"] for row in live_rows]
        if (
            party is None
            or party["leader_id"] != initial["leader_id"]
            or party["revision"] != initial["revision"]
            or current_members != member_ids
        ):
            raise ValueError("Party changed during dungeon entry")
        leader = next((row for row in live_rows if row["id"] == character_id), None)
        if (
            leader is None
            or leader["account_id"] != account_id
            or leader["generation"] != generation
            or leader["selected_character_id"] != character_id
            or party["leader_id"] != character_id
        ):
            raise ValueError("Only the selected party leader may enter")
        existing = db.execute(
            "SELECT * FROM dungeon_instances WHERE party_id=%s AND status='active' "
            "FOR UPDATE",
            (party["id"],),
        ).fetchone()
        if existing is not None:
            expected = (
                selected_route.template_id,
                selected_route.definition_id,
                selected_route.entry_map_id,
                selected_route.entry_object_id,
                selected_route.destination_id,
                selected_route.start_map_id,
            )
            actual = tuple(
                existing[key]
                for key in (
                    "template_id",
                    "definition_id",
                    "entry_map_id",
                    "entry_object_id",
                    "entry_destination_id",
                    "start_map_id",
                )
            )
            stored_members = db.execute(
                "SELECT character_id,session_generation FROM dungeon_instance_members "
                "WHERE instance_id=%s AND status='active' ORDER BY character_id",
                (existing["instance_id"],),
            ).fetchall()
            if (
                expected != actual
                or [m["character_id"] for m in stored_members] != member_ids
            ):
                raise ValueError(
                    "Party already owns a different active dungeon session"
                )
            if transition_destination is not None and _party_is_at_destination(
                live_rows, existing, transition_destination
            ):
                if any(
                    member["selected_character_id"] != member["id"]
                    or member["expires_at"] <= store.now()
                    for member in live_rows
                ):
                    raise ValueError(
                        "Every party member must have a current selected session"
                    )
                if any(
                    prior["session_generation"] != live["generation"]
                    for prior, live in zip(stored_members, live_rows)
                ):
                    raise ValueError(
                        "Dungeon entry retry has a stale member generation"
                    )
                result = _session_result(existing, member_ids, reused=True)
                result["transition"] = _destination_result(
                    existing, transition_destination, moved=(), already_entered=True
                )
                return result
            _validate_entry_members(live_rows, selected_route, store.now())
            if authorize_entry(dict(leader), selected_route) is not True:
                raise ValueError("Native dungeon entry is not authorized")
            prior_generations = {
                row["character_id"]: row["session_generation"] for row in stored_members
            }
            generation_changed = False
            for member in live_rows:
                if prior_generations[member["id"]] == member["generation"]:
                    continue
                db.execute(
                    "UPDATE dungeon_instance_members SET session_generation=%s "
                    "WHERE instance_id=%s AND character_id=%s AND status='active'",
                    (member["generation"], existing["instance_id"], member["id"]),
                )
                generation_changed = True
            if generation_changed:
                existing = db.execute(
                    "UPDATE dungeon_instances SET revision=revision+1 "
                    "WHERE instance_id=%s RETURNING *",
                    (existing["instance_id"],),
                ).fetchone()
            result = _session_result(existing, member_ids, reused=True)
            if transition_destination is not None:
                result["transition"] = _move_party_members(
                    db, live_rows, existing, transition_destination
                )
            return result

        occupied = db.execute(
            "SELECT character_id FROM dungeon_instance_members WHERE status='active' "
            "AND character_id=ANY(%s) LIMIT 1",
            (member_ids,),
        ).fetchone()
        if occupied is not None:
            raise ValueError(
                "Party member already belongs to an active dungeon session"
            )

        _validate_entry_members(live_rows, selected_route, store.now())
        if authorize_entry(dict(leader), selected_route) is not True:
            raise ValueError("Native dungeon entry is not authorized")

        instance = db.execute(
            "INSERT INTO dungeon_instances(party_id,party_revision,created_by_character_id,"
            "template_id,definition_id,entry_map_id,entry_object_id,entry_destination_id,"
            "start_map_id) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *",
            (
                party["id"],
                party["revision"],
                character_id,
                selected_route.template_id,
                selected_route.definition_id,
                selected_route.entry_map_id,
                selected_route.entry_object_id,
                selected_route.destination_id,
                selected_route.start_map_id,
            ),
        ).fetchone()
        for member in live_rows:
            db.execute(
                "INSERT INTO dungeon_instance_members(instance_id,party_id,character_id,"
                "session_generation,party_revision,role) VALUES(%s,%s,%s,%s,%s,%s)",
                (
                    instance["instance_id"],
                    party["id"],
                    member["id"],
                    member["generation"],
                    party["revision"],
                    "leader" if member["id"] == party["leader_id"] else "member",
                ),
            )
        result = _session_result(instance, member_ids, reused=False)
        if transition_destination is not None:
            result["transition"] = _move_party_members(
                db, live_rows, instance, transition_destination
            )
        return result


def _move_party_members(db, live_rows, session, destination):
    """CAS all already-locked members into the session before commit."""
    if not isinstance(destination, dict) or set(destination) != {
        "map_id",
        "x",
        "y",
        "z",
    }:
        raise ValueError("Invalid dungeon destination")
    if any(type(destination[key]) is not int for key in ("map_id", "x", "y", "z")):
        raise ValueError("Invalid dungeon destination")
    if (
        destination["map_id"] != session["start_map_id"]
        or destination["map_id"] <= 0
        or not -(1 << 31) <= destination["x"] < (1 << 31)
        or not -(1 << 31) <= destination["y"] < (1 << 31)
        or not -(1 << 15) <= destination["z"] < (1 << 15)
    ):
        raise ValueError("Invalid dungeon destination")

    moved = []
    for member in live_rows:
        updated = db.execute(
            "UPDATE characters SET map_id=%s,instance_id=%s,x=%s,y=%s,z=%s "
            "WHERE id=%s AND account_id=%s AND deleted_at IS NULL "
            "AND map_id=%s AND instance_id=%s AND x=%s AND y=%s AND z=%s",
            (
                destination["map_id"],
                session["instance_id"],
                destination["x"],
                destination["y"],
                destination["z"],
                member["id"],
                member["account_id"],
                member["map_id"],
                member["instance_id"],
                member["x"],
                member["y"],
                member["z"],
            ),
        )
        if updated.rowcount != 1:
            raise ValueError("Party member location changed during dungeon entry")
        moved.append(member["id"])
    return _destination_result(session, destination, moved=moved)


def _destination_result(session, destination, *, moved, already_entered=False):
    return {
        "map_id": destination["map_id"],
        "instance_id": session["instance_id"],
        "x": destination["x"],
        "y": destination["y"],
        "z": destination["z"],
        "members": tuple(moved),
        "already_entered": already_entered,
    }


def _party_is_at_destination(live_rows, session, destination):
    if not isinstance(destination, dict) or set(destination) != {
        "map_id",
        "x",
        "y",
        "z",
    }:
        return False
    if any(type(destination.get(key)) is not int for key in ("map_id", "x", "y", "z")):
        return False
    if destination["map_id"] != session["start_map_id"]:
        return False
    return all(
        member["map_id"] == destination["map_id"]
        and member["instance_id"] == session["instance_id"]
        and all(member[key] == destination[key] for key in ("x", "y", "z"))
        for member in live_rows
    )


def _validate_entry_members(live_rows, selected_route, now):
    for member in live_rows:
        if (
            member["selected_character_id"] != member["id"]
            or member["expires_at"] <= now
            or member["map_id"] != selected_route.entry_map_id
            or member["instance_id"] != 0
        ):
            raise ValueError(
                "Every party member must be online at the dungeon entrance"
            )


def _session_result(row, member_ids, *, reused):
    return {
        "instance_id": row["instance_id"],
        "party_id": row["party_id"],
        "party_revision": row["party_revision"],
        "template_id": row["template_id"],
        "definition_id": row["definition_id"],
        "entry_map_id": row["entry_map_id"],
        "entry_object_id": row["entry_object_id"],
        "entry_destination_id": row["entry_destination_id"],
        "start_map_id": row["start_map_id"],
        "status": row["status"],
        "revision": row["revision"],
        "members": tuple(member_ids),
        "reused": reused,
    }


def authorize_member(store, account_id, generation, character_id, instance_id):
    """Return a live membership only for the currently selected owned session."""
    for value, field in (
        (account_id, "account"),
        (character_id, "character"),
        (instance_id, "instance"),
    ):
        _positive_int(value, field)
    with store.connection() as db:
        store.lock_character(db, account_id, generation, character_id)
        row = db.execute(
            "SELECT i.instance_id,i.party_id,i.template_id,i.definition_id,i.status,"
            "m.role,m.party_revision FROM dungeon_instances i "
            "JOIN dungeon_instance_members m ON m.instance_id=i.instance_id "
            "WHERE i.instance_id=%s AND i.status='active' AND m.character_id=%s "
            "AND m.status='active' AND m.session_generation=%s",
            (instance_id, character_id, generation),
        ).fetchone()
        return None if row is None else dict(row)
