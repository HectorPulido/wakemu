"""Source-backed Emiw roles and the current arena's actual native QI.P.

This is an explicit Wakemu reconstruction, not recovered dungeon coordinates.
The original553/96026 requires challenger team1. First-hand guides describe
starting on terrain tiles and ending within two cells of Emiw each round.
Actual source geometry and participant world origins are never replaced.
"""
from hashlib import sha256
import json

ROLE_POLICY = "wakemu.emiw-native-challenger1-v1"
BORDER_POLICY = "wakemu.emiw-existing-native-perimeter553-v1"
AUTHORITY = "authorized_wakemu_native_content_reconstruction"
SOURCES = (
    "https://www.youtube.com/watch?v=wbWgIF_srIE",
    "https://fabulousgang.forumgaming.fr/t72-strategie-black-wabbit",
)
# Original family549: these four ordinary members and the single native boss.
_ROSTER = frozenset((2559, 2560, 2561, 2562, 2563))


def emiw_roles(map_id, references):
    from .combat_encounter_roles import EncounterRoles, _scope

    references = _scope(map_id, references)
    if references.count(2563) != 1 or not set(references) <= _ROSTER:
        return None
    return EncounterRoles(ROLE_POLICY, AUTHORITY, map_id, references, 1, 0)


def _record(map_id, references, cells):
    return dict(
        policy=BORDER_POLICY,
        authority=AUTHORITY,
        version=1,
        map_id=map_id,
        monster_references=list(references),
        reference=553,
        source_urls=list(SOURCES),
        cells_sha256=sha256(
            json.dumps(
                sorted(tuple(cell) for cell in cells), separators=(",", ":")
            ).encode()
        ).hexdigest(),
    )


def validate_emiw_border(receipt, *, map_id, role_record, cells):
    from .combat_encounter_roles import roles_from_record

    roles = roles_from_record(role_record, map_id=map_id)
    expected_roles = emiw_roles(map_id, roles.monster_references)
    if (
        expected_roles is None
        or roles != expected_roles
        or not cells
        or receipt != _record(map_id, roles.monster_references, cells)
    ):
        raise ValueError("Emiw perimeter differs from its frozen native scope")
    return 553


def prepare_emiw_border(arena):
    """Freeze actual existing P membership after the normal role projection."""
    role = arena.get("native_encounter_roles")
    if not isinstance(role, dict) or role.get("policy") != ROLE_POLICY:
        return arena
    from .combat_encounter_roles import roles_from_record
    from .combat_battleground_border import SUPPORTED_POLICIES
    from .combat_qi_snapshot import NativeQISnapshot

    roles = roles_from_record(role, map_id=arena["map_id"])
    cells = {tuple(cell) for cell in arena.get("native_border_cells", ())}
    qi = NativeQISnapshot(arena)
    actual = {
        (x, y)
        for y in range(qi.y, qi.y + qi.height)
        for x in range(qi.x, qi.x + qi.width)
        if qi.P(x, y)
    }
    if (
        arena.get("native_border_policy") not in SUPPORTED_POLICIES
        or not cells
        or not cells <= set(arena["validated_cells"])
        or {cell[:2] for cell in cells} != actual
    ):
        raise ValueError("Emiw requires the actual selected native QI.P perimeter")
    receipt = _record(arena["map_id"], roles.monster_references, cells)
    validate_emiw_border(receipt, map_id=arena["map_id"], role_record=role, cells=cells)
    return dict(arena, native_emiw_border=receipt, terrain_effect_id=553)
