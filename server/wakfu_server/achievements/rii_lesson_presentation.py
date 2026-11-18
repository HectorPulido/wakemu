"""Native Airyna lesson presentations observed in the official session."""

import struct

from wakfu_server.dungeon_main_completion import presentation_packet

# contract, objective, fight start event, successful objective event
LESSONS = (
    ("rii_orientation_contract", 10574, 22409, 22540),
    ("rii_element_lesson_contract", 10575, 22494, 22541),
    ("rii_distance_lesson_contract", 10576, 22495, 22542),
    ("rii_los_lesson_contract", 10608, 22507, 22543),
    ("rii_area_lesson_contract", 10609, 22508, 22544),
    ("rii_movement_lesson_contract", 10610, 22516, 22545),
    ("rii_states_lesson_contract", 10611, 22517, 22546),
)
# Exact displayGuide operands from installed scenario/2543.lua.
GUIDES = dict(zip((entry[2] for entry in LESSONS), range(115, 122)))


def _lesson(fight):
    active = [entry for entry in LESSONS if getattr(fight, entry[0], None)]
    if len(active) > 1:
        raise ValueError("A fight cannot present multiple Rii lessons")
    return active[0] if active else None


def _packet(event):
    return presentation_packet(
        {"scenario_id": 2543, "event_id": event, "parameters": []}
    )


def begin(node_id, choice_id):
    """Show the lesson guide at the captured Airyna dialogue choice."""
    choices = {
        (5756, 13260): 0,
        (5787, 13322): 0,
        **{(5787, 13323 + i): i + 1 for i in range(6)},
    }
    index = choices.get((node_id, choice_id))
    return _packet(LESSONS[index][2]) if index is not None else None


def admission(fight, character_id, node_id, choice_id):
    """Validate the guide against the encounter actually admitted for its owner."""
    lesson = _lesson(fight)
    packet = begin(node_id, choice_id)
    if (
        lesson is None
        or getattr(fight, lesson[0]).get("owner") != character_id
        or packet != _packet(lesson[2])
    ):
        raise ValueError("Lesson guide does not match its admitted owner and exercise")
    return packet


def claim_admission(db, fight, character_id, node_id, choice_id):
    """Claim the presentation only after its owned placement is published.

    The native guide ID is permanent per character, including older event
    receipts. A delivery revision must never reopen an already shown guide.
    """
    from . import tutorial_presentation_once

    packet = admission(fight, character_id, node_id, choice_id)
    event_id = _lesson(fight)[2]
    return (
        [packet]
        if tutorial_presentation_once.claim_guide(
            db,
            character_id,
            GUIDES[event_id],
            legacy=(
                {
                    "prefix": f"tutorial-presentation:2543:{event_id}:",
                    "payload": {
                        "kind": "tutorial_presentation",
                        "scenario_id": 2543,
                        "event_id": event_id,
                    },
                },
            ),
        )
        else []
    )


def finish(fight, packets):
    """Present success only when this settlement published its objective."""
    lesson = _lesson(fight)
    if lesson is None:
        return None
    for opcode, payload in packets:
        if (
            opcode == 13832
            and len(payload) == 12
            and struct.unpack(">qi", payload)[1] == lesson[1]
        ):
            return _packet(lesson[3])
    return None
