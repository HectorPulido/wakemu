"""Owned Osamodas roster data; native yS/yT/tr codec, independent of combat control.

No profile factory, capture eligibility, ability catalog, or database is inferred.
Native eHX.b resolves profile identities before installing descriptors in ten slots.
"""
from dataclasses import dataclass
import struct


SLOT_COUNT = 10
SCHEMA = "wakemu-captured-roster-v1"


def _integer(value, minimum, maximum, field):
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValueError("Invalid captured roster " + field)
    return value


@dataclass(frozen=True)
class CapturedCreature:
    slot: int
    profile_id: int
    name: str
    native_quantity: int = 1

    def __post_init__(self):
        _integer(self.slot, -128, 127, "slot byte")
        _integer(self.profile_id, -32768, 32767, "profile short")
        _integer(self.native_quantity, -32768, 32767, "quantity short")
        if not isinstance(self.name, str):
            raise ValueError("Invalid captured creature name")
        if len(self.name.encode("utf-8")) > 65535:
            raise ValueError("Captured creature name exceeds native UTF-8 length")


@dataclass(frozen=True)
class NativeCapturedRoster:
    entries: tuple[CapturedCreature, ...] = ()
    selected_slot: int = 0

    def __post_init__(self):
        _integer(self.selected_slot, -128, 127, "selected byte")
        if type(self.entries) is not tuple or len(self.entries) > 255:
            raise ValueError("Invalid native captured entry count")
        if any(not isinstance(entry, CapturedCreature) for entry in self.entries):
            raise ValueError("Invalid native captured entry")

    def encode(self):
        parts = [struct.pack(">B", len(self.entries))]
        for entry in self.entries:
            name = entry.name.encode("utf-8")
            parts += [
                struct.pack(
                    ">bhhH",
                    entry.slot,
                    entry.profile_id,
                    entry.native_quantity,
                    len(name),
                ),
                name,
            ]
        parts.append(struct.pack(">b", self.selected_slot))
        return b"".join(parts)

    @classmethod
    def decode(cls, body):
        if not isinstance(body, bytes) or not body:
            raise ValueError("Missing captured roster bytes")
        count = body[0]
        offset = 1
        entries = []
        try:
            for _ in range(count):
                slot, profile, quantity, length = struct.unpack_from(
                    ">bhhH", body, offset
                )
                offset += 7
                if offset + length > len(body):
                    raise ValueError("Truncated captured creature name")
                # java String(byte[], UTF_8) replaces malformed sequences.
                name = body[offset : offset + length].decode("utf-8", errors="replace")
                offset += length
                entries.append(CapturedCreature(slot, profile, name, quantity))
            selected = struct.unpack_from(">b", body, offset)[0]
        except struct.error as error:
            raise ValueError("Truncated captured roster") from error
        if offset + 1 != len(body):
            raise ValueError("Trailing captured roster bytes")
        return cls(tuple(entries), selected)


@dataclass(frozen=True)
class OwnedCapturedRoster:
    owner_id: int
    slots: tuple[CapturedCreature | None, ...] = (None,) * SLOT_COUNT
    available: tuple[bool, ...] = (False,) * SLOT_COUNT
    selected_slot: int = 0

    def __post_init__(self):
        _integer(self.owner_id, -(1 << 63), (1 << 63) - 1, "owner long")
        _integer(self.selected_slot, -128, 127, "selected byte")
        if type(self.slots) is not tuple or len(self.slots) != SLOT_COUNT:
            raise ValueError("Owned captured roster requires ten slots")
        if type(self.available) is not tuple or len(self.available) != SLOT_COUNT:
            raise ValueError("Owned captured roster requires ten availability flags")
        for index, (entry, available) in enumerate(zip(self.slots, self.available)):
            if type(available) is not bool:
                raise ValueError("Invalid captured availability flag")
            if entry is not None and (
                not isinstance(entry, CapturedCreature) or entry.slot != index
            ):
                raise ValueError("Captured slot identity mismatch")

    @classmethod
    def import_native(cls, owner_id, source, profile_resolver):
        """Clear and resolve only owned profile seeds, as eHX.b does.

        The resolver must supply actual descriptor authority, not capture eligibility.
        It is never called for profiles inferred from arbitrary monster catalogs.
        """
        if not isinstance(source, NativeCapturedRoster) or not callable(
            profile_resolver
        ):
            raise ValueError("Native roster and explicit profile resolver required")
        slots, available = [None] * SLOT_COUNT, [False] * SLOT_COUNT
        for entry in source.entries:
            if profile_resolver(entry.profile_id) is None:
                continue
            if 0 <= entry.slot < SLOT_COUNT:
                slots[entry.slot] = CapturedCreature(
                    entry.slot, entry.profile_id, entry.name
                )
                available[entry.slot] = True
        return cls(owner_id, tuple(slots), tuple(available), source.selected_slot)

    @property
    def free_slots(self):
        return sum(entry is None for entry in self.slots)

    @property
    def selected_creature(self):
        if 0 <= self.selected_slot < SLOT_COUNT:
            return self.slots[self.selected_slot]
        return None

    def to_native(self):
        # eHX.a serializes occupied slots regardless of availability, quantity1.
        return NativeCapturedRoster(
            tuple(
                CapturedCreature(entry.slot, entry.profile_id, entry.name)
                for entry in self.slots
                if entry is not None
            ),
            self.selected_slot,
        )

    def to_record(self):
        return {
            "schema": SCHEMA,
            "owner_id": self.owner_id,
            "selected_slot": self.selected_slot,
            "available": list(self.available),
            "slots": [
                None
                if entry is None
                else {
                    "slot": entry.slot,
                    "profile_id": entry.profile_id,
                    "name": entry.name,
                }
                for entry in self.slots
            ],
        }

    @classmethod
    def from_record(cls, record, *, expected_owner_id):
        if not isinstance(record, dict) or set(record) != {
            "schema",
            "owner_id",
            "selected_slot",
            "available",
            "slots",
        }:
            raise ValueError("Invalid captured roster record fields")
        if record["schema"] != SCHEMA or record["owner_id"] != expected_owner_id:
            raise ValueError("Captured roster schema or owner mismatch")
        if type(record["slots"]) is not list or type(record["available"]) is not list:
            raise ValueError("Invalid captured roster record arrays")
        slots = []
        for entry in record["slots"]:
            if entry is None:
                slots.append(None)
            elif isinstance(entry, dict) and set(entry) == {
                "slot",
                "profile_id",
                "name",
            }:
                slots.append(CapturedCreature(**entry))
            else:
                raise ValueError("Invalid captured creature record")
        return cls(
            record["owner_id"],
            tuple(slots),
            tuple(record["available"]),
            record["selected_slot"],
        )


def roster_from_character(character):
    """Resolve only the hydrated owned component; non-Osa has no component."""
    if character.get("breed") != 2:
        return None
    if "captured_roster" not in character:
        raise ValueError("Owned Osamodas captured roster has not been hydrated")
    record = character["captured_roster"]
    if record is None:
        return None  # Unavailable persistence producer, not an empty roster.
    return OwnedCapturedRoster.from_record(record, expected_owner_id=character["id"])


def breed_specific_section(character):
    """Native pd optional presence byte -> pg.SK/yS for eHe.BREED_SPECIFIC."""
    roster = roster_from_character(character)
    return b"\x00" if roster is None else b"\x01" + roster.to_native().encode()


def selected_availability_status(roster):
    """Original eON: no selected descriptor=-1, available=0, unavailable=-2."""
    if not isinstance(roster, OwnedCapturedRoster):
        raise ValueError("Native eHP owned Symbiot component required")
    if roster.selected_creature is None:
        return -1
    return 0 if roster.available[roster.selected_slot] else -2


def captured_profile_seeds(roster):
    """Only actual occupied owned slots seed dynamic ability compilation."""
    if not isinstance(roster, OwnedCapturedRoster):
        raise ValueError("Owned captured roster required")
    return tuple(
        sorted({entry.profile_id for entry in roster.slots if entry is not None})
    )
