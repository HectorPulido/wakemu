"""Native introductory cinematic messages and callback sequence.

Only the flow observed in the official 2698 scene is represented here. The
caller owns the private scene, actor publication and durable map transition.
"""
import struct
from dataclasses import dataclass

SCENARIO_ID = 2698
SCENARIO_EVENT_OPCODE = 13411
SCENARIO_CALLBACK_OPCODE = 12921
INTRO_WORLD_ID = 1465
INCARNAM_WORLD_ID = 1361


def private_instance_id(character_id):
    """Stable private onboarding scope for this character on both intro maps."""
    if type(character_id) is not int or not 0 < character_id < 2**48:
        raise ValueError("Invalid introductory scene owner")
    return (1 << 62) + character_id


def assign_new_character(db, account_id, character_id, *, tutorial):
    """Set a just-created character's location from the client's tutorial choice.

    This runs inside the creation transaction. Existing rows are never migrated;
    the caller must pass the ID just returned by INSERT.
    """
    if tutorial is None:
        return
    if type(tutorial) is not bool:
        raise ValueError("Introductory choice must be boolean")
    if type(account_id) is not int or account_id <= 0:
        raise ValueError("Invalid introductory scene account")
    map_id, instance_id, x, y, z = (
        (INTRO_WORLD_ID, private_instance_id(character_id), 0, 0, 40)
        if tutorial
        else (1385, 0, 27, 1, 1)
    )
    result = db.execute(
        "UPDATE characters SET map_id=%s,instance_id=%s,x=%s,y=%s,z=%s "
        "WHERE id=%s AND account_id=%s AND deleted_at IS NULL",
        (map_id, instance_id, x, y, z, character_id, account_id),
    )
    if result.rowcount != 1:
        raise ValueError("New introductory character was not found")


def ogrest_actor(character_id):
    """Publish the scene's private native Ogrest with an owned runtime ID.

    The breed, position, direction, level and property 7 are from the official
    opening scene. IDs are derived from the selected character, not replayed
    from the captured session.
    """
    if type(character_id) is not int or not 0 < character_id < 2**48:
        raise ValueError("Invalid introductory scene owner")
    actor_id = -(3 * 2**49 + character_id)
    group_id = 3 * 2**49 + character_id
    actor = b"\x0b" + struct.pack(">qBqHh", actor_id, 1, -1, 0, 5814)
    actor += struct.pack(">iihqBB", 0, -6, 40, INTRO_WORLD_ID, 3, 0)
    actor += b"\x01" + struct.pack(">hH", 245, 0)
    actor += b"\x00" + struct.pack(">iBBBBbB", -1, 0, 0, 0, 0, -1, 0)
    actor += b"\x01" + struct.pack(">HBB", 1, 7, 1)
    actor += struct.pack(">qHhh", group_id, 1, 5814, 245)
    actor += struct.pack(">hhH", -1, -1, 0) + bytes(21)
    packet = b"\x00\x01" + struct.pack(">BqH", 1, actor_id, len(actor)) + actor
    return actor_id, (12608, packet)


def scenario_event(event_id, scenario_id, *arguments):
    """Encode a native scenario event; arguments are signed 64-bit values."""
    if len(arguments) > 255:
        raise ValueError("Too many scenario event arguments")
    try:
        return SCENARIO_EVENT_OPCODE, (
            struct.pack(">BiiB", 0, event_id, scenario_id, len(arguments))
            + b"".join(struct.pack(">q", value) for value in arguments)
        )
    except (struct.error, TypeError) as error:
        raise ValueError("Invalid scenario event") from error


def callback_id(body):
    if len(body) != 4:
        raise ValueError("Invalid scenario callback")
    return struct.unpack(">i", body)[0]


@dataclass
class IntroCinematic:
    """Per-session progression; only the expected callback can advance it."""

    ogrest_id: int
    expected: int = 23908
    done: bool = False

    def start(self):
        return scenario_event(23908, SCENARIO_ID)

    def retry_completion(self):
        """Re-arm the final callback after a failed transactional transition.

        A disconnected client gets a fresh scene on the next map bootstrap.
        Repeated callbacks within the same scene are ignored by ``receive``;
        only a failed final transition may explicitly be re-armed.
        """
        if not self.done or self.expected != 23912:
            raise ValueError("Introductory scene is not awaiting transition recovery")
        self.done = False

    def receive(self, body, *, map_id):
        event = callback_id(body)
        if self.done or map_id != INTRO_WORLD_ID or event != self.expected:
            return None
        if event == 23908:
            self.expected = 23909
            return scenario_event(23909, SCENARIO_ID)
        if event == 23909:
            self.expected = 23910
            return scenario_event(23910, SCENARIO_ID, self.ogrest_id)
        if event == 23910:
            self.expected = 23912
            return scenario_event(23912, SCENARIO_ID)
        if event == 23912:
            self.done = True
            return ("enter_incarnam", INCARNAM_WORLD_ID)
        return None
