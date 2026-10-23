"""Owned account cosmetics and native eST/eSX account component encoding."""
import struct
from dataclasses import dataclass
from wakfu_server.wire import proto_field


# Original fn categories with one selectable item per character preset.
SINGLE_CATEGORIES = frozenset((1, 2, 4, 6, 7, 8, 9, 10, 11, 12, 13, 14))


def _positive(value, label, *, bits=31):
    if type(value) is not int or not 0 < value < 1 << bits:
        raise ValueError(f"Invalid owned cosmetic {label}")
    return value


@dataclass(frozen=True)
class OwnedCosmetics:
    account_id: int
    items: tuple
    selections: tuple = ()
    inactive_characters: tuple = ()
    costumes: tuple = ()
    single_selections: tuple = ()

    def __post_init__(self):
        _positive(self.account_id, "account", bits=63)
        if type(self.items) is not tuple or type(self.selections) is not tuple:
            raise ValueError("Immutable owned cosmetic collections required")
        if any(type(row) is not tuple or len(row) != 4 for row in self.items):
            raise ValueError("Malformed owned cosmetic item")
        if any(
            type(row) is not tuple or len(row) != 2 or type(row[1]) is not tuple
            for row in self.selections
        ):
            raise ValueError("Malformed owned cosmetic selection")
        keys = set()
        for category, reference, color, accessory in self.items:
            if type(category) is not int or not 1 <= category <= 16:
                raise ValueError("Invalid native cosmetic category")
            _positive(reference, "reference")
            if any(
                type(v) is not int or not -(1 << 31) <= v < 1 << 31
                for v in (color, accessory)
            ):
                raise ValueError("Invalid native cosmetic item operands")
            if (category, reference) in keys:
                raise ValueError("Duplicate owned cosmetic")
            keys.add((category, reference))
        owners = set()
        for character_id, references in self.selections:
            _positive(character_id, "character", bits=63)
            for reference in references:
                _positive(reference, "selected reference")
            if character_id in owners or len(set(references)) != len(references):
                raise ValueError("Duplicate cosmetic selection")
            owners.add(character_id)
            if any((5, reference) not in keys for reference in references):
                raise ValueError("Selected finisher is not owned")
        if type(self.inactive_characters) is not tuple or len(
            set(self.inactive_characters)
        ) != len(self.inactive_characters):
            raise ValueError("Malformed inactive cosmetic presets")
        for identity in self.inactive_characters:
            _positive(identity, "inactive character", bits=63)
            if identity not in owners:
                raise ValueError("Inactive cosmetic preset is absent")

        if type(self.costumes) is not tuple:
            raise ValueError("Immutable owned costume selections required")
        costume_owners = set()
        for row in self.costumes:
            if type(row) is not tuple or len(row) != 2:
                raise ValueError("Malformed owned costume selection")
            identity, reference = row
            _positive(reference, "costume reference")
            _positive(identity, "costume character", bits=63)
            if identity in costume_owners or identity not in owners:
                raise ValueError("Duplicate or missing costume preset")
            if (3, reference) not in keys:
                raise ValueError("Selected costume is not owned")
            costume_owners.add(identity)

        if type(self.single_selections) is not tuple:
            raise ValueError("Immutable owned cosmetic selections required")
        single_keys = set()
        for row in self.single_selections:
            if type(row) is not tuple or len(row) != 3:
                raise ValueError("Malformed owned single cosmetic selection")
            identity, category, reference = row
            _positive(identity, "cosmetic character", bits=63)
            _positive(reference, "cosmetic reference")
            if category == 7 and reference > 65535:
                raise ValueError("Native selected title exceeds unsigned short")
            if (
                type(category) is not int
                or category not in SINGLE_CATEGORIES
                or identity not in owners
            ):
                raise ValueError(
                    "Unsupported single cosmetic category or missing preset"
                )
            if (identity, category) in single_keys or (category, reference) not in keys:
                raise ValueError("Duplicate or unowned single cosmetic selection")
            single_keys.add((identity, category))

    def selected_single(self, character_id, category):
        if category == 3:
            return self.selected_costume(character_id)
        if character_id in self.inactive_characters:
            return 0
        return next(
            (
                ref
                for identity, kind, ref in self.single_selections
                if identity == character_id and kind == category
            ),
            0,
        )

    def equip_single(self, character, category, reference):
        if category == 3:
            return self.equip_costume(character, reference)
        if category not in SINGLE_CATEGORIES:
            raise ValueError("Unsupported single cosmetic category")
        record = self.equip_finishers(
            character, dict(self.selections).get(character["id"], ())
        )
        rows = tuple(
            row
            for row in record.single_selections
            if row[:2] != (character["id"], category)
        )
        if reference:
            rows += ((character["id"], category, reference),)
        return OwnedCosmetics(
            record.account_id,
            record.items,
            record.selections,
            record.inactive_characters,
            record.costumes,
            rows,
        )

    def selected_costume(self, character_id):
        return (
            0
            if character_id in self.inactive_characters
            else dict(self.costumes).get(character_id, 0)
        )

    def equip_costume(self, character, reference):
        record = self.equip_finishers(
            character, dict(self.selections).get(character["id"], ())
        )
        values = tuple(row for row in record.costumes if row[0] != character["id"])
        if reference:
            values += ((character["id"], reference),)
        return OwnedCosmetics(
            record.account_id,
            record.items,
            record.selections,
            record.inactive_characters,
            values,
            record.single_selections,
        )

    def equip_finishers(self, character, references):
        if character.get("account_id") != self.account_id:
            raise ValueError("Cosmetic character belongs to another account")
        identity = _positive(character.get("id"), "character", bits=63)
        references = tuple(references)
        selections = tuple(
            (key, references if key == identity else values)
            for key, values in self.selections
        )
        if identity not in dict(selections):
            selections += ((identity, references),)
        return OwnedCosmetics(
            self.account_id,
            self.items,
            selections,
            tuple(key for key in self.inactive_characters if key != identity),
            self.costumes,
            self.single_selections,
        )

    def activate_preset(self, character, active):
        identity = _positive(character.get("id"), "character", bits=63)
        if character.get("account_id") != self.account_id or identity not in dict(
            self.selections
        ):
            raise ValueError("Missing owned character finisher preset")
        inactive = tuple(key for key in self.inactive_characters if key != identity)
        if not active:
            inactive += (identity,)
        return OwnedCosmetics(
            self.account_id,
            self.items,
            self.selections,
            inactive,
            self.costumes,
            self.single_selections,
        )

    def selected_finishers(self, character_id):
        if character_id in self.inactive_characters:
            return ()
        return dict(self.selections).get(character_id, ())

    def to_record(self):
        return {
            "schema_version": 1,
            "account_id": self.account_id,
            "items": [list(row) for row in self.items],
            "selections": [
                [identity, list(values)] for identity, values in self.selections
            ],
            "inactive_characters": list(self.inactive_characters),
            "costumes": [list(row) for row in self.costumes],
            "single_selections": [list(row) for row in self.single_selections],
        }

    @classmethod
    def from_record(cls, record, *, account_id):
        if (
            not isinstance(record, dict)
            or record.get("schema_version") != 1
            or record.get("account_id") != account_id
        ):
            raise ValueError("Invalid owned account cosmetic record")
        if (
            type(record.get("items")) is not list
            or type(record.get("selections")) is not list
        ):
            raise ValueError("Malformed owned cosmetic record collections")
        if any(
            type(row) is not list or len(row) != 4 for row in record["items"]
        ) or any(
            type(row) is not list or len(row) != 2 or type(row[1]) is not list
            for row in record["selections"]
        ):
            raise ValueError("Malformed owned cosmetic record rows")
        inactive = record.get("inactive_characters", [])
        if type(inactive) is not list:
            raise ValueError("Malformed inactive cosmetic presets")
        costumes = record.get("costumes", [])
        if type(costumes) is not list or any(
            type(row) is not list or len(row) != 2 for row in costumes
        ):
            raise ValueError("Malformed owned costume record")
        singles = record.get("single_selections", [])
        if type(singles) is not list or any(
            type(row) is not list or len(row) != 3 for row in singles
        ):
            raise ValueError("Malformed owned single cosmetic record")
        return cls(
            account_id,
            tuple(tuple(row) for row in record["items"]),
            tuple((row[0], tuple(row[1])) for row in record["selections"]),
            tuple(inactive),
            tuple(tuple(row) for row in costumes),
            tuple(tuple(row) for row in singles),
        )

    def inventory_component(self):
        categories = {}
        for category, reference, color, accessory in self.items:
            item = b"".join(
                proto_field(tag, value)
                for tag, value in ((8, reference), (16, color), (24, accessory))
                if tag != 24 or category not in (1, 2) or accessory != 0
            )
            categories.setdefault(category, bytearray()).extend(proto_field(10, item))
        payload = b"".join(
            proto_field(10, proto_field(8, category) + proto_field(18, bytes(items)))
            for category, items in sorted(categories.items())
        )
        return struct.pack(">I", len(payload)) + payload

    def preset_component(self):
        payload = bytearray()
        # Preset IDs are server-owned stable indices; each references only owned items.
        for preset_id, (identity, references) in enumerate(self.selections, 1):
            items = {
                (category, reference): (color, accessory)
                for category, reference, color, accessory in self.items
            }
            active = b""
            for reference in references:
                color, accessory = items[(5, reference)]
                active += proto_field(
                    10,
                    b"".join(
                        proto_field(tag, value)
                        for tag, value in ((8, reference), (16, color), (24, accessory))
                    ),
                )
            positions = proto_field(42, proto_field(8, 5) + proto_field(18, active))
            costume = dict(self.costumes).get(identity)
            if costume is not None:
                color, accessory = items[(3, costume)]
                costume_item = b"".join(
                    proto_field(tag, value)
                    for tag, value in ((8, costume), (16, color), (24, accessory))
                )
                positions += proto_field(
                    42,
                    proto_field(8, 3) + proto_field(18, proto_field(10, costume_item)),
                )
            for owner, category, reference in self.single_selections:
                if owner != identity:
                    continue
                color, accessory = items[(category, reference)]
                cosmetic_item = b"".join(
                    proto_field(tag, value)
                    for tag, value in ((8, reference), (16, color), (24, accessory))
                    if tag != 24 or category not in (1, 2) or accessory != 0
                )
                positions += proto_field(
                    42,
                    proto_field(8, category)
                    + proto_field(18, proto_field(10, cosmetic_item)),
                )
            preset = (
                proto_field(8, preset_id)
                + proto_field(16, 0)
                + proto_field(
                    26,
                    b"Appearance"
                    if any(row[0] != 5 for row in self.items)
                    else b"Finisher",
                )
                + proto_field(32, 0)
                + positions
                + proto_field(48, 0)
            )
            payload.extend(proto_field(10, preset))
            if identity not in self.inactive_characters:
                payload.extend(
                    proto_field(
                        18, proto_field(8, identity) + proto_field(16, preset_id)
                    )
                )
        return struct.pack(">I", len(payload)) + payload


def finisher_request(record, character, opcode, body):
    """Decode native cof/col for existing owned costume and finisher presets."""
    from wakfu_server.wire import proto_fields

    if (
        not isinstance(record, OwnedCosmetics)
        or character.get("account_id") != record.account_id
    ):
        raise ValueError("Missing owned finisher account")
    if not isinstance(body, bytes):
        raise ValueError("Invalid cosmetic request bytes")
    if opcode == 12455:
        if len(body) != 13:
            raise ValueError("Invalid native cof cosmetic request")
        preset, identity, active = struct.unpack(">iqB", body)
        if active not in (0, 1) or identity != character["id"]:
            raise ValueError("Invalid owned cosmetic activation")
        rows = record.selections
        if not 1 <= preset <= len(rows) or rows[preset - 1][0] != identity:
            raise ValueError("Missing owned character finisher preset")
        return record.activate_preset(character, bool(active))
    if opcode == 13765:
        if len(body) < 10:
            raise ValueError("Incomplete native col cosmetic request")
        preset, category, add, present = struct.unpack(">iiBB", body[:10])
        if (
            category not in SINGLE_CATEGORIES | {3, 5}
            or add not in (0, 1)
            or present not in (0, 1)
        ):
            raise ValueError("Unsupported cosmetic preset request")
        if (
            not 1 <= preset <= len(record.selections)
            or record.selections[preset - 1][0] != character["id"]
        ):
            raise ValueError("Missing owned character finisher preset")
        selected = dict(record.selections)[character["id"]]
        if not present:
            if add or len(body) != 10:
                raise ValueError("Invalid native empty cosmetic request")
            return (
                record.equip_single(character, category, 0)
                if category != 5
                else record.equip_finishers(character, ())
            )
        fields = list(proto_fields(body[10:]))
        item = dict(fields)
        if (
            len(fields) != len(item)
            or 8 not in item
            or not set(item) <= {8, 16, 24}
            or any(type(value) is not int for value in item.values())
        ):
            raise ValueError("Invalid native finisher item")
        signed = lambda value: (value + (1 << 31)) % (1 << 32) - (1 << 31)
        row = (
            category,
            signed(item[8]),
            signed(item.get(16, 0)),
            signed(item.get(24, 0)),
        )
        if row not in record.items:
            raise ValueError("Finisher item is not owned with these operands")
        reference = row[1]
        if category != 5:
            current = record.selected_single(character["id"], category)
            if add:
                return record.equip_single(character, category, reference)
            if current != reference:
                raise ValueError("Cannot remove an unselected costume")
            return record.equip_single(character, category, 0)
        if add and reference in selected or not add and reference not in selected:
            raise ValueError("Invalid duplicate or absent finisher selection")
        values = (
            selected + (reference,)
            if add
            else tuple(value for value in selected if value != reference)
        )
        return record.equip_finishers(character, values)
    raise ValueError("Unsupported owned finisher opcode")


def actor_component(character):
    """Native pq.Tb/tF/tG selected costume and finishers from owned character data."""
    record = character.get("owned_cosmetics")
    if record is None:
        return b"\x00"
    owned = OwnedCosmetics.from_record(record, account_id=character.get("account_id"))
    references = owned.selected_finishers(character["id"])
    if len(references) > 32767:
        raise ValueError("Native finisher selection count exceeds signed short")
    title = owned.selected_single(character["id"], 7)
    if type(title) is not int:
        raise ValueError("Missing owned current title")
    if not 0 <= title <= 65535:
        raise ValueError("Native selected title exceeds unsigned short")
    return (
        b"\x01"
        + struct.pack(
            ">iBiiHH",
            owned.selected_costume(character["id"]),
            1,
            owned.selected_single(character["id"], 4),
            owned.selected_single(character["id"], 6),
            title,
            len(references),
        )
        + b"".join(struct.pack(">i", value) for value in references)
    )


def actor_update(character):
    """Native eHf.FOR_COSMETICS_UPDATE (30), delivered through csZ13046."""
    from wakfu_server.combat.combat_world_refresh import actor_refresh

    identity = _positive(character.get("id"), "character", bits=63)
    return actor_refresh(
        identity, b"\x1e" + struct.pack(">q", identity) + actor_component(character)
    )
