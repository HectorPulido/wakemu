"""Independent copied-character descriptor slice; not a full1002 executor model.

Native vJ/vK/up byte identities are separate from generated actor identity.
Book and owner fields are decoded literally. Encoded owner is not by itself
proof of live control, privacy filtering, timeline enrollment or availability.
"""
from dataclasses import dataclass
import re
from .combat_protocol_reconstruction import (
    MalformedPacket,
    _Reader,
    _field,
    _protobuf,
    _signed,
)
from .combat_core_reconstruction import UnknownCoreLayout


@dataclass(frozen=True)
class NativeCopyContract:
    include_levels: bool
    evidence_sha256: str

    def __post_init__(self):
        if type(self.include_levels) is not bool or not re.fullmatch(
            r"[0-9a-f]{64}", self.evidence_sha256
        ):
            raise ValueError("Explicit native faB.fTc evidence required")


def decode_copy_descriptor(body, *, contract):
    if not isinstance(contract, NativeCopyContract):
        raise UnknownCoreLayout("Missing native copied-descriptor variant contract")
    reader = _Reader(body)
    reference = reader.read("h")
    try:
        name = reader.blob("H").decode("utf-8", errors="strict")
    except UnicodeDecodeError as error:
        raise MalformedPacket("Malformed native copied name") from error
    minimum_hp, descriptor_actor, level, obstacle = reader.read("iqhb")
    if reader.read("B") != 1:
        raise UnknownCoreLayout("Native copied descriptor lacks supported vK/up")
    percentage, model = reader.read("ii")
    appearance = reader.blob("H")
    appearance_flag = reader.read("B")
    book = [
        dict(zip(("uid", "reference", "level"), reader.read("qih")))
        for _ in range(reader.count("H"))
    ]
    characteristics = [
        dict(
            zip(
                ("id", "current", "minimum", "maximum", "percentage"),
                reader.read("biiii"),
            )
        )
        for _ in range(reader.count("H"))
    ]
    categories = [reader.read("bi") for _ in range(reader.count("H"))]
    if reader.read("B") != 0:
        raise UnknownCoreLayout("Non-null native vM copied descriptor")
    direction, owner = reader.read("iq")
    symbiot = reader.read("B")
    if symbiot not in (0, 1):
        raise MalformedPacket("Invalid native copied symbiot flag")
    levels = (
        [reader.read("ii") for _ in range(reader.count("B"))]
        if contract.include_levels
        else None
    )
    reader.done()
    return dict(
        reference=reference,
        name=name,
        minimum_hp=minimum_hp,
        descriptor_actor=descriptor_actor,
        level=level,
        obstacle=obstacle,
        percentage=percentage,
        model=model,
        appearance=appearance,
        appearance_flag=appearance_flag,
        book=book,
        characteristics=characteristics,
        categories=categories,
        direction=direction,
        owner=owner,
        from_symbiot=bool(symbiot),
        level_trailer=levels,
    )


def decode_copy_running_effect(body, *, contract):
    fields = _protobuf(body)
    additional = _protobuf(_field(fields, 8, 2, required=True))
    descriptor = decode_copy_descriptor(
        _field(additional, 1, 2, required=True), contract=contract
    )
    generated = _protobuf(_field(fields, 12, 2, required=True))
    actor = _signed(_field(generated, 4, 0, required=True), 64)
    if actor <= 0:
        raise MalformedPacket("Missing positive generated copied actor identity")
    return dict(
        actor=actor,
        effect_uid=_signed(_field(fields, 1, 0, required=True), 64),
        caster=_signed(_field(fields, 6, 0, required=True), 64),
        descriptor=descriptor,
    )
