"""Persistent, per-character deduplication of one-shot tutorial presentations."""
import struct

from . import storage


def claim(db, character_id, scenario_id, event_id, variant=0):
    """Reserve a single presentation without suppressing gameplay events."""
    if any(
        type(value) is not int
        for value in (character_id, scenario_id, event_id, variant)
    ):
        raise ValueError("Invalid tutorial presentation identity")
    if character_id <= 0 or scenario_id <= 0 or event_id <= 0:
        raise ValueError("Invalid tutorial presentation identity")
    payload = {
        "kind": "tutorial_presentation",
        "scenario_id": scenario_id,
        "event_id": event_id,
        "variant": variant,
    }
    return storage.record_event(
        db,
        character_id,
        f"tutorial-presentation:{scenario_id}:{event_id}:{variant}",
        payload,
    )


def filter_packets(db, character_id, packets):
    """Deduplicate scenario presentations by event and optional first argument."""
    result = []
    for opcode, payload in packets:
        if opcode != 13411 or len(payload) < 10:
            raise ValueError("Invalid tutorial presentation packet")
        mode, event_id, scenario_id, count = struct.unpack(">BiiB", payload[:10])
        if mode != 0 or len(payload) != 10 + count * 8:
            raise ValueError("Invalid tutorial presentation packet")
        # Fight IDs are dynamic, while 22529's argument denotes the tutorial step.
        variant = (
            struct.unpack(">q", payload[10:18])[0] if event_id == 22529 and count else 0
        )
        if claim(db, character_id, scenario_id, event_id, variant):
            result.append((opcode, payload))
    return result
