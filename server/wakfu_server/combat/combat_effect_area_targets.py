"""Qq targets for the resolver, distinct from fighters and their resources."""
from dataclasses import dataclass
from .combat_effect_area_queries import _rows


@dataclass(frozen=True)
class NativeAreaTarget:
    id: int
    position: tuple
    team: int
    owner_id: int
    physical_radius: int = 0
    direction: int = 7


def area_targets(fight):
    targets = []
    for row in _rows(fight):
        owner = fight.actors.get(row["owner_id"])
        if owner is None:
            raise ValueError("Missing authoritative Qq owner affiliation")
        targets.append(
            NativeAreaTarget(
                row["uid"],
                tuple(row["cell"]),
                getattr(owner, "native_fight_affiliation", owner.team),
                row["owner_id"],
                direction=row["direction"],
            )
        )
    return tuple(targets)


def area_target_context(target):
    if not isinstance(target, NativeAreaTarget):
        raise ValueError("Unknown native area target")
    # faV.bEe true, Qq.bcL=0/bcN=-1 and installed faZ/Qq contract.
    return dict(
        is_Qq=True,
        is_eGj=False,
        is_eHH=False,
        is_amO=True,
        bEe=True,
        bcR=False,
        bcN=-1,
        q_owner_id=target.owner_id,
    )


def target_available(target):
    # Native Qq has no HP resource. Its presence in Qs, not a fabricated
    # positive HP field, determines whether the resolver can inspect it.
    return isinstance(target, NativeAreaTarget) or target.hp > 0
