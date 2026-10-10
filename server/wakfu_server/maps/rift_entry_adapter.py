"""Native rift admission with an atomic, server-owned party transition.

The caller supplies native approach and walkability checks and delivers its
normal map bootstrap after commit. No client-provided instance ID is accepted.
"""
import secrets
import struct

from wakfu_server import player_parties, rift_runtime


def decode_action(body):
    if (
        not isinstance(body, (bytes, bytearray, memoryview))
        or len(body) != 12
        or bytes(body[10:]) != b"\0\0"
    ):
        raise ValueError("Invalid native interactive action")
    return struct.unpack(">qH", body[:10])


def resolve_portal(catalog, map_id, body):
    object_id, action = decode_action(body)
    if action != 11:
        return None
    found = [
        (value, source)
        for value in catalog.values()
        for source in value["entrances"]
        if source["map_id"] == map_id and source["object_id"] == object_id
    ]
    if len(found) > 1:
        raise ValueError("Ambiguous native rift portal")
    return found[0] if found else None


def _roster(db, store, account_id, generation, character_id):
    party = db.execute(
        "SELECT p.id,p.leader_id,p.revision FROM player_parties p "
        "JOIN player_party_members m ON m.party_id=p.id WHERE m.character_id=%s",
        (character_id,),
    ).fetchone()
    ids = (
        [character_id]
        if party is None
        else [
            r["character_id"]
            for r in db.execute(
                "SELECT character_id FROM player_party_members WHERE party_id=%s ORDER BY character_id",
                (party["id"],),
            ).fetchall()
        ]
    )
    player_parties._lock_members(db, ids)
    rows = db.execute(
        "SELECT c.*,s.generation,s.character_id AS selected_character_id,s.expires_at "
        "FROM characters c JOIN sessions s ON s.account_id=c.account_id "
        "WHERE c.id=ANY(%s) AND c.deleted_at IS NULL ORDER BY c.id FOR UPDATE OF s,c",
        (ids,),
    ).fetchall()
    current = db.execute(
        "SELECT p.id,p.leader_id,p.revision FROM player_parties p "
        "JOIN player_party_members m ON m.party_id=p.id WHERE m.character_id=%s",
        (character_id,),
    ).fetchone()
    if current != party:
        raise ValueError("Party changed during rift entry")
    if party is not None:
        locked = db.execute(
            "SELECT id,leader_id,revision FROM player_parties WHERE id=%s FOR UPDATE",
            (party["id"],),
        ).fetchone()
        members = [
            r["character_id"]
            for r in db.execute(
                "SELECT character_id FROM player_party_members WHERE party_id=%s ORDER BY character_id",
                (party["id"],),
            ).fetchall()
        ]
        if locked != party or members != ids or party["leader_id"] != character_id:
            raise ValueError("Only the current party leader may enter a rift")
    owner = next((r for r in rows if r["id"] == character_id), None)
    if (
        owner is None
        or owner["account_id"] != account_id
        or owner["generation"] != generation
        or [r["id"] for r in rows] != ids
    ):
        raise ValueError("Invalid rift character session")
    if any(
        r["selected_character_id"] != r["id"] or r["expires_at"] <= store.now()
        for r in rows
    ):
        raise ValueError("Every rift member must have a current selected session")
    from wakfu_server.characters.heroes import expand_session_rows

    rows = expand_session_rows(db, store, rows)
    ids = [row["id"] for row in rows]
    if db.execute(
        "SELECT 1 FROM combat_fight_participants p JOIN combat_fights f ON f.id=p.fight_id "
        "WHERE p.character_id=ANY(%s) AND f.status IN('placement','active') LIMIT 1",
        (ids,),
    ).fetchone():
        raise ValueError("Rift members cannot already be fighting")
    return rows


def enter(
    store,
    account_id,
    generation,
    character_id,
    map_id,
    body,
    *,
    source_allowed,
    resolve_destination,
    seed=None,
    allowed_accounts=None
):
    """Return run and moved session rows; map packet delivery remains caller-owned."""
    if not callable(source_allowed) or not callable(resolve_destination):
        raise ValueError("Native source and destination authorities are required")
    with store.connection() as db:
        catalog = db.execute(
            "SELECT value FROM settings WHERE name='rift_catalog'"
        ).fetchone()
        if catalog is None:
            return None
        resolved = resolve_portal(catalog["value"], map_id, body)
        if resolved is None:
            return None
        selected, source = resolved
        rows = _roster(db, store, account_id, generation, character_id)
        if allowed_accounts is not None and any(
            r["account_id"] not in allowed_accounts for r in rows
        ):
            raise ValueError("Party changed outside the position barrier scope")
        owner = next(r for r in rows if r["id"] == character_id)
        for row in rows:
            if (
                row["map_id"] != map_id
                or row["instance_id"] != owner["instance_id"]
                or row["level"] < selected["level"]
                or source_allowed(row, dict(source)) is not True
            ):
                raise ValueError("Rift member is not eligible at the native portal")
        run = rift_runtime.enter(
            db,
            selected["wave_id"],
            character_id,
            [r["id"] for r in rows],
            seed=seed or secrets.token_hex(16),
            authorize=lambda frozen, members: frozen == selected,
        )
        destination = resolve_destination(
            db, dict(selected), tuple(dict(r) for r in rows)
        )
        if (
            not isinstance(destination, dict)
            or destination.get("map_id") != selected["map_id"]
            or any(
                type(destination.get(k)) is not int for k in ("map_id", "x", "y", "z")
            )
            or any(not -(1 << 31) <= destination[k] < (1 << 31) for k in ("x", "y"))
            or not -(1 << 15) <= destination["z"] < (1 << 15)
        ):
            raise ValueError("Unverified native rift arrival")
        for row in rows:
            db.execute(
                "UPDATE characters SET map_id=%s,instance_id=%s,x=%s,y=%s,z=%s WHERE id=%s",
                (
                    destination["map_id"],
                    run["instance_id"],
                    destination["x"],
                    destination["y"],
                    destination["z"],
                    row["id"],
                ),
            )
        return {
            "run": run,
            "destination": {**destination, "instance_id": run["instance_id"]},
            "members": tuple(rows),
        }


def authorize_start(
    db, store, account_id, generation, character_id, body, *, source_allowed
):
    """Validate classic activator action 0; ultimate paid starts are separate."""
    object_id, action = decode_action(body)
    if action != 0:
        return None
    store.lock_character(db, account_id, generation, character_id)
    character = store.character(account_id, character_id, db)
    run = db.execute(
        "SELECT * FROM rift_instances WHERE instance_id=%s FOR UPDATE",
        (character["instance_id"],),
    ).fetchone()
    if run is None:
        return None
    if run["catalog"]["type"] != "INFINITE_WAVE":
        raise ValueError("Ultimate rifts require a separate native key authority")
    sources = [
        r
        for r in run["catalog"]["objects"]
        if r["id"] == object_id
        and r["type"] == "GenericActivableInteractiveElement"
        and r["map_id"] == character["map_id"] == run["catalog"]["map_id"]
    ]
    if not sources:
        return None
    if (
        len(sources) != 1
        or run["status"] != "entered"
        or run["owner_character_id"] != character_id
        or not callable(source_allowed)
        or source_allowed(character, sources[0]) is not True
    ):
        raise ValueError("Native rift start was not authorized")
    members = db.execute(
        "SELECT c.id,c.account_id,c.map_id,c.instance_id,s.character_id AS selected_character_id,s.expires_at "
        "FROM characters c LEFT JOIN sessions s ON s.account_id=c.account_id "
        "WHERE c.id=ANY(%s)",
        (run["members"],),
    ).fetchall()
    from wakfu_server.characters.heroes import session_authorized

    if {r["id"] for r in members} != set(run["members"]) or any(
        r["map_id"] != character["map_id"]
        or r["instance_id"] != run["instance_id"]
        or not session_authorized(db, r)
        or r["expires_at"] is None
        or r["expires_at"] <= store.now()
        for r in members
    ):
        raise ValueError("Frozen rift members left the instance")
    return run
