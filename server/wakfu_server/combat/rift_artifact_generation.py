"""Declared Rift artifact producer, executing unchanged native315/faM consumers.

Tier weights, displayed-wave cadence and seeded placement are Wakemu policy.
Original prototypes, effect parameters, contact children and stat arithmetic
remain the published native definitions. The chosen reference is carried by
native eVt.SQ, never by modifying a template parameter or its execution level.
"""
from collections import defaultdict, deque

from wakfu_server.combat_definitions import effect_profile
from wakfu_server.combat_effect_dispatch import EffectInvocation
from wakfu_server.combat_encounter_roles import assigned_roles
from wakfu_server.combat_execution_context import constructed_execution_context
from wakfu_server.combat_value_transfer import transfer_value_context
from wakfu_server.rift_native_gameplay import policy, register_artifact_group

PRODUCER_POLICY = "wakemu.rift.native-context-area-reference.v1"


def _settings(dispatcher):
    fight = dispatcher.native_retention.fight
    document = policy(fight)
    if document is None or document.get("artifacts", {}).get("enabled") is not True:
        return None
    settings = document["artifacts"]
    producer = settings.get("producer", {})
    if (
        producer.get("policy") != PRODUCER_POLICY
        or producer.get("source_kind") != "native_context_area_ref"
        or producer.get("native_contract") != "faM"
        or producer.get("level_policy") != "owner_effective_level"
        or producer.get("context_policy") != "eVt_mb_false_SQ_area_reference"
    ):
        raise ValueError("Unreviewed Rift artifact producer policy")
    return settings


def _reachable_free_cells(fight, actor):
    """Use the same accepted terrain edges and complete QI walk blockers as move.

    No MP is paid by this placement query. Its cardinal fallback is exactly the
    same-level legacy terrain rule in Fight._move_actor, not a spawn radius.
    """
    from wakfu_server.combat_qi_movement import movement_blocked_cells

    cells = set(fight.walkable)
    blocked = movement_blocked_cells(fight, actor, cells)
    if blocked is None:
        raise ValueError("Artifact production requires the actual complete native QI")
    available = cells - blocked
    available.add(actor.position)
    adjacency = defaultdict(list)
    if fight.edges is not None:
        for start, end in fight.edges:
            if start in available and end in available:
                adjacency[start].append(end)
    else:
        for x, y, z in available:
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                target = (x + dx, y + dy, z)
                if target in available:
                    adjacency[(x, y, z)].append(target)
    reached, pending = {actor.position}, deque((actor.position,))
    while pending:
        for target in adjacency[pending.popleft()]:
            if target not in reached:
                reached.add(target)
                pending.append(target)
    occupied = {a.position for a in fight.actors.values() if fight._in_play(a)}
    area_cells = {
        tuple(row["cell"]) for row in getattr(fight, "native_effect_areas", {}).values()
    }
    return sorted(reached - occupied - area_cells)


def _draw_references(settings, wave, count, rng):
    pools = settings.get("pools")
    weights = settings.get("rarity_weights")
    if (
        not isinstance(pools, dict)
        or not isinstance(weights, dict)
        or set(weights) != set(pools)
        or any(type(weight) is not int or weight < 0 for weight in weights.values())
        or any(
            not isinstance(pool, (tuple, list))
            or not pool
            or any(type(ref) is not int or ref <= 0 for ref in pool)
            or len(set(pool)) != len(pool)
            for pool in pools.values()
        )
        or len({ref for pool in pools.values() for ref in pool})
        != sum(len(pool) for pool in pools.values())
    ):
        raise ValueError("Invalid frozen native Rift artifact pools/weights")
    if (
        settings.get("selection")
        != "weighted_tier_uniform_reference_without_replacement"
    ):
        raise ValueError("Unreviewed native Rift artifact selection policy")
    cadence = settings.get("legendary_cadence")
    if (
        type(cadence) is not int
        or cadence < 1
        or settings.get("legendary_anchor") != "displayed_wave_multiple"
        or settings.get("legendary_mode") != "whole_choice_group"
    ):
        raise ValueError("Unreviewed legendary Rift artifact cadence")
    available = {tier: list(pool) for tier, pool in pools.items()}
    legendary = wave % cadence == 0
    selected = []
    for _ in range(count):
        weighted = [
            (tier, weight)
            for tier, weight in sorted(weights.items())
            if weight and available[tier]
        ]
        if legendary:
            weighted = [("legendary", 1)] if available.get("legendary") else []
        total = sum(weight for _, weight in weighted)
        if total == 0:
            raise ValueError(
                "Native Rift artifact pool cannot fill this complete group"
            )
        draw = rng.randrange(total)
        for tier, weight in weighted:
            if draw < weight:
                pool = available[tier]
                selected.append(pool.pop(rng.randrange(len(pool))))
                break
            draw -= weight
    return selected


def spawn_artifacts(dispatcher, *, wave):
    """Produce one complete native choice group on an unpublished preview.

    The caller commits the preview, packets and transaction RNG together. Any
    rejection raises; it never publishes a partial group or rerolls a receipt.
    """
    fight = dispatcher.native_retention.fight
    settings = _settings(dispatcher)
    if settings is None:
        return ()
    state = fight.rift_wave_state
    if (
        fight.phase != "active"
        or type(wave) is not int
        or wave < 1
        or wave not in (state["wave"], state["wave"] + 1)
    ):
        raise ValueError("Actual active Rift wave required for artifact production")
    if wave == state["wave"] + 1:
        pending = state.get("pending_wave")
        if (
            not isinstance(pending, dict)
            or pending.get("completed_wave") != state["wave"]
            or set(pending.get("actor_ids", ())) != set(state["wave_actor_ids"])
            or any(
                uid not in fight.actors or fight._in_play(fight.actors[uid])
                for uid in state["wave_actor_ids"]
            )
        ):
            raise ValueError(
                "Successor artifacts require the actual cleared native wave"
            )
    previous = state.get("native_artifact_generation", {}).get(str(wave))
    if previous is not None:
        group = state.get("native_artifact_groups", {}).get(str(wave))
        if (
            previous.get("policy") != PRODUCER_POLICY
            or group is None
            or group["original"]
            != {
                str(uid): ref
                for uid, ref in zip(previous["area_uids"], previous["references"])
            }
        ):
            raise ValueError(
                "Rift artifact generation replay changed its original group"
            )
        for uid in group["remaining"]:
            row = fight.native_effect_areas.get(uid)
            if row is None or row["reference"] != group["original"][str(uid)]:
                raise ValueError(
                    "Unconsumed native Rift artifact lost its original area"
                )
        return tuple(previous["area_uids"])
    if (
        settings.get("placement_policy")
        != "uniform_free_native_reachable_cells_without_replacement"
    ):
        raise ValueError("Unreviewed Rift artifact placement policy")
    players = sorted(
        (
            actor
            for actor in fight.actors.values()
            if actor.controlled
            and actor.team == assigned_roles(fight).player_team
            and fight._in_play(actor)
            and actor.id not in getattr(fight, "native_summon_registrations", {})
        ),
        key=lambda actor: actor.id,
    )
    if not players:
        raise ValueError("Rift artifact production requires a living original player")
    actor = players[0]
    count = settings[
        "ultimate_count"
        if state["catalog"]["type"] == "ULTIMATE_INFINITE_WAVE"
        else "classic_count"
    ]
    if type(count) is not int or count < 2 or count % 2:
        raise ValueError("Native Rift artifact group must contain complete pairs")
    cells = sorted(
        {cell for player in players for cell in _reachable_free_cells(fight, player)}
    )
    if len(cells) < count:
        raise ValueError("Native Rift arena cannot place its complete artifact group")
    rng = getattr(dispatcher, "rift_artifact_rng", None)
    if not callable(getattr(rng, "randrange", None)):
        raise ValueError("Rift artifacts require the accepted transaction RNG")
    template = settings["producer"].get("template_effect_reference")
    effect = dispatcher.effects.get(str(template))
    level = actor.effective_level
    if type(template) is not int or effect is None or effect.get("effect_class") != 315:
        raise ValueError("Missing original native315 Rift producer template")
    evaluated = effect_profile(effect, level)
    if (
        effect.get("children")
        or effect.get("criteria", "").strip()
        or evaluated["probability"] != 100
    ):
        raise ValueError(
            "Native Rift producer template has an unqualified execution guard"
        )
    references = _draw_references(settings, wave, count, rng)
    selected_cells = [cells.pop(rng.randrange(len(cells))) for _ in range(count)]
    identities = []
    for reference, cell in zip(references, selected_cells):
        before = set(fight.native_effect_areas)
        context = transfer_value_context(
            constructed_execution_context().payload(),
            reference,
        )
        if not dispatcher.execute(
            EffectInvocation(
                template,
                level,
                actor.id,
                None,
                cell,
                native_context_hex=context.hex(),
                native_retained_container={"present": False},
            )
        ):
            raise ValueError("Native315 Rift artifact construction was rejected")
        created = set(fight.native_effect_areas) - before
        if len(created) != 1:
            raise ValueError(
                "Native315 did not create exactly one original Rift artifact"
            )
        uid = created.pop()
        row = fight.native_effect_areas[uid]
        if (
            row["reference"] != reference
            or row.get("native_area_contract") != "faM"
            or tuple(row["cell"]) != cell
            or row["owner_id"] != actor.id
            or row["level"] != level
        ):
            raise ValueError(
                "Native Rift artifact creation differs from its source request"
            )
        identities.append(uid)
    register_artifact_group(fight, wave=wave, area_uids=identities)
    state.setdefault("native_artifact_generation", {})[str(wave)] = dict(
        policy=PRODUCER_POLICY,
        wave=wave,
        owner_id=actor.id,
        level=level,
        template_effect_reference=template,
        references=references,
        cells=[list(cell) for cell in selected_cells],
        area_uids=identities,
        source_kind="native_context_area_ref",
    )
    return tuple(identities)
