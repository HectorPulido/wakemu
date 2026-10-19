"""Explicit native actors withheld from ordinary wild encounters.

Native definitions remain intact. Encounter implementations may construct their
real actors through the existing owned native factory; ordinary admin spawning
and automatic activation must respect this separate reversible policy.
"""

# Original source-proven baseline registry. Preserve this public historical
# inventory contract; current policy consumers use effective_minigame_references.
MINIGAME_BLOCKED_REFERENCES = frozenset(
    {2782, 2784, 3217, 3893, 3896, 3897, 3942, 3943, 3944}
)
# Installed quest1264/objective2393: the DJ dance/beatbox challenge. These two
# exact actors require its four native colored floor areas and encounter setup.
# Ordinary Bilbyboy combat variants are not included by name or family.
QUEST_MINIGAME_BLOCKED_REFERENCES = frozenset({2502, 2518})
# Native Sokoban push/undo books own paired puzzle areas and exact crate/state
# guards: 3891 (1032/1033,3889/4080),4113 (1119/1121,4112/4426),
# 5030 (1032/1033,5029/5871). Installed scenario2382 supplies puzzle lifecycle.
SOKOBAN_MINIGAME_BLOCKED_REFERENCES = frozenset({3891, 4113, 5030})
# Native Bworkball family587: reception/touchdown requires ball breed2783;
# pass excludes the ball and targets an ally. Preserve these encounter actors.
BWORKBALL_MINIGAME_BLOCKED_REFERENCES = frozenset({2780, 2789, 2790, 2791})
# Installed mercenary Riktus push/undo puzzle and Moogrr cosmetic floor
# selection challenge require their native encounter setup and victory scripts.
MERCENARY_MINIGAME_BLOCKED_REFERENCES = frozenset({4794, 4838})
REASON = "minigame_requires_encounter"

# Explicit user inventory exclusion: these native definitions are named
# "Monstruo admin genérico". Preserve source data and native construction.
ADMIN_TEMPLATE_BLOCKED_REFERENCES = frozenset({2381, 3070})
ADMIN_TEMPLATE_REASON = "admin_template_excluded_by_user"

# Native 5347 starts with zero WP and has no owned WP producer, while every
# action costs WP. User excludes such actors rather than granting resources.
NO_RESOURCE_PRODUCER_BLOCKED_REFERENCES = frozenset({5347})
NO_RESOURCE_PRODUCER_REASON = "unpayable_native_book_without_resource_producer"

# Native state7583 ->341714/341730/341731/341733 ->307(341734,341735)
# creates these turnless Tentacles. They remain available to actual native
# summon factories, but are not independent ordinary population candidates.
# These additional published307 targets have native world property116,
# eHQ.SUMMON_WITH_DROP. Keep the explicit positive inventory: ordinary Tofu6
# and other dual natural/summon forms do not acquire this exclusion.
NPC_SUMMON_ONLY_BLOCKED_REFERENCES = frozenset(
    {4189, 4194, 4195, 4196, 4539, 5034, 5403, 5404}
)
NPC_SUMMON_ONLY_REASON = "npc_summon_only"

# Explicit implemented class-summon policy, not a blanket summon exclusion.
# Monster-owned or dual class/NPC producers remain eligible unless separately
# attested and explicitly classified. Actual summon construction is unchanged.
CLASS_SUMMON_BLOCKED_REFERENCES = frozenset({3251, 4559})
CLASS_SUMMON_REASON = "class_summon_implemented"

# Explicit implemented class routes; preserve the original public baseline set.
# This policy does not assert absence of unindexed or future NPC producers.
ADDITIONAL_IMPLEMENTED_CLASS_SUMMON_REFERENCES = frozenset(
    {
        182,
        1236,
        1380,
        1381,
        1382,
        1383,
        1384,
        1620,
        1775,
        3745,
        3746,
        3747,
        3748,
        3749,
        3750,
        3751,
        5528,
        5533,
    }
)


def effective_class_summon_references():
    return (
        CLASS_SUMMON_BLOCKED_REFERENCES | ADDITIONAL_IMPLEMENTED_CLASS_SUMMON_REFERENCES
    )


def effective_ordinary_summon_only_references():
    """Positively classified class/NPC summons excluded from wild population."""
    return effective_class_summon_references() | NPC_SUMMON_ONLY_BLOCKED_REFERENCES


# Implemented Uginak6286 -> native307 effect240997 -> profile4559.
# This ordinary-wild policy does not claim universal NPC exclusivity; actual
# native summon construction remains unrestricted for future proven producers.

# Native NPC2437 owns4603 -> 410879 -> 409848 -> family307(120894) ->3251.
# Its real dependent summon route remains pending end-to-end qualification.
# Sadida class/NPC dual profiles3745/3748/3750 retain all positively indexed
# NPC creators. Blocking ordinary wild spawning does not complete these paths.
NPC_SUMMON_REQUIRED_REFERENCES = (
    frozenset({3251, 3745, 3748, 3750}) | NPC_SUMMON_ONLY_BLOCKED_REFERENCES
)


def effective_minigame_references():
    """Current reversible policy, separate from the original baseline inventory."""
    return (
        MINIGAME_BLOCKED_REFERENCES
        | QUEST_MINIGAME_BLOCKED_REFERENCES
        | SOKOBAN_MINIGAME_BLOCKED_REFERENCES
        | BWORKBALL_MINIGAME_BLOCKED_REFERENCES
        | MERCENARY_MINIGAME_BLOCKED_REFERENCES
    )


def effective_inventory():
    """All current reversible ordinary-wild blocks and their explicit reasons."""
    return tuple(
        dict(reference=reference, reason=exclusion_reason(reference))
        for reference in sorted(
            effective_minigame_references()
            | effective_class_summon_references()
            | ADMIN_TEMPLATE_BLOCKED_REFERENCES
            | NO_RESOURCE_PRODUCER_BLOCKED_REFERENCES
            | NPC_SUMMON_ONLY_BLOCKED_REFERENCES
        )
    )


def exclusion_reason(reference, *, context="ordinary_wild"):
    if context not in ("ordinary_wild", "native_summon"):
        raise ValueError("Unknown monster policy context")
    if context == "native_summon":
        return None
    if reference in ADMIN_TEMPLATE_BLOCKED_REFERENCES:
        return ADMIN_TEMPLATE_REASON
    if reference in NO_RESOURCE_PRODUCER_BLOCKED_REFERENCES:
        return NO_RESOURCE_PRODUCER_REASON
    if reference in NPC_SUMMON_ONLY_BLOCKED_REFERENCES:
        return NPC_SUMMON_ONLY_REASON
    if reference in effective_minigame_references():
        return REASON
    if reference in effective_class_summon_references():
        return CLASS_SUMMON_REASON
    return None


def require_ordinary_spawn(reference):
    reason = exclusion_reason(reference)
    if reason == ADMIN_TEMPLATE_REASON:
        raise ValueError("This admin template is excluded from ordinary monsters")
    if reason == NO_RESOURCE_PRODUCER_REASON:
        raise ValueError("This monster cannot pay for its native actions")
    if reason == NPC_SUMMON_ONLY_REASON:
        raise ValueError("This NPC requires its native summon creator")
    if reason == REASON:
        raise ValueError("This monster requires its native minigame encounter")
    if reason == CLASS_SUMMON_REASON:
        raise ValueError(
            "This implemented class summon is unavailable as a wild monster"
        )


def requires_npc_summon_validation(reference):
    """Retain actual monster-owned dependencies despite an ordinary-wild block."""
    return reference in NPC_SUMMON_REQUIRED_REFERENCES


def ordinary_group_members(members, *, instance_id=0):
    """Project public ordinary groups without discarding valid mixed members.

    Private encounter rosters and actual summon construction own their separate
    native producers. Existing public rows can remain durably intact while all
    world publication and claim consumers see the same eligible composition.
    """
    if instance_id != 0:
        return tuple(members)
    blocked = effective_ordinary_summon_only_references()
    return tuple(member for member in members if member["ref"] not in blocked)
