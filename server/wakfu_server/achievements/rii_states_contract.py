"""Owned Rii state lesson: four reconstructed state reactions.

States 8013--8016 and their conditions are native. The reaction order and
selected cells are observed in one official run; other variants are unknown.
All state and actor positions belong to the fight preview.
"""

from .lesson_states import REQUIRED, STATES, observe

SPELL_EFFECT = 361204  # Native damage effect of 7967.
MESSAGES = (
    "State lesson: use the spell from the marked green cell.",
    "State lesson: use the spell from the marked red cell.",
    "State lesson: end your turn adjacent to the sack.",
    "State lesson: end your turn at least 6 cells from the sack.",
)


def _contract(fight):
    value = getattr(fight, "rii_states_lesson_contract", None)
    return value if isinstance(value, dict) else None


def _marker_los(fight, owner_id, target_id, cell):
    """Evaluate a hypothetical marker with the native cast ray on a clone."""
    from copy import deepcopy
    from types import SimpleNamespace
    from wakfu_server.combat_casting_los import native_casting_los
    from wakfu_server.combat_qi_fight import move_registered_actor

    preview = deepcopy(fight)
    caster, target = preview.actors[owner_id], preview.actors[target_id]
    move_registered_actor(preview, caster, cell)

    class Authority:
        def __call__(self, _fight, _actor):
            return SimpleNamespace(native_instance_id=1388)

        def properties(self, _fight, actor):
            # The original actor snapshots install native fight properties.
            # Unknown properties fail closed instead of claiming a clear ray.
            properties = getattr(actor, "native_fight_properties", None)
            if properties is None:
                raise ValueError("Missing native marker LOS properties")
            return properties

    return native_casting_los(preview, Authority(), owner_id, target.position, target)


def choose_markers(fight, target, *, owner_id):
    from collections import deque
    from wakfu_server.combat_casting_eligibility import native_casting_distance

    owner = fight.actors.get(owner_id)
    if owner is None:
        raise ValueError("Missing state lesson owner")
    occupied = {
        tuple(actor.position)
        for actor in fight.actors.values()
        if actor.hp > 0 and actor.id != owner_id
    }
    x, y, z = target.position
    walkable = {tuple(cell) for cell in fight.walkable if len(cell) == 3}
    start = tuple(owner.position)
    if start not in walkable:
        raise ValueError("State lesson owner is outside fight terrain")
    reachable = {start}
    queue = deque([start])
    while queue:
        origin = queue.popleft()
        neighbours = (
            (origin[0] + dx, origin[1] + dy, origin[2])
            for dx, dy in ((0, 1), (1, 0), (0, -1), (-1, 0))
        )
        for cell in neighbours:
            if (
                cell not in walkable
                or cell in occupied
                or cell in reachable
                or (fight.edges is not None and (origin, cell) not in fight.edges)
            ):
                continue
            reachable.add(cell)
            queue.append(cell)
    # Cells used in the captured official encounter. They are selected only
    # for that authenticated formation and still require native terrain/LOS.
    captured = ((0, -9, 0), (-4, -11, 0))
    if tuple(target.position) == (0, -13, 0):
        if all(
            cell in reachable and _marker_los(fight, owner_id, target.id, cell)
            for cell in captured
        ):
            return captured
    # Choose adjacent reachable cells: no other fighter can stand between an
    # adjacent caster and target. Still verify both rays on native QI authority.
    cells = sorted(
        cell
        for cell in reachable
        if cell[2] == z
        and native_casting_distance((x, y), cell[:2]) == 1
        and _marker_los(fight, owner_id, target.id, cell)
    )
    if len(cells) < 2 or not any(
        cell[2] == z and native_casting_distance((x, y), cell[:2]) >= 6
        for cell in reachable
    ):
        raise ValueError("State lesson terrain lacks the required positions")
    return cells[0], cells[1]


def initialize(fight, packets, *, action_id):
    contract = _contract(fight)
    if contract is None:
        return False
    if isinstance(contract, dict) and contract.get("native_lesson") is True:
        return True
    owner, target = fight.actors.get(contract.get("owner")), fight.actors.get(
        contract.get("target")
    )
    if (
        fight.phase != "active"
        or contract.get("initialized") is not None
        or owner is None
        or target is None
        or owner.team == target.team
    ):
        raise ValueError("Invalid state lesson start")
    green, red = choose_markers(fight, target, owner_id=owner.id)
    from wakfu_server.rii_lesson_grants import install

    contract["green"], contract["red"] = list(green), list(red)
    contract["grant_uids"] = install(
        fight,
        owner.id,
        packets,
        action_id=action_id,
        allocate_uid=fight.allocate_effect_uid,
        lesson="states",
    )
    contract["initialized"] = True
    announce(fight, packets, action_id=action_id)
    return True


def _sync_state(fight, packets, *, action_id, wanted):
    """Replace only this lesson's carrier with the installed native state."""
    from wakfu_server.achievements.rii_lesson_state import install, remove

    contract = _contract(fight)
    previous = contract.get("state_uid")
    if previous is not None and contract.get("visible_state") != wanted:
        remove(
            fight,
            target_id=contract["target"],
            uid=previous,
            action_id=action_id,
            packets=packets,
        )
        contract.pop("state_uid", None)
        contract.pop("visible_state", None)
    if wanted is not None and contract.get("state_uid") is None:
        contract["state_uid"] = install(
            fight,
            owner_id=contract["owner"],
            target_id=contract["target"],
            reference=wanted,
            level=1,
            action_id=action_id,
            packets=packets,
        )
        contract["visible_state"] = wanted


def announce(fight, packets, *, action_id):
    contract = _contract(fight)
    if isinstance(contract, dict) and contract.get("native_lesson") is True:
        return False
    if contract is None or contract.get("initialized") is not True:
        return
    hits = contract.get("hits")
    if type(hits) is not int or not 0 <= hits <= REQUIRED:
        raise ValueError("Invalid state lesson progress")
    if hits == REQUIRED:
        return
    _sync_state(fight, packets, action_id=action_id, wanted=STATES[hits])
    from wakfu_server.ecology_feedback import information
    from wakfu_server.combat_tactical_markers import _marker_packet

    if hits in (0, 1):
        marker = contract["green" if hits == 0 else "red"]
        packets.append(_marker_packet(fight.id, marker, contract["owner"], hits, True))
    packets.append(information(MESSAGES[hits]))


def _observe(fight, actor_id, target_id, event, *, spell_id=None):
    contract = _contract(fight)
    if contract is None or contract.get("initialized") is not True:
        return False
    owner, target = fight.actors.get(contract.get("owner")), fight.actors.get(
        contract.get("target")
    )
    if owner is None or target is None:
        raise ValueError("Missing state lesson participants")
    previous = {"hits": contract.get("hits")}
    updated = observe(
        previous,
        owner_id=owner.id,
        target_id=target.id,
        actor_id=actor_id,
        target_actor_id=target_id,
        event=event,
        actor_xy=tuple(owner.position[:2]),
        target_xy=tuple(target.position[:2]),
        green=tuple(contract["green"][:2]),
        red=tuple(contract["red"][:2]),
        spell_id=spell_id,
    )
    contract.update(updated)
    return updated["hits"] > previous["hits"]


def turn_end(fight, actor_id):
    """Apply authentic turn-end reactions without altering unrelated fights."""
    contract = _contract(fight)
    if isinstance(contract, dict) and contract.get("native_lesson") is True:
        return False
    if contract is None or actor_id != contract.get("owner"):
        return False
    if not _observe(fight, actor_id, contract["target"], "turn_end"):
        return False
    # The state descriptions say ending in the right position damages the sack.
    # The 25-point amount is reconstructed from its observed 100 HP/four stages.
    fight.apply_effect_damage(actor_id, contract["target"], 25)
    return True


def hit(fight, *, source_id, target_id, effect_reference, damage):
    contract = _contract(fight)
    if isinstance(contract, dict) and contract.get("native_lesson") is True:
        return None
    if contract is None or target_id != contract.get("target"):
        return None
    if (
        source_id != contract.get("owner")
        or effect_reference != SPELL_EFFECT
        or damage <= 0
    ):
        return 0
    from wakfu_server.combat_active_spell import active_spell_id

    try:
        spell_id = active_spell_id(fight)
    except ValueError:
        return 0
    if spell_id != 7967:
        return 0
    return 25 if _observe(fight, source_id, target_id, "hit", spell_id=7967) else 0
