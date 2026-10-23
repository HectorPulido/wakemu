"""Native cBs12705 outside-combat food emote execution, without a fake cast."""
import struct
from .wire import proto_field
from .inventory_consumables import CATALOG

FOOD_EMOTES = {
    effect["id"]
    for item in CATALOG.values()
    for effect in item["effects"]
    if effect["generic"] == 550
    and effect["params"] == [20019.0, 0.0]
    and not effect["effect_criteria"]
}


def eating(*, actor_id, action_id, effect_uid, effect_id):
    """Execute eXH550 -> own actor Y(20019) -> emotes/20019.lua.

    action_id and effect_uid are locally allocated identities. cBs has an
    explicit actor action tuple; leaving it empty would execute nothing.
    """
    if (
        type(actor_id) is not int
        or not 0 < actor_id < (1 << 63)
        or type(action_id) is not int
        or not 0 < action_id < (1 << 31)
        or type(effect_uid) is not int
        or not 0 < effect_uid < (1 << 63)
        or effect_id not in FOOD_EMOTES
    ):
        raise ValueError("Invalid own food animation identities")
    return consumable_emote(
        actor_id=actor_id,
        action_id=action_id,
        effect_uid=effect_uid,
        effect_id=effect_id,
        emote_id=20019,
    )


def consumable_emote(*, actor_id, action_id, effect_uid, effect_id, emote_id):
    """Publish a descriptor-authorized native 550 effect, without learning it."""
    if any(
        type(value) is not int or not 0 < value < limit
        for value, limit in (
            (actor_id, 2**63),
            (action_id, 2**31),
            (effect_uid, 2**63),
            (effect_id, 2**31),
            (emote_id, 2**31),
        )
    ):
        raise ValueError("Invalid native consumable emote identities")
    # iN required UID1/baseUID2. Effect reference3 resolves installed food
    # generic550; value4 supplies emote20019. Caster6/target7 are the same owner.
    effect = b"".join(
        proto_field(field, value)
        for field, value in (
            (8, effect_uid),
            (16, 0),
            (24, effect_id),
            (32, emote_id),
            (48, actor_id),
            (56, actor_id),
        )
    )
    body = struct.pack(">iiBBih", action_id, -1, 0, 0, 550, len(effect)) + effect
    body += struct.pack(">iiq", action_id, -1, actor_id)
    return (12705, body)
