"""Explicit reconstructed score policies with reviewed native terminal states.

Only these descriptors bypass the older generic survival termination. The
records do not evaluate damage or execute states; shared native runtime does.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class NativeBossScorePolicy:
    name: str
    reference: int
    success_state: int | None
    minimum_score: int
    scoring_tables: int
    outgoing_score_step: int = 0
    outgoing_constructor_state: int = 0
    drop_score_step: int = 0
    drop_bonus_bp: int = 0
    drop_source: str = ""
    loot_minimum_score: int = 0
    terminal_source: str = ""


NOX_SCORE = NativeBossScorePolicy(
    "wakemu-nox-score-1.92-v1",
    5664,
    9031,
    3000000,
    10,
    drop_score_step=50000,
    drop_bonus_bp=50,
    drop_source="methodwakfu-nox-1.92-2026-09-23",
)
RUSHU_SCORE = NativeBossScorePolicy(
    "wakemu-rushu-score-v1",
    5306,
    7110,
    3000000,
    20,
    50000,
    7000,
)

OGREST_SCORE = NativeBossScorePolicy(
    "wakemu-ogrest-six-phases-v1",
    4378,
    None,
    0,
    18,
    loot_minimum_score=1000000,
    terminal_source="https://wakfu.guide/ogrest/",
)


def native_score_policy(profile):
    """Resolve only the exact versioned descriptor profile, never a name match."""
    if not profile:
        return None
    for policy in (NOX_SCORE, RUSHU_SCORE, OGREST_SCORE):
        if profile.get("encounter_controller") != policy.name:
            continue
        bosses = profile.get("bosses", {})
        if len(bosses) != 1 or any(
            row.get("reference") != policy.reference for row in bosses.values()
        ):
            raise ValueError("Native score policy disagrees with its boss descriptor")
        minimum = profile.get("minimum_score")
        if type(minimum) is not int or minimum < policy.minimum_score:
            raise ValueError("Native score policy lost its reviewed minimum")
        if policy == OGREST_SCORE and (
            minimum != 0
            or profile.get("round_limit") != policy.scoring_tables
            or profile.get("loot_minimum_score") != policy.loot_minimum_score
            or profile.get("terminal_table_limit") != 20
            or profile.get("terminal_source") != policy.terminal_source
        ):
            raise ValueError(
                "Ogrest result policy lost its reviewed exit/loot contract"
            )
        return policy
    return None


def score_drop_rate_bp(policy, score):
    """Guide reconstruction: completed score steps, then exact basis points."""
    if type(score) is not int or score < 0:
        raise ValueError("Invalid terminal boss score")
    if not policy.drop_score_step:
        return 10000
    return 10000 + (score // policy.drop_score_step) * policy.drop_bonus_bp
