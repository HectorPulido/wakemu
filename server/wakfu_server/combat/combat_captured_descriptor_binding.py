"""Native eHD.pRM active actor identity, separate from persistent species data.

Missing slots are unqualified historical checkpoints; explicit None represents
an attested descriptor without an active UID. Mutations use copy-on-write.
"""


def _keys(owner_id, slot):
    if (
        type(owner_id) is not int
        or not 0 < owner_id < (1 << 63)
        or type(slot) is not int
        or not 0 <= slot < 10
    ):
        raise ValueError("Invalid captured descriptor owner/slot")
    return str(owner_id), str(slot)


def _ledger(fight):
    ledger = getattr(fight, "native_captured_descriptor_actor_ids", {})
    if type(ledger) is not dict:
        raise ValueError("Malformed captured descriptor UID component")
    for owner, slots in ledger.items():
        if (
            type(owner) is not str
            or not owner.isascii()
            or not owner.isdecimal()
            or owner != str(int(owner))
            or not 0 < int(owner) < (1 << 63)
            or type(slots) is not dict
        ):
            raise ValueError("Malformed captured descriptor owner UID component")
        for slot, identity in slots.items():
            if type(slot) is not str or slot not in tuple(
                str(index) for index in range(10)
            ):
                raise ValueError("Malformed captured descriptor slot key")
            if identity is not None and (
                type(identity) is not int or not 0 < identity < (1 << 63)
            ):
                raise ValueError("Malformed captured descriptor actor UID")
    return ledger


def descriptor_actor_id(fight, owner_id, slot):
    owner, selected = _keys(owner_id, slot)
    slots = _ledger(fight).get(owner, {})
    if selected not in slots:
        return False, None
    return True, slots[selected]


def _publish(fight, owner_id, slot, actor_id):
    owner, selected = _keys(owner_id, slot)
    descriptor_actor_id(fight, owner_id, slot)
    ledger = getattr(fight, "native_captured_descriptor_actor_ids", {})
    fight.native_captured_descriptor_actor_ids = {
        **ledger,
        owner: {**ledger.get(owner, {}), selected: actor_id},
    }


def bind_descriptor_actor(fight, owner_id, slot, actor_id):
    """eZr.c assigns the allocated actor UID before the common factory."""
    if type(actor_id) is not int or not 0 < actor_id < (1 << 63):
        raise ValueError("Missing native captured actor UID")
    _publish(fight, owner_id, slot, actor_id)


def clear_descriptor_actor(fight, owner_id, slot):
    """Fresh/released descriptors and completed fcb.aP have fwV == -1."""
    _publish(fight, owner_id, slot, None)
