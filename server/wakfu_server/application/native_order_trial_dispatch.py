"""Optional native source admission; ordinary gameplay is unchanged while disabled.

Entry uses the existing owned generic transition and outbox. Mode-start and
postcommit publication remain explicit callbacks owned by the actual native
encounter adapter; this module never constructs a fight, form or score.
"""
import struct

from .dispatch_result import DispatchResult


def handle(app, *, mode_start=None, mode_publish=None):
    state, runtime = app.state, app.runtime
    if state.opcode != 12870 or type(state.body) is not bytes or len(state.body) != 12:
        return None
    from wakfu_server import native_order_trial_admission as admission

    capability = admission.document()
    if not capability["enabled"]:
        return None
    identity, _, _ = struct.unpack(">qHH", state.body)
    selected = next(
        (
            source
            for source in capability["sources"].values()
            if source["object_id"] == identity
        ),
        None,
    )
    if selected is None:
        return None
    from psycopg import Error as DatabaseError
    from psycopg_pool import PoolTimeout
    from wakfu_server.position_buffer import PositionOwnerBusy
    from wakfu_server import dungeon_position_barrier, dungeon_runtime
    from wakfu_server import owned_story_generic_entry as generic_entry
    from wakfu_server.combat_geometry import prepare_geometry
    from wakfu_server.combat_terrain import map_geometry

    try:
        if (
            state.character is None
            or not state.loaded
            or state.fight is not None
            or getattr(state, "combat_session", None) is not None
            or state.spectator_session is not None
            or state.bag_session is not None
            or state.environment_ticket is not None
            or app.environment_blocked()
        ):
            raise ValueError("Native order admission requires a loaded idle owner")
        is_entry = identity == capability["sources"]["entrance"]["object_id"]
        if not is_entry:
            mode_start = mode_start or getattr(
                runtime, "native_order_trial_mode_start", None
            )
            mode_publish = mode_publish or getattr(
                runtime, "native_order_trial_mode_publish", None
            )
            if mode_start is None and mode_publish is None:
                from .native_order_trial_mode import callbacks

                mode_start, mode_publish = callbacks(app)
            if not callable(mode_start) or not callable(mode_publish):
                raise ValueError("Native order encounter start is not installed")
        with runtime.POSITIONS.account_barrier(state.account_id):
            runtime.flush_positions(
                account_id=state.account_id,
                generation=state.generation,
                character_id=state.character["id"],
            )
            with runtime.STORE.connection() as db:
                runtime.STORE.lock_character(
                    db,
                    state.account_id,
                    state.generation,
                    state.character["id"],
                    selected=True,
                )
                current = runtime.STORE.character(
                    state.account_id, state.character["id"], db
                )
            if (
                current is None
                or current["account_id"] != state.account_id
                or current["map_id"] != selected["map_id"]
                or (current.get("instance_id", 0) == 0) != is_entry
                or (current["map_id"], current.get("instance_id", 0))
                != (state.character["map_id"], state.character.get("instance_id", 0))
            ):
                raise ValueError("Native order source belongs to another owned scene")
            state.character = current
            goals = frozenset(map(tuple, selected["approaches"]))
            if tuple(current[k] for k in ("x", "y", "z")) not in goals:
                if app.approach_actor(
                    goals.__contains__,
                    geometry=prepare_geometry(map_geometry(current["map_id"])),
                ):
                    return DispatchResult.CONTINUE
                raise ValueError(
                    "Native order source has no reachable original approach"
                )

        def transition(accounts):
            with runtime.STORE.connection() as db:
                current = runtime.STORE.character(
                    state.account_id, state.character["id"], db
                )
                if (
                    current is None
                    or current["account_id"] != state.account_id
                    or current["id"] != state.character["id"]
                ):
                    raise ValueError(
                        "Native order admission lost its current selected character"
                    )
                proof = admission.qualify(
                    db,
                    runtime.STORE,
                    state.account_id,
                    state.generation,
                    current,
                    state.body,
                    loaded=state.loaded,
                    blocked=app.environment_blocked()
                    or state.environment_ticket is not None,
                    value=capability,
                )
                if not is_entry:
                    accepted = mode_start(db, runtime.STORE, current, proof, capability)
                    if accepted is not True and not isinstance(
                        accepted, DispatchResult
                    ):
                        raise ValueError(
                            "Native order encounter did not accept its original mode source"
                        )
                    return accepted
                configuration = generic_entry.configuration(
                    db, current["map_id"], identity
                )
                if configuration is None:
                    raise ValueError("Native order context is not published")
                metadata = configuration["route"].get("native_generic_entry", {})
                if (
                    configuration["route"]["start_map_id"]
                    != capability["context"]["map_id"]
                    or metadata.get("effect_reference") != proof.effect_reference
                    or metadata.get("approaches") != selected["approaches"]
                    or admission.digest(metadata.get("program"))
                    != proof.descriptor_sha256
                ):
                    raise ValueError(
                        "Native order context differs from its source-qualified program"
                    )

                def initialize(entry_db, session):
                    dungeon_runtime.initialize_instance(
                        entry_db,
                        session,
                        groups=runtime.COMBAT_GROUPS,
                        geometry=map_geometry(capability["context"]["map_id"]),
                        store=runtime.STORE,
                    )

                return generic_entry.enter(
                    runtime.STORE,
                    state.account_id,
                    state.generation,
                    current,
                    state.body,
                    loaded=state.loaded,
                    blocked=False,
                    allowed_position_accounts=accounts,
                    initialize_instance=initialize,
                    resolve_destination=dungeon_runtime.entry_destination,
                    _db=db,
                )

        accepted = dungeon_position_barrier.run_party_entry(
            runtime.STORE,
            runtime.POSITIONS,
            state.account_id,
            state.character["id"],
            transition=transition,
        )
        if is_entry:
            app.deliver_dungeon_transitions(before_action=True)
            return DispatchResult.CONTINUE
        # The constructor/enqueue owner must publish its existing queue outcome
        # after SQL commit. A truthy acknowledgement alone cannot replace it.
        published = mode_publish(app, accepted)
        if isinstance(published, DispatchResult):
            return published
        if published is not True:
            raise ValueError(
                "Native order start publication did not acknowledge its normal queue outcome"
            )
        return DispatchResult.CONTINUE
    except (ValueError, DatabaseError, PoolTimeout, PositionOwnerBusy) as error:
        from wakfu_server.ecology_feedback import information

        runtime.record(
            event="native_order_admission_rejected",
            actor_id=None if state.character is None else state.character["id"],
            reason=type(error).__name__,
            detail=str(error),
        )
        runtime.send(
            state.connection,
            state.service,
            *information(
                "This arcade is unavailable. Use its original entrance or mode control and try again."
            )
        )
        return DispatchResult.CONTINUE
