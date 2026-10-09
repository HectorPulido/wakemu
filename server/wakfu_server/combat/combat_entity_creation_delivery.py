"""Execute an evaluated immediate entity descriptor on the native client."""
import struct


def immediate_effect_application(fight_id, action_id, effect_class, payload):
    if (
        any(
            type(value) is not int or not 0 < value < 1 << 31
            for value in (fight_id, action_id, effect_class)
        )
        or not isinstance(payload, bytes)
        or not 0 < len(payload) <= 32767
    ):
        raise ValueError("Invalid native immediate entity creation delivery")
    # cvY/aTR observes without c(). These immediate runners have no Qf record
    # for the retained-delivery normalizer. cvX/eIK=true calls bbL then a(),
    # executing the already decoded descriptor without C() or Qf retention.
    return (
        12613,
        struct.pack(">iiiBih", fight_id, action_id, -1, 1, effect_class, len(payload))
        + payload,
    )


immediate_entity_creation = immediate_effect_application
