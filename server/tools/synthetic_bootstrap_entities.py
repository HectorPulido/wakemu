"""Construct neutral eHk entities from fresh original section serializers.

Input defaults come from the original eHk/eHf constructors, not a player packet.
Only explicit synthetic identity/name/position fields differ from those native
empty sections. Offsets and fingerprints describe the newly built bytes.
"""
from collections.abc import Mapping
import hashlib
import struct


FORMATS = (4, 5, 10, 11, 22, 28)
DEFAULT_FORMATS = (5, 10, 11, 22, 28)


def _identity(value, label):
    if type(value) is not int or not 0 < value < 2**63:
        raise ValueError("Invalid synthetic " + label)
    return value


def _section_bytes(section, account_id, character_id, name):
    if (
        not isinstance(section, Mapping)
        or section.get("status") != "original-default-roundtrip"
        or not isinstance(section.get("name"), str)
        or not isinstance(section.get("class"), str)
    ):
        raise ValueError("Missing round-tripped original entity section")
    encoded = bytes.fromhex(section["hex"])
    if type(section.get("size")) is not int or len(encoded) != section["size"]:
        raise ValueError("Original entity section length differs from its serializer")
    key = section["name"]
    if key == "ID":
        if section["class"] != "qt" or len(encoded) != 8:
            raise ValueError("Unsupported native ID section")
        return struct.pack(">q", character_id)
    if key == "IDENTITY":
        if section["class"] != "qv" or len(encoded) != 9:
            raise ValueError("Unsupported native identity section")
        return encoded[:1] + struct.pack(">q", account_id)
    if key == "NAME":
        if section["class"] != "qR":
            raise ValueError("Unsupported native name section")
        return struct.pack(">H", len(name)) + name
    if key == "POSITION":
        if section["class"] != "rE" or len(encoded) != 20:
            raise ValueError("Unsupported native empty position section")
        # Original rE.aF encodes primary rH fields, direction, presence byte,
        # then optional rH.aF (18 bytes). A real secondary position preserves
        # haven_bag's format28 contract without copying or padding a packet.
        return struct.pack(">iihqBB", -12, -8, -1, 1134, 0, 1) + struct.pack(
            ">iihq", 0, 0, 0, 0
        )
    return encoded


def build_entities(defaults, account_id, character_id, name):
    """Return ({format_id: bytes}, newly measured entity-layout records)."""
    _identity(account_id, "account identity")
    _identity(character_id, "character identity")
    if account_id == character_id or not isinstance(name, str) or not name:
        raise ValueError("Synthetic actor requires distinct identities and a name")
    encoded_name = name.encode("utf-8")
    if len(encoded_name) > 65535:
        raise ValueError("Synthetic name exceeds native qR bounds")
    if not isinstance(defaults, Mapping) or not isinstance(
        defaults.get("formats"), list
    ):
        raise ValueError("Missing original entity format defaults")
    formats = {}
    for item in defaults["formats"]:
        if (
            not isinstance(item, Mapping)
            or type(item.get("id")) is not int
            or item["id"] in formats
        ):
            raise ValueError("Malformed or repeated original entity format")
        formats[item["id"]] = item
    if set(formats) != set(DEFAULT_FORMATS):
        raise ValueError("Incomplete original entity format defaults")
    # Native format 4 consists only of oY BAGS. Reuse that exact fresh section
    # from format 10, rather than inheriting a captured format-4 layout.
    bags = [row for row in formats[10]["sections"] if row["name"] == "BAGS"]
    if len(bags) != 1 or bags[0]["class"] != "oY":
        raise ValueError("Missing fresh native BAGS section")
    formats[4] = dict(id=4, sections=bags)
    entities, layouts = {}, []
    for format_id in FORMATS:
        item = formats[format_id]
        if not isinstance(item.get("sections"), list) or not item["sections"]:
            raise ValueError("Missing original entity section sequence")
        chunks, sections, names = [bytes((format_id,))], [], set()
        offset = 1
        for section in item["sections"]:
            chunk = _section_bytes(section, account_id, character_id, encoded_name)
            if section["name"] in names:
                raise ValueError("Repeated original entity section")
            names.add(section["name"])
            sections.append(
                dict(
                    name=section["name"],
                    **{"class": section["class"]},
                    start=offset,
                    end=offset + len(chunk)
                )
            )
            offset += len(chunk)
            chunks.append(chunk)
        body = b"".join(chunks)
        if len(body) != offset or format_id == 28 and len(body) != 56:
            raise ValueError("Synthetic entity differs from native section bounds")
        entities[format_id] = body
        layouts.append(
            dict(
                format=format_id,
                sections=sections,
                bytes=len(body),
                fully_consumed=True,
                template_sha256=hashlib.sha256(body).hexdigest(),
            )
        )
    return entities, layouts
