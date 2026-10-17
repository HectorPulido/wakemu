"""Last-living-owner shared abort with real per-account exit continuations."""
from collections import deque
from copy import deepcopy

from .combat_pve_withdraw import Withdrawal, _clone_runtime, live_owner_accounts, plan
from .combat_terminal_metadata import registered_summon_actor_ids


def requires_shared_abort(fight, session):
    """Preserve the existing singleton path unless another KO owes an exit."""
    summons = registered_summon_actor_ids(fight)
    return any(
        actor.controlled
        and actor.id not in summons
        and actor.owner_id != session.account_id
        and actor.hp <= 0
        and not getattr(actor, "pve_withdrawn", False)
        for actor in fight.actors.values()
    )


def prepare(store, registry, session, character, body, *, groups=None, shared=None):
    """Prepare every consumer before atomically persisting all native exits."""
    if (
        body != b""
        or character.get("id") != session.character_id
        or character.get("account_id") != session.account_id
    ):
        raise ValueError("Invalid shared abandonment request")
    if shared is None:
        shared = registry.lookup_character(session.character_id)
    if shared is None:
        raise ValueError("Missing shared abandonment participant")
    with shared.lock:
        if registry.fights.get(shared.fight.id) is not shared:
            raise ValueError("Shared abandonment registry identity changed")
        # Retry after a committed abort cannot mint a second terminal batch.
        if (
            getattr(shared, "full_abandon_owner", None) == session
            and shared.fight.phase == "finished"
        ):
            registry._live(session)
            return dict(
                character=store.character(session.account_id, session.character_id),
                packets=(),
                applied=False,
                group_restored=False,
                shared_full_abort=True,
            )
        registry._member(shared, session)
        if getattr(shared, "is_duel", False) or shared.settlement_ready:
            raise ValueError("Explicit abandonment requires unresolved shared PvE")
        original = shared.fight
        root = original.actors.get(session.character_id)
        summons = registered_summon_actor_ids(original)
        if (
            root is None
            or root.id in summons
            or not root.controlled
            or root.owner_id != session.account_id
            or getattr(root, "pve_withdrawn", False)
            or original.phase not in ("placement", "active")
            or live_owner_accounts(original) - {session.account_id}
        ):
            raise ValueError("Another live primary owner prevents full abandonment")
        if shared.runtime is None:
            from .combat_abandon import placement_runtime

            source_runtime = placement_runtime(original, None)
        else:
            source_runtime = shared.runtime
        candidate = deepcopy(original)
        runtime = _clone_runtime(source_runtime, candidate)
        receipts = dict(shared.withdrawals)
        new_receipts = {}
        for owner, participant in sorted(shared.participants.items()):
            if (
                owner == session.account_id
                or owner in shared.returned
                or owner in receipts
            ):
                continue
            primaries = [
                a
                for a in original.actors.values()
                if a.controlled and a.owner_id == owner and a.id not in summons
            ]
            if not primaries or any(a.hp > 0 for a in primaries):
                raise ValueError("Other owner has no authoritative settled KO roster")
            withdrawal = plan(participant, candidate, runtime)
            candidate, runtime = withdrawal.fight, withdrawal.runtime
            from .combat_captured_roster_lifecycle import restore_departing_roster

            restore_departing_roster(
                candidate, store.character(owner, participant.character_id)
            )
            new_receipts[owner] = dict(
                session=participant,
                withdrawal=withdrawal,
                character=None,
                full_abort_requester=False,
            )
        from .combat_captured_roster_lifecycle import restore_departing_roster

        restore_departing_roster(candidate, character)
        from .combat_abandon import _participant, _terminal_packets

        _participant(session.account_id, character, runtime)
        runtime.fight.phase = "finished"
        runtime.fight.winner = None
        runtime.awaiting_ack = None
        runtime.pending = []
        runtime.turn_deadline = runtime.deadline_turn = None
        runtime.abandon_owner = (session.account_id, session.character_id)
        runtime.abandon_returned = False
        packets = runtime.prepare_delivery(_terminal_packets(runtime, root.team))
        # The requester keeps the existing native scalar ACK path. Its durable
        # receipt also permits recovery if that socket disappears before ACK.
        private = _clone_runtime(runtime, deepcopy(candidate))
        root_ids = tuple(
            a.id
            for a in candidate.actors.values()
            if a.controlled and a.owner_id == session.account_id
        )
        new_receipts[session.account_id] = dict(
            session=session,
            character=None,
            full_abort_requester=True,
            withdrawal=Withdrawal(
                candidate,
                runtime,
                private,
                tuple(packets),
                (),
                deepcopy(root),
                root_ids,
                False,
            ),
        )
        from .combat_shared import Batch

        # Validate native deliveries before opening the durable transaction.
        queues = {
            owner: registry._packets(row["withdrawal"].private_packets)
            for owner, row in new_receipts.items()
        }
        from .combat_health import persist_aborted_shared_fight
        from .fight_store import _write_terminal_checkpoint
        from .combat_captured_roster_checkpoint import persist_captured_roster_updates

        with store.connection() as db:
            health = persist_aborted_shared_fight(
                store, shared, groups=groups, requesting_session=session, db=db
            )
            for owner, receipt in sorted(new_receipts.items()):
                participant = receipt["session"]
                owned = [
                    a.id
                    for a in original.actors.values()
                    if a.controlled and a.owner_id == owner and a.id not in summons
                ]
                for identity in owned:
                    db.execute(
                        "INSERT INTO combat_pve_withdrawals "
                        "(fight_id,character_id,account_id,session_generation,created_at) "
                        "VALUES(%s,%s,%s,%s,%s) ON CONFLICT(fight_id,character_id) DO NOTHING",
                        (
                            original.id,
                            identity,
                            owner,
                            participant.generation,
                            store.now(),
                        ),
                    )
                receipt["character"] = health[participant.character_id]["character"]
            departing_ids = {
                a.id
                for a in original.actors.values()
                if a.controlled and a.owner_id in new_receipts and a.id not in summons
            }
            persist_captured_roster_updates(
                db, candidate, owner_ids=departing_ids, departure=True
            )
            _write_terminal_checkpoint(
                db, store, session.account_id, session.generation, candidate
            )
            db.execute(
                "UPDATE fight_checkpoints SET status='aborted' WHERE fight_id=%s",
                (candidate.id,),
            )
            revision = db.execute(
                "SELECT revision FROM fight_checkpoints WHERE fight_id=%s",
                (candidate.id,),
            ).fetchone()["revision"]
        # All constructors, encoders and durability have succeeded. Publish
        # native results only now; prior private withdrawal receipts survive.
        shared.ack.cancel_for_recovery()
        receipts.update(new_receipts)
        shared.fight, shared.runtime = candidate, runtime
        shared.withdrawals = receipts
        shared.full_abandon_owner = session
        shared.checkpoint_revision, shared.checkpoint_terminal = revision, True
        shared.disconnect_abort_pending = False
        registry._retire_join_aliases_locked(shared)
        for owner in sorted(new_receipts):
            if owner == session.account_id:
                continue  # The requesting socket sends its native result once.
            shared.sequence += 1
            shared.outboxes.setdefault(owner, deque()).append(
                Batch(shared.sequence, queues[owner])
            )
        return dict(
            character=health[session.character_id]["character"],
            packets=packets,
            applied=True,
            group_restored=shared.group_lease is not None,
            shared_full_abort=True,
        )
