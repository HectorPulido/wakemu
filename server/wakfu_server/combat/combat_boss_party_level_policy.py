"""Versioned Rushu party-level reconstruction over frozen owned participants.

The guide establishes245 x1.2. Applying that factor throughout231..245 and
selecting the maximum effective party level are explicit Wakemu policy.
"""
from dataclasses import dataclass
from fractions import Fraction


@dataclass(frozen=True)
class FrozenPartyLevels:
    participants: tuple[tuple[int, int], ...]

    def __post_init__(self):
        if (
            type(self.participants) is not tuple
            or not self.participants
            or any(
                type(row) is not tuple
                or len(row) != 2
                or type(row[0]) is not int
                or type(row[1]) is not int
                or not 1 <= row[1] <= 245
                for row in self.participants
            )
            or tuple(sorted(self.participants)) != self.participants
            or len({identity for identity, _ in self.participants})
            != len(self.participants)
        ):
            raise ValueError("Invalid frozen party levels")

    @property
    def maximum_effective_level(self):
        return max(level for _, level in self.participants)


@dataclass(frozen=True)
class BossPartyLevelPolicy:
    name: str
    reference: int
    baseline_maximum: int
    verified_level: int
    verified_multiplier: Fraction

    def multiplier(self, frozen):
        level = frozen.maximum_effective_level
        if level <= self.baseline_maximum:
            return Fraction(1)
        if level <= self.verified_level:
            return self.verified_multiplier
        raise ValueError("Unsupported frozen party level")


RUSHU_PARTY_LEVEL = BossPartyLevelPolicy(
    "wakemu-rushu-max-effective-231-245-v1",
    5306,
    230,
    245,
    Fraction(6, 5),
)
LEVEL_SOURCE = "guide245_endpoint;reconstructed231-244_and_max_effective_party"
LEVEL_FIELDS = frozenset(
    (
        "party_effective_levels",
        "max_effective_level",
        "outgoing_level_factor_bp",
        "outgoing_level_policy",
        "outgoing_level_source",
    )
)


def freeze_participant_levels(profile, actors):
    """Snapshot only the actual owned players already bound to score authority.

    The maximum-effective-level selection is explicit reconstruction policy,
    not an assertion that the original server used maximum or effective level.
    This function neither publishes the snapshot nor changes an actor.
    """
    identities = profile["player_ids"]
    if (
        not identities
        or any(type(identity) is not int for identity in identities)
        or len(set(identities)) != len(identities)
    ):
        raise ValueError("Party level snapshot requires unique owned participants")
    rows = []
    for identity in sorted(identities):
        actor = actors.get(identity)
        if (
            actor is None
            or actor.id != identity
            or actor.controlled is not True
            or actor.team != profile["player_team"]
            or type(actor.effective_level) is not int
            or not 1 <= actor.effective_level <= 245
        ):
            raise ValueError(
                "Party level snapshot lacks actual effective-level authority"
            )
        rows.append((identity, actor.effective_level))
    return FrozenPartyLevels(tuple(rows))


def freeze_level_profile(profile, actors):
    """Return JSON-compatible facts before any damage, never a live multiplier."""
    from .combat_boss_score_policy import native_score_policy

    policy = native_score_policy(profile)
    if policy is None or policy.reference != RUSHU_PARTY_LEVEL.reference:
        raise ValueError("Rushu party level requires its typed encounter profile")
    frozen = freeze_participant_levels(profile, actors)
    return dict(
        party_effective_levels=[list(row) for row in frozen.participants],
        max_effective_level=frozen.maximum_effective_level,
        outgoing_level_factor_bp=int(RUSHU_PARTY_LEVEL.multiplier(frozen) * 10000),
        outgoing_level_policy=RUSHU_PARTY_LEVEL.name,
        outgoing_level_source=LEVEL_SOURCE,
    )


def validate_level_profile(profile):
    """Validate frozen facts without recalculating levels from current actors."""
    from .combat_boss_score_policy import native_score_policy

    policy = native_score_policy(profile)
    if (
        policy is None
        or policy.reference != RUSHU_PARTY_LEVEL.reference
        or not LEVEL_FIELDS <= profile.keys()
        or profile["outgoing_level_policy"] != RUSHU_PARTY_LEVEL.name
        or profile["outgoing_level_source"] != LEVEL_SOURCE
    ):
        raise ValueError("Missing versioned frozen Rushu party-level policy")
    rows = profile["party_effective_levels"]
    if type(rows) is not list or any(type(row) is not list for row in rows):
        raise ValueError("Invalid JSON frozen Rushu party levels")
    frozen = FrozenPartyLevels(tuple(tuple(row) for row in rows))
    identities = profile["player_ids"]
    if (
        not identities
        or any(type(identity) is not int for identity in identities)
        or len(set(identities)) != len(identities)
        or tuple(sorted(identities))
        != tuple(identity for identity, _ in frozen.participants)
        or type(profile["max_effective_level"]) is not int
        or profile["max_effective_level"] != frozen.maximum_effective_level
        or type(profile["outgoing_level_factor_bp"]) is not int
        or profile["outgoing_level_factor_bp"]
        != int(RUSHU_PARTY_LEVEL.multiplier(frozen) * 10000)
    ):
        raise ValueError("Frozen Rushu party-level binding or factor changed")
    return profile["outgoing_level_factor_bp"]
