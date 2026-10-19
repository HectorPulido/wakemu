"""Fence dungeon travel against buffered movement and its Redis journal."""
from contextlib import ExitStack

from wakfu_server.position_buffer import PositionOwnerBusy


def run_party_entry(store, positions, account_id, character_id, *, transition):
    """Fence the complete entry party, including other selected accounts."""
    with store.connection() as db:
        members = db.execute(
            "SELECT c.id,c.account_id FROM characters c WHERE c.id=%s OR c.id IN("
            "SELECT member.character_id FROM player_party_members member "
            "JOIN player_party_members owner ON owner.party_id=member.party_id "
            "WHERE owner.character_id=%s) ORDER BY c.id",
            (character_id, character_id),
        ).fetchall()
    accounts = sorted({account_id, *(row["account_id"] for row in members)})
    return _run_accounts(store, positions, accounts, transition)


def _run_accounts(store, positions, accounts, transition):
    """Keep source checkpoints and committed destination rebinding in one fence."""
    if not callable(transition):
        raise ValueError("Authoritative dungeon transition callback is required")
    accounts = sorted(set(accounts))
    with ExitStack() as barriers:
        for account in accounts:
            barriers.enter_context(positions.account_barrier(account))
        for account in accounts:
            positions.flush(account_id=account)
        # The SQL producer checks this scope against its locked final roster;
        # a concurrently joined account cannot bypass the position barrier.
        result = transition(frozenset(accounts))
        _rebind_clean(store, positions, accounts)
        return result


def run_manual_transition(store, positions, account_id, character_id, *, transition):
    """Fence the active instance roster, which can differ from the current party."""
    with store.connection() as db:
        members = db.execute(
            "SELECT c.account_id FROM dungeon_instance_members owner "
            "JOIN dungeon_instance_members member ON member.instance_id=owner.instance_id "
            "JOIN characters c ON c.id=member.character_id "
            "WHERE owner.character_id=%s AND owner.status='active' "
            "AND member.status='active' ORDER BY c.id",
            (character_id,),
        ).fetchall()
    accounts = {account_id, *(row["account_id"] for row in members)}
    return _run_accounts(store, positions, accounts, transition)


def run_account_exit(store, positions, account_id, *, transition):
    """Fence a departing account and its heroes without moving other accounts."""
    return _run_accounts(store, positions, (account_id,), lambda _: transition())


def _rebind_clean(store, positions, accounts):
    for (account, generation, character_id), entry in positions._entry_snapshot():
        if account not in accounts or not positions.lease_active(
            account, generation, character_id
        ):
            continue
        if entry["dirty"]:
            raise ValueError("Dungeon travel requires a clean position baseline")
        character = store.character(account, character_id)
        positions.attach(account, generation, character)


def run_auto_transition(
    store, positions, instance_id, fight_id, *, transition, topology, in_fight
):
    """Flush source movement, commit travel, then rebind live position baselines.

    Account locks cover both the SQL transition and the new buffer baseline.
    The domain callback still owns membership, session, victory and outbox
    validation. A raced member outside the locked scope must defer travel.
    No dirty movement or conflicting PostgreSQL baseline is discarded.
    """
    if not callable(transition) or not callable(in_fight):
        raise ValueError("Authoritative dungeon transition callbacks are required")
    with store.connection() as db:
        members = db.execute(
            "SELECT c.id,c.account_id FROM dungeon_instance_members m "
            "JOIN characters c ON c.id=m.character_id "
            "WHERE m.instance_id=%s AND m.status='active' ORDER BY c.id",
            (instance_id,),
        ).fetchall()
    member_ids = {row["id"] for row in members}
    accounts = sorted({row["account_id"] for row in members})
    with ExitStack() as barriers:
        try:
            for account in accounts:
                barriers.enter_context(
                    positions.account_barrier(account, blocking=False)
                )
        except PositionOwnerBusy:
            return dict(
                deferred=True, reason="position_owner_busy", instance_id=instance_id
            )
        for account in accounts:
            # RedisPositions.flush also completes durable journal ACKs. Any
            # failed checkpoint aborts before the callback can move the party.
            positions.flush(account_id=account)
        result = transition(
            store,
            instance_id,
            fight_id,
            topology=topology,
            in_fight=lambda identity: (
                True if identity not in member_ids else in_fight(identity)
            ),
        )
        # Travel has committed. Replace only clean, still-owned entries while
        # movement remains fenced; network hydration can safely attach again.
        _rebind_clean(store, positions, accounts)
        return result
