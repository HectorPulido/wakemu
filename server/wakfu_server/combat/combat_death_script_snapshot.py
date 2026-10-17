"""Exact immediate eWE PI operand replay, independent of retained Qf runners."""
from .combat_effect_removal import _identity_fields
from .combat_stat_effects import owned_effect_application
from .combat_observation_delivery import evaluated_application_from_observation


def immediate_death_script_packets(fight, actors, action_id):
    """Restore public immediate PI operands for the recipient's visible roster."""
    packets = []
    for actor in actors:
        packet = immediate_death_script_packet(fight, actor, action_id)
        if packet is not None:
            packets.append(packet)
    return tuple(packets)


def immediate_death_script_packet(fight, actor, action_id):
    record = getattr(actor, "native_immediate_death_script", None)
    if record is None:
        return None
    if fight.actors.get(actor.id) is not actor or not isinstance(record, dict):
        raise ValueError("Missing owned immediate death-script actor")
    if (
        record.get("producer") != "eWE.c.eGj.PI"
        or record.get("fight_id") != fight.id
        or record.get("actor_id") != actor.id
    ):
        raise ValueError("Invalid immediate death-script provenance")
    value = record.get("value")
    if type(value) is not int or value != getattr(
        actor, "native_death_script_id", None
    ):
        raise ValueError("Immediate death-script no longer matches actual PI")
    try:
        payload = bytes.fromhex(record["payload_hex"])
    except (KeyError, TypeError, ValueError):
        raise ValueError("Invalid immediate death-script payload") from None
    fields = _identity_fields(payload)
    signed_value = ((fields.get(4, 0) + (1 << 31)) % (1 << 32)) - (1 << 31)
    if (
        fields.get(1) != record.get("uid")
        or fields.get(3) != record.get("reference")
        or fields.get(6) != record.get("caster_id")
        or fields.get(7) != actor.id
        or signed_value != value
    ):
        raise ValueError("Immediate death-script payload identity mismatch")
    if record.get("uid") in getattr(fight, "owned_stat_effects", {}) or record.get(
        "uid"
    ) in getattr(fight, "native_retained_records", {}):
        raise ValueError("Immediate death-script UID is retained")
    body = owned_effect_application(
        fight.id,
        action_id,
        effect_class=1099,
        target_id=actor.id,
        uid=record["uid"],
        running_effect_payload=payload,
    )
    return 12613, evaluated_application_from_observation(body, execute=True)
