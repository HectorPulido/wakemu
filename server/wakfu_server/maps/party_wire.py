"""Native party codecs; these functions do not authorize membership changes.

Ow1031, OG1072, Ou1074/Ov1066 and OH1049 are verified against the
installed native serializers. Roster1184 requires its separate fga codec.
"""
import struct


def _identity(value):
    if type(value) is not int or not 0 < value < 2**63:
        raise ValueError("Invalid party identity")
    return value


def member_request(body):
    """Shared layout for removal1074 and leader transfer1066."""
    if not isinstance(body, bytes) or len(body) != 16:
        raise ValueError("Invalid party member request")
    group_id, member_id = struct.unpack(">qq", body)
    return {"group_id": _identity(group_id), "member_id": _identity(member_id)}


def _read_name(body, offset):
    if offset >= len(body):
        raise ValueError("Missing party name")
    size = body[offset]
    # OG uses a signed Java byte as its array length, so lengths >=128
    # cannot be represented safely by the corresponding native reader.
    if size > 127 or offset + 1 + size > len(body):
        raise ValueError("Invalid party name length")
    try:
        name = body[offset + 1 : offset + 1 + size].decode("utf-8")
    except UnicodeDecodeError as error:
        raise ValueError("Invalid party name encoding") from error
    if "\x00" in name:
        raise ValueError("Invalid party name")
    return name, offset + 1 + size


def invitation_answer(body):
    """Decode Ow1031; inviter identity still requires durable validation."""
    if not isinstance(body, bytes) or len(body) < 12:
        raise ValueError("Invalid party invitation answer")
    if body[0] != 1 or body[1] not in (0, 1):
        raise ValueError("Invalid party invitation type or answer")
    first, offset = _read_name(body, 2)
    second, offset = _read_name(body, offset)
    if len(body) != offset + 8:
        raise ValueError("Invalid party invitation context")
    # Ow defaults to -1 before OG1072 supplies the inviter character ID.
    inviter_id = struct.unpack_from(">q", body, offset)[0]
    if inviter_id != -1:
        _identity(inviter_id)
    return {
        "accepted": bool(body[1]),
        "first_name": first,
        "second_name": second,
        "inviter_id": inviter_id,
    }


def invitation_request(body):
    """Decode Or1156 without interpreting its two opaque context fields."""
    if not isinstance(body, bytes) or len(body) < 19 or body[0] != 1:
        raise ValueError("Invalid party invitation request")
    first_context, second_context = struct.unpack_from(">qq", body, 1)
    selector = body[17]
    if selector == 0:
        name, offset = _read_name(body, 18)
        if not name or offset != len(body):
            raise ValueError("Invalid party invitation target name")
        target = {"target_name": name}
    elif selector == 1:
        if len(body) != 26:
            raise ValueError("Invalid party invitation target identity")
        target = {"target_id": _identity(struct.unpack_from(">q", body, 18)[0])}
    else:
        raise ValueError("Invalid party invitation target selector")
    return {"first_context": first_context, "second_context": second_context, **target}


def invitation(inviter_id, inviter_name):
    """Encode OG1072 for the PARTY type only."""
    _identity(inviter_id)
    if not isinstance(inviter_name, str) or not inviter_name or "\x00" in inviter_name:
        raise ValueError("Invalid party inviter name")
    encoded = inviter_name.encode("utf-8")
    if len(encoded) > 127:
        raise ValueError("Party inviter name is too long")
    return 1072, bytes((1, len(encoded))) + encoded + struct.pack(">q", inviter_id)


def removed(group_id, member_ids):
    """Encode OH1049: group followed by IDs, without a count field."""
    _identity(group_id)
    if not isinstance(member_ids, (list, tuple)) or not member_ids:
        raise ValueError("Missing removed party members")
    identities = [_identity(member_id) for member_id in member_ids]
    if len(set(identities)) != len(identities):
        raise ValueError("Duplicate removed party member")
    return 1049, struct.pack(">q", group_id) + b"".join(
        struct.pack(">q", member_id) for member_id in identities
    )


def roster(group_id, leader_id, members):
    """OE1184 identity, fight/death state, effective/real level and HP.

    Association remains an explicit native input, not a guessed account ID.
    Portrait variant and identity flag remain explicit native inputs.
    No companion section6 is emitted for human characters.
    """
    _identity(group_id)
    _identity(leader_id)
    if group_id >> 56 != 1:
        raise ValueError("Group identity does not encode PARTY")
    if not isinstance(members, (list, tuple)) or not 1 <= len(members) <= 6:
        raise ValueError("Invalid party roster size")
    records, identities = [], set()
    for member in members:
        if not isinstance(member, dict):
            raise ValueError("Invalid party member")
        identity = _identity(member.get("id"))
        association = _identity(member.get("association_id"))
        name = member.get("name")
        if not isinstance(name, str) or not name or "\x00" in name:
            raise ValueError("Invalid party member name")
        encoded = name.encode("utf-8")
        if len(encoded) > 127 or identity in identities:
            raise ValueError("Invalid party member identity or name length")
        identities.add(identity)
        for key in ("level", "effective_level"):
            if type(member.get(key)) is not int or not 1 <= member[key] < 2**15:
                raise ValueError("Invalid party member level")
        for key in ("in_fight", "dead"):
            if type(member.get(key)) is not bool:
                raise ValueError("Invalid party member status")
        hp, maximum = member.get("hp"), member.get("max_hp")
        if (
            type(hp) is not int
            or type(maximum) is not int
            or not 0 <= hp <= maximum < 2**31
            or maximum == 0
        ):
            raise ValueError("Invalid party member health")
        breed, variant = member.get("breed"), member.get("portrait_variant")
        flag = member.get("native_identity_flag")
        if (
            type(breed) is not int
            or not 0 < breed < 2**15
            or type(variant) is not int
            or not 0 <= variant < 128
            or type(flag) is not bool
        ):
            raise ValueError("Invalid party member portrait identity")
        sections = [
            (
                0,
                struct.pack(">qqB", association, identity, len(encoded))
                + encoded
                + struct.pack(">h?B", breed, flag, variant),
            ),
            (1, struct.pack(">?", member["in_fight"])),
            (2, struct.pack(">?", member["dead"])),
            (3, struct.pack(">h", member["effective_level"])),
            # Send authoritative final maxHP with zero additional percentage;
            # avoid applying equipment/level modifiers a second time in UI.
            (5, struct.pack(">iiii", hp, maximum, 0, 0)),
            (7, struct.pack(">h", member["level"])),
        ]
        offset = 1 + len(sections) * 5
        directory, payload = [], []
        for tag, section in sections:
            directory.append(struct.pack(">Bi", tag, offset))
            payload.append(bytes((tag,)) + section)
            offset += 1 + len(section)
        record = bytes((len(sections),)) + b"".join(directory) + b"".join(payload)
        records.append(struct.pack(">qh", identity, len(record)) + record)
    if leader_id not in identities:
        raise ValueError("Party leader is absent from roster")
    body = struct.pack(">qBhqh", group_id, 0, 8, leader_id, len(records))
    return 1184, body + b"".join(records)
