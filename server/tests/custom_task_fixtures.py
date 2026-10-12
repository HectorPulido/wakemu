"""Explicit test-only local task fixtures; production policy lives in PostgreSQL."""
import copy

_DEFINITIONS = [
    {
        "key": "gobball-kills-20",
        "title": "Gobball hunter",
        "description": "Defeat 20 original Gobball-family monsters.",
        "target": 20,
        "enabled": True,
        "predicate": {
            "kind": "original_monster_killed",
            "references": [1, 2, 3, 39, 41, 44, 4085, 4086],
        },
        "rewards": [],
    },
    {
        "key": "gobball-seeds-20",
        "title": "Gobball shepherd",
        "description": "Successfully plant 20 Gobball seeds.",
        "target": 20,
        "enabled": True,
        "predicate": {
            "kind": "monster_seed_planted",
            "family_id": 68,
            "seed_reference": 7361,
            "resource_reference": 192,
        },
        "rewards": [],
    },
]


def task_definitions():
    return copy.deepcopy(_DEFINITIONS)
