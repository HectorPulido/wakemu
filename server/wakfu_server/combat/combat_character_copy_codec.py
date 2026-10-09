"""Original eHI vJ/vK/up descriptor, including owned dS appearance."""
from dataclasses import dataclass
import struct


@dataclass(frozen=True)
class CopiedAppearance:
    source_id: int
    model: int
    appearance: bytes
    categories: tuple[tuple[int, int], ...]


@dataclass(frozen=True)
class CopyCharacteristic:
    identifier: int
    current: int
    minimum: int
    maximum: int
    percentage: int


@dataclass(frozen=True)
class CopiedCharacterDescriptor:
    reference: int
    name: str | None
    minimum_hp: int
    actor_id: int
    level: int
    obstacle_index: int
    direction: int
    owner_id: int
    from_symbiot: bool
    percentage: int
    appearance: CopiedAppearance
    book: tuple
    characteristics: tuple[CopyCharacteristic, ...]


def _pack(format, *values):
    if any(type(value) is not int for value in values):
        raise ValueError("Missing typed native copied descriptor integer")
    try:
        return struct.pack(format, *values)
    except (struct.error, OverflowError) as error:
        raise ValueError("Copied descriptor integer outside native domain") from error


def _count(rows):
    if not isinstance(rows, tuple) or len(rows) > 65535:
        raise ValueError("Missing ordered native copied descriptor collection")
    return _pack(">H", len(rows))


def encode_copy_descriptor(descriptor):
    """eHI.a(vJ), vJ.aF, vK.aF/up.aF; agr remains native null."""
    from .combat_character_copy_book import CopyBookAction

    if type(descriptor) is not CopiedCharacterDescriptor:
        raise ValueError("Missing actual typed copied character descriptor")
    d = descriptor
    if d.name is not None and not isinstance(d.name, str):
        raise ValueError("Invalid native copied actor name")
    name = b"" if d.name is None else d.name.encode("utf-8")
    if len(name) > 65535 or type(d.from_symbiot) is not bool:
        raise ValueError("Invalid native copied actor name/source")
    a = d.appearance
    if (
        type(a) is not CopiedAppearance
        or not isinstance(a.appearance, bytes)
        or len(a.appearance) > 65535
    ):
        raise ValueError("Missing owned copied dS appearance")
    _pack(">q", a.source_id)
    up = (
        _pack(">iiH", d.percentage, a.model, len(a.appearance)) + a.appearance + b"\x01"
    )
    up += _count(d.book)
    for action in d.book:
        if type(action) is not CopyBookAction:
            raise ValueError("Missing typed native yC/yy spell action")
        action.validate()
        up += _pack(">qih", action.uid, action.reference, action.level)
    up += _count(d.characteristics)
    for characteristic in d.characteristics:
        if type(characteristic) is not CopyCharacteristic:
            raise ValueError("Missing typed native ffh/tB characteristic")
        up += _pack(
            ">biiii",
            characteristic.identifier,
            characteristic.current,
            characteristic.minimum,
            characteristic.maximum,
            characteristic.percentage,
        )
    up += _count(a.categories)
    for category in a.categories:
        if not isinstance(category, tuple) or len(category) != 2:
            raise ValueError("Missing actual ordered don category entry")
        up += _pack(">bi", *category)
    return (
        _pack(">hH", d.reference, len(name))
        + name
        + _pack(">iqhb", d.minimum_hp, d.actor_id, d.level, d.obstacle_index)
        + b"\x01"
        + up
        + b"\x00"
        + _pack(">iqB", d.direction, d.owner_id, int(d.from_symbiot))
    )


def encode_copy_additional(descriptor, *, include_levels):
    """eZo.as appends reference/int-level rows iff actual faB.fTc()."""
    if type(include_levels) is not bool:
        raise ValueError("Missing actual character-copy spell-level policy")
    encoded = encode_copy_descriptor(descriptor)
    if not include_levels:
        return encoded
    actions = tuple(action for action in descriptor.book if action.level != 0)
    return (
        encoded
        + _pack(">B", len(actions) & 255)
        + b"".join(_pack(">ii", action.reference, action.level) for action in actions)
    )


def character_copy_payload(
    *,
    descriptor,
    include_levels,
    uid,
    base_uid,
    effect_reference,
    caster_id,
    cell,
    timing_payload,
    status=-1,
    container_type=None,
    container_id=None,
    context_payload=None,
    running_value=0,
    actual_actor_id=None
):
    from .combat_effects import _integer, _varint
    from .combat_displacement import position_payload
    from .combat_running_context import running_context_payload
    from .combat_summon import summon_additional_payload

    if base_uid is None:
        base_uid = uid
    if (
        type(uid) is not int
        or not 0 < uid < 1 << 63
        or type(base_uid) is not int
        or not 0 <= base_uid < 1 << 63
        or type(effect_reference) is not int
        or not 0 < effect_reference < 1 << 31
        or type(running_value) is not int
        or not -(1 << 31) <= running_value < 1 << 31
        or type(status) is not int
        or not -128 <= status <= 127
        or not isinstance(timing_payload, bytes)
    ):
        raise ValueError("Missing actual copied runner envelope")
    _pack(">q", caster_id)
    blob = encode_copy_additional(descriptor, include_levels=include_levels)
    body = b"".join(
        _integer(key, value)
        for key, value in (
            (1, uid),
            (2, base_uid),
            (3, effect_reference),
            (4, running_value),
            (6, caster_id),
        )
    )
    position = position_payload(cell)
    body += b"\x2a" + _varint(len(position)) + position
    additional = b"\x0a" + _varint(len(blob)) + blob
    body += b"\x42" + _varint(len(additional)) + additional
    timing = timing_payload + _integer(2, status) + _integer(5, 1)
    body += b"\x5a" + _varint(len(timing)) + timing
    if actual_actor_id is None:
        actual_actor_id = descriptor.actor_id
    _pack(">q", actual_actor_id)
    return (
        body
        + summon_additional_payload(actual_actor_id)
        + running_context_payload(
            container_type=container_type,
            container_id=container_id,
            context_payload=context_payload,
        )
    )


def character_copy_application(fight_id, action_id, **kwargs):
    if any(
        type(value) is not int or not 0 < value < 1 << 31
        for value in (fight_id, action_id)
    ):
        raise ValueError("Invalid native copied actor fight/action")
    body = character_copy_payload(**kwargs)
    if len(body) > 32767:
        raise ValueError("Native copied effect exceeds cvY short size")
    from .combat_entity_creation_delivery import immediate_entity_creation

    return immediate_entity_creation(fight_id, action_id, 1002, body)


def connected_copy_appearance(authority, fight, actor, *, model_query=None):
    """Read the actual connected character and attested live don/model source."""
    from wakfu_server.wire import appearance_section

    ordinary = getattr(authority, "ordinary", authority)
    characters = getattr(ordinary, "characters", None)
    character = None if not isinstance(characters, dict) else characters.get(actor.id)
    if (
        fight.actors.get(actor.id) is not actor
        or not isinstance(character, dict)
        or character.get("id") != actor.id
        or not isinstance(character.get("appearance"), dict)
    ):
        raise ValueError("Missing connected copied appearance provenance")
    source = getattr(actor, "native_copy_appearance_source", None)
    if source is None and model_query is None and callable(authority):
        from .combat_character_copy_models import native_class_copy_model

        model_query = native_class_copy_model
    if source is None and callable(model_query):
        from wakfu_server.wire import ENTITY_DEFAULTS
        from .combat_runtime_adapter import NativeActorAuthority

        metadata = authority(fight, actor)
        if (
            not isinstance(metadata, NativeActorAuthority)
            or getattr(metadata, "native_actor_type", None) != 0
            or getattr(metadata, "native_is_ehp", None) is not True
            or actor.id in getattr(fight, "native_morph_spellbooks", {})
            or ENTITY_DEFAULTS.get("EQUIPMENT_APPEARANCE") != b"\x00"
        ):
            raise ValueError("Missing ordinary connected entity appearance producer")
        breed, sex = character.get("breed"), character["appearance"].get("sex", 0)
        cloth = character["appearance"].get("clothIndex", 0)
        _pack(">h", breed)
        _pack(">i", sex)
        _pack(">i", cloth)
        # Original bjy.zm clears igU, then iterates pO.TP. The actual
        # ordinary entity encoder emits pO count0, so this population is empty.
        # bhe.b receives sex byte and dpi (clothIndex narrowed to byte).
        byte = lambda value: (value + 128) % 256 - 128
        source = dict(
            source_id=actor.id,
            producer="owned.character.dS.don.v1",
            model=model_query(breed, byte(sex), byte(cloth)),
            categories=(),
        )
    if (
        not isinstance(source, dict)
        or source.get("source_id") != actor.id
        or source.get("producer") != "owned.character.dS.don.v1"
    ):
        raise ValueError("Missing actual copied appearance model/category provenance")
    categories = source.get("categories")
    if not isinstance(categories, (tuple, list)):
        raise ValueError("Missing actual native don category population")
    result = CopiedAppearance(
        actor.id,
        source.get("model"),
        appearance_section(character["appearance"])[2:],
        tuple(tuple(row) for row in categories),
    )
    _pack(">i", result.model)
    _count(result.categories)
    for row in result.categories:
        if len(row) != 2:
            raise ValueError("Invalid native don category entry")
        _pack(">bi", *row)
    return result
