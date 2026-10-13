"""Explicit native actors withheld from ordinary wild encounters.

Native definitions remain intact. Encounter implementations may construct their
real actors through the existing owned native factory; ordinary admin spawning
and automatic activation must respect this separate reversible policy.
"""

MINIGAME_BLOCKED_REFERENCES = frozenset(
    {2782, 2784, 3217, 3893, 3896, 3897, 3942, 3943, 3944}
)
REASON = "minigame_requires_encounter"

# Explicit implemented class-summon policy, not a blanket summon exclusion.
# Monster-owned or dual class/NPC producers remain eligible unless separately
# attested and explicitly classified. Actual summon construction is unchanged.
CLASS_SUMMON_BLOCKED_REFERENCES = frozenset({3251})
CLASS_SUMMON_REASON = "class_summon_implemented"

# Native NPC2437 owns4603 -> 410879 -> 409848 -> family307(120894) ->3251.
# Its real dependent summon route remains pending end-to-end qualification.
NPC_SUMMON_REQUIRED_REFERENCES = frozenset({3251})


def exclusion_reason(reference, *, context="ordinary_wild"):
    if context not in ("ordinary_wild", "native_summon"):
        raise ValueError("Unknown monster policy context")
    if context == "native_summon":
        return None
    if reference in MINIGAME_BLOCKED_REFERENCES:
        return REASON
    if reference in CLASS_SUMMON_BLOCKED_REFERENCES:
        return CLASS_SUMMON_REASON
    return None


def require_ordinary_spawn(reference):
    reason = exclusion_reason(reference)
    if reason == REASON:
        raise ValueError("This monster requires its native minigame encounter")
    if reason == CLASS_SUMMON_REASON:
        raise ValueError(
            "This implemented class summon is unavailable as a wild monster"
        )


def requires_npc_summon_validation(reference):
    """Retain actual monster-owned dependencies despite an ordinary-wild block."""
    return reference in NPC_SUMMON_REQUIRED_REFERENCES
