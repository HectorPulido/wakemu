"""Native hero request codecs; roster mutation remains account-authorized."""
import struct


def add_request(body):
    """cnY12219 carries one positive real character identity."""
    if not isinstance(body, bytes) or len(body) != 8:
        raise ValueError("Native hero addition requires eight bytes")
    identity = struct.unpack(">q", body)[0]
    if identity <= 0:
        raise ValueError("Hero addition requires a real owned character")
    return identity


def switch_request(body):
    """cnZ12006 uses the same exact character-identity layout as cnY."""
    return add_request(body)


def switched_result(character_id, result=0):
    """cwE13440 starts native master handoff; csF12054 completes it."""
    if type(character_id) is not int or character_id <= 0:
        raise ValueError("Invalid native hero switch identity")
    if type(result) is not int or not 0 <= result <= 6:
        raise ValueError("Invalid native hero switch result")
    return 13440, struct.pack(">Bq", result, character_id)


def added_success():
    """cwC12587 eEQ.NO_ERROR is native enum value1, not a boolean0."""
    return 12587, b"\x01"


def company(account_id, main_character_id):
    """eSJ COMPANY identifies the real main and activates the owned company."""
    if any(
        type(value) is not int or value <= 0
        for value in (account_id, main_character_id)
    ):
        raise ValueError("Invalid native company owner or chief")
    return 13873, struct.pack(
        ">IIqqiqIiB", 1, 1, account_id, main_character_id, 0, 0, 0, 1, 1
    )


def added_result(result):
    """Native eEQ results1..15 re-enable the hero UI after an add attempt."""
    if type(result) is not int or not 1 <= result <= 15:
        raise ValueError("Invalid native hero addition result")
    return 12587, bytes((result,))


def refresh(template, character):
    """csZ13046 updates an already-loaded owned hero biB from its real blob."""
    from wakfu_server import wire

    blob = wire.header(
        wire.position(wire.minimal_entity(template, character), character),
        character["account_id"],
        character,
    )
    if len(blob) > 32767:
        raise ValueError("Owned hero entity exceeds native signed-short size")
    return 13046, struct.pack(">qh", character["id"], len(blob)) + blob


def activate(template, character):
    """cue12093 hydrates and activates an owned hero in the native registry."""
    from wakfu_server.builds import build_set, aptitude_registry

    entity = refresh(template, character)[1][10:]
    blocks = (entity, build_set(character, b""), aptitude_registry(character))
    return 12093, b"".join(struct.pack(">I", len(block)) + block for block in blocks)


def statistics(character):
    """Hydrate owned HP limits and level absent from the admission format10."""
    from wakfu_server.combat_lifecycle import outside_progression

    return outside_progression(character)


def configuration(body):
    """cEo23053 replaces all eEI overrides; preserve unrelated supplied values."""
    from protocol_codec import Reader

    reader = Reader(body)
    payload = reader.take(reader.number("I"))
    reader.finish()
    reader = Reader(payload)
    count = reader.number("I")
    if count > 4096:
        raise ValueError("Invalid native server configuration count")
    values = {}
    for _ in range(count):
        key = reader.number("h")
        value = reader.take(reader.number("I")).decode("utf-8")
        if key in values:
            raise ValueError("Duplicate native server configuration")
        values[key] = value
    reader.finish()
    values.update({431: "true", 602: "true", 603: "true", 622: "2"})
    payload = struct.pack(">I", len(values))
    for key, value in values.items():
        encoded = value.encode("utf-8")
        payload += struct.pack(">hI", key, len(encoded)) + encoded
    return 23053, struct.pack(">I", len(payload)) + payload
