"""Observed encounter score feedback over actual preview-owned damage receipts.

Rushu gains one final-damage percentage point for each completed 50,000 score.
This reconstructed policy does not change native marker definitions or states.
"""
from .combat_boss_score_policy import native_score_policy


def _outgoing_policy(fight, source):
    profile = getattr(fight, "boss_score_profile", None)
    policy = native_score_policy(profile)
    if policy is None or policy.outgoing_score_step == 0:
        return None
    if str(source.id) not in profile["bosses"]:
        return None  # Players, summons and other NPCs do not inherit the bonus.
    receipt = getattr(fight, "native_npc_initialization_receipts", {}).get(source.id)
    if (
        fight.actors.get(source.id) is not source
        or source.controlled
        or not isinstance(receipt, dict)
        or receipt.get("ref") != policy.reference
        or receipt.get("initialized") is not True
        or not any(
            row.get("state_id") == policy.outgoing_constructor_state
            for row in receipt.get("resolved_states", ())
        )
    ):
        raise ValueError("Outgoing boss score lacks its actual native constructor")
    return policy, profile


def outgoing_score_final(fight, source):
    """Read the current score without accumulating buffs or another counter."""
    selected = _outgoing_policy(fight, source)
    if selected is None:
        return 0
    policy, _ = selected
    from wakfu_server.maps.boss_score_runtime import staged_score

    return staged_score(fight) // policy.outgoing_score_step


def outgoing_level_factor_bp(fight, source):
    """Read the separate multiplier; the damage pipeline owns flags/rounding."""
    selected = _outgoing_policy(fight, source)
    if selected is None:
        return 10000
    from .combat_boss_party_level_policy import validate_level_profile

    return validate_level_profile(selected[1])
