"""Native eZq994/faD ordered target book selection; no actor construction."""
from dataclasses import dataclass


@dataclass(frozen=True)
class TargetCopyBookAction:
    # Object is retained: faB.fTf is false, so faD never clones or replaces UID.
    action: object
    root_effect_classes: tuple
    elemental: bool | None


def copy_target_book(actions):
    """Keep the first four eligible frL entries in their original order.

    Caller must attest actual frL order, current-level fyF.fG roots and native
    eVg.fa(gtQ()).fLF. Unknown element is rejected by faD rather than guessed.
    This pure primitive does not grant source-book or descriptor authority.
    """
    if not isinstance(actions, (tuple, list)):
        raise ValueError("Missing actual ordered native target spellbook")
    selected = []
    for row in actions:
        if (
            not isinstance(row, TargetCopyBookAction)
            or not isinstance(row.root_effect_classes, tuple)
            or any(type(kind) is not int for kind in row.root_effect_classes)
            or row.elemental is not None
            and type(row.elemental) is not bool
        ):
            raise ValueError("Missing actual faD target spell operands")
        if 307 in row.root_effect_classes or 324 in row.root_effect_classes:
            continue
        if row.elemental is True:
            selected.append(row.action)
    return tuple(selected[:4])
