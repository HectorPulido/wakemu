"""Compose source-qualified native scene grants with existing owned outcomes.

Normal fights preserve the original no-op identity and runtime allocation.
Cleanup uses the same action identifier on a detached settlement candidate.
"""
from copy import deepcopy


def active_scene_grants(fight, *, actor_ids=None):
    """Cheap interest only; each scene independently verifies its real receipt."""
    selected = None if actor_ids is None else frozenset(actor_ids)
    result = []
    abomination = getattr(fight, "native_abomination_quest_grant", None)
    if isinstance(abomination, dict) and abomination.get("status") == "granted":
        identity = abomination.get("source", {}).get("participant_id")
        if selected is None or identity in selected:
            result.append("abomination")
    spirit = getattr(fight, "native_spirit_scene_admission", None)
    if isinstance(spirit, dict) and spirit.get("status") == "granted":
        carriers = spirit.get("carrier_uids", {})
        if not isinstance(carriers, dict):
            raise ValueError("Spirit scene lost its owned carrier identities")
        cleaned = frozenset(spirit.get("cleaned_actor_ids", ()))
        remaining = (
            int(identity) for identity in carriers if int(identity) not in cleaned
        )
        if any(selected is None or identity in selected for identity in remaining):
            result.append("spirit")
    return tuple(result)


def cleanup_scene_grants(fight, runtime_factory, packets, *, actor_ids=None):
    """Remove only selected owned grants; scene validators retain authority."""
    interested = active_scene_grants(fight, actor_ids=actor_ids)
    for scene in interested:
        if scene == "abomination":
            from .combat_abomination_scene import cleanup

            cleanup(fight, runtime_factory, packets)
        elif scene == "spirit":
            from .combat_encounter_objective_spirit import cleanup_spirit_scene

            cleanup_spirit_scene(fight, runtime_factory, packets, actor_ids=actor_ids)
    return bool(interested)


def prepare_outcome(fight, runtime_factory, *, action_id):
    from .combat_consumable_lifecycle import prepare_outcome as consumable_outcome

    candidate, packets = consumable_outcome(
        fight,
        runtime_factory,
        action_id=action_id,
    )
    if not active_scene_grants(candidate):
        return candidate, packets
    if not callable(runtime_factory):
        raise ValueError("Earned scene cleanup requires its actual native runtime")
    if candidate is fight:
        candidate = deepcopy(fight)
    extra = []
    with candidate.effect_resolution():
        cleanup_scene_grants(candidate, runtime_factory(action_id=action_id), extra)
    return candidate, tuple(packets) + tuple(extra)
