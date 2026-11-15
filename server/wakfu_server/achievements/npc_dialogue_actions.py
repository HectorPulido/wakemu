"""Explicit action-specific dialogue contracts for native NPC placements.

Native action criteria do not identify a dialogue root or graph. Add a contract
only when its placement and action are qualified; inferred edges remain marked.
"""

_CONTRACTS = {
    (4688, -1776810790485981, 527, 0, 969): {
        "root": 7119,
        "edges": {
            (7119, 15212): 7120,
            (7120, 15214): 7121,
            (7121, 15215): 7122,
            (7121, 15223): 7122,
            (7122, 15216): 7123,
            (7123, 15217): 7124,
            (7124, 15218): 7125,
            (7125, 15219): 7126,
            (7125, 15221): 7126,
            (7125, 15222): 7126,
            (7126, 15220): 0,
        },
        "phases": [
            {
                "requires_completed": [11544],
                "root": 7137,
                "edges": {},
                "terminal_root": True,
            },
            {
                "requires_completed": [11515],
                "requires_incomplete": [11544],
                "root": 7129,
                "edges": {
                    (7129, 15226): 7130,
                    (7129, 15227): 7130,
                    (7130, 15228): 7131,
                    (7131, 15229): 7132,
                    (7132, 15230): 7133,
                    (7133, 15231): 7134,
                    (7134, 15232): 7135,
                    (7134, 15233): 7135,
                    (7135, 15234): 7136,
                    (7136, 15235): 7137,
                    (7137, 15236): 0,
                },
            },
            {
                "requires_completed": [11510],
                "requires_incomplete": [11515],
                "root": 7128,
                "edges": {(7128, 15225): 0},
            },
        ],
        # Placement/action are captured. These narrative joins are reviewed
        # local reconstruction from native choices, replies and quest criteria.
        "edge_authority": "reconstructed_from_native_text_and_quest_5568_criteria",
    },
    (3257, -1776810787923716, 895, 0, 587): {
        "root": 7115,
        "edges": {
            (7115, 15205): 7116,
            (7116, 15208): 7117,
            (7117, 15209): 7118,
            (7118, 15210): 0,
        },
        "repeat_root": 7118,
        "repeat_after_objective": 11508,
        "edge_authority": "official_rii_20261112_frames_7197_7206",
    },
    (5459, -1706442046308330, 1385, 0, 1239): {
        "root": 5763,
        "edges": {(5763, 13287): 5775},
        "edge_authority": "official_rii_20261112_frames_4755_4758_4771",
    },
    (5461, -1706442046308322, 1385, 0, 1241): {
        "root": 5757,
        "edges": {
            (5757, 13263): 5758,
            (5757, 13267): 5759,
            (5757, 13264): 0,
            (5758, 13266): 5757,
            (5759, 13286): 5771,
            (5759, 13268): 5760,
            (5759, 13272): 5761,
            (5759, 13269): 0,
            (5760, 13270): 5759,
            (5760, 13271): 0,
            (5761, 13273): 5759,
            (5761, 13274): 0,
            (5771, 13284): 5759,
            (5771, 13285): 0,
        },
        "edge_authority": "inferred_from_native_text",
    },
}


def resolve(row, action_id, *, facts=None):
    """Return only a contract for the exact placement and action."""
    if row is None:
        return None
    key = (
        row.get("reference_id"),
        row.get("actor_id"),
        row.get("map_id"),
        row.get("instance_id"),
        action_id,
    )
    contract = _CONTRACTS.get(key)
    if contract is not None and facts is not None:
        for phase in contract.get("phases", ()):
            if all(
                facts.get(objective, False)
                for objective in phase.get("requires_completed", ())
            ) and all(
                not facts.get(objective, False)
                for objective in phase.get("requires_incomplete", ())
            ):
                return dict(contract, **phase)
    if (
        contract is not None
        and facts is not None
        and facts.get(contract.get("repeat_after_objective"), False)
    ):
        return dict(
            contract, root=contract["repeat_root"], edges={}, terminal_root=True
        )
    return contract


def allow(opcode, body, character, session):
    """Admit exact reviewed action contracts to the ordinary NPC validator.

    This gate does not establish range, actor publication or mission criteria;
    the existing dispatcher checks those against its current database rows.
    """
    import struct

    scene = character.get("map_id"), character.get("instance_id", 0)
    contracts = [(key, value) for key, value in _CONTRACTS.items() if key[2:4] == scene]
    if opcode == 13222 and len(body) == 16:
        actor, action = struct.unpack(">qq", body)
        return any((key[1], key[4]) == (actor, action) for key, _ in contracts)
    if opcode == 12535 and len(body) == 13:
        node, kind, actor = struct.unpack(">ibq", body)
        return kind == 2 and any(
            key[1] == actor
            and node
            in (
                value["root"],
                value.get("repeat_root"),
                *(phase["root"] for phase in value.get("phases", ())),
            )
            for key, value in contracts
        )
    if opcode == 12058 and len(body) == 8 and session is not None:
        return any(
            key[1] == getattr(session, "speaker_id", None) for key, _ in contracts
        )
    return False
