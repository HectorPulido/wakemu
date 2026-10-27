"""Selected-owner emergency cancellation, independent of native turn ACKs."""
from dataclasses import dataclass


def bind_selected(store, registry, session, checkpoint_writer):
    """Fence an emergency command onto a replacement selected lease only.

    This transfers durable custody; it does not attach native presentation or
    resume gameplay. Source bindings, action ordering and ACKs stay unchanged.
    """
    registry._live(session)
    shared = registry.lookup_character(session.character_id)
    if shared is None:
        return None
    previous = shared.participants.get(session.account_id)
    if (
        previous is None
        or previous.character_id != session.character_id
        or (session.map_id, session.instance_id) != (shared.map_id, shared.instance_id)
    ):
        raise ValueError("Emergency command cannot take another encounter or character")
    if previous == session:
        return shared
    if not checkpoint_writer.flush_for_takeover(
        shared.fight.id,
        session.account_id,
        previous.generation,
        session.generation,
        timeout=10,
    ):
        raise ValueError("Emergency command checkpoint takeover is still pending")
    with registry._locked_fight(
        character_id=session.character_id, registry=False
    ) as current:
        if (
            current is not shared
            or shared.participants.get(session.account_id) != previous
        ):
            raise ValueError("Emergency command owner changed during checkpoint drain")
        registry._live(session)
        if registry._lease_live(previous):
            raise ValueError("Previous emergency command owner is still live")
        if (
            session.account_id in shared.returned
            or session.account_id in shared.withdrawals
        ):
            raise ValueError("Emergency command owner already left its encounter")
        from wakfu_server.fight_store import takeover_participant

        checkpoint_writer.takeover_writer(
            shared.fight.id,
            session.account_id,
            previous.generation,
            session.generation,
            persist=lambda: takeover_participant(
                store,
                session.account_id,
                session.generation,
                session.character_id,
                shared.fight.id,
                previous_generation=previous.generation,
            ),
        )
        shared.participants[session.account_id] = session
        shared.connected.discard(session.account_id)
        shared.outboxes[session.account_id].clear()
        return shared


def bind_current_owners(store, registry, character_id, checkpoint_writer):
    """Transfer only current same-character replacement leases for a command."""
    # Several owners may have logged back in while native publications
    # still wait for the whole cohort. Transfer only real current leases
    # selecting their exact frozen main character, before taking Fight.
    pending = registry.lookup_character(character_id)
    if pending is not None:
        owners = tuple(pending.participants.values())
        with store.connection() as db:
            leases = db.execute(
                "SELECT account_id,generation,character_id,expires_at FROM sessions WHERE account_id=ANY(%s)",
                ([owner.account_id for owner in owners],),
            ).fetchall()
        by_account = {row["account_id"]: row for row in leases}
        from wakfu_server.combat_shared import Session

        for previous in owners:
            lease = by_account.get(previous.account_id)
            if (
                lease is not None
                and lease["generation"] != previous.generation
                and lease["character_id"] == previous.character_id
                and lease["expires_at"] > store.now()
            ):
                bind_selected(
                    store,
                    registry,
                    Session(
                        previous.account_id,
                        previous.character_id,
                        lease["generation"],
                        pending.map_id,
                        pending.instance_id,
                    ),
                    checkpoint_writer,
                )


def apply_outcome(registry, session, *, win):
    """Apply an authorized operator outcome without gameplay turn/live gates.

    Current selected ownership remains mandatory. Recovery acknowledgements,
    current turn and actor HP gate ordinary actions, not emergency commands.
    Native publication preparation and ordering remain the normal boundary.
    """
    registry._live(session)
    with registry._locked_fight(
        character_id=session.character_id, registry=False
    ) as shared:
        if shared is None:
            return None
        if (
            shared.participants.get(session.account_id) != session
            or session.account_id in shared.returned
            or session.account_id in shared.withdrawals
        ):
            raise ValueError("Operator outcome requires its current owned membership")
        if type(win) is not bool:
            raise ValueError("Invalid operator outcome")
        if shared.settlement_ready:
            return shared
        from wakfu_server.combat_test_commands import finish

        terminal = finish(
            shared.fight,
            shared.runtime,
            account_id=session.account_id,
            character_id=session.character_id,
            win=win,
        )
        prepared = registry._prepare_publication(
            shared,
            terminal.fight,
            terminal.runtime,
            terminal.packets,
            operation="CommandRecovery.apply_outcome",
        )
        shared.fight, shared.runtime, shared.ack = (
            prepared.fight,
            prepared.runtime,
            prepared.ack,
        )
        shared.command_outcome_owner = session
        registry._retire_join_aliases_locked(shared)
        registry._broadcast(shared, prepared.packets)
        return shared


def take_cancelled(registry, session):
    """Deliver a committed recovery even after the live fight indexes retire."""
    with registry.lock:
        pending = getattr(registry, "command_cancellations", {})
        return pending.pop(session, None)


def release_deferred_owners(store, registry, shared):
    """Return selected world-only owners after an administrative settlement."""
    with shared.lock:
        if (
            not shared.settlement_ready
            or getattr(shared, "command_outcome_owner", None) is None
        ):
            return ()
        owners = tuple(
            owner
            for account, owner in shared.participants.items()
            if account not in shared.connected
            and account not in shared.returned
            and account not in shared.withdrawals
            and registry._lease_live(owner)
        )
        for owner in owners:
            release_settled(store, registry, owner, queue_world=True)
        return owners


def release_settled(store, registry, session, *, queue_world=False):
    """Release an explicit travel request after settlement without changing it.

    This administrative return does not certify a native result-screen ACK.
    A duel's already committed health is retained without another HP reset.
    """
    registry._live(session)
    with registry._locked_fight(
        character_id=session.character_id, registry=False
    ) as shared:
        if shared is None:
            return None
        if (
            shared.participants.get(session.account_id) != session
            or shared.fight.phase != "finished"
            or not shared.settlement_ready
        ):
            raise ValueError("Emergency return requires its committed owned result")
        with store.connection() as db:
            store.lock_character(
                db, session.account_id, session.generation, session.character_id
            )
            character = store.character(session.account_id, session.character_id, db)
            if getattr(shared, "is_duel", False):
                if (
                    db.execute(
                        "SELECT 1 FROM friendly_duel_outcomes WHERE fight_id=%s",
                        (shared.fight.id,),
                    ).fetchone()
                    is None
                    or db.execute(
                        "SELECT 1 FROM fight_health_exits WHERE fight_id=%s AND character_id=%s AND reason='return'",
                        (shared.fight.id, session.character_id),
                    ).fetchone()
                    is None
                ):
                    raise ValueError(
                        "Duel outcome and health must commit before emergency return"
                    )
                result = dict(character=character, applied=False)
            else:
                from wakfu_server.combat_health import persist_owned

                result = persist_owned(
                    store,
                    session.account_id,
                    session.generation,
                    character,
                    shared.fight,
                    db=db,
                )
        shared.command_return_owner = session
        exits = getattr(shared, "publication_recovery_aborted", None)
        if exits is None:
            exits = shared.publication_recovery_aborted = {}
        exits[session.character_id] = result
        if queue_world:
            # Publish the committed owner receipt before retiring its indexes;
            # the next socket boundary can always find this world-only return.
            with registry.lock:
                if not hasattr(registry, "command_cancellations"):
                    registry.command_cancellations = {}
                registry.command_cancellations[session] = shared
        registry.mark_returned(shared.fight.id, session)
        return dict(shared=shared, exits=exits)


@dataclass(frozen=True)
class CommandCancellation:
    shared: object
    db: object
    session: object
    participants: tuple

    def require(self, shared, db):
        if (
            self.shared is not shared
            or self.db is not db
            or self.participants != tuple(sorted(shared.participants.items()))
            or shared.participants.get(self.session.account_id) != self.session
            or shared.settlement_ready
            or getattr(shared, "is_duel", False)
        ):
            raise ValueError("Emergency exit lost its selected encounter authority")
        row = db.execute(
            "SELECT generation,character_id,expires_at FROM sessions WHERE account_id=%s FOR UPDATE",
            (self.session.account_id,),
        ).fetchone()
        if (
            row is None
            or row["generation"] != self.session.generation
            or row["character_id"] != self.session.character_id
        ):
            raise ValueError("Emergency exit selected session changed")
        for table in (
            "fight_rewards",
            "fight_reward_policy_receipts",
            "rift_settlement_receipts",
        ):
            if db.execute(
                "SELECT 1 FROM " + table + " WHERE fight_id=%s LIMIT 1",
                (shared.fight.id,),
            ).fetchone():
                raise ValueError(
                    "Emergency cancellation cannot rewrite settled rewards"
                )


def cancel(store, registry, session, *, groups=None, checkpoint_writer=None):
    """Commit all real wounds and release the complete unresolved PvE encounter.

    Caller has authorized the travel command. Every affected socket retains
    its shared object and consumes publication_recovery_aborted before any
    further native combat publication. Travel is performed after this commit.
    """
    registry._live(session)
    if checkpoint_writer is not None:
        bind_current_owners(store, registry, session.character_id, checkpoint_writer)
    with registry._locked_fight(
        character_id=session.character_id, registry=False
    ) as shared:
        if shared is None:
            return None
        if (
            shared.participants.get(session.account_id) != session
            or shared.fight.phase not in ("placement", "active", "finished")
            or shared.settlement_ready
            or getattr(shared, "is_duel", False)
        ):
            raise ValueError(
                "Emergency exit requires its unresolved owned PvE encounter"
            )
        actor = shared.fight.actors.get(session.character_id)
        if (
            actor is None
            or not actor.controlled
            or actor.owner_id != session.account_id
        ):
            raise ValueError("Emergency exit character is outside its encounter")
        from wakfu_server.combat_health import persist_aborted_shared_fight
        from wakfu_server.fight_checkpoint_store import snapshot
        from psycopg.types.json import Jsonb

        with store.connection() as db:
            exits = persist_aborted_shared_fight(
                store,
                shared,
                groups=groups,
                requesting_session=session,
                db=db,
                administrative_cancellation=CommandCancellation(
                    shared, db, session, tuple(sorted(shared.participants.items()))
                ),
            )
            # Preserve the actual source state in the terminal checkpoint; no
            # synthetic win, wounds, turn or acknowledgement is manufactured.
            checkpoint = db.execute(
                "UPDATE fight_checkpoints SET status='aborted',snapshot=%s,revision=revision+1,updated_at=%s "
                "WHERE fight_id=%s RETURNING revision",
                (
                    Jsonb(snapshot(shared.fight, runtime=shared.runtime)),
                    store.now(),
                    shared.fight.id,
                ),
            ).fetchone()
        if checkpoint is not None:
            shared.checkpoint_revision = checkpoint["revision"]
        shared.checkpoint_terminal = True
        shared.publication_recovery_aborted = exits
        with registry.lock:
            pending = getattr(registry, "command_cancellations", None)
            if pending is None:
                pending = registry.command_cancellations = {}
            for previous in tuple(pending):
                if not registry._lease_live(previous):
                    pending.pop(previous, None)
            for participant in shared.participants.values():
                if registry._lease_live(participant):
                    pending[participant] = shared
            if registry.fights.get(shared.fight.id) is shared:
                registry._remove_locked(registry, shared)
        return dict(shared=shared, exits=exits)
