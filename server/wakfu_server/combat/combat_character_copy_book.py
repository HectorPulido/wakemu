"""Original faC/faE selection and eZx level caps over an attested ordered book.

This component does not construct a copied fighter or invent its source book.
The caller supplies actual frL encounter order, fzf/gvd state and MX bounds.
"""
from dataclasses import dataclass, replace


@dataclass(frozen=True)
class CopyBookAction:
    uid: int
    reference: int
    level: int
    special: bool  # fyF.elO()
    elemental: bool | None  # eVg.fa(gtQ()).fLF(); None = no native element.
    neutral: bool  # eVg.fa(gtQ()) == eVg.rpl.

    def validate(self):
        if (
            type(self.uid) is not int
            or not -(1 << 63) <= self.uid < (1 << 63)
            or type(self.reference) is not int
            or not 0 < self.reference < (1 << 31)
            or type(self.level) is not int
            or not -32768 <= self.level <= 32767
            or type(self.special) is not bool
            or type(self.neutral) is not bool
            or self.elemental is not None
            and type(self.elemental) is not bool
        ):
            raise ValueError("Invalid native character-copy book action")


def copy_spell_level(
    level, *, selector_present, selector_cap, actor_cap, minimum, maximum
):
    """eZx: Math.min -> i2s before GS.a native MX.aYm domain clamp."""
    if (
        type(selector_present) is not bool
        or any(
            type(v) is not int or not -32768 <= v <= 32767
            for v in (level, actor_cap, minimum, maximum)
        )
        or minimum > maximum
        or type(selector_cap) is not int
        or not -(1 << 31) <= selector_cap < (1 << 31)
    ):
        raise ValueError("Missing native copied-spell level operands")
    if selector_present:
        cap = actor_cap if selector_cap == -1 else selector_cap
        level = ((min(level, cap) + 32768) % 65536) - 32768
    return max(minimum, min(maximum, level))


def copy_character_book(
    actions,
    *,
    availability_present,
    available_references,
    selector_present,
    selector_cap,
    actor_cap,
    minimum,
    maximum,
    allocate_uid,
    capacity=20,
    neutral_limit=5
):
    """eZw faB: clone fresh UIDs; faC selected branch, else faE fallback.

    faC allocates before filtering. An empty selected book starts faE afresh,
    allocating another clone for each original row. No UID sorting is allowed.
    """
    if (
        not isinstance(actions, tuple)
        or type(availability_present) is not bool
        or not isinstance(available_references, tuple)
        or any(
            type(v) is not int or not 0 <= v < (1 << 31) for v in available_references
        )
        or type(capacity) is not int
        or not 0 <= capacity <= 32767
        or type(neutral_limit) is not int
        or not 0 <= neutral_limit <= 32767
        or not callable(allocate_uid)
    ):
        raise ValueError("Missing exact character-copy book selection source")
    for action in actions:
        if not isinstance(action, CopyBookAction):
            raise ValueError("Untyped character-copy source action")
        action.validate()

    def clones():
        for action in actions:
            copied = replace(action, uid=allocate_uid())
            copied.validate()
            yield copied

    selected = []
    if availability_present:
        for action in clones():
            # eZw mG(true) preserves special actions; mI(false) uses fzf.gvd.
            if action.reference in available_references and len(selected) < capacity:
                selected.append(action)
    if not selected:
        elemental, neutral = [], []
        for action in clones():
            if action.elemental is True:
                elemental.append(action)
            elif action.elemental is not None and action.neutral:
                neutral.append(action)
        selected = (neutral[:neutral_limit] + elemental)[:capacity]
    return tuple(
        replace(
            action,
            level=copy_spell_level(
                action.level,
                selector_present=selector_present,
                selector_cap=selector_cap,
                actor_cap=actor_cap,
                minimum=minimum,
                maximum=maximum,
            ),
        )
        for action in selected
    )
