"""Atomic native travel between explicitly reviewed solo quest instances.

No route is enabled by this module. A source run must pin an exact transfer
and the destination must already be an activated, independently owned profile.
The ordinary departure, admission, payment and delivery producers share one
transaction; an admission failure never strands a player outside the old run.
"""

import struct

from wakfu_server import (
    dungeon_exit,
    dungeon_runtime,
    dungeon_transport,
    dungeon_runtime_config,
    dungeon_instances,
)
from wakfu_server.achievements import owned_quest_encounters, storage

_REQUEST = struct.Struct(">qiBi")
_SCHEMA = "owned-quest-transfer-v1"


def source_policy(configuration):
    """Recognize existing settled encounters or explicitly typed world trials."""
    selected = owned_quest_encounters.policy(configuration)
    if selected is not None:
        return "encounter", selected
    from wakfu_server import owned_object_trials

    selected = owned_object_trials.policy(configuration)
    if selected is not None:
        return "object_trial", selected
    from wakfu_server import owned_story_controller

    selected = owned_story_controller.policy(configuration)
    return ("story", selected) if selected is not None else (None, None)


def selection(topology, body):
    declarations = topology.get("owned_quest_transfers", ())
    if not declarations:
        return None
    if (
        not isinstance(body, (bytes, bytearray, memoryview))
        or len(body) != _REQUEST.size
    ):
        raise ValueError("Invalid native quest transfer request")
    source, destination, flag, mode = _REQUEST.unpack(body)
    matches = []
    for row in declarations:
        if (
            not isinstance(row, dict)
            or set(row) != {"schema", "source_id", "destination_id", "target_route_key"}
            or row.get("schema") != _SCHEMA
            or any(
                type(row.get(k)) is not int or row[k] <= 0
                for k in ("source_id", "destination_id")
            )
            or not isinstance(row.get("target_route_key"), str)
            or not row["target_route_key"]
        ):
            raise ValueError("Invalid pinned quest transfer declaration")
        if (row["source_id"], row["destination_id"]) == (source, destination):
            matches.append(row)
    if len(matches) > 1:
        raise ValueError("Ambiguous pinned quest transfer")
    if matches and (flag not in (0, 1) or not 1 <= mode <= 10):
        raise ValueError("Unsupported native quest transfer mode")
    return matches[0] if matches else None


def declared_sources(topology, sources, *, map_id):
    """Qualify transfer objects independently of ordinary dungeon exits.

    Presentation never authorizes payment or admission. Those remain in the
    exact native `_enter` transaction when the player selects the destination.
    """
    declarations = topology.get("owned_quest_transfers", ())
    if not declarations:
        return frozenset()
    if source_policy(dict(topology=topology))[1] is None:
        raise ValueError("Owned transfers require their declared quest source policy")
    owned = {source["id"]: source for source in sources}
    identities = set()
    for row in declarations:
        try:
            body = _REQUEST.pack(row["source_id"], row["destination_id"], 0, 2)
        except (KeyError, TypeError, struct.error) as error:
            raise ValueError("Invalid declared native quest transfer") from error
        declared = selection(topology, body)
        resolved = dungeon_transport.resolve_request(map_id, body)
        if (
            resolved is None
            or resolved["route"].key != declared["target_route_key"]
            or resolved["route"].start_map_id == map_id
            or owned.get(declared["source_id"]) != resolved["source"]
        ):
            raise ValueError("Owned transfer differs from its activated native target")
        identities.add(declared["source_id"])
    return frozenset(identities)


def target_policy(configuration):
    """Use the same strict qualification as activated owned-route registration."""
    from wakfu_server.quest_instance_configuration import reviewed_owned_policy

    return reviewed_owned_policy(configuration)


def transfer(
    store,
    account_id,
    generation,
    character_id,
    body,
    *,
    source_allowed,
    criterion_allowed,
    in_fight,
    initialize_instance=None,
    resolve_destination=None,
    positions=None
):
    """Leave and enter through one native source without an observable exterior."""
    if not all(callable(f) for f in (source_allowed, criterion_allowed, in_fight)):
        raise ValueError("Authoritative quest transfer callbacks are required")
    if positions is not None:
        from wakfu_server.dungeon_position_barrier import run_account_exit

        return run_account_exit(
            store,
            positions,
            account_id,
            defer_rebind_busy=True,
            transition=lambda: transfer(
                store,
                account_id,
                generation,
                character_id,
                body,
                source_allowed=source_allowed,
                criterion_allowed=criterion_allowed,
                in_fight=in_fight,
                initialize_instance=initialize_instance,
                resolve_destination=resolve_destination,
            ),
        )
    with store.connection() as db:
        from wakfu_server import player_parties, companions

        player_parties._lock_members(db, [character_id])
        store.lock_character(db, account_id, generation, character_id)
        character = store.character(account_id, character_id, db=db)
        run, configuration = dungeon_runtime.configuration_for_instance(
            db, character["instance_id"]
        )
        declared = selection(configuration["topology"], body)
        if declared is None:
            return None
        source_kind, policy = source_policy(configuration)
        if policy is None:
            raise ValueError("Quest transfer requires an owned source policy")
        # Freeze the same party lock as departure and admission. A social party
        # or a company added after the original admission cannot travel alone.
        db.execute(
            "SELECT id FROM player_parties WHERE id=%s FOR UPDATE", (run["party_id"],)
        ).fetchone()
        members = db.execute(
            "SELECT character_id,session_generation FROM dungeon_instance_members "
            "WHERE instance_id=%s AND status='active' ORDER BY character_id FOR UPDATE",
            (run["instance_id"],),
        ).fetchall()
        social = db.execute(
            "SELECT character_id FROM player_party_members WHERE party_id=%s ORDER BY character_id",
            (run["party_id"],),
        ).fetchall()
        progress = db.execute(
            "SELECT status FROM dungeon_room_runs WHERE instance_id=%s FOR UPDATE",
            (run["instance_id"],),
        ).fetchone()
        if source_kind == "object_trial":
            from wakfu_server import owned_object_trials

            owned_object_trials._scope(db, store, character)
        elif source_kind == "story":
            from wakfu_server import owned_story_controller, owned_story_native_links

            selected, completed = owned_story_controller._scope(db, store, character)
            link = owned_story_native_links.selected_link(selected, body)
            if link is None or not set(link["requires"]) <= completed:
                raise ValueError(
                    "Story transfer requires its earned native link frontier"
                )
        settled = (
            progress is None
            if source_kind == "object_trial"
            else progress is not None and progress["status"] == "completed"
        )
        if (
            members != [dict(character_id=character_id, session_generation=generation)]
            or social != [dict(character_id=character_id)]
            or companions.controlled_count(db, [character_id])
            or not settled
            or in_fight(character_id) is not False
        ):
            raise ValueError("Quest transfer requires a settled solo encounter")
        # Physical content visits need the actual settled source encounter,
        # not an assigned quest/objective. Story settlement remains independent.
        resolved = dungeon_transport.resolve_request(character["map_id"], body)
        if (
            resolved is None
            or resolved["route"].key != declared["target_route_key"]
            or resolved["route"].start_map_id == character["map_id"]
            or source_allowed(character, dict(resolved["source"])) is not True
        ):
            raise ValueError("Quest transfer has no exact authorized native target")
        target_configuration = dungeon_runtime_config.active_configuration(
            db, dungeon_instances.canonical_context_key(resolved["route"])
        )
        if target_policy(target_configuration) is None:
            raise ValueError("Quest transfer target has no owned admission policy")
        origin = {k: character[k] for k in ("map_id", "instance_id", "x", "y", "z")}
        # Departure uses its ordinary member/company cleanup and supersedes any
        # pending old bootstrap. The intermediate public location never commits.
        dungeon_exit._leave(
            store,
            account_id,
            generation,
            character_id,
            in_fight=in_fight,
            destination_for=lambda *_: {
                k: origin[k] for k in ("map_id", "x", "y", "z")
            },
            _db=db,
        )

        if target_configuration["topology"].get("owned_story_controller") is not None:
            from wakfu_server import owned_story_reentry

            owned_story_reentry.prepare(
                db,
                store,
                account_id,
                generation,
                character_id,
                resolved,
                target_configuration,
            )

        def admitted_source(actor, source):
            return (
                actor["instance_id"] == 0
                and all(actor[k] == origin[k] for k in ("map_id", "x", "y", "z"))
                and source == resolved["source"]
            )

        def initialize_target(db, session):
            pinned = dungeon_runtime_config.pinned_configuration(
                db,
                dungeon_instances.canonical_context_key(resolved["route"]),
                session["context_policy_version"],
            )
            if target_policy(pinned) is None:
                raise ValueError("Quest transfer target lost its pinned owned policy")
            if initialize_instance is not None:
                initialize_instance(db, session)

        result = dungeon_transport._enter(
            store,
            account_id,
            generation,
            character_id,
            origin["map_id"],
            body,
            source_allowed=admitted_source,
            criterion_allowed=criterion_allowed,
            initialize_instance=initialize_target,
            resolve_destination=resolve_destination,
            allowed_position_accounts=frozenset((account_id,)),
            _db=db,
        )
        db.execute(
            "UPDATE dungeon_transition_outbox SET status='superseded',superseded_at=%s "
            "WHERE instance_id=%s AND character_id=%s AND status='pending'",
            (store.now(), origin["instance_id"], character_id),
        )
        # Retain the true private source in the durable event, rather than the
        # unobservable intermediate public location used by standard admission.
        db.execute(
            "UPDATE dungeon_transition_outbox SET source_instance_id=%s "
            "WHERE instance_id=%s AND character_id=%s AND session_generation=%s AND status='pending'",
            (origin["instance_id"], result["instance_id"], character_id, generation),
        )
        return result
