"""Transaction-scoped delivery of items through a qualified quest conversation.

The operator supplies an explicit reconstructed binding and the caller owns the
session barrier, transaction, session.choose, commit/rollback and packet delivery.
The item requirement must be backed by evidence; dialogue text is not executable
policy. This module does not publish or activate quests.
"""
from dataclasses import dataclass

from . import conversation


@dataclass(frozen=True)
class TurnInRequirement:
    """One exact item payment; the supported conversation scope is nonrecurring."""

    reference: int
    quantity: int

    def __post_init__(self):
        if (
            type(self.reference) is not int
            or not 0 < self.reference < 2**31
            or type(self.quantity) is not int
            or not 0 < self.quantity <= 32767
        ):
            raise ValueError("Invalid quest delivery requirement")


def settle(
    db,
    store,
    character,
    session,
    binding,
    definition,
    requirement,
    *,
    node_id,
    choice_id,
):
    """Debit the owner and advance the offered objective in the same transaction.

    Call only after verifying an explicit item requirement against a qualified
    offered dialogue edge. A replay after the objective is complete returns no
    changes and never debits again. An insufficient payment or failed reward
    aborts the caller's transaction, including item debit and quest progress.
    """
    from . import storage, wire
    from .service import _owner, drain_rewards
    from wakfu_server.native_generic_rewards import _payment

    if type(requirement) is not TurnInRequirement:
        raise ValueError("Missing qualified quest delivery requirement")
    if (
        definition.get("cjU") != 0
        or definition.get("cjL") != 0
        or definition.get("getDuration") != 0
    ):
        raise ValueError("Recurring or timed quest delivery is not supported")
    _owner(db, character)
    row = db.execute(
        "SELECT * FROM world_dialogue_npcs WHERE actor_id=%s AND enabled FOR SHARE",
        (session.speaker_id,),
    ).fetchone()
    if row is None:
        raise ValueError("Quest NPC is not currently published")
    fact = conversation.authorize_fact(
        character,
        row,
        session,
        binding,
        definition,
        node_id=node_id,
        choice_id=choice_id,
    )
    before = storage.load_locked(db, character["id"])
    now_ms = int(store.now().timestamp() * 1000)
    after, intents, objectives, completed = conversation.advance(
        before,
        fact,
        definition,
        character=character,
        store=store,
        now_ms=now_ms,
    )
    if not objectives:
        return dict(applied=False, packets=[], completed=[], new_objectives=[])
    # _payment supports carried, personal-quest and account-quest items; it
    # protects equipped/offered items and returns the appropriate inventory wire.
    _, payment_packets, _ = _payment(
        db,
        store,
        character,
        {"group_cod": requirement.reference, "group_coe": requirement.quantity},
    )
    fact.update(
        item_reference=requirement.reference, item_quantity=requirement.quantity
    )
    event_key = f"native-quest-delivery:{binding.quest_id}:{binding.objective_id}"
    if not storage.record_event(db, character["id"], event_key, fact):
        raise ValueError("Quest delivery receipt is missing its progress")
    for identity, reward in intents:
        storage.claim_reward(db, character["id"], identity, "once", reward["d"], reward)
    storage.store(db, character["id"], after)
    packets = payment_packets + wire.changes(
        character["id"], before, after, objectives, completed, now_ms
    )
    packets.extend(drain_rewards(db, store, character))
    return dict(
        applied=True, packets=packets, completed=completed, new_objectives=objectives
    )
