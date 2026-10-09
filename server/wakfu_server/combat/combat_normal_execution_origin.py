"""Server-owned normal dispatch policy, distinct from original caller evidence."""
from dataclasses import dataclass
from .combat_execution_context import constructed_execution_context


@dataclass(frozen=True)
class NormalExecutionOrigin:
    caster_id: int
    spell_id: int
    level: int
    context_payload: bytes
    policy: str = "wakemu.normal-spell.original-eVt-constructor-v1"

    def __post_init__(self):
        if (
            type(self.caster_id) is not int
            or self.caster_id == 0
            or not -(1 << 63) <= self.caster_id < 1 << 63
            or type(self.spell_id) is not int
            or not 0 < self.spell_id < 1 << 31
            or type(self.level) is not int
            or not 0 <= self.level <= 32767
            or not isinstance(self.context_payload, bytes)
            or not self.context_payload
        ):
            raise ValueError("Missing typed normal spell execution origin")


def normal_execution_origin(plan):
    """Choose original constructor scalars for a newly validated owned cast.

    This is an explicit server policy, not a claim about an unavailable original
    server caller. Incoming/restored/trigger contexts are handled by their own
    dispatch boundary and must not call this fresh-origin function.
    """
    return NormalExecutionOrigin(
        plan["actor_id"],
        plan["spell_id"],
        plan["evaluation_level"],
        constructed_execution_context().payload(),
    )


def normal_root_context(origin, *, caster_id, spell_id, level, existing_payload=None):
    if existing_payload is not None:
        if not isinstance(existing_payload, bytes):
            raise ValueError("Existing native execution context must be bytes")
        return existing_payload
    if not isinstance(origin, NormalExecutionOrigin) or (
        origin.caster_id,
        origin.spell_id,
        origin.level,
    ) != (caster_id, spell_id, level):
        raise ValueError("Normal root execution origin does not match validated cast")
    return origin.context_payload
