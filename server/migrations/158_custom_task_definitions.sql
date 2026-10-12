-- Preserve exact custom task semantics and earned history; no reward policy invented.
INSERT INTO settings(name,value) VALUES ('custom_task_definitions', $tasks$[
  {
    "key": "gobball-kills-20",
    "title": "Gobball hunter",
    "description": "Defeat 20 original Gobball-family monsters.",
    "target": 20,
    "enabled": true,
    "predicate": {
      "kind": "original_monster_killed",
      "references": [
        1,
        2,
        3,
        39,
        41,
        44,
        4085,
        4086
      ]
    },
    "rewards": []
  },
  {
    "key": "gobball-seeds-20",
    "title": "Gobball shepherd",
    "description": "Successfully plant 20 Gobball seeds.",
    "target": 20,
    "enabled": true,
    "predicate": {
      "kind": "monster_seed_planted",
      "family_id": 68,
      "seed_reference": 7361,
      "resource_reference": 192
    },
    "rewards": []
  }
]$tasks$::jsonb);
