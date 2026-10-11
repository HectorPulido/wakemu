"""Known native objective facts for NPC criteria, without quest progression.

Native bdO initializes every defined objective as incomplete. Unknown IDs are
not incomplete: native bdM.Bd raises, and our evaluator rejects them too.
GetInstanceId reads the POSITION world identity, represented by map_id here.
"""
from functools import lru_cache
import gzip
import json
from pathlib import Path
import re


@lru_cache(maxsize=1)
def definitions():
    path = (
        Path(__file__).resolve().parents[2]
        / "protocol/npc-objective-definitions.json.gz"
    )
    with gzip.open(path, "rt", encoding="utf-8") as source:
        return frozenset(map(int, json.load(source)["objectives"]))


def load(db, account_id, character_id):
    """Check ownership even when this character has no stored completion facts."""
    owner = db.execute(
        "SELECT id FROM characters WHERE account_id=%s AND id=%s",
        (account_id, character_id),
    ).fetchone()
    if owner is None:
        raise ValueError("NPC objective facts require an owned character")
    rows = db.execute(
        "SELECT objective_id,completed FROM npc_objective_facts "
        "WHERE account_id=%s AND character_id=%s",
        (account_id, character_id),
    ).fetchall()
    return {row["objective_id"]: row["completed"] for row in rows}


def supported(criteria, known=None):
    known = definitions() if known is None else known
    for term in re.split(r"\s+and\s+", criteria.strip()) if criteria else ():
        match = re.fullmatch(
            r"(?:not\s+)?IsAchievementObjectiveComplete\((\d+)\)", term
        )
        if match and int(match[1]) in known:
            continue
        if re.fullmatch(r"GetInstanceId\(\)\s*==\s*\d+", term):
            continue
        if re.fullmatch(r'GetRealLevel\("caster"\)\s*>=\s*\d+', term):
            continue
        return False
    return True


def evaluate(criteria, character, facts, known=None):
    """Evaluate only accredited simple conjunctions; everything else fails closed."""
    if not criteria:
        return True
    known = definitions() if known is None else known
    terms = re.split(r"\s+and\s+", criteria.strip())
    for term in terms:
        match = re.fullmatch(r"(not\s+)?IsAchievementObjectiveComplete\((\d+)\)", term)
        if match:
            objective = int(match[2])
            if objective not in known:
                return False
            complete = facts.get(objective, False)
            if type(complete) is not bool or complete == bool(match[1]):
                return False
            continue
        match = re.fullmatch(r"GetInstanceId\(\)\s*==\s*(\d+)", term)
        if match:
            if character.get("map_id") != int(match[1]):
                return False
            continue
        match = re.fullmatch(r'GetRealLevel\("caster"\)\s*>=\s*(\d+)', term)
        if match:
            # Owned character.level is progression drm, not selected build cmZ.
            level = character.get("level")
            if type(level) is not int or not 1 <= level <= 200 or level < int(match[1]):
                return False
            continue
        return False
    return True
