"""Owned combat loot recipients under real main sessions, including heroes."""
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass


@dataclass(frozen=True)
class _DurableSettlement:
    database: object
    transaction_id: str
    fight_id: int
    recipients: frozenset


_SETTLEMENT = ContextVar("combat_reward_durable_settlement", default=None)


@contextmanager
def _durable_settlement_scope(db, fight, participants):
    """Only settle_shared opens this after locking and validating its roster.

    Earned rewards belong to the frozen participants, including offline owners
    and heroes. This capability never authorizes ordinary inventory requests.
    """
    from psycopg.pq import TransactionStatus

    if (
        db.info.transaction_status != TransactionStatus.INTRANS
        or _SETTLEMENT.get() is not None
        or fight.phase != "finished"
        or type(fight.id) is not int
        or fight.id <= 0
        or type(fight.winner) is not int
        or fight.winner not in (0, 1)
    ):
        raise ValueError("Missing locked durable settlement transaction")
    recipients, identities = set(), set()
    for participant in participants:
        owner, identity, generation, team, withdrawn = (
            participant.get(key)
            for key in (
                "account_id",
                "character_id",
                "session_generation",
                "team",
                "withdrawn",
            )
        )
        if (
            type(owner) is not int
            or owner <= 0
            or type(identity) is not int
            or identity <= 0
            or identity in identities
            or not isinstance(generation, str)
            or not generation
            or type(team) is not int
            or team not in (0, 1)
            or type(withdrawn) is not bool
        ):
            raise ValueError("Invalid locked durable settlement roster")
        identities.add(identity)
        if team == fight.winner and not withdrawn:
            recipients.add((owner, generation, identity))
    transaction = db.execute(
        "SELECT pg_current_xact_id()::text AS transaction_id"
    ).fetchone()
    authority = _DurableSettlement(
        db, transaction["transaction_id"], fight.id, frozenset(recipients)
    )
    token = _SETTLEMENT.set(authority)
    try:
        yield
    finally:
        _SETTLEMENT.reset(token)


def lock_recipient(store, db, account_id, generation, character_id, fight_id):
    """Fence a selected main or a durable same-company hero; never create leases.

    Inactive ordinary characters are not authorized by account ownership alone.
    A hero must still belong to the selected main's native company and both must
    be recorded in this finished fight with the same generation and team.
    """
    settlement = _SETTLEMENT.get()
    if settlement is not None:
        from psycopg.pq import TransactionStatus

        if (
            settlement.database is not db
            or db.info.transaction_status != TransactionStatus.INTRANS
            or type(account_id) is not int
            or type(character_id) is not int
            or type(fight_id) is not int
            or not isinstance(generation, str)
            or settlement.fight_id != fight_id
            or (account_id, generation, character_id) not in settlement.recipients
        ):
            raise ValueError("Loot recipient differs from the locked settlement roster")
        transaction = db.execute(
            "SELECT pg_current_xact_id_if_assigned()::text AS transaction_id"
        ).fetchone()
        if transaction["transaction_id"] != settlement.transaction_id:
            raise ValueError("Loot settlement transaction changed")
        if (
            db.execute(
                "SELECT id FROM characters WHERE id=%s AND account_id=%s "
                "AND deleted_at IS NULL FOR UPDATE",
                (character_id, account_id),
            ).fetchone()
            is None
        ):
            raise ValueError("Durable loot recipient is unavailable")
        return
    lease = db.execute(
        "SELECT character_id FROM sessions WHERE account_id=%s AND generation=%s "
        "AND expires_at>%s FOR UPDATE",
        (account_id, generation, store.now()),
    ).fetchone()
    if lease is None:
        raise ValueError("Combat loot recipient has no current account lease")
    main_id = lease["character_id"]
    if main_id == character_id:
        store.lock_character(db, account_id, generation, character_id)
        return
    roster = db.execute(
        "SELECT leader_id FROM account_hero_rosters WHERE account_id=%s FOR UPDATE",
        (account_id,),
    ).fetchone()
    hero = db.execute(
        "SELECT 1 FROM account_hero_slots WHERE account_id=%s AND character_id=%s",
        (account_id, character_id),
    ).fetchone()
    participants = db.execute(
        "SELECT p.character_id,p.team FROM combat_fight_participants p "
        "JOIN combat_fights f ON f.id=p.fight_id WHERE p.fight_id=%s AND "
        "p.account_id=%s AND p.session_generation=%s AND p.character_id=ANY(%s) "
        "AND f.status='finished'",
        (fight_id, account_id, generation, [main_id, character_id]),
    ).fetchall()
    if (
        roster is None
        or roster["leader_id"] != main_id
        or hero is None
        or {p["character_id"] for p in participants} != {main_id, character_id}
        or len({p["team"] for p in participants}) != 1
    ):
        raise ValueError("Combat loot recipient is not a frozen owned hero")
    store.lock_character(db, account_id, generation, character_id, selected=False)
