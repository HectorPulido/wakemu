"""Explicit authorized owner takeover of an otherwise frozen native encounter."""
from dataclasses import dataclass
from wakfu_server.maps.proto_dungeon import decode
from .combat_instance_publication import (
    InstancePublicationTracker,
    PartyPublicationLease,
    bind_party_encounter,
    native_roster_bindings,
    require_current_publication,
    withdrawn_player_ids,
)


@dataclass(frozen=True)
class PendingPublicationRecovery:
    original_session: object
    session: object
    publication: tuple


class OwnerPublicationsPending(ValueError):
    """A verified new owner may attach durably, but cannot resume gameplay."""

    def __init__(self, entry, missing):
        super().__init__("Native recovery awaits other participant publications")
        self.entry = entry
        self.missing = tuple(missing)


def publication_recovery_waiting(shared):
    return bool(
        getattr(shared, "pending_publication_recoveries", {})
        or getattr(shared, "publication_recovery_origins", {})
    )


def requires_publication_recovery(fight):
    """Never-published ordinary entry and terminal/duel recovery stay unchanged."""
    return bool(
        fight.phase != "finished"
        and getattr(fight, "native_instance_publication_required", False)
        and getattr(fight, "native_instance_publication_lease", None) is not None
        and getattr(fight, "native_instance_publication_receipt", None) is not None
        and getattr(fight, "native_instance_difficulty_snapshots", None)
    )


def _new_source(session, publication, frozen_gn):
    if type(publication) is not tuple or len(publication) != 2:
        raise ValueError("Native recovery requires the new actual owner publication")
    tracker, scope = publication
    expected = (
        session.account_id,
        session.generation,
        session.character_id,
        session.map_id,
        session.instance_id,
    )
    if (
        not isinstance(tracker, InstancePublicationTracker)
        or scope != expected
        or tracker.scope != scope
        or tracker.published is None
        or tracker.lease.current is None
    ):
        raise ValueError(
            "Native recovery publication has no matching completed new session source"
        )
    receipt = tracker.lease.current
    if receipt[1] != scope or receipt[3] != tracker.published.sha256:
        raise ValueError("Native recovery publication changed during source capture")
    if decode(tracker.published.payload)["difficulty_level"] != frozen_gn:
        raise ValueError(
            "Native recovery cannot change the frozen encounter difficulty"
        )
    return receipt


def rebind_recovered_owner(fight, shared, session, publication, *, session_live=None):
    """Prepare real replacement sources; never resume a partial owner cohort."""
    if not requires_publication_recovery(fight):
        return False
    previous = shared.participants.get(session.account_id)
    staged_entry = getattr(shared, "pending_publication_recoveries", {}).get(
        session.account_id
    )
    resume_staged = (
        staged_entry is not None
        and staged_entry.session == session
        and previous == session
        and session.account_id not in shared.connected
    )
    if (
        previous is None
        or previous.account_id != session.account_id
        or previous.character_id != session.character_id
        or (previous.generation == session.generation and not resume_staged)
        or (session.map_id, session.instance_id) != (shared.map_id, shared.instance_id)
    ):
        raise ValueError(
            "Native recovery requires the authorized same owner and character takeover"
        )
    lease = fight.native_instance_publication_lease
    bindings = getattr(lease, "owner_bindings", ())
    receipt = fight.native_instance_publication_receipt
    receipts = receipt if isinstance(lease, PartyPublicationLease) else (receipt,)
    if not bindings or len(bindings) != len(receipts):
        raise ValueError(
            "Native recovery lacks the original owner publication identities"
        )
    if [scope[0] for _source, scope in bindings].count(session.account_id) != 1:
        raise ValueError(
            "Native recovery owner is absent or duplicated in the frozen encounter"
        )
    original_gn = {
        snapshot.difficulty
        for snapshot in fight.native_instance_difficulty_snapshots.values()
        if snapshot.difficulty is not None
    }
    if len(original_gn) != 1:
        raise ValueError("Native recovery lacks one original concrete NPC difficulty")
    frozen_gn = next(iter(original_gn))
    _new_source(session, publication, frozen_gn)
    origins = getattr(shared, "publication_recovery_origins", {})
    entry = PendingPublicationRecovery(
        origins.get(session.account_id, previous), session, publication
    )
    pending = dict(getattr(shared, "pending_publication_recoveries", {}))
    pending[session.account_id] = entry
    rebound, missing, unchanged = [], [], []
    for (source, old_scope), old_receipt in zip(bindings, receipts):
        owner = old_scope[0]
        staged = pending.get(owner)
        if staged is not None:
            origin = staged.original_session
            if old_scope != (
                origin.account_id,
                origin.generation,
                origin.character_id,
                origin.map_id,
                origin.instance_id,
            ):
                raise ValueError(
                    "Native recovery previous session differs from the frozen owner source"
                )
            if owner != session.account_id:
                if (
                    staged.session != shared.participants.get(owner)
                    or not callable(session_live)
                    or not session_live(staged.session)
                ):
                    missing.append(owner)
                    continue
                try:
                    _new_source(staged.session, staged.publication, frozen_gn)
                except ValueError:
                    missing.append(owner)
                    continue
            rebound.append(staged.publication)
        elif source.scope != old_scope or source.lease.current != old_receipt:
            missing.append(owner)
        else:
            rebound.append((source, old_scope))
            unchanged.append((source, old_receipt))
    if missing:
        raise OwnerPublicationsPending(entry, missing)
    players, npcs = native_roster_bindings(fight)
    if not bind_party_encounter(
        fight,
        publications=tuple(rebound),
        npc_ids=npcs,
        player_ids=players,
        inactive_player_ids=withdrawn_player_ids(fight),
    ):
        raise ValueError("Native recovery lost a completed owner publication")
    if any(
        snapshot.difficulty not in (None, frozen_gn)
        for snapshot in fight.native_instance_difficulty_snapshots.values()
    ):
        raise ValueError(
            "Native recovery difficulty changed during publication binding"
        )
    if any(source.lease.current != expected for source, expected in unchanged):
        raise ValueError("Another owner publication changed during recovery binding")
    for owner, staged in pending.items():
        if owner != session.account_id and not session_live(staged.session):
            raise ValueError("Staged participant lease changed during recovery binding")
    require_current_publication(fight)
    return True
