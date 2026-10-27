"""Explicit fixture adapter. The complete entity serializer is still pending."""
from wakfu_server import native_catalog as protocol_catalog
from .paths import DATA_ROOT
import struct
import json
import hashlib
from pathlib import Path
from protocol_codec import Reader, APPEARANCE_FIELDS
from wakfu_server.spells import spell_inventory, default_deck
from wakfu_server.progression import level_xp, character_xp

TEMPLATE_ACCOUNT = 83668792
TEMPLATE_CHARACTER = 2409354
TEMPLATE_NAME = "Pekebu"
SYNTHETIC_BOOTSTRAP = False
INITIAL_POSITION = struct.pack(">iih", -12, -8, -1)
PROTOCOL = DATA_ROOT
ENTITY_LAYOUTS = {
    record["format"]: record
    for record in protocol_catalog.load(PROTOCOL / "entity-layouts.json")
}
ENTITY_DEFAULTS = {
    name: bytes.fromhex(value)
    for name, value in protocol_catalog.load(PROTOCOL / "entity-defaults.json").items()
}
EMPTY_SECTIONS = {
    "HP",
    "PHOENIX_PART",
    "ACCOUNT_INFORMATION",
    "GUILD_ID",
    "GUILD_BLAZON",
    "SOCIAL_STATES",
    "NATION_ID",
    "CHARACTER_LIST_NATION_ID",
    "NATION_SYNCHRO",
    "SHORTCUT_INVENTORIES",
    "INVENTORIES",
    "BAGS",
    "PROTO_TEMPORARY_INVENTORY",
    "CHALLENGES",
    "XP",
    "XP_CHARACTERISTICS",
    "CITIZEN_POINT",
    "PASSEPORT_INFO",
    "PET",
    "ACHIEVEMENTS",
    "PERSONAL_EFFECTS",
    "RUNNING_EFFECTS",
    "SPELL_DECK",
    "DUNGEON_PROGRESSION",
    "EQUIPMENT_APPEARANCE",
    "COSMETICS",
}


def register_synthetic_bootstrap(metadata):
    """Install explicitly generated fixture layouts, independently of legacy captures.

    This changes template identities only. Every section must retain the native
    format's section names/classes; the generated body has its own SHA authority.
    """
    global TEMPLATE_ACCOUNT, TEMPLATE_CHARACTER, TEMPLATE_NAME, SYNTHETIC_BOOTSTRAP
    if (
        not isinstance(metadata, dict)
        or metadata.get("policy") != "wakemu-synthetic-bootstrap-v1"
    ):
        raise ValueError("Unknown synthetic bootstrap authority")
    account, character = metadata.get("account_id"), metadata.get("character_id")
    name = metadata.get("name")
    if (
        type(account) is not int
        or type(character) is not int
        or not 0 < account < 2**63
        or not 0 < character < 2**63
        or account == character
        or not isinstance(name, str)
        or not name
        or len(name.encode("utf-8")) > 255
    ):
        raise ValueError("Invalid synthetic bootstrap identity")
    layouts = metadata.get("layouts")
    if not isinstance(layouts, list):
        raise ValueError("Missing synthetic entity layouts")
    checked = {}
    for layout in layouts:
        if not isinstance(layout, dict) or type(layout.get("format")) is not int:
            raise ValueError("Invalid synthetic entity format")
        kind = layout["format"]
        if kind not in (4, 5, 10, 11, 22, 28) or kind in checked:
            raise ValueError("Unexpected synthetic entity format")
        sections = layout.get("sections")
        if not isinstance(sections, list) or not sections:
            raise ValueError("Missing synthetic entity sections")
        original = ENTITY_LAYOUTS.get(kind)
        signature = [(row.get("name"), row.get("class")) for row in sections]
        if original is not None and signature != [
            (row["name"], row["class"]) for row in original["sections"]
        ]:
            raise ValueError("Synthetic sections differ from native format")
        if original is None and (
            kind != 22
            or [row[0] for row in signature]
            != ["NATION_ID", "NATION_SYNCHRO", "GUILD_LOCAL_INFO", "NATION_PVP_MONEY"]
        ):
            raise ValueError("Unverified synthetic entity sections")
        offset = 1
        for section in sections:
            if (
                type(section.get("start")) is not int
                or type(section.get("end")) is not int
                or section["start"] != offset
                or section["end"] < offset
            ):
                raise ValueError("Noncontiguous synthetic entity layout")
            offset = section["end"]
        digest = layout.get("template_sha256")
        if (
            layout.get("bytes") != offset
            or layout.get("fully_consumed") is not True
            or not isinstance(digest, str)
            or len(digest) != 64
            or any(c not in "0123456789abcdef" for c in digest)
        ):
            raise ValueError("Invalid synthetic entity body authority")
        checked[kind] = json.loads(json.dumps(layout))
    if set(checked) != {4, 5, 10, 11, 22, 28}:
        raise ValueError("Incomplete synthetic entity format set")
    ENTITY_LAYOUTS.update(checked)
    TEMPLATE_ACCOUNT, TEMPLATE_CHARACTER, TEMPLATE_NAME = account, character, name
    SYNTHETIC_BOOTSTRAP = True


def minimal_entity(body, character):
    """Replace verified fixture sections with the client's own empty encoding."""
    if character.get("level") is None:
        return body
    if body and body[0] == 22:
        # Native FOR_GLOBAL_TO_LOCAL_CHARACTER: NATION_ID (i32),
        # NATION_SYNCHRO (27 bytes), GUILD_LOCAL_INFO, NATION_PVP_MONEY.
        # This later snapshot otherwise restores the fixture's nation after
        # the primary owned entity has already established neutral identity.
        from wakfu_server.characters.guild_wire import replace_local_entity

        body = replace_local_entity(
            body,
            character.get("guild_native"),
            character.get("guild_moderation_factor", 0.0),
        )
        from wakfu_server.characters.nation_state import nation_id, synchro

        return (
            body[:1]
            + struct.pack(">i", nation_id(character))
            + synchro(character)
            + body[32:]
        )
    level_xp(character["level"])
    layout = ENTITY_LAYOUTS.get(body[0])
    if layout is None or not any(
        s["name"] in EMPTY_SECTIONS for s in layout["sections"]
    ):
        return body
    if hashlib.sha256(body).hexdigest() != layout["template_sha256"]:
        raise ValueError("Entity fixture does not match verified section boundaries")
    for section in reversed(layout["sections"]):
        replacement = None
        if section["name"] == "CREATION_DATA" and character.get("recustomization"):
            from wakfu_server.character_recustomization import creation_section

            replacement = creation_section(character)
        elif (
            section["name"] in ("GUILD_ID", "GUILD_BLAZON")
            and "guild_native" in character
        ):
            guild = character["guild_native"]
            key = "guildId" if section["name"] == "GUILD_ID" else "blazon"
            replacement = struct.pack(">q", guild[key] if guild else 0)
        elif section["name"] == "GUILD_REMOTE_INFO" and "guild_native" in character:
            from wakfu_server.characters.guild_wire import remote_info

            guild = character["guild_native"]
            replacement = (
                remote_info(
                    guild["guildId"], guild["blazon"], guild["level"], guild["name"]
                )
                if guild
                else remote_info(0, 0, 0, "")
            )
        elif section["name"] == "GUILD_NAME" and "guild_native" in character:
            guild = character["guild_native"]
            name = guild["name"].encode("utf-8") if guild else b""
            if len(name) > 255:
                raise ValueError("Guild name exceeds native qn byte length")
            replacement = bytes((len(name),)) + name
        elif section["name"] == "APPEARANCE" and character.get("appearance"):
            replacement = appearance_section(character["appearance"])
        elif section["name"] == "EQUIPMENT_APPEARANCE":
            from wakfu_server.items.equipment_appearance import (
                section as equipment_section,
            )

            replacement = equipment_section(character)
        elif section["name"] in ("NATION_ID", "CHARACTER_LIST_NATION_ID"):
            from wakfu_server.characters.nation_state import nation_id

            replacement = struct.pack(">i", nation_id(character))
        elif section["name"] == "PHOENIX_PART":
            from wakfu_server.phoenix_points import section as phoenix_section

            replacement = phoenix_section(character)
        elif section["name"] == "NATION_SYNCHRO":
            from wakfu_server.characters.nation_state import synchro

            replacement = synchro(character)
        elif section["name"] == "CITIZEN_POINT":
            from wakfu_server.national_progression import citizen_section

            replacement = citizen_section(character)
            if replacement is None:
                replacement = ENTITY_DEFAULTS[section["name"]]
        elif (
            section["name"] == "WORLD_PROPERTIES"
            and character.get("exploration_secrets") is not None
        ):
            from wakfu_server.characters.exploration_secrets import world_properties

            replacement = world_properties(character)
        elif section["name"] == "COSMETICS":
            from wakfu_server.characters.cosmetics import actor_component

            replacement = actor_component(character)
        elif (
            section["name"] == "ACHIEVEMENTS"
            and character.get("achievement_section") is not None
        ):
            replacement = character["achievement_section"]
            if not isinstance(replacement, bytes):
                raise ValueError("Invalid owned achievement section")
        elif section["name"] == "ACCOUNT_INFORMATION":
            from wakfu_server.maps.admin_chat_rights import project_account_information

            replacement = project_account_information(
                body[section["start"] : section["end"]],
                is_admin=character.get("account_is_admin", False),
            )
        elif section["name"] == "BREED_SPECIFIC":
            from wakfu_server.characters.captured_roster import breed_specific_section

            replacement = breed_specific_section(character)
        elif section["name"] == "BREED":
            replacement = struct.pack(">h", character["breed"])
        elif section["name"] == "DIMENSIONAL_BAG_FOR_LOCAL_CLIENT":
            from wakfu_server.haven_bag import own_bag

            replacement = own_bag(character)
        elif section["name"] == "INVENTORIES":
            from wakfu_server.items.quest_inventory import section as quest_section

            replacement = quest_section(character)
        elif section["name"] == "BAGS":
            from wakfu_server.inventory import bags

            replacement = bags(character)
        elif section["name"] == "PUBLIC_CHARACTERISTICS":
            replacement = owned_public_characteristics(character)
        elif section["name"] == "HP":
            from wakfu_server.equipment_stats import effective_character

            replacement = struct.pack(
                ">i",
                effective_character(character, include_consumable_buffs=True)["hp"],
            )
        elif section["name"] == "PET":
            from .mount_inventory import actor_pet

            replacement = actor_pet(character)
        elif section["name"] == "SPELL_INVENTORY":
            replacement = spell_inventory(character)
        elif section["name"] == "SPELL_DECK" and character.get("builds"):
            from wakfu_server.builds import deck_collection

            replacement = deck_collection(character)
        elif section["name"] == "SPELL_DECK":
            deck = struct.pack(">iB", 1, 0) + default_deck(character)
            replacement = struct.pack(">H", len(deck)) + deck
        elif section["name"] == "XP":
            replacement = struct.pack(">q", character_xp(character))
        elif section["name"] == "XP_CHARACTERISTICS":
            from .ecology_progression import native_score

            replacement = struct.pack(
                ">i", native_score(character.get("ecology_value", 0))
            )
        elif section["name"] == "SHORTCUT_INVENTORIES":
            from wakfu_server.world_shortcuts import owned_collection

            replacement = owned_collection(character)
        elif section["name"] == "PROTO_TEMPORARY_INVENTORY":
            replacement = character.get("temporary_inventory_section", b"\x00\x00")
            if not isinstance(replacement, bytes) or len(replacement) < 2:
                raise ValueError("Invalid owned temporary inventory section")
            size = struct.unpack_from(">h", replacement)[0]
            if size < 0 or size != len(replacement) - 2:
                raise ValueError("Invalid owned temporary inventory section length")
        elif section["name"] in EMPTY_SECTIONS:
            replacement = ENTITY_DEFAULTS[section["name"]]
        if replacement is not None:
            body = body[: section["start"]] + replacement + body[section["end"] :]
    return body


def owned_public_characteristics(character):
    """Use the existing authoritative PC codec for a world actor refresh.

    A full PET/entity refresh must not restore the captured template's public
    characteristics over the owned actor's effective equipment and aptitudes.
    """
    from wakfu_server.combat_actor import actor_stats
    from wakfu_server.equipment_stats import effective_character, combat_resources

    owned = effective_character(character, include_consumable_buffs=True)
    resources = combat_resources(owned, include_consumable_buffs=True)
    blob = actor_stats(
        owned,
        1,
        wp=resources["wp"],
        ap=resources["ap"],
        mp=resources["mp"],
        initiative=resources["initiative"],
        include_consumable_buffs=True,
    )
    offset = 1 + 8 + struct.calcsize(">iihqBB") + struct.calcsize(">iBBBBbB")
    count = struct.unpack_from(">H", blob, offset)[0]
    end = offset + 2 + count * struct.calcsize(">Biiii")
    return complete_public_characteristics(blob[offset:end])


def complete_public_characteristics(payload):
    """Complete a sparse owned PC contribution snapshot with native defaults.

    Resource/current rows already carry authoritative absolute values. Other
    supplied rows are equipment/aptitude contributions to native baselines.
    Missing rows must be explicit so the original partial native consumer clears
    a contribution removed by a build change or outside-combat refresh.
    """
    if type(payload) is not bytes or len(payload) < 2:
        raise ValueError("Invalid owned public characteristics payload")
    count = struct.unpack_from(">H", payload)[0]
    row_size = struct.calcsize(">Biiii")
    if len(payload) != 2 + count * row_size:
        raise ValueError("Invalid owned public characteristics length")
    from wakfu_server.combat_actor_snapshot import (
        native_actor_catalog,
        native_characteristic_definitions,
    )
    from wakfu_server.combat_published_catalogs import static_catalog_descriptor

    # A refresh can target an actor that previously received a richer capture
    # or another equipment sheet. Send native defaults explicitly so omitted
    # damage/resistance rows cannot survive from that older snapshot.
    catalog = native_actor_catalog()
    native_rows = catalog["characteristics"]
    if (
        static_catalog_descriptor(native_rows) is not None
        and native_rows.representation == "native_json"
    ):
        # Reuse the same bounded immutable index as combat snapshots. Keep
        # caller-owned legacy dictionaries on the original validation path.
        native_rows = {
            str(identity): row
            for identity, row in native_characteristic_definitions(catalog).items()
        }
    rows = {
        int(identity): (
            int(identity),
            row["current"],
            row["minimum"],
            row["maximum"],
            0,
        )
        for identity, row in native_rows.items()
    }
    seen = set()
    for index in range(count):
        row = struct.unpack_from(">Biiii", payload, 2 + index * row_size)
        if str(row[0]) not in native_rows or row[0] in seen:
            raise ValueError("Unknown or duplicate owned public characteristic")
        seen.add(row[0])
        if row[0] not in (1, 2, 3, 4, 35):
            # actor_stats serializes non-resource equipment contributions.
            # Apply them to ffh defaults with the same bounds as fresh combat
            # snapshots, rather than replacing a nonzero native baseline.
            native = native_rows[str(row[0])]
            delta = row[1]
            maximum = native["maximum"]
            if native["expandable"]:
                maximum = min(
                    native["hard_maximum"],
                    max(
                        native["hard_minimum"],
                        ((maximum + delta + (1 << 31)) % (1 << 32)) - (1 << 31),
                    ),
                )
            current = min(
                maximum,
                max(
                    native["minimum"],
                    ((native["current"] + delta + (1 << 31)) % (1 << 32)) - (1 << 31),
                ),
            )
            row = (row[0], current, native["minimum"], maximum, 0)
        rows[row[0]] = row
    from wakfu_server.combat_characteristic_order import health_dependency_order

    return health_dependency_order(
        struct.pack(">H", len(rows))
        + b"".join(struct.pack(">Biiii", *row) for _, row in sorted(rows.items()))
    )


def appearance_section(appearance):
    """oW: u16 length + dS ProtoAppearance, with signed int32 varints."""
    if any(
        key not in APPEARANCE_FIELDS
        or type(value) is not int
        or not -(1 << 31) <= value < (1 << 31)
        for key, value in appearance.items()
    ):
        raise ValueError("Invalid appearance fields")
    appearance = {
        **{
            key: -1 if number < 9 else 0
            for number, key in enumerate(APPEARANCE_FIELDS[:12])
        },
        **appearance,
    }
    encoded = b"".join(
        varint(number << 3) + varint(value if value >= 0 else value + (1 << 64))
        for number, key in enumerate(APPEARANCE_FIELDS, 1)
        if (value := appearance.get(key)) is not None
    )
    return struct.pack(">H", len(encoded)) + encoded


def initial_progression(body, character):
    """Set owned character XP in the two verified eHf entity formats.

    Offsets apply before the variable-length name is rewritten. eHk's section
    readers consumed both original blobs completely; sG reads one i64 XP.
    Equipment and aptitudes still require separate initialization.
    """
    offsets = {5: 262, 10: 4614}
    offset = offsets.get(body[0])
    if offset is None or character.get("level") is None:
        return body
    if struct.unpack_from(">q", body, offset)[0] != 4094076145:
        raise ValueError("Unexpected fixture XP layout")
    return (
        body[:offset] + struct.pack(">q", character_xp(character)) + body[offset + 8 :]
    )


def character_levels(body, character):
    """13873 CHARACTERS section: count, kind=0, count, (i64, i16)."""
    r = Reader(body)
    sections, kind = r.number("I"), r.number("I")
    if kind != 0:
        return identity(body, character["account_id"], character)
    r.take(r.number("I") * 10)
    return struct.pack(
        ">IIIqH", sections, kind, 1, character["id"], character["level"]
    ) + identity(body[r.pos :], character["account_id"], character)


def without_equipment_appearance(body, character):
    """pO is u8 count + count pR entries (slot u8, item i32, skin i32).

    Boundaries come from OfflineEntityLayout for this exact fixture; applied
    before the name changes. Inventory ownership is initialized separately.
    """
    if character.get("level") is None:
        return body
    level_xp(character["level"])
    bounds = {5: (147, 256), 10: (10336, 10445), 11: (808, 917)}
    if body[0] not in bounds:
        return body
    start, end = bounds[body[0]]
    if len(body) < end or 1 + body[start] * 9 != end - start:
        raise ValueError("Unexpected fixture equipment appearance layout")
    return body[:start] + b"\x00" + body[end:]


def varint(value):
    result = bytearray()
    while value > 127:
        result.append((value & 127) | 128)
        value >>= 7
    result.append(value)
    return bytes(result)


def proto_fields(body):
    """Read protobuf wire fields without interpreting opaque nested messages."""
    r = Reader(body)

    def integer():
        value = 0
        for shift in range(0, 70, 7):
            byte = r.number("B")
            value |= (byte & 127) << shift
            if byte < 128:
                return value
        raise ValueError("Invalid protobuf varint")

    while r.pos < len(body):
        tag = integer()
        kind = tag & 7
        if kind == 0:
            value = integer()
        elif kind == 2:
            value = r.take(integer())
        elif kind in (1, 5):
            value = r.take(8 if kind == 1 else 4)
        else:
            raise ValueError("Unsupported protobuf field")
        yield tag, value


def proto_field(tag, value):
    if tag & 7 == 0:
        return varint(tag) + varint(value)
    if tag & 7 == 2:
        return varint(tag) + varint(len(value)) + value
    return varint(tag) + value


def attribute_sheets(body, characters):
    """12393/cxD: u32 length + hN, repeated hV with characterId field 2.

    Layout confirmed against cia, fpi and hV.writeTo in this client version.
    Clean defaults match the observed fresh-character sheet at every level: map key 0,
    an empty ia/ProtoEquipmentSheet with level -1 (field 53), and own characterId.
    """
    r = Reader(body)
    sets = list(proto_fields(r.take(r.number("I"))))
    r.finish()
    templates = [list(proto_fields(value)) for tag, value in sets if tag == 10]
    template = next(
        fields for fields in templates if (16, TEMPLATE_CHARACTER) in fields
    )
    from wakfu_server.builds import equipment_registry

    result = b"".join(
        proto_field(10, equipment_registry(character))
        if character.get("level") is not None
        else proto_field(
            10,
            b"".join(
                proto_field(tag, character["id"] if tag == 16 else value)
                for tag, value in template
            ),
        )
        for character in characters
    )
    return struct.pack(">I", len(result)) + result


def identity(body, account_id, character=None):
    body = body.replace(
        struct.pack(">q", TEMPLATE_ACCOUNT), struct.pack(">q", account_id)
    )
    if character:
        body = body.replace(
            struct.pack(">q", TEMPLATE_CHARACTER), struct.pack(">q", character["id"])
        )
    return body


def header(body, account_id, character):
    r = Reader(body)
    r.take(18)  # type u8, actor i64, identity flag u8, account i64
    name = r.text("H")
    if name != TEMPLATE_NAME:
        raise ValueError("Unexpected captured character header")
    suffix = body[r.pos :]
    encoded_name = character["name"].encode()
    return (
        identity(body[:18], account_id, character)
        + struct.pack(">H", len(encoded_name))
        + encoded_name
        + suffix
    )


def position(body, character):
    if body.count(INITIAL_POSITION) != 1:
        raise ValueError("Ambiguous captured position")
    offset = body.index(INITIAL_POSITION)
    result = body.replace(
        INITIAL_POSITION,
        struct.pack(">iih", character["x"], character["y"], character["z"]),
    )
    if "map_id" in character:
        from wakfu_server.guild_haven_world import world_identity

        map_id = world_identity(character)
        # rE.Vp becomes eGj.arM(). Ordinary actors retain the positive asset
        # identity; an owned Haven World uses native fiH.su(guild)=-guild.
        # Positive server-instance identity remains separate in both cases.
        map_offset = offset + struct.calcsize(">iih")
        if map_offset + 8 > len(result):
            raise ValueError("Truncated native world position")
        result = (
            result[:map_offset] + struct.pack(">q", map_id) + result[map_offset + 8 :]
        )
    if "direction" in character:
        direction = character["direction"]
        if type(direction) is not int or not 0 <= direction <= 7:
            raise ValueError("Invalid native world direction")
        # rE: x:i32,y:i32,z:i16,map:i64,direction:u8,present:u8,
        # followed by the secondary rH position. Preserve the secondary data.
        direction_offset = offset + struct.calcsize(">iihq")
        if direction_offset >= len(result):
            raise ValueError("Truncated native world position")
        result = (
            result[:direction_offset]
            + bytes([direction])
            + result[direction_offset + 1 :]
        )
    return result


def character_list(template, account_id, characters):
    from .characters.selection_capacity import NATIVE_MAX_CHARACTERS

    if len(characters) > NATIVE_MAX_CHARACTERS:
        raise ValueError("Character roster exceeds native signed-byte capacity")
    r = Reader(template)
    r.take(1)
    template_blob = r.take(r.number("I"))
    result = bytearray([len(characters)])
    for character in characters:
        blob = header(minimal_entity(template_blob, character), account_id, character)
        result.extend(struct.pack(">I", len(blob)))
        result.extend(blob)
    result.extend(b"\x00")  # No inherited companion records.
    return bytes(result)


def spawn_player(template, character):
    blob = header(
        position(minimal_entity(template, character), character),
        character["account_id"],
        character,
    )
    return b"\x00\x01" + struct.pack(">BqH", 0, character["id"], len(blob)) + blob


def refresh_player(template, character):
    """15548: update an existing actor from the same own entity serializer."""
    from .mount_codec import entity_refresh

    blob = header(
        position(minimal_entity(template, character), character),
        character["account_id"],
        character,
    )
    return entity_refresh(character["id"], blob)


def remove_player(character_id):
    # ctA: teleport flag, secondary flag, count, then (type, actorId).
    return b"\x00\x00\x01" + struct.pack(">Bq", 0, character_id)


def without_captured_players(body):
    r = Reader(body)
    flag = r.number("B")
    entries = []
    for _ in range(r.number("B")):
        actor_type, actor_id = r.number("B"), r.number("q")
        blob = r.take(r.number("H"))
        if actor_type != 0:
            entries.append(struct.pack(">BqH", actor_type, actor_id, len(blob)) + blob)
    r.finish()
    return bytes([flag, len(entries)]) + b"".join(entries)


def captured_haven_bag_records(body):
    """cwG (13664): dynamic interactive records from the captured session.

    Template 3700 is confirmed by the fixture's owner name Manama and the
    client's visible "Merkasako de Manama" tooltip. Preserve other templates.
    """
    r = Reader(body)
    entries = []
    for _ in range(r.number("H")):
        start = r.pos
        instance_id, template_id = r.number("q"), r.number("q")
        r.take(r.number("H"))
        r.number("q")
        entries.append((instance_id, template_id, body[start : r.pos]))
    r.finish()
    return entries


def without_captured_haven_bags(body):
    entries = [
        record
        for _, template, record in captured_haven_bag_records(body)
        if template != 3700
    ]
    return struct.pack(">H", len(entries)) + b"".join(entries)


def remove_captured_haven_bags(body):
    ids = [
        instance
        for instance, template, _ in captured_haven_bag_records(body)
        if template == 3700
    ]
    return struct.pack(">H", len(ids)) + b"".join(
        struct.pack(">q", instance) for instance in ids
    )


def movement_path(character_id, request_body):
    """csR (13852): forward the client's exact packed path, including height.

    cny (13331) prefixes aAT with an i32 movement mode; csR replaces that
    prefix with i64 actor ID. The owning client already animates this path.
    """
    from protocol_codec import decode_body

    decode_body("out", 13331, request_body)
    return struct.pack(">q", character_id) + request_body[4:]


def chat(character, text):
    name, text = character["name"].encode(), text.encode()
    if len(name) > 255 or not 1 <= len(text) <= 2048:
        raise ValueError("Invalid chat message length")
    # On (674), vicinity: NQ payload without NP's channel prefix.
    # The identity flag is true for a character ID, false for an account ID.
    return (
        struct.pack(">B", len(name))
        + name
        + struct.pack(">BBqB", 6, 4, character["id"], 1)
        + struct.pack(">H", len(text))
        + text
    )


def private_chat(account_id, sender, recipient, text):
    """Oi720: recipient character link followed by account-identity NQ."""
    source = sender["name"].encode("utf-8")
    target = recipient["name"].encode("utf-8")
    content = text.encode("utf-8")
    if (
        type(account_id) is not int
        or not 0 < account_id < 2**63
        or type(recipient["id"]) is not int
        or not 0 < recipient["id"] < 2**63
        or not 1 <= len(source) <= 255
        or not 1 <= len(target) <= 127
        or not 1 <= len(content) <= 2048
    ):
        raise ValueError("Invalid private chat identity or length")
    return (
        struct.pack(">B", len(target))
        + target
        + struct.pack(">qB", recipient["id"], len(source))
        + source
        + struct.pack(">BBqB", 6, 4, account_id, 0)
        + struct.pack(">H", len(content))
        + content
    )


def private_chat_error(code, recipient=None):
    """Encode NE349; native 101/102/103 all carry a u16-length target name."""
    if type(code) is not int or code not in (101, 102, 103, 104, 140):
        raise ValueError("Unsupported private chat error")
    body = struct.pack(">h", code)
    if code in (101, 102, 103):
        if not isinstance(recipient, str):
            raise ValueError("Private chat error requires recipient name")
        name = recipient.encode("utf-8")
        if not 1 <= len(name) <= 127:
            raise ValueError("Invalid private chat recipient")
        body += struct.pack(">H", len(name)) + name
    return body


def empty_equipment_sheets(body, character):
    """Keep build slots, remove each ProtoEquipmentSheet's item references."""
    r = Reader(body)
    r.take(8)
    fields = list(proto_fields(r.take(r.number("I"))))
    r.finish()
    result = bytearray()
    for tag, value in fields:
        if tag == 10:  # ProtoEquipmentSet.sheets map entry
            entry = bytearray()
            for entry_tag, entry_value in proto_fields(value):
                if entry_tag == 18:
                    entry_value = b"".join(
                        proto_field(t, (1 << 64) - 1 if t == 424 else v)
                        for t, v in proto_fields(entry_value)
                        if t != 10
                    )
                entry.extend(proto_field(entry_tag, entry_value))
            value = bytes(entry)
        elif tag == 16:
            value = character["id"]
        result.extend(proto_field(tag, value))
    return struct.pack(">qI", character["id"], len(result)) + result


def native_configuration_packet(key, value):
    """cEp22318 updates one native configuration key without replacing others."""
    if (
        type(key) is not str
        or type(value) is not str
        or not key
        or "\x00" in key
        or "\x00" in value
    ):
        raise ValueError("Invalid native configuration update")
    key, value = key.encode("utf-8"), value.encode("utf-8")
    if len(key) > 256 or len(value) > 65536:
        raise ValueError("Native configuration update is too large")
    return (
        22318,
        struct.pack(">I", len(key)) + key + struct.pack(">I", len(value)) + value,
    )


def native_chat_flood_packet():
    """Disable native text flood checks while retaining other action policies."""
    return native_configuration_packet("chat.flood.check.enabled", "false")


def native_xp_rate_packet(rate_bp):
    """cEp22318 updates only BASE_XP_RATIO, preserving all other overrides.

    Native bhR/fCn reads this global configuration dynamically. The caller
    owns its display context and must not restore a newer rate immediately
    after publishing an older, completion-frozen result.
    """
    from wakfu_server.reward_rates import MAX_REWARD_RATE_BP, REWARD_RATE_SCALE

    if type(rate_bp) is not int or not 0 <= rate_bp <= MAX_REWARD_RATE_BP:
        raise ValueError("Invalid native XP presentation rate")
    whole, fraction = divmod(rate_bp, REWARD_RATE_SCALE)
    value = (
        str(whole)
        if not fraction
        else (str(whole) + "." + f"{fraction:04d}".rstrip("0"))
    )
    key, encoded = b"base.xp.ratio", value.encode("ascii")
    return (
        22318,
        struct.pack(">I", len(key)) + key + struct.pack(">I", len(encoded)) + encoded,
    )


def adapt(opcode, body, account_id, character=None, *, kamas=None):
    if opcode == 472 and SYNTHETIC_BOOTSTRAP:
        if (
            len(body) < 30
            or body[:2] != b"\x00\x01"
            or type(account_id) is not int
            or not 0 < account_id < 2**63
        ):
            raise ValueError("Invalid synthetic authentication response")
        # The two native account namespaces are explicitly assigned to the
        # authenticated local account by this fixture policy, never copied from
        # an original capture or inferred from its identities.
        return body[:2] + struct.pack(">qq", account_id, account_id) + body[18:]
    if opcode == 15548 and character and character.get("level") is not None:
        if len(body) < 11:
            raise ValueError("Truncated native global-to-local actor update")
        _, size = struct.unpack_from(">qH", body)
        if len(body) != 10 + size:
            raise ValueError("Invalid native global-to-local actor update length")
        if body[10] == 22:
            entity = minimal_entity(body[10:], character)
            return struct.pack(">qH", character["id"], len(entity)) + entity
    if opcode == 12436 and character is not None:
        from wakfu_server.health import packet, exploration_coefficient

        return packet(
            character["id"],
            character["hp"],
            exploration_coefficient(character["max_hp"], character["hp"]),
        )
    if kamas is None:
        kamas = character.get("kamas", 0) if character else 0
    if type(kamas) is not int or not 0 <= kamas < 2**63:
        raise ValueError("Invalid account wallet balance")
    if opcode == 13021:
        # foF applies this balance after account initialization; replaying the
        # captured value would overwrite the local account's zero kamas.
        if len(body) != 8:
            raise ValueError("Invalid kama update length")
        return struct.pack(">q", kamas)
    if opcode == 12753:
        # cye/chS mutates the already-installed account foF and notifies its
        # observers. Keep the native absolute-balance carrier authoritative.
        if len(body) != 8:
            raise ValueError("Invalid account wallet refresh length")
        return account_kamas_update(kamas)
    if opcode == 13873 and len(body) >= 8 and struct.unpack(">II", body[:8]) == (1, 4):
        r = Reader(body)
        r.take(8)
        r.take(r.number("I"))
        r.finish()
        return struct.pack(">III", 1, 4, 0)
    if opcode == 13873 and len(body) == 16 and struct.unpack(">II", body[:8]) == (1, 6):
        return account_kamas(kamas)
    if character and character.get("level") is not None:
        if opcode == 13078:
            from wakfu_server.inventory_items import equipment_inventory

            return equipment_inventory(character)[1]
        if opcode == 12103:
            from wakfu_server.builds import aptitude_registry

            proto = aptitude_registry(character)
            return struct.pack(">qI", character["id"], len(proto)) + proto
        if opcode == 12996:
            from wakfu_server.builds import build_set

            r = Reader(body)
            r.take(8)
            proto = r.take(r.number("I"))
            r.finish()
            proto = build_set(character, proto)
            return struct.pack(">qI", character["id"], len(proto)) + proto
        if opcode == 13713:
            return struct.pack(">q", character["id"]) + minimal_entity(
                body[8:], character
            )
    if opcode == 12666 and character:
        r = Reader(body)
        count = r.number("H")
        prefix = struct.pack(">H", count) + r.take(count * 8)
        blocks = [r.take(r.number("I")) for _ in range(3)]
        r.finish()
        blocks[0] = header(
            position(minimal_entity(blocks[0], character), character),
            account_id,
            character,
        )
        blocks[1:] = [identity(block, account_id, character) for block in blocks[1:]]
        if character.get("level") is not None:
            from wakfu_server.builds import aptitude_registry

            blocks[2] = aptitude_registry(character)
        if character.get("level") is not None:
            from wakfu_server.builds import build_set

            blocks[1] = build_set(character, blocks[1])
        return prefix + b"".join(
            struct.pack(">I", len(block)) + block for block in blocks
        )
    if opcode == 13974 and character:
        from wakfu_server.haven_bag import map_transition

        return map_transition(body, character, character["map_id"])
    if opcode == 13873 and character:
        return character_levels(body, character)
    return identity(body, account_id, character)


def account_kamas(amount):
    """13873/eDS.KAMAS/fpq: single section with signed i64 balance."""
    if type(amount) is not int or not 0 <= amount < (1 << 63):
        raise ValueError("Invalid kama balance")
    return struct.pack(">IIq", 1, 6, amount)


def account_kamas_update(amount):
    """12753/cye: absolute i64 balance applied to the existing wallet model."""
    if type(amount) is not int or not 0 <= amount < (1 << 63):
        raise ValueError("Invalid kama balance")
    return struct.pack(">q", amount)
