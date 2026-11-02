"""Durable party-owned dungeon sessions; not connected to native transport yet.

The entry callback is intentionally mandatory: it must validate the installed
server's native criterion, source interaction/proximity, and configured route.
This module owns session creation and party authorization, not room composition,
map movement, combat, or reward policy.
"""
from __future__ import annotations
from wakfu_server import native_catalog as protocol_catalog

from dataclasses import dataclass, replace
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
    native_template_id: int | None = None
    context_route_key: str | None = None


# These are catalog identities, not permission to enter. The native
# `not IsNeoServer()` criterion and approach check still need a caller-owned,
# source-verified callback before this API can be wired to the dispatcher.
def _load_routes(rows=None):
    """Load server-owned mappings; native criteria are never evaluated here."""
    if rows is None:
        rows = protocol_catalog.load(DATA_ROOT / "dungeon-entry-routes.json")
    native_rows = protocol_catalog.load(DATA_ROOT / "native-generic-teleporters.json")
    native_sources = {(row["map_id"], row["id"]): row for row in native_rows}
    if not isinstance(rows, list) or not rows:
        raise RuntimeError("Dungeon entry route configuration is empty")
    result = {}
    entrances = set()
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
    legacy_fields = {
        "registration_policy",
        "native_definition_id",
        "native_template_id",
        "native_localization_key",
    }
    for raw in rows:
        legacy = (
            isinstance(raw, dict)
            and raw.get("registration_policy") == "local_legacy_map_registry"
        )
        if not isinstance(raw, dict) or set(raw) != (
            required | legacy_fields if legacy else required
        ):
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
        entrance = (raw["entry_map_id"], raw["entry_object_id"], raw["destination_id"])
        if entrance in entrances:
            raise RuntimeError("Duplicate dungeon native entrance")
        entrances.add(entrance)
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
            or (not legacy and destination["cyZ"] != raw["template_id"])
            or destination["criterion"] != raw["criterion"]
        ):
            raise RuntimeError(
                "Dungeon route no longer matches the native teleporter catalog"
            )
        if legacy:
            from .dungeon_legacy_catalog import validate_legacy_route

            validate_legacy_route(raw, native_sources)
        result[raw["key"]] = EntryRoute(
            **{field: raw[field] for field in required},
            native_template_id=raw["native_template_id"] if legacy else None,
        )
    return result


def canonical_context_key(configured):
    """Aliases keep literal entrances while pinning the reviewed source context."""
    return configured.context_route_key or configured.key


def _derive_entry_aliases(configured, configurations, *, native_rows=None):
    """Derive only reviewed native exterior entrances; never create policies.

    Configurations are loaded through pinned_configuration at startup. All
    entrance identities are validated again against the published native source.
    """
    if native_rows is None:
        native_rows = protocol_catalog.load(
            DATA_ROOT / "native-generic-teleporters.json"
        )
    sources = {(row["map_id"], row["id"]): row for row in native_rows}
    result = dict(configured)
    entrances = {
        (r.entry_map_id, r.entry_object_id, r.destination_id): r
        for r in result.values()
    }
    for configuration in configurations:
        topology = configuration["topology"]
        policy = topology.get("entry_path_policy")
        if policy is None:
            continue
        if policy.get("policy") != "native-entry-discriminated-encounter-paths-v1":
            raise RuntimeError("Unknown native dungeon entry-path policy")
        canonical = result.get(configuration["route"]["key"])
        if canonical is None or canonical.context_route_key is not None:
            raise RuntimeError("Native entry aliases lack their canonical route")
        for name in (
            "template_id",
            "definition_id",
            "entry_map_id",
            "entry_object_id",
            "destination_id",
            "start_map_id",
            "criterion",
        ):
            if configuration["route"].get(name) != getattr(canonical, name):
                raise RuntimeError(
                    "Native entry aliases contradict their canonical route"
                )
        if topology.get("asset_map_id") != canonical.start_map_id:
            raise RuntimeError("Native entry aliases contradict their asset map")
        paths = policy.get("paths")
        entries = policy.get("entry_sources")
        if (
            not isinstance(paths, list)
            or not paths
            or any(
                not isinstance(p, dict)
                or not isinstance(p.get("key"), str)
                or not p["key"]
                for p in paths
            )
            or len({p["key"] for p in paths}) != len(paths)
            or not isinstance(entries, list)
            or not entries
        ):
            raise RuntimeError("Native entry aliases lack reviewed paths and entrances")
        path_keys = {p["key"] for p in paths}
        seen = set()
        for entry in entries:
            if (
                not isinstance(entry, dict)
                or set(entry) != {"map_id", "source_id", "destination_id", "path"}
                or entry["path"] not in path_keys
                or any(
                    type(entry[k]) is not int or entry[k] <= 0
                    for k in ("map_id", "source_id", "destination_id")
                )
            ):
                raise RuntimeError("Invalid native dungeon entry alias")
            identity = (entry["map_id"], entry["source_id"], entry["destination_id"])
            if identity in seen:
                raise RuntimeError("Duplicate reviewed native dungeon entrance")
            seen.add(identity)
            source = sources.get(identity[:2])
            matches = (
                []
                if source is None
                else [
                    d
                    for d in source["destinations"]
                    if d["destination_id"] == identity[2]
                ]
            )
            if (
                len(matches) != 1
                or matches[0]["map_id"] != canonical.start_map_id
                or matches[0]["cyZ"]
                != (canonical.native_template_id or canonical.template_id)
                or not isinstance(matches[0]["criterion"], str)
            ):
                raise RuntimeError(
                    "Native entry alias no longer matches its source catalog"
                )
            previous = entrances.get(identity)
            if previous is not None:
                if canonical_context_key(previous) != canonical.key:
                    raise RuntimeError(
                        "Native entrance already belongs to another dungeon context"
                    )
                if previous.criterion != matches[0]["criterion"]:
                    raise RuntimeError("Native entry alias criterion changed")
                continue
            key = f"{canonical.key}@entry:{identity[0]}:{identity[1]}:{identity[2]}"
            if key in result:
                raise RuntimeError("Duplicate native dungeon entry alias key")
            alias = replace(
                canonical,
                key=key,
                entry_map_id=identity[0],
                entry_object_id=identity[1],
                destination_id=identity[2],
                criterion=matches[0]["criterion"],
                context_route_key=canonical.key,
            )
            result[key] = alias
            entrances[identity] = alias
    return result


_ROUTES = _load_routes()


def load_runtime_routes(store):
    """Install one fully validated startup registry from the committed bundle.

    An absent setting keeps catalog defaults. A present malformed registry never
    falls back to defaults; startup must fail and expose the configuration error.
    No registry is partially published while native validation runs.
    """
    global _ROUTES
    with store.connection() as db:
        row = db.execute(
            "SELECT value FROM settings WHERE name='dungeon_runtime_routes'"
        ).fetchone()
    if row is None:
        prepared = _load_routes()
    else:
        registry = row["value"]
        if (
            not isinstance(registry, dict)
            or set(registry) != {"schema_version", "routes"}
            or type(registry["schema_version"]) is not int
            or registry["schema_version"] != 1
            or not isinstance(registry["routes"], list)
        ):
            raise RuntimeError("Invalid installed dungeon route registry")
        prepared = _load_routes(registry["routes"])
    from wakfu_server.dungeon_runtime_config import pinned_configuration

    with store.connection() as db:
        active = db.execute(
            "SELECT route_key,policy_version FROM dungeon_runtime_active_configurations "
            "ORDER BY route_key"
        ).fetchall()
        configurations = [
            pinned_configuration(db, row["route_key"], row["policy_version"])
            for row in active
        ]
    prepared = _derive_entry_aliases(prepared, configurations)
    _ROUTES = prepared
    return tuple(prepared.values())


def _positive_int(value, field):
    if type(value) is not int or not 0 < value < 2**63:
        raise ValueError(f"Invalid dungeon {field}")


def route(key):
    configured = _ROUTES
    if not isinstance(key, str) or key not in configured:
        raise ValueError("Unknown configured dungeon route")
    return configured[key]


def has_entry_aliases(configured):
    key = canonical_context_key(configured)
    return any(row.context_route_key == key for row in _ROUTES.values())


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


def entry_object_ids(map_id):
    """Snapshot the installed registry's exterior entrance identities."""
    configured = _ROUTES
    return frozenset(
        row.entry_object_id for row in configured.values() if row.entry_map_id == map_id
    )


def create_or_reuse(
    store,
    account_id,
    generation,
    character_id,
    route_key,
    *,
    authorize_entry,
    difficulty_selection=None,
    transition_destination=None,
    initialize_instance=None,
    resolve_destination=None,
    allowed_position_accounts=None,
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
    if initialize_instance is not None and not callable(initialize_instance):
        raise ValueError("Dungeon initializer must be a trusted callback")
    if resolve_destination is not None and not callable(resolve_destination):
        raise ValueError("Dungeon destination resolver must be a trusted callback")

    with store.connection() as db:
        initial = db.execute(
            "SELECT p.id,p.leader_id,p.revision FROM player_parties p "
            "JOIN player_party_members m ON m.party_id=p.id "
            "WHERE m.character_id=%s",
            (character_id,),
        ).fetchone()
        if initial is None:
            # Serialize the ungrouped-to-singleton transition with invitations
            # and other entry attempts. Do not acquire another party's member
            # locks after holding this individual lock: reject a raced join so
            # the next request can follow the ordinary ascending lock order.
            player_parties._lock_members(db, [character_id])
            raced_party = db.execute(
                "SELECT p.id,p.leader_id,p.revision FROM player_parties p "
                "JOIN player_party_members m ON m.party_id=p.id WHERE m.character_id=%s",
                (character_id,),
            ).fetchone()
            if raced_party is not None:
                raced_members = db.execute(
                    "SELECT character_id FROM player_party_members WHERE party_id=%s",
                    (raced_party["id"],),
                ).fetchall()
                if raced_party["leader_id"] != character_id or raced_members != [
                    {"character_id": character_id}
                ]:
                    raise ValueError("Party changed during dungeon entry")
                initial = raced_party
            else:
                store.lock_character(db, account_id, generation, character_id)
                initial = db.execute(
                    "INSERT INTO player_parties(leader_id,dungeon_solo) VALUES(%s,true) "
                    "RETURNING id,leader_id,revision",
                    (character_id,),
                ).fetchone()
                db.execute(
                    "INSERT INTO player_party_members(character_id,party_id) VALUES(%s,%s)",
                    (character_id, initial["id"]),
                )
        initial_members = db.execute(
            "SELECT character_id FROM player_party_members WHERE party_id=%s "
            "ORDER BY character_id",
            (initial["id"],),
        ).fetchall()
        member_ids = [row["character_id"] for row in initial_members]
        if has_entry_aliases(selected_route):
            from psycopg.errors import LockNotAvailable

            try:
                owned = db.execute(
                    "SELECT instance_id FROM dungeon_instances WHERE party_id=%s "
                    "AND status='active' FOR UPDATE NOWAIT",
                    (initial["id"],),
                ).fetchone()
                if owned is not None:
                    db.execute(
                        "SELECT instance_id FROM dungeon_room_runs WHERE instance_id=%s FOR UPDATE NOWAIT",
                        (owned["instance_id"],),
                    ).fetchone()
            except LockNotAvailable as error:
                raise ValueError(
                    "Dungeon reentry is busy; retry interaction"
                ) from error
        from wakfu_server.dungeon_entry_paths import (
            lock_members_nowait,
            owner_lock_query,
            lock_accounts_nowait,
            lock_owned_heroes_nowait,
        )

        alias_family = has_entry_aliases(selected_route)
        if alias_family:
            lock_members_nowait(db, member_ids)
        else:
            player_parties._lock_members(db, member_ids)

        if alias_family:
            accounts = db.execute(
                "SELECT DISTINCT account_id FROM characters WHERE id=ANY(%s)",
                (member_ids,),
            ).fetchall()
            lock_accounts_nowait(db, [row["account_id"] for row in accounts])
        # Match party mutations' lock order: member advisory locks, session and
        # character rows in stable character order, then the party row.
        live_rows = owner_lock_query(
            db,
            "SELECT c.id,c.account_id,c.map_id,c.instance_id,c.x,c.y,c.z,"
            "s.generation,s.character_id AS selected_character_id,s.expires_at "
            "FROM player_party_members m JOIN characters c ON c.id=m.character_id "
            "JOIN sessions s ON s.account_id=c.account_id "
            "WHERE m.party_id=%s AND c.deleted_at IS NULL "
            "ORDER BY c.id FOR UPDATE OF s,c",
            (initial["id"],),
            nonblocking=alias_family,
        ).fetchall()
        party = owner_lock_query(
            db,
            "SELECT id,leader_id,revision FROM player_parties WHERE id=%s FOR UPDATE",
            (initial["id"],),
            nonblocking=alias_family,
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
        ):
            raise ValueError("Only a selected party leader or frozen member may enter")
        from wakfu_server.characters.heroes import expand_session_rows

        if alias_family:
            lock_owned_heroes_nowait(db, live_rows)
        live_rows = expand_session_rows(db, store, live_rows)
        if allowed_position_accounts is not None and any(
            member["account_id"] not in allowed_position_accounts
            for member in live_rows
        ):
            raise ValueError("Dungeon entry party changed outside position barrier")
        member_ids = [row["id"] for row in live_rows]
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
            # Removed heroes remain historical members. Returned members still
            # belong to the frozen roster and may rejoin this same active run.
            stored_members = db.execute(
                "SELECT character_id,session_generation,status FROM dungeon_instance_members "
                "WHERE instance_id=%s AND status IN ('active','returned') ORDER BY character_id",
                (existing["instance_id"],),
            ).fetchall()
            if [m["character_id"] for m in stored_members] != member_ids:
                raise ValueError(
                    "Party already owns a different active dungeon session"
                )
            requested_entry_path = None
            if expected != actual or has_entry_aliases(selected_route):
                if existing["context_route_key"] != canonical_context_key(
                    selected_route
                ):
                    raise ValueError(
                        "Party already owns a different active dungeon session"
                    )
                from wakfu_server.dungeon_entry_paths import pinned_reentry_path

                requested_entry_path = pinned_reentry_path(db, existing, selected_route)
                if expected != actual and requested_entry_path is None:
                    raise ValueError(
                        "Party already owns a different active dungeon session"
                    )
            if existing["context_route_key"] != canonical_context_key(selected_route):
                raise ValueError(
                    "Active dungeon session has no matching pinned context policy"
                )
            from wakfu_server.dungeon_context import policy_version

            pinned_policy = policy_version(
                db, selected_route, existing["context_policy_version"]
            )
            if difficulty_selection is not None:
                from wakfu_server import dungeon_difficulty

                dungeon_difficulty.configure_entry(
                    db, existing["instance_id"], character_id, **difficulty_selection
                )
                from wakfu_server.characters.dungeon_modulation_health import reconcile

                reconcile(store, db, [member["id"] for member in live_rows])
            if transition_destination is not None and resolve_destination is not None:
                transition_destination = resolve_destination(
                    db,
                    _session_result(existing, member_ids, reused=True),
                    dict(transition_destination),
                )
            outside = [m for m in live_rows if m["instance_id"] == 0]
            inside = [
                m for m in live_rows if m["instance_id"] == existing["instance_id"]
            ]
            if transition_destination is not None and outside and inside:
                # Rejoin a frozen roster without teleporting companions already
                # progressing inside. New members remain rejected above.
                _validate_entry_members(outside, selected_route, store.now())
                if len(outside) + len(inside) != len(live_rows) or any(
                    m["selected_character_id"] != m.get("hero_main_id", m["id"])
                    or m["expires_at"] <= store.now()
                    for m in inside
                ):
                    raise ValueError("Every frozen member must have a current session")
                if (
                    authorize_entry(
                        store.character(account_id, character_id, db), selected_route
                    )
                    is not True
                ):
                    raise ValueError("Native dungeon entry is not authorized")
                for member in outside:
                    db.execute(
                        "UPDATE dungeon_instance_members SET status='active',ended_at=NULL,"
                        "session_generation=%s WHERE instance_id=%s AND character_id=%s",
                        (member["generation"], existing["instance_id"], member["id"]),
                    )
                    db.execute(
                        "UPDATE dungeon_transition_outbox SET status='superseded',"
                        "superseded_at=%s WHERE character_id=%s AND status='pending'",
                        (store.now(), member["id"]),
                    )
                existing = db.execute(
                    "UPDATE dungeon_instances SET revision=revision+1 "
                    "WHERE instance_id=%s RETURNING *",
                    (existing["instance_id"],),
                ).fetchone()
                result = _session_result(existing, member_ids, reused=True)
                result["context_policy_version"] = pinned_policy.policy_version
                result["transition"] = _move_party_members(
                    db, outside, existing, transition_destination, store=store
                )
                if initialize_instance is not None:
                    initialize_instance(
                        db, dict(result, _requested_entry_path=requested_entry_path)
                    )
                return result
            if transition_destination is not None and _party_is_at_destination(
                live_rows, existing, transition_destination
            ):
                if any(
                    member["selected_character_id"]
                    != member.get("hero_main_id", member["id"])
                    or member["expires_at"] <= store.now()
                    for member in live_rows
                ):
                    raise ValueError(
                        "Every party member must have a current selected session"
                    )
                generation_changed = False
                for prior, live in zip(stored_members, live_rows):
                    if prior["session_generation"] == live["generation"]:
                        continue
                    db.execute(
                        "UPDATE dungeon_instance_members SET session_generation=%s "
                        "WHERE instance_id=%s AND character_id=%s AND status='active'",
                        (
                            live["generation"],
                            existing["instance_id"],
                            live["id"],
                        ),
                    )
                    db.execute(
                        "UPDATE dungeon_transition_outbox SET status='superseded',"
                        "superseded_at=%s WHERE instance_id=%s AND character_id=%s "
                        "AND status='pending' AND session_generation<>%s",
                        (
                            store.now(),
                            existing["instance_id"],
                            live["id"],
                            live["generation"],
                        ),
                    )
                    generation_changed = True
                if generation_changed:
                    existing = db.execute(
                        "UPDATE dungeon_instances SET revision=revision+1 "
                        "WHERE instance_id=%s RETURNING *",
                        (existing["instance_id"],),
                    ).fetchone()
                result = _session_result(existing, member_ids, reused=True)
                result["context_policy_version"] = pinned_policy.policy_version
                result["transition"] = _destination_result(
                    existing, transition_destination, moved=(), already_entered=True
                )
                if initialize_instance is not None:
                    initialize_instance(
                        db, dict(result, _requested_entry_path=requested_entry_path)
                    )
                return result
            _validate_entry_members(live_rows, selected_route, store.now())
            if (
                authorize_entry(
                    store.character(leader["account_id"], leader["id"], db),
                    selected_route,
                )
                is not True
            ):
                raise ValueError("Native dungeon entry is not authorized")
            prior_members = {row["character_id"]: row for row in stored_members}
            generation_changed = False
            for member in live_rows:
                prior = prior_members[member["id"]]
                if (
                    prior["session_generation"] == member["generation"]
                    and prior["status"] == "active"
                ):
                    continue
                db.execute(
                    "UPDATE dungeon_instance_members SET session_generation=%s,"
                    "status='active',ended_at=NULL "
                    "WHERE instance_id=%s AND character_id=%s "
                    "AND status IN ('active','returned')",
                    (member["generation"], existing["instance_id"], member["id"]),
                )
                db.execute(
                    "UPDATE dungeon_transition_outbox SET status='superseded',"
                    "superseded_at=%s WHERE instance_id=%s AND character_id=%s "
                    "AND status='pending'",
                    (
                        store.now(),
                        existing["instance_id"],
                        member["id"],
                    ),
                )
                generation_changed = True
            if generation_changed:
                existing = db.execute(
                    "UPDATE dungeon_instances SET revision=revision+1 "
                    "WHERE instance_id=%s RETURNING *",
                    (existing["instance_id"],),
                ).fetchone()
            if transition_destination is not None:
                existing = db.execute(
                    "UPDATE dungeon_instances SET revision=revision+1 "
                    "WHERE instance_id=%s RETURNING *",
                    (existing["instance_id"],),
                ).fetchone()
            result = _session_result(existing, member_ids, reused=True)
            result["context_policy_version"] = pinned_policy.policy_version
            if transition_destination is not None:
                result["transition"] = _move_party_members(
                    db, live_rows, existing, transition_destination, store=store
                )
            if initialize_instance is not None:
                initialize_instance(
                    db, dict(result, _requested_entry_path=requested_entry_path)
                )
            return result

        if party["leader_id"] != character_id:
            raise ValueError("Only the selected party leader may enter")

        # An outside character can retain membership after leaving an old
        # party. Reconcile only foreign rosters whose authoritative location
        # is outside all instances; never release a member still inside a run.
        stale_members = db.execute(
            "UPDATE dungeon_instance_members m SET status='returned',ended_at=%s "
            "FROM characters c WHERE c.id=m.character_id AND m.status='active' "
            "AND m.character_id=ANY(%s) AND m.party_id<>%s AND c.instance_id=0 "
            "RETURNING m.instance_id,m.character_id",
            (store.now(), member_ids, party["id"]),
        ).fetchall()
        for stale_member in stale_members:
            db.execute(
                "UPDATE dungeon_transition_outbox SET status='superseded',superseded_at=%s "
                "WHERE instance_id=%s AND character_id=%s AND status='pending'",
                (
                    store.now(),
                    stale_member["instance_id"],
                    stale_member["character_id"],
                ),
            )

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
        if (
            authorize_entry(
                store.character(leader["account_id"], leader["id"], db), selected_route
            )
            is not True
        ):
            raise ValueError("Native dungeon entry is not authorized")

        from wakfu_server.dungeon_context import active_policy

        context_policy = active_policy(db, selected_route)

        instance = db.execute(
            "INSERT INTO dungeon_instances(party_id,party_revision,created_by_character_id,"
            "template_id,definition_id,entry_map_id,entry_object_id,entry_destination_id,"
            "start_map_id,context_route_key,context_policy_version) "
            "VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *",
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
                context_policy.route_key,
                context_policy.policy_version,
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
        if difficulty_selection is not None:
            from wakfu_server import dungeon_difficulty

            dungeon_difficulty.configure_entry(
                db, instance["instance_id"], character_id, **difficulty_selection
            )
        result = _session_result(instance, member_ids, reused=False)
        result["context_policy_version"] = context_policy.policy_version
        if transition_destination is not None and resolve_destination is not None:
            transition_destination = resolve_destination(
                db, result, dict(transition_destination)
            )
        if transition_destination is not None:
            result["transition"] = _move_party_members(
                db, live_rows, instance, transition_destination, store=store
            )
        if initialize_instance is not None:
            initialize_instance(db, result)
        return result


def _move_party_members(db, live_rows, session, destination, *, store):
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
    from wakfu_server.characters.dungeon_modulation_health import reconcile

    reconcile(store, db, moved)
    for member in live_rows:
        if member.get("hero_main_id") is not None:
            continue
        db.execute(
            "INSERT INTO dungeon_transition_outbox(instance_id,party_id,"
            "transition_revision,character_id,session_generation,source_map_id,"
            "source_instance_id,source_x,source_y,source_z,destination_map_id,"
            "destination_instance_id,destination_x,destination_y,destination_z) "
            "VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (
                session["instance_id"],
                session["party_id"],
                session["revision"],
                member["id"],
                member["generation"],
                member["map_id"],
                member["instance_id"],
                member["x"],
                member["y"],
                member["z"],
                destination["map_id"],
                session["instance_id"],
                destination["x"],
                destination["y"],
                destination["z"],
            ),
        )
    return _destination_result(session, destination, moved=moved)


def pending_transitions(store, account_id, generation, character_id):
    """Return durable map changes for the exact currently selected lease.

    A new session may supersede its old generation's unacknowledged packet
    intent. Reconnection already bootstraps from the authoritative character
    location, so this never moves the replacement session.
    """
    for value, field in ((account_id, "account"), (character_id, "character")):
        _positive_int(value, field)
    if not isinstance(generation, str) or not generation:
        raise ValueError("Invalid dungeon session generation")
    with store.connection() as db:
        db.execute("SET LOCAL lock_timeout = '250ms'")
        store.lock_character(db, account_id, generation, character_id)
        db.execute(
            "UPDATE dungeon_transition_outbox SET status='superseded',"
            "superseded_at=%s WHERE character_id=%s AND status='pending' "
            "AND session_generation<>%s",
            (store.now(), character_id, generation),
        )
        character = db.execute(
            "SELECT map_id,instance_id,x,y,z FROM characters WHERE id=%s "
            "AND account_id=%s AND deleted_at IS NULL",
            (character_id, account_id),
        ).fetchone()
        rows = db.execute(
            "SELECT o.* FROM dungeon_transition_outbox o "
            "JOIN dungeon_instance_members m "
            "ON m.instance_id=o.instance_id AND m.character_id=o.character_id "
            "JOIN dungeon_instances i "
            "ON i.instance_id=o.instance_id AND i.party_id=o.party_id "
            "WHERE o.character_id=%s AND o.session_generation=%s "
            "AND o.status='pending' "
            "AND ((o.transition_kind='exit' AND m.status='returned' "
            "AND i.status IN ('active','completed','closed')) "
            "OR (o.transition_kind<>'exit' AND m.status='active' AND i.status='active')) "
            "AND m.session_generation=%s "
            "ORDER BY o.transition_revision,o.event_id FOR UPDATE OF o",
            (character_id, generation, generation),
        ).fetchall()
        pending = []
        for row in rows:
            if any(
                row[f"destination_{field}"] != character[field]
                for field in ("map_id", "instance_id", "x", "y", "z")
            ):
                db.execute(
                    "UPDATE dungeon_transition_outbox SET status='superseded',"
                    "superseded_at=%s WHERE event_id=%s AND status='pending'",
                    (store.now(), row["event_id"]),
                )
                continue
            pending.append(dict(row))
        return tuple(pending)


def acknowledge_transition(store, account_id, generation, character_id, event_id):
    """Acknowledge one fully sent transition, not visual client consumption.

    The caller must send its complete map bootstrap before calling this API.
    The lease, membership generation, active run, and persisted destination are
    rechecked under row locks. Repeating an ACK by the same live lease is safe.
    """
    for value, field in (
        (account_id, "account"),
        (character_id, "character"),
        (event_id, "transition event"),
    ):
        _positive_int(value, field)
    if not isinstance(generation, str) or not generation:
        raise ValueError("Invalid dungeon session generation")
    with store.connection() as db:
        db.execute("SET LOCAL lock_timeout = '250ms'")
        # Match create_or_reuse's row-lock order: session/character, party,
        # run, membership, then outbox. The initial character lock serializes
        # this ACK against party transitions before either takes party/run
        # locks.
        store.lock_character(db, account_id, generation, character_id)
        identity = db.execute(
            "SELECT instance_id,party_id FROM dungeon_transition_outbox "
            "WHERE event_id=%s AND character_id=%s",
            (event_id, character_id),
        ).fetchone()
        if identity is None:
            raise ValueError("Dungeon transition does not belong to this character")
        party = db.execute(
            "SELECT id FROM player_parties WHERE id=%s FOR UPDATE",
            (identity["party_id"],),
        ).fetchone()
        instance = db.execute(
            "SELECT status FROM dungeon_instances WHERE instance_id=%s AND party_id=%s "
            "FOR UPDATE",
            (identity["instance_id"], identity["party_id"]),
        ).fetchone()
        member = db.execute(
            "SELECT status,session_generation FROM dungeon_instance_members "
            "WHERE instance_id=%s AND character_id=%s FOR UPDATE",
            (identity["instance_id"], character_id),
        ).fetchone()
        row = db.execute(
            "SELECT status,transition_kind,session_generation,destination_map_id,destination_instance_id,"
            "destination_x,destination_y,destination_z FROM dungeon_transition_outbox "
            "WHERE event_id=%s AND character_id=%s FOR UPDATE",
            (event_id, character_id),
        ).fetchone()
        character = db.execute(
            "SELECT map_id,instance_id,x,y,z FROM characters WHERE id=%s",
            (character_id,),
        ).fetchone()
        if (
            party is None
            or instance is None
            or member is None
            or row is None
            or character is None
        ):
            raise ValueError("Dungeon transition membership no longer exists")
        if (
            row["session_generation"] != generation
            or member["session_generation"] != generation
            or (
                row["transition_kind"] == "exit"
                and (
                    member["status"] != "returned"
                    or instance["status"] not in ("active", "completed", "closed")
                )
            )
            or (
                row["transition_kind"] != "exit"
                and (member["status"] != "active" or instance["status"] != "active")
            )
        ):
            raise ValueError("Dungeon transition membership or session was replaced")
        if row["status"] == "acknowledged":
            return False
        if row["status"] != "pending":
            raise ValueError("Dungeon transition is no longer pending")
        if any(
            row[f"destination_{field}"] != character[field]
            for field in ("map_id", "instance_id", "x", "y", "z")
        ):
            raise ValueError("Dungeon transition destination is no longer current")
        updated = db.execute(
            "UPDATE dungeon_transition_outbox SET status='acknowledged',"
            "acknowledged_at=%s,acknowledged_generation=%s "
            "WHERE event_id=%s AND status='pending' RETURNING event_id",
            (store.now(), generation, event_id),
        ).fetchone()
        return updated is not None


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
            member["selected_character_id"] != member.get("hero_main_id", member["id"])
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
