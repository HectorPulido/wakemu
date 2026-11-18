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


def requirement_from_entry(entry):
    """Parse the legacy single item or explicit distinct-item basket shape."""
    identity = {"reference_id", "action_id", "node_id", "choice_id"}
    if not isinstance(entry, dict) or any(
        type(entry.get(key)) is not int or entry[key] <= 0 for key in identity
    ):
        raise ValueError("Malformed reconstructed item turn-in")
    if set(entry) == identity | {"item_reference", "quantity"}:
        return TurnInRequirement(entry["item_reference"], entry["quantity"])
    if (
        set(entry) != identity | {"items"}
        or not isinstance(entry["items"], list)
        or len(entry["items"]) < 2
    ):
        raise ValueError("Malformed reconstructed item basket")
    items = []
    for row in entry["items"]:
        if not isinstance(row, dict) or set(row) != {"item_reference", "quantity"}:
            raise ValueError("Malformed reconstructed basket item")
        items.append(TurnInRequirement(row["item_reference"], row["quantity"]))
    if len({row.reference for row in items}) != len(items):
        raise ValueError("Duplicate reconstructed basket item")
    return tuple(items)


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
    speaker_row=None,
):
    """Debit the owner and advance the offered objective in the same transaction.

    Call only after verifying an explicit item requirement against a qualified
    offered dialogue edge. A replay after the objective is complete returns no
    changes and never debits again. An insufficient payment or failed reward
    aborts the caller's transaction, including item debit and quest progress.
    speaker_row may supply the caller's locked, publication-validated physical
    provider; it still passes the unchanged offered-edge authorization.
    """
    from . import storage, wire
    from .service import _owner, drain_rewards
    from wakfu_server.native_generic_rewards import _payment

    if type(requirement) is TurnInRequirement:
        requirements = (requirement,)
    elif (
        type(requirement) is tuple
        and len(requirement) >= 2
        and all(type(item) is TurnInRequirement for item in requirement)
        and len({item.reference for item in requirement}) == len(requirement)
    ):
        requirements = requirement
    else:
        raise ValueError("Missing qualified quest delivery requirement")
    if (
        definition.get("cjU") != 0
        or definition.get("cjL") != 0
        or definition.get("getDuration") != 0
    ):
        raise ValueError("Recurring or timed quest delivery is not supported")
    _owner(db, character)
    row = speaker_row
    if row is None:
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
    payment_packets = []
    payment_character = character
    for item in requirements:
        payment_character, item_packets, _ = _payment(
            db,
            store,
            payment_character,
            {"group_cod": item.reference, "group_coe": item.quantity},
        )
        payment_packets.extend(item_packets)
    if type(requirement) is TurnInRequirement:
        fact.update(
            item_reference=requirement.reference, item_quantity=requirement.quantity
        )
    else:
        fact["items"] = [
            dict(item_reference=item.reference, quantity=item.quantity)
            for item in requirements
        ]
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
    from . import mission_toolkit

    for item in requirements:
        packets.extend(
            mission_toolkit.settle(
                db,
                store,
                character,
                token=event_key,
                kind="item_delivery",
                reference=item.reference,
                quantity=item.quantity,
            )
        )
    packets.extend(mission_toolkit.settle_completions(db, store, character, completed))
    return dict(
        applied=True, packets=packets, completed=completed, new_objectives=objectives
    )
