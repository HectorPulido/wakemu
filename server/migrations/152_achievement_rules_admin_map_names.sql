-- Preserve reviewed policies and native labels; no achievement activation change.
INSERT INTO settings(name,value) VALUES
('achievement_qualified_rules', $rules${
  "schema_version": 1,
  "policy": "reviewed_local_native_identity_v1",
  "source_sha256": {
    "docs/reports/achievements/installed-definition-ledger.json": "be72ff00ba36765ee365b489444ed5756a5c1249e43d07be6d73dd0dfe055051",
    "docs/reports/dungeons/inventory.json": "e16b0cfd377b098fc25afcbd0aa40fbfa70dc816ca3c764bc9853101aea7ee65",
    ".runtime/local/item-pricing-20261011/monster-metadata-source.json": "3c85bb9f77f9c1a2a3d6d053169d10c9591150f2e9f460446c0e14ad9c3f6998",
    ".runtime/local/item-pricing-20261011/monster-source.json": "b3fef4fbb5000f1b0b0d0d686823fc3edf84e8f942f1da2f547076099293897d"
  },
  "variable_bindings": [
    {
      "variable_id": 51,
      "breed_id": 39,
      "native_family_id": 68,
      "native_species_pool_dungeon_id": 90,
      "native_name_es": "Jalat\u00edn blanco",
      "authority": "proposed_explicit_local_policy",
      "exclusions": "No fuzzy aliases, no Neo variants, no summons/duplicates; original authoritative victory roster only."
    },
    {
      "variable_id": 52,
      "breed_id": 2,
      "native_family_id": 68,
      "native_species_pool_dungeon_id": 90,
      "native_name_es": "Jalat\u00edn negro",
      "authority": "proposed_explicit_local_policy",
      "exclusions": "No fuzzy aliases, no Neo variants, no summons/duplicates; original authoritative victory roster only."
    },
    {
      "variable_id": 53,
      "breed_id": 1,
      "native_family_id": 68,
      "native_species_pool_dungeon_id": 90,
      "native_name_es": "Jalat\u00f3",
      "authority": "proposed_explicit_local_policy",
      "exclusions": "No fuzzy aliases, no Neo variants, no summons/duplicates; original authoritative victory roster only."
    },
    {
      "variable_id": 54,
      "breed_id": 41,
      "native_family_id": 68,
      "native_species_pool_dungeon_id": 90,
      "native_name_es": "Jalal\u00ednea",
      "authority": "proposed_explicit_local_policy",
      "exclusions": "No fuzzy aliases, no Neo variants, no summons/duplicates; original authoritative victory roster only."
    },
    {
      "variable_id": 55,
      "breed_id": 3,
      "native_family_id": 68,
      "native_species_pool_dungeon_id": 90,
      "native_name_es": "Jefe de guerra jalat\u00f3",
      "authority": "proposed_explicit_local_policy",
      "exclusions": "No fuzzy aliases, no Neo variants, no summons/duplicates; original authoritative victory roster only."
    },
    {
      "variable_id": 109,
      "breed_id": 44,
      "native_family_id": 68,
      "native_species_pool_dungeon_id": 90,
      "native_name_es": "Jalat\u00f3 Real",
      "authority": "proposed_explicit_local_policy",
      "exclusions": "No fuzzy aliases, no Neo variants, no summons/duplicates; original authoritative victory roster only."
    },
    {
      "variable_id": 56,
      "breed_id": 6,
      "native_family_id": 81,
      "native_species_pool_dungeon_id": 27,
      "native_name_es": "Beb\u00e9 tofu",
      "authority": "proposed_explicit_local_policy",
      "exclusions": "No fuzzy aliases, no Neo variants, no summons/duplicates; original authoritative victory roster only."
    },
    {
      "variable_id": 57,
      "breed_id": 4,
      "native_family_id": 81,
      "native_species_pool_dungeon_id": 27,
      "native_name_es": "Tofu",
      "authority": "proposed_explicit_local_policy",
      "exclusions": "No fuzzy aliases, no Neo variants, no summons/duplicates; original authoritative victory roster only."
    },
    {
      "variable_id": 58,
      "breed_id": 5,
      "native_family_id": 81,
      "native_species_pool_dungeon_id": 27,
      "native_name_es": "Tofona",
      "authority": "proposed_explicit_local_policy",
      "exclusions": "No fuzzy aliases, no Neo variants, no summons/duplicates; original authoritative victory roster only."
    },
    {
      "variable_id": 59,
      "breed_id": 704,
      "native_family_id": 81,
      "native_species_pool_dungeon_id": 27,
      "native_name_es": "Gorditofu",
      "authority": "proposed_explicit_local_policy",
      "exclusions": "No fuzzy aliases, no Neo variants, no summons/duplicates; original authoritative victory roster only."
    },
    {
      "variable_id": 108,
      "breed_id": 1259,
      "native_family_id": 81,
      "native_species_pool_dungeon_id": 27,
      "native_name_es": "Tofu Real",
      "authority": "proposed_explicit_local_policy",
      "exclusions": "No fuzzy aliases, no Neo variants, no summons/duplicates; original authoritative victory roster only."
    },
    {
      "variable_id": 254,
      "breed_id": 2201,
      "native_family_id": 481,
      "native_names": {
        "fr": "Paquet Cadeau",
        "en": "Gift Package",
        "es": "Regalo"
      },
      "native_family_names": {
        "fr": "Cadeaux de Nowel",
        "en": "Kwismas Gifts",
        "es": "Regalos de Nawidad"
      },
      "authority": "reviewed_explicit_local_policy",
      "exclusions": []
    },
    {
      "variable_id": 254,
      "breed_id": 2224,
      "native_family_id": 481,
      "native_names": {
        "fr": "Paquet Cadeau",
        "en": "Gift Package",
        "es": "Regalo"
      },
      "native_family_names": {
        "fr": "Cadeaux de Nowel",
        "en": "Kwismas Gifts",
        "es": "Regalos de Nawidad"
      },
      "authority": "reviewed_explicit_local_policy",
      "exclusions": []
    },
    {
      "variable_id": 254,
      "breed_id": 2231,
      "native_family_id": 481,
      "native_names": {
        "fr": "Paquet Cadeau",
        "en": "Gift Package",
        "es": "Regalo"
      },
      "native_family_names": {
        "fr": "Cadeaux de Nowel",
        "en": "Kwismas Gifts",
        "es": "Regalos de Nawidad"
      },
      "authority": "reviewed_explicit_local_policy",
      "exclusions": []
    },
    {
      "variable_id": 254,
      "breed_id": 2232,
      "native_family_id": 481,
      "native_names": {
        "fr": "Paquet Cadeau",
        "en": "Gift Package",
        "es": "Regalo"
      },
      "native_family_names": {
        "fr": "Cadeaux de Nowel",
        "en": "Kwismas Gifts",
        "es": "Regalos de Nawidad"
      },
      "authority": "reviewed_explicit_local_policy",
      "exclusions": []
    },
    {
      "variable_id": 254,
      "breed_id": 2233,
      "native_family_id": 481,
      "native_names": {
        "fr": "Paquet Cadeau",
        "en": "Gift Package",
        "es": "Regalo"
      },
      "native_family_names": {
        "fr": "Cadeaux de Nowel",
        "en": "Kwismas Gifts",
        "es": "Regalos de Nawidad"
      },
      "authority": "reviewed_explicit_local_policy",
      "exclusions": []
    },
    {
      "variable_id": 254,
      "breed_id": 2234,
      "native_family_id": 481,
      "native_names": {
        "fr": "Paquet Cadeau",
        "en": "Gift Package",
        "es": "Regalo"
      },
      "native_family_names": {
        "fr": "Cadeaux de Nowel",
        "en": "Kwismas Gifts",
        "es": "Regalos de Nawidad"
      },
      "authority": "reviewed_explicit_local_policy",
      "exclusions": []
    },
    {
      "variable_id": 254,
      "breed_id": 2874,
      "native_family_id": 481,
      "native_names": {
        "fr": "Paquet Cadeau",
        "en": "Gift Package",
        "es": "Regalo"
      },
      "native_family_names": {
        "fr": "Cadeaux de Nowel",
        "en": "Kwismas Gifts",
        "es": "Regalos de Nawidad"
      },
      "authority": "reviewed_explicit_local_policy",
      "exclusions": []
    },
    {
      "variable_id": 254,
      "breed_id": 2875,
      "native_family_id": 481,
      "native_names": {
        "fr": "Paquet Cadeau",
        "en": "Gift Package",
        "es": "Regalo"
      },
      "native_family_names": {
        "fr": "Cadeaux de Nowel",
        "en": "Kwismas Gifts",
        "es": "Regalos de Nawidad"
      },
      "authority": "reviewed_explicit_local_policy",
      "exclusions": []
    },
    {
      "variable_id": 362,
      "breed_id": 2754,
      "native_family_id": 839,
      "native_names": {
        "fr": "Goule d'Halouine",
        "en": "Al Howin Ghoul",
        "es": "Ghul de Halu\u00edn"
      },
      "native_family_names": {
        "fr": "Halouine",
        "en": "Al Howin",
        "es": "Halu\u00edn"
      },
      "authority": "reviewed_explicit_local_policy",
      "exclusions": []
    },
    {
      "variable_id": 224,
      "breed_id": 2048,
      "native_family_id": 839,
      "native_names": {
        "fr": "Bouftou d'Halouine",
        "en": "Al Howin Gobball",
        "es": "Jalat\u00f3 de Halu\u00edn"
      },
      "native_family_names": {
        "fr": "Halouine",
        "en": "Al Howin",
        "es": "Halu\u00edn"
      },
      "authority": "reviewed_explicit_local_policy",
      "exclusions": []
    },
    {
      "variable_id": 224,
      "breed_id": 2092,
      "native_family_id": 839,
      "native_names": {
        "fr": "Bouftou d'Halouine",
        "en": "Al Howin Gobball",
        "es": "Jalat\u00f3 de Halu\u00edn"
      },
      "native_family_names": {
        "fr": "Halouine",
        "en": "Al Howin",
        "es": "Halu\u00edn"
      },
      "authority": "reviewed_explicit_local_policy",
      "exclusions": []
    },
    {
      "variable_id": 224,
      "breed_id": 2104,
      "native_family_id": 839,
      "native_names": {
        "fr": "Bouftou d'Halouine",
        "en": "Al Howin Gobball",
        "es": "Jalat\u00f3 de Halu\u00edn"
      },
      "native_family_names": {
        "fr": "Halouine",
        "en": "Al Howin",
        "es": "Halu\u00edn"
      },
      "authority": "reviewed_explicit_local_policy",
      "exclusions": []
    },
    {
      "variable_id": 559,
      "breed_id": 3644,
      "native_family_id": 745,
      "native_names": {
        "fr": "Mama Wapin",
        "en": "Mama Wodent",
        "es": "Mam\u00e1 wonejo"
      },
      "native_family_names": {
        "fr": "Pwak",
        "en": "Fleaster",
        "es": "Pazcuak"
      },
      "authority": "reviewed_explicit_local_policy",
      "exclusions": []
    },
    {
      "variable_id": 559,
      "breed_id": 3645,
      "native_family_id": 745,
      "native_names": {
        "fr": "Ti Wapin",
        "en": "Tiwodent",
        "es": "Pekewonejo"
      },
      "native_family_names": {
        "fr": "Pwak",
        "en": "Fleaster",
        "es": "Pazcuak"
      },
      "authority": "reviewed_explicit_local_policy",
      "exclusions": []
    },
    {
      "variable_id": 559,
      "breed_id": 3646,
      "native_family_id": 745,
      "native_names": {
        "fr": "Wapin",
        "en": "Wodent",
        "es": "Wonejo"
      },
      "native_family_names": {
        "fr": "Pwak",
        "en": "Fleaster",
        "es": "Pazcuak"
      },
      "authority": "reviewed_explicit_local_policy",
      "exclusions": []
    },
    {
      "variable_id": 540,
      "breed_id": 4018,
      "native_family_id": 817,
      "native_names": {
        "fr": "Mimi P\u00e2ti",
        "en": "Mimi Sk\u00e4te",
        "es": "Torrejill\u00e4 de \u00e4ren\u00e4"
      },
      "native_family_names": {
        "fr": "La M\u00e2dr\u00e2gue",
        "en": "La M\u00e4drague",
        "es": "La \u00c4lm\u00e4dr\u00e4b\u00e4"
      },
      "authority": "reviewed_explicit_local_policy",
      "exclusions": []
    },
    {
      "variable_id": 540,
      "breed_id": 4019,
      "native_family_id": 817,
      "native_names": {
        "fr": "P\u00e2ti Bulleur",
        "en": "Bubble Sk\u00e4te",
        "es": "M\u00e4gd\u00e4ren\u00e4"
      },
      "native_family_names": {
        "fr": "La M\u00e2dr\u00e2gue",
        "en": "La M\u00e4drague",
        "es": "La \u00c4lm\u00e4dr\u00e4b\u00e4"
      },
      "authority": "reviewed_explicit_local_policy",
      "exclusions": []
    },
    {
      "variable_id": 540,
      "breed_id": 4020,
      "native_family_id": 817,
      "native_names": {
        "fr": "P\u00e2ti Imp\u00e9ri\u00e2l",
        "en": "Imperi\u00e4l Sk\u00e4te",
        "es": "Torrej\u00e4 imperi\u00e4l"
      },
      "native_family_names": {
        "fr": "La M\u00e2dr\u00e2gue",
        "en": "La M\u00e4drague",
        "es": "La \u00c4lm\u00e4dr\u00e4b\u00e4"
      },
      "authority": "reviewed_explicit_local_policy",
      "exclusions": []
    },
    {
      "variable_id": 540,
      "breed_id": 4022,
      "native_family_id": 817,
      "native_names": {
        "fr": "P\u00e2ti Noir",
        "en": "Bl\u00e4ck Sk\u00e4te",
        "es": "P\u00e4tinoj\u00e4ldre"
      },
      "native_family_names": {
        "fr": "La M\u00e2dr\u00e2gue",
        "en": "La M\u00e4drague",
        "es": "La \u00c4lm\u00e4dr\u00e4b\u00e4"
      },
      "authority": "reviewed_explicit_local_policy",
      "exclusions": []
    },
    {
      "variable_id": 554,
      "breed_id": 4212,
      "native_family_id": 880,
      "native_names": {
        "fr": "Bouftou Patraque",
        "en": "Potrick Gobball",
        "es": "Jalat\u00f3 de San Pat\u00edrico"
      },
      "native_family_names": {
        "fr": "Fin Patraque",
        "en": "Saint Potrick",
        "es": "San Pat\u00edrico"
      },
      "authority": "reviewed_explicit_local_policy",
      "exclusions": []
    },
    {
      "variable_id": 697,
      "breed_id": 4852,
      "native_family_id": 839,
      "native_names": {
        "fr": "Yokai",
        "en": "Yokai",
        "es": "Yokai"
      },
      "native_family_names": {
        "fr": "Halouine",
        "en": "Al Howin",
        "es": "Halu\u00edn"
      },
      "authority": "reviewed_explicit_local_policy",
      "exclusions": []
    }
  ],
  "definitions": [
    {
      "definition_id": 232,
      "event": {
        "kind": "owned_final_dungeon_victory",
        "native_dungeon_id": 26
      },
      "objectives": [
        {
          "objective_id": 1013,
          "dungeon_id": 26
        }
      ],
      "prerequisites": [],
      "rewards": [
        {
          "aeV": 5,
          "ckk": false,
          "ckl": [
            20672,
            10
          ],
          "d": 4608,
          "native_class": "aJP",
          "native_type_name": "GIVE_PLAYER_ITEM"
        }
      ],
      "authority": "proposed_explicit_local_policy_not_activated",
      "source_criteria": {
        "aHe": "",
        "cjI": ""
      },
      "native_repeatable": false,
      "native_period": 0,
      "mission_dependency": false
    },
    {
      "definition_id": 238,
      "event": {
        "kind": "original_breed_kill",
        "variable_ids": [
          51,
          52,
          53
        ]
      },
      "objectives": [
        {
          "objective_id": 617,
          "variable_id": 51,
          "breed_id": 39,
          "operator": "==",
          "threshold": 1
        },
        {
          "objective_id": 618,
          "variable_id": 52,
          "breed_id": 2,
          "operator": "==",
          "threshold": 1
        },
        {
          "objective_id": 619,
          "variable_id": 53,
          "breed_id": 1,
          "operator": "==",
          "threshold": 1
        }
      ],
      "prerequisites": [],
      "rewards": [
        {
          "aeV": 5,
          "ckk": false,
          "ckl": [
            7361,
            5
          ],
          "d": 284,
          "native_class": "aJP",
          "native_type_name": "GIVE_PLAYER_ITEM"
        }
      ],
      "authority": "proposed_explicit_local_policy_not_activated",
      "source_criteria": {
        "aHe": "",
        "cjI": ""
      },
      "native_repeatable": false,
      "native_period": 0,
      "mission_dependency": false
    },
    {
      "definition_id": 239,
      "event": {
        "kind": "original_breed_kill",
        "variable_ids": [
          51,
          52,
          53,
          54,
          55
        ]
      },
      "objectives": [
        {
          "objective_id": 620,
          "variable_id": 51,
          "breed_id": 39,
          "operator": "==",
          "threshold": 5
        },
        {
          "objective_id": 621,
          "variable_id": 52,
          "breed_id": 2,
          "operator": "==",
          "threshold": 5
        },
        {
          "objective_id": 622,
          "variable_id": 53,
          "breed_id": 1,
          "operator": "==",
          "threshold": 5
        },
        {
          "objective_id": 623,
          "variable_id": 54,
          "breed_id": 41,
          "operator": "==",
          "threshold": 5
        },
        {
          "objective_id": 624,
          "variable_id": 55,
          "breed_id": 3,
          "operator": "==",
          "threshold": 1
        }
      ],
      "prerequisites": [
        238
      ],
      "rewards": [
        {
          "aeV": 5,
          "ckk": false,
          "ckl": [
            2021,
            1
          ],
          "d": 285,
          "native_class": "aJP",
          "native_type_name": "GIVE_PLAYER_ITEM"
        }
      ],
      "authority": "proposed_explicit_local_policy_not_activated",
      "source_criteria": {
        "aHe": "IsAchievementComplete(238)",
        "cjI": ""
      },
      "native_repeatable": false,
      "native_period": 0,
      "mission_dependency": false
    },
    {
      "definition_id": 240,
      "event": {
        "kind": "original_breed_kill",
        "variable_ids": [
          51,
          52,
          53,
          54,
          55
        ]
      },
      "objectives": [
        {
          "objective_id": 625,
          "variable_id": 51,
          "breed_id": 39,
          "operator": "==",
          "threshold": 10
        },
        {
          "objective_id": 626,
          "variable_id": 52,
          "breed_id": 2,
          "operator": "==",
          "threshold": 10
        },
        {
          "objective_id": 627,
          "variable_id": 53,
          "breed_id": 1,
          "operator": "==",
          "threshold": 10
        },
        {
          "objective_id": 628,
          "variable_id": 54,
          "breed_id": 41,
          "operator": "==",
          "threshold": 10
        },
        {
          "objective_id": 629,
          "variable_id": 55,
          "breed_id": 3,
          "operator": "==",
          "threshold": 10
        }
      ],
      "prerequisites": [
        239
      ],
      "rewards": [
        {
          "aeV": 5,
          "ckk": false,
          "ckl": [
            2024,
            1
          ],
          "d": 286,
          "native_class": "aJP",
          "native_type_name": "GIVE_PLAYER_ITEM"
        }
      ],
      "authority": "proposed_explicit_local_policy_not_activated",
      "source_criteria": {
        "aHe": "IsAchievementComplete(239)",
        "cjI": ""
      },
      "native_repeatable": false,
      "native_period": 0,
      "mission_dependency": false
    },
    {
      "definition_id": 241,
      "event": {
        "kind": "original_breed_kill",
        "variable_ids": [
          51,
          52,
          53,
          54,
          55
        ]
      },
      "objectives": [
        {
          "objective_id": 630,
          "variable_id": 51,
          "breed_id": 39,
          "operator": "==",
          "threshold": 50
        },
        {
          "objective_id": 631,
          "variable_id": 52,
          "breed_id": 2,
          "operator": "==",
          "threshold": 50
        },
        {
          "objective_id": 632,
          "variable_id": 53,
          "breed_id": 1,
          "operator": "==",
          "threshold": 50
        },
        {
          "objective_id": 633,
          "variable_id": 54,
          "breed_id": 41,
          "operator": "==",
          "threshold": 50
        },
        {
          "objective_id": 634,
          "variable_id": 55,
          "breed_id": 3,
          "operator": "==",
          "threshold": 50
        }
      ],
      "prerequisites": [
        240
      ],
      "rewards": [
        {
          "aeV": 2,
          "ckk": false,
          "ckl": [
            98
          ],
          "d": 287,
          "native_class": "aJP",
          "native_type_name": "GIVE_PLAYER_TITLE"
        },
        {
          "aeV": 5,
          "ckk": false,
          "ckl": [
            9812,
            1
          ],
          "d": 288,
          "native_class": "aJP",
          "native_type_name": "GIVE_PLAYER_ITEM"
        }
      ],
      "authority": "proposed_explicit_local_policy_not_activated",
      "source_criteria": {
        "aHe": "IsAchievementComplete(240)",
        "cjI": ""
      },
      "native_repeatable": false,
      "native_period": 0,
      "mission_dependency": false
    },
    {
      "definition_id": 242,
      "event": {
        "kind": "original_breed_kill",
        "variable_ids": [
          51,
          52,
          53,
          54,
          55,
          109
        ]
      },
      "objectives": [
        {
          "objective_id": 635,
          "variable_id": 51,
          "breed_id": 39,
          "operator": "==",
          "threshold": 100
        },
        {
          "objective_id": 636,
          "variable_id": 52,
          "breed_id": 2,
          "operator": "==",
          "threshold": 100
        },
        {
          "objective_id": 637,
          "variable_id": 53,
          "breed_id": 1,
          "operator": "==",
          "threshold": 100
        },
        {
          "objective_id": 638,
          "variable_id": 54,
          "breed_id": 41,
          "operator": "==",
          "threshold": 100
        },
        {
          "objective_id": 639,
          "variable_id": 55,
          "breed_id": 3,
          "operator": "==",
          "threshold": 100
        },
        {
          "objective_id": 817,
          "variable_id": 109,
          "breed_id": 44,
          "operator": "==",
          "threshold": 1
        }
      ],
      "prerequisites": [
        241
      ],
      "rewards": [
        {
          "aeV": 5,
          "ckk": false,
          "ckl": [
            10309,
            1
          ],
          "d": 290,
          "native_class": "aJP",
          "native_type_name": "GIVE_PLAYER_ITEM"
        }
      ],
      "authority": "proposed_explicit_local_policy_not_activated",
      "source_criteria": {
        "aHe": "IsAchievementComplete(241)",
        "cjI": ""
      },
      "native_repeatable": false,
      "native_period": 0,
      "mission_dependency": false
    },
    {
      "definition_id": 243,
      "event": {
        "kind": "original_breed_kill",
        "variable_ids": [
          56,
          57
        ]
      },
      "objectives": [
        {
          "objective_id": 640,
          "variable_id": 56,
          "breed_id": 6,
          "operator": "==",
          "threshold": 1
        },
        {
          "objective_id": 641,
          "variable_id": 57,
          "breed_id": 4,
          "operator": "==",
          "threshold": 1
        }
      ],
      "prerequisites": [],
      "rewards": [
        {
          "aeV": 5,
          "ckk": false,
          "ckl": [
            7358,
            5
          ],
          "d": 291,
          "native_class": "aJP",
          "native_type_name": "GIVE_PLAYER_ITEM"
        }
      ],
      "authority": "proposed_explicit_local_policy_not_activated",
      "source_criteria": {
        "aHe": "",
        "cjI": ""
      },
      "native_repeatable": false,
      "native_period": 0,
      "mission_dependency": false
    },
    {
      "definition_id": 244,
      "event": {
        "kind": "original_breed_kill",
        "variable_ids": [
          56,
          57,
          58,
          59
        ]
      },
      "objectives": [
        {
          "objective_id": 643,
          "variable_id": 56,
          "breed_id": 6,
          "operator": "==",
          "threshold": 5
        },
        {
          "objective_id": 644,
          "variable_id": 57,
          "breed_id": 4,
          "operator": "==",
          "threshold": 5
        },
        {
          "objective_id": 645,
          "variable_id": 58,
          "breed_id": 5,
          "operator": "==",
          "threshold": 5
        },
        {
          "objective_id": 646,
          "variable_id": 59,
          "breed_id": 704,
          "operator": "==",
          "threshold": 1
        }
      ],
      "prerequisites": [
        243
      ],
      "rewards": [
        {
          "aeV": 5,
          "ckk": false,
          "ckl": [
            2038,
            1
          ],
          "d": 292,
          "native_class": "aJP",
          "native_type_name": "GIVE_PLAYER_ITEM"
        }
      ],
      "authority": "proposed_explicit_local_policy_not_activated",
      "source_criteria": {
        "aHe": "IsAchievementComplete(243)",
        "cjI": ""
      },
      "native_repeatable": false,
      "native_period": 0,
      "mission_dependency": false
    },
    {
      "definition_id": 245,
      "event": {
        "kind": "original_breed_kill",
        "variable_ids": [
          56,
          57,
          58,
          59
        ]
      },
      "objectives": [
        {
          "objective_id": 647,
          "variable_id": 56,
          "breed_id": 6,
          "operator": "==",
          "threshold": 10
        },
        {
          "objective_id": 648,
          "variable_id": 57,
          "breed_id": 4,
          "operator": "==",
          "threshold": 10
        },
        {
          "objective_id": 649,
          "variable_id": 58,
          "breed_id": 5,
          "operator": "==",
          "threshold": 10
        },
        {
          "objective_id": 650,
          "variable_id": 59,
          "breed_id": 704,
          "operator": "==",
          "threshold": 10
        }
      ],
      "prerequisites": [
        244
      ],
      "rewards": [
        {
          "aeV": 5,
          "ckk": false,
          "ckl": [
            2089,
            1
          ],
          "d": 293,
          "native_class": "aJP",
          "native_type_name": "GIVE_PLAYER_ITEM"
        }
      ],
      "authority": "proposed_explicit_local_policy_not_activated",
      "source_criteria": {
        "aHe": "IsAchievementComplete(244)",
        "cjI": ""
      },
      "native_repeatable": false,
      "native_period": 0,
      "mission_dependency": false
    },
    {
      "definition_id": 246,
      "event": {
        "kind": "original_breed_kill",
        "variable_ids": [
          56,
          57,
          58,
          59
        ]
      },
      "objectives": [
        {
          "objective_id": 651,
          "variable_id": 56,
          "breed_id": 6,
          "operator": "==",
          "threshold": 50
        },
        {
          "objective_id": 652,
          "variable_id": 57,
          "breed_id": 4,
          "operator": "==",
          "threshold": 50
        },
        {
          "objective_id": 653,
          "variable_id": 58,
          "breed_id": 5,
          "operator": "==",
          "threshold": 50
        },
        {
          "objective_id": 654,
          "variable_id": 59,
          "breed_id": 704,
          "operator": "==",
          "threshold": 50
        }
      ],
      "prerequisites": [
        245
      ],
      "rewards": [
        {
          "aeV": 5,
          "ckk": false,
          "ckl": [
            9812,
            1
          ],
          "d": 295,
          "native_class": "aJP",
          "native_type_name": "GIVE_PLAYER_ITEM"
        },
        {
          "aeV": 2,
          "ckk": false,
          "ckl": [
            99
          ],
          "d": 294,
          "native_class": "aJP",
          "native_type_name": "GIVE_PLAYER_TITLE"
        }
      ],
      "authority": "proposed_explicit_local_policy_not_activated",
      "source_criteria": {
        "aHe": "IsAchievementComplete(245)",
        "cjI": ""
      },
      "native_repeatable": false,
      "native_period": 0,
      "mission_dependency": false
    },
    {
      "definition_id": 247,
      "event": {
        "kind": "original_breed_kill",
        "variable_ids": [
          56,
          57,
          58,
          59,
          108
        ]
      },
      "objectives": [
        {
          "objective_id": 656,
          "variable_id": 56,
          "breed_id": 6,
          "operator": "==",
          "threshold": 100
        },
        {
          "objective_id": 658,
          "variable_id": 57,
          "breed_id": 4,
          "operator": "==",
          "threshold": 100
        },
        {
          "objective_id": 659,
          "variable_id": 58,
          "breed_id": 5,
          "operator": "==",
          "threshold": 100
        },
        {
          "objective_id": 660,
          "variable_id": 59,
          "breed_id": 704,
          "operator": "==",
          "threshold": 100
        },
        {
          "objective_id": 816,
          "variable_id": 108,
          "breed_id": 1259,
          "operator": "==",
          "threshold": 1
        }
      ],
      "prerequisites": [
        246
      ],
      "rewards": [
        {
          "aeV": 5,
          "ckk": false,
          "ckl": [
            10310,
            1
          ],
          "d": 296,
          "native_class": "aJP",
          "native_type_name": "GIVE_PLAYER_ITEM"
        }
      ],
      "authority": "proposed_explicit_local_policy_not_activated",
      "source_criteria": {
        "aHe": "IsAchievementComplete(246)",
        "cjI": ""
      },
      "native_repeatable": false,
      "native_period": 0,
      "mission_dependency": false
    },
    {
      "definition_id": 818,
      "event": {
        "kind": "owned_final_dungeon_victory",
        "native_dungeon_id": 65
      },
      "objectives": [
        {
          "objective_id": 1638,
          "dungeon_id": 65
        }
      ],
      "prerequisites": [],
      "rewards": [
        {
          "aeV": 5,
          "ckk": false,
          "ckl": [
            12686,
            10
          ],
          "d": 4603,
          "native_class": "aJP",
          "native_type_name": "GIVE_PLAYER_ITEM"
        }
      ],
      "authority": "proposed_explicit_local_policy_not_activated",
      "source_criteria": {
        "aHe": "",
        "cjI": ""
      },
      "native_repeatable": false,
      "native_period": 0,
      "mission_dependency": false
    },
    {
      "definition_id": 840,
      "event": {
        "kind": "original_breed_kill",
        "variable_ids": [
          254
        ]
      },
      "objectives": [
        {
          "objective_id": 1684,
          "variable_id": 254,
          "operator": ">=",
          "threshold": 40
        }
      ],
      "prerequisites": [],
      "rewards": [
        {
          "aeV": 2,
          "ckk": false,
          "ckl": [
            200
          ],
          "d": 1199,
          "native_class": "aJP",
          "native_type_name": "GIVE_PLAYER_TITLE"
        }
      ],
      "authority": "proposed_explicit_local_policy_not_activated",
      "source_criteria": {
        "aHe": "",
        "cjI": ""
      },
      "native_repeatable": false,
      "native_period": 0,
      "mission_dependency": false
    },
    {
      "definition_id": 2198,
      "event": {
        "kind": "owned_final_dungeon_victory",
        "native_dungeon_id": 89
      },
      "objectives": [
        {
          "objective_id": 4339,
          "dungeon_id": 89
        }
      ],
      "prerequisites": [],
      "rewards": [
        {
          "aeV": 5,
          "ckk": false,
          "ckl": [
            20672,
            10
          ],
          "d": 4612,
          "native_class": "aJP",
          "native_type_name": "GIVE_PLAYER_ITEM"
        }
      ],
      "authority": "proposed_explicit_local_policy_not_activated",
      "source_criteria": {
        "aHe": "",
        "cjI": ""
      },
      "native_repeatable": false,
      "native_period": 0,
      "mission_dependency": false
    },
    {
      "definition_id": 2204,
      "event": {
        "kind": "owned_final_dungeon_victory",
        "native_dungeon_id": 90
      },
      "objectives": [
        {
          "objective_id": 4347,
          "dungeon_id": 90
        }
      ],
      "prerequisites": [],
      "rewards": [
        {
          "aeV": 5,
          "ckk": false,
          "ckl": [
            12686,
            10
          ],
          "d": 4606,
          "native_class": "aJP",
          "native_type_name": "GIVE_PLAYER_ITEM"
        }
      ],
      "authority": "proposed_explicit_local_policy_not_activated",
      "source_criteria": {
        "aHe": "",
        "cjI": ""
      },
      "native_repeatable": false,
      "native_period": 0,
      "mission_dependency": false
    },
    {
      "definition_id": 2209,
      "event": {
        "kind": "owned_final_dungeon_victory",
        "native_dungeon_id": 27
      },
      "objectives": [
        {
          "objective_id": 4354,
          "dungeon_id": 27
        }
      ],
      "prerequisites": [],
      "rewards": [
        {
          "aeV": 5,
          "ckk": false,
          "ckl": [
            12686,
            10
          ],
          "d": 4600,
          "native_class": "aJP",
          "native_type_name": "GIVE_PLAYER_ITEM"
        }
      ],
      "authority": "proposed_explicit_local_policy_not_activated",
      "source_criteria": {
        "aHe": "",
        "cjI": ""
      },
      "native_repeatable": false,
      "native_period": 0,
      "mission_dependency": false
    },
    {
      "definition_id": 2382,
      "event": {
        "kind": "original_breed_kill",
        "variable_ids": [
          362
        ]
      },
      "objectives": [
        {
          "objective_id": 4685,
          "variable_id": 362,
          "operator": ">=",
          "threshold": 666
        }
      ],
      "prerequisites": [],
      "rewards": [
        {
          "aeV": 2,
          "ckk": false,
          "ckl": [
            260
          ],
          "d": 3873,
          "native_class": "aJP",
          "native_type_name": "GIVE_PLAYER_TITLE"
        },
        {
          "aeV": 5,
          "ckk": false,
          "ckl": [
            19009,
            30
          ],
          "d": 3874,
          "native_class": "aJP",
          "native_type_name": "GIVE_PLAYER_ITEM"
        }
      ],
      "authority": "proposed_explicit_local_policy_not_activated",
      "source_criteria": {
        "aHe": "",
        "cjI": ""
      },
      "native_repeatable": false,
      "native_period": 0,
      "mission_dependency": false
    },
    {
      "definition_id": 2383,
      "event": {
        "kind": "original_breed_kill",
        "variable_ids": [
          224
        ]
      },
      "objectives": [
        {
          "objective_id": 4686,
          "variable_id": 224,
          "operator": ">=",
          "threshold": 666
        }
      ],
      "prerequisites": [],
      "rewards": [
        {
          "aeV": 2,
          "ckk": false,
          "ckl": [
            176
          ],
          "d": 3875,
          "native_class": "aJP",
          "native_type_name": "GIVE_PLAYER_TITLE"
        },
        {
          "aeV": 5,
          "ckk": false,
          "ckl": [
            19009,
            30
          ],
          "d": 3876,
          "native_class": "aJP",
          "native_type_name": "GIVE_PLAYER_ITEM"
        }
      ],
      "authority": "proposed_explicit_local_policy_not_activated",
      "source_criteria": {
        "aHe": "",
        "cjI": ""
      },
      "native_repeatable": false,
      "native_period": 0,
      "mission_dependency": false
    },
    {
      "definition_id": 2384,
      "event": {
        "kind": "original_breed_kill",
        "variable_ids": [
          362
        ]
      },
      "objectives": [
        {
          "objective_id": 4687,
          "variable_id": 362,
          "operator": ">=",
          "threshold": 66
        }
      ],
      "prerequisites": [],
      "rewards": [
        {
          "aeV": 5,
          "ckk": false,
          "ckl": [
            19009,
            10
          ],
          "d": 3877,
          "native_class": "aJP",
          "native_type_name": "GIVE_PLAYER_ITEM"
        }
      ],
      "authority": "proposed_explicit_local_policy_not_activated",
      "source_criteria": {
        "aHe": "",
        "cjI": ""
      },
      "native_repeatable": false,
      "native_period": 0,
      "mission_dependency": false
    },
    {
      "definition_id": 2385,
      "event": {
        "kind": "original_breed_kill",
        "variable_ids": [
          224
        ]
      },
      "objectives": [
        {
          "objective_id": 4688,
          "variable_id": 224,
          "operator": ">=",
          "threshold": 66
        }
      ],
      "prerequisites": [],
      "rewards": [
        {
          "aeV": 5,
          "ckk": false,
          "ckl": [
            19009,
            10
          ],
          "d": 3878,
          "native_class": "aJP",
          "native_type_name": "GIVE_PLAYER_ITEM"
        }
      ],
      "authority": "proposed_explicit_local_policy_not_activated",
      "source_criteria": {
        "aHe": "",
        "cjI": ""
      },
      "native_repeatable": false,
      "native_period": 0,
      "mission_dependency": false
    },
    {
      "definition_id": 2611,
      "event": {
        "kind": "original_breed_kill",
        "variable_ids": [
          559
        ]
      },
      "objectives": [
        {
          "objective_id": 5177,
          "variable_id": 559,
          "operator": ">=",
          "threshold": 30
        }
      ],
      "prerequisites": [],
      "rewards": [
        {
          "aeV": 2,
          "ckk": false,
          "ckl": [
            134
          ],
          "d": 4156,
          "native_class": "aJP",
          "native_type_name": "GIVE_PLAYER_TITLE"
        }
      ],
      "authority": "proposed_explicit_local_policy_not_activated",
      "source_criteria": {
        "aHe": "",
        "cjI": ""
      },
      "native_repeatable": false,
      "native_period": 0,
      "mission_dependency": false
    },
    {
      "definition_id": 2917,
      "event": {
        "kind": "original_breed_kill",
        "variable_ids": [
          540
        ]
      },
      "objectives": [
        {
          "objective_id": 5991,
          "variable_id": 540,
          "operator": ">",
          "threshold": 59
        }
      ],
      "prerequisites": [],
      "rewards": [
        {
          "aeV": 5,
          "ckk": false,
          "ckl": [
            20392,
            1
          ],
          "d": 4517,
          "native_class": "aJP",
          "native_type_name": "GIVE_PLAYER_ITEM"
        },
        {
          "aeV": 2,
          "ckk": false,
          "ckl": [
            414
          ],
          "d": 4516,
          "native_class": "aJP",
          "native_type_name": "GIVE_PLAYER_TITLE"
        }
      ],
      "authority": "proposed_explicit_local_policy_not_activated",
      "source_criteria": {
        "aHe": "",
        "cjI": ""
      },
      "native_repeatable": false,
      "native_period": 0,
      "mission_dependency": false
    },
    {
      "definition_id": 2980,
      "event": {
        "kind": "owned_original_breed_victory"
      },
      "objectives": [
        {
          "objective_id": 6222,
          "breed_id": 4086,
          "required_kills": 1
        },
        {
          "objective_id": 6223,
          "breed_id": 4101,
          "required_kills": 1
        },
        {
          "objective_id": 6224,
          "breed_id": 4097,
          "required_kills": 1
        }
      ],
      "prerequisites": [],
      "rewards": [
        {
          "aeV": 6,
          "ckk": false,
          "ckl": [
            37220
          ],
          "d": 4665,
          "native_class": "aJP",
          "native_type_name": "GIVE_PLAYER_XP"
        },
        {
          "aeV": 5,
          "ckk": false,
          "ckl": [
            12686,
            20
          ],
          "d": 4664,
          "native_class": "aJP",
          "native_type_name": "GIVE_PLAYER_ITEM"
        }
      ],
      "authority": "proposed_explicit_local_policy_not_activated",
      "source_criteria": {
        "aHe": "",
        "cjI": ""
      },
      "native_repeatable": false,
      "native_period": 0,
      "mission_dependency": false,
      "native_identity_proof": [
        {
          "definition_id": 2980,
          "objective_id": 6222,
          "required_kills": 1,
          "breed_ref": 4086,
          "family_id": 68,
          "family_names": {
            "fr": "Bouftous",
            "en": "Gobballs",
            "es": "Jalat\u00f3s"
          },
          "names": {
            "fr": "Bouchtrou l'Esseul\u00e9",
            "en": "Filholl the Forsaken",
            "es": "Jalabujero el Abandonado"
          },
          "native_role_id": 2,
          "native_role_name": "ARCHMONSTER",
          "min_level": 23,
          "max_level": 28,
          "objective": {
            "definition_id": 2980,
            "objective_id": 6222,
            "text_en": "Defeat the Archmonster \"Filholl the Forsaken\"",
            "text_es": "Vencer al archimonstruo Jalabujero el Abandonado",
            "criterion_ckc": "",
            "criterion_cke": "",
            "variable_rules": [],
            "markers": [],
            "raw_flag_ckb": true
          },
          "category_chain": [
            642,
            939
          ],
          "authority": "explicit_local_policy_with_exact_native_archmonster_identity",
          "confidence": "high",
          "exclusions": []
        },
        {
          "definition_id": 2980,
          "objective_id": 6223,
          "required_kills": 1,
          "breed_ref": 4101,
          "family_id": 81,
          "family_names": {
            "fr": "Tofus",
            "en": "Tofus",
            "es": "Tofus"
          },
          "names": {
            "fr": "Griffu l'Ac\u00e9r\u00e9",
            "en": "Claud Sharpe",
            "es": "Ganchudo el Acerado"
          },
          "native_role_id": 2,
          "native_role_name": "ARCHMONSTER",
          "min_level": 23,
          "max_level": 28,
          "objective": {
            "definition_id": 2980,
            "objective_id": 6223,
            "text_en": "Defeat the Archmonster \"Claud Sharpe\"",
            "text_es": "Vencer al archimonstruo Ganchudo el Acerado",
            "criterion_ckc": "",
            "criterion_cke": "",
            "variable_rules": [],
            "markers": [],
            "raw_flag_ckb": true
          },
          "category_chain": [
            642,
            939
          ],
          "authority": "explicit_local_policy_with_exact_native_archmonster_identity",
          "confidence": "high",
          "exclusions": []
        },
        {
          "definition_id": 2980,
          "objective_id": 6224,
          "required_kills": 1,
          "breed_ref": 4097,
          "family_id": 147,
          "family_names": {
            "fr": "Larves",
            "en": "Larvae",
            "es": "Larvas"
          },
          "names": {
            "fr": "Lartifice l'Explosive",
            "en": "Explosive Larvawork",
            "es": "Lartificia la Explosiva"
          },
          "native_role_id": 2,
          "native_role_name": "ARCHMONSTER",
          "min_level": 23,
          "max_level": 28,
          "objective": {
            "definition_id": 2980,
            "objective_id": 6224,
            "text_en": "Defeat the Archmonster \"Explosive Larvawork\"",
            "text_es": "Vencer al archimonstruo Lartificia la Explosiva",
            "criterion_ckc": "",
            "criterion_cke": "",
            "variable_rules": [],
            "markers": [],
            "raw_flag_ckb": true
          },
          "category_chain": [
            642,
            939
          ],
          "authority": "explicit_local_policy_with_exact_native_archmonster_identity",
          "confidence": "high",
          "exclusions": []
        }
      ]
    },
    {
      "definition_id": 2981,
      "event": {
        "kind": "owned_original_breed_victory"
      },
      "objectives": [
        {
          "objective_id": 6225,
          "breed_id": 4100,
          "required_kills": 1
        },
        {
          "objective_id": 6226,
          "breed_id": 4098,
          "required_kills": 1
        }
      ],
      "prerequisites": [],
      "rewards": [
        {
          "aeV": 6,
          "ckk": false,
          "ckl": [
            131500
          ],
          "d": 4698,
          "native_class": "aJP",
          "native_type_name": "GIVE_PLAYER_XP"
        },
        {
          "aeV": 5,
          "ckk": false,
          "ckl": [
            20672,
            20
          ],
          "d": 4697,
          "native_class": "aJP",
          "native_type_name": "GIVE_PLAYER_ITEM"
        }
      ],
      "authority": "proposed_explicit_local_policy_not_activated",
      "source_criteria": {
        "aHe": "",
        "cjI": ""
      },
      "native_repeatable": false,
      "native_period": 0,
      "mission_dependency": false,
      "native_identity_proof": [
        {
          "definition_id": 2981,
          "objective_id": 6225,
          "required_kills": 1,
          "breed_ref": 4100,
          "family_id": 79,
          "family_names": {
            "fr": "Pious",
            "en": "Piwis",
            "es": "P\u00edos"
          },
          "names": {
            "fr": "Pewpew l'Artilleur",
            "en": "Gunner Pewpew",
            "es": "Piupiu, el Artillero"
          },
          "native_role_id": 2,
          "native_role_name": "ARCHMONSTER",
          "min_level": 38,
          "max_level": 43,
          "objective": {
            "definition_id": 2981,
            "objective_id": 6225,
            "text_en": "Defeat the Archmonster \"Gunner Pewpew\"",
            "text_es": "Vencer al archimonstruo Piupiu, el Artillero",
            "criterion_ckc": "",
            "criterion_cke": "",
            "variable_rules": [],
            "markers": [],
            "raw_flag_ckb": true
          },
          "category_chain": [
            643,
            939
          ],
          "authority": "explicit_local_policy_with_exact_native_archmonster_identity",
          "confidence": "high",
          "exclusions": []
        },
        {
          "definition_id": 2981,
          "objective_id": 6226,
          "required_kills": 1,
          "breed_ref": 4098,
          "family_id": 829,
          "family_names": {
            "fr": "Abraknes",
            "en": "Treechnees",
            "es": "Abraknos"
          },
          "names": {
            "fr": "Abribus le Protecteur",
            "en": "Abribus the Protector",
            "es": "Marquesino, el Protector"
          },
          "native_role_id": 2,
          "native_role_name": "ARCHMONSTER",
          "min_level": 38,
          "max_level": 43,
          "objective": {
            "definition_id": 2981,
            "objective_id": 6226,
            "text_en": "Defeat the Archmonster \"Abribus the Protector\"",
            "text_es": "Vencer al archimonstruo Marquesino, el Protector",
            "criterion_ckc": "",
            "criterion_cke": "",
            "variable_rules": [],
            "markers": [],
            "raw_flag_ckb": true
          },
          "category_chain": [
            643,
            939
          ],
          "authority": "explicit_local_policy_with_exact_native_archmonster_identity",
          "confidence": "high",
          "exclusions": []
        }
      ]
    },
    {
      "definition_id": 3107,
      "event": {
        "kind": "original_breed_kill",
        "variable_ids": [
          554
        ]
      },
      "objectives": [
        {
          "objective_id": 6507,
          "variable_id": 554,
          "operator": ">=",
          "threshold": 20
        }
      ],
      "prerequisites": [],
      "rewards": [
        {
          "aeV": 2,
          "ckk": false,
          "ckl": [
            133
          ],
          "d": 4879,
          "native_class": "aJP",
          "native_type_name": "GIVE_PLAYER_TITLE"
        }
      ],
      "authority": "proposed_explicit_local_policy_not_activated",
      "source_criteria": {
        "aHe": "",
        "cjI": ""
      },
      "native_repeatable": false,
      "native_period": 0,
      "mission_dependency": false
    },
    {
      "definition_id": 3299,
      "event": {
        "kind": "original_breed_kill",
        "variable_ids": [
          559
        ]
      },
      "objectives": [
        {
          "objective_id": 6973,
          "variable_id": 559,
          "operator": ">=",
          "threshold": 200
        }
      ],
      "prerequisites": [],
      "rewards": [
        {
          "aeV": 2,
          "ckk": false,
          "ckl": [
            464
          ],
          "d": 5585,
          "native_class": "aJP",
          "native_type_name": "GIVE_PLAYER_TITLE"
        }
      ],
      "authority": "proposed_explicit_local_policy_not_activated",
      "source_criteria": {
        "aHe": "",
        "cjI": ""
      },
      "native_repeatable": false,
      "native_period": 0,
      "mission_dependency": false
    },
    {
      "definition_id": 3629,
      "event": {
        "kind": "owned_final_dungeon_victory",
        "native_dungeon_id": 125
      },
      "objectives": [
        {
          "objective_id": 7491,
          "dungeon_id": 125
        }
      ],
      "prerequisites": [],
      "rewards": [
        {
          "aeV": 5,
          "ckk": false,
          "ckl": [
            20672,
            10
          ],
          "d": 6387,
          "native_class": "aJP",
          "native_type_name": "GIVE_PLAYER_ITEM"
        }
      ],
      "authority": "proposed_explicit_local_policy_not_activated",
      "source_criteria": {
        "aHe": "",
        "cjI": ""
      },
      "native_repeatable": false,
      "native_period": 0,
      "mission_dependency": false,
      "native_identity_proof": {
        "definition_id": 125,
        "map_id": 1091,
        "native_species_pool": [
          4076,
          4077,
          4078,
          4079,
          4107
        ],
        "configuration_slug": "donjon-des-abraknes",
        "original_objective_fr": "Terminer le Donjon \"Donjon des Abraknes\""
      }
    },
    {
      "definition_id": 3800,
      "event": {
        "kind": "owned_original_breed_victory"
      },
      "objectives": [
        {
          "objective_id": 7851,
          "breed_id": 4368,
          "required_kills": 1
        },
        {
          "objective_id": 11502,
          "breed_id": 1632,
          "required_kills": 1
        },
        {
          "objective_id": 11503,
          "breed_id": 5005,
          "required_kills": 1
        }
      ],
      "prerequisites": [],
      "rewards": [
        {
          "aeV": 6,
          "ckk": false,
          "ckl": [
            378100
          ],
          "d": 6754,
          "native_class": "aJP",
          "native_type_name": "GIVE_PLAYER_XP"
        },
        {
          "aeV": 5,
          "ckk": false,
          "ckl": [
            20968,
            20
          ],
          "d": 6755,
          "native_class": "aJP",
          "native_type_name": "GIVE_PLAYER_ITEM"
        }
      ],
      "authority": "proposed_explicit_local_policy_not_activated",
      "source_criteria": {
        "aHe": "",
        "cjI": ""
      },
      "native_repeatable": false,
      "native_period": 0,
      "mission_dependency": false,
      "native_identity_proof": [
        {
          "definition_id": 3800,
          "objective_id": 7851,
          "required_kills": 1,
          "breed_ref": 4368,
          "family_id": 291,
          "family_names": {
            "fr": "Craqueleurs",
            "en": "Cracklers",
            "es": "Crujidores"
          },
          "names": {
            "fr": "Craqnoix le G\u00eaneur",
            "en": "Cracknut the Nuisance",
            "es": "Crujenueces el Molesto"
          },
          "native_role_id": 2,
          "native_role_name": "ARCHMONSTER",
          "min_level": 53,
          "max_level": 58,
          "objective": {
            "definition_id": 3800,
            "objective_id": 7851,
            "text_en": "Defeat the Archmonster \"Cracknut the Nuisance\"",
            "text_es": "Vencer al archimonstruo Crujenueces el Molesto",
            "criterion_ckc": "",
            "criterion_cke": "",
            "variable_rules": [],
            "markers": [],
            "raw_flag_ckb": true
          },
          "category_chain": [
            644,
            939
          ],
          "authority": "explicit_local_policy_with_exact_native_archmonster_identity",
          "confidence": "high",
          "exclusions": []
        },
        {
          "definition_id": 3800,
          "objective_id": 11502,
          "required_kills": 1,
          "breed_ref": 1632,
          "family_id": 219,
          "family_names": {
            "fr": "Moogrr",
            "en": "Moogrr",
            "es": "Muuugresa"
          },
          "names": {
            "fr": "Moumoute la Postiche",
            "en": "Moothane the Gas",
            "es": "Pacmuuungr la Hambrienta"
          },
          "native_role_id": 2,
          "native_role_name": "ARCHMONSTER",
          "min_level": 53,
          "max_level": 58,
          "objective": {
            "definition_id": 3800,
            "objective_id": 11502,
            "text_en": "Defeat the Archmonster \"Moothane the Gas\"",
            "text_es": "Vencer al archimonstruo Pacmuuungr la Hambrienta",
            "criterion_ckc": "",
            "criterion_cke": "",
            "variable_rules": [],
            "markers": [],
            "raw_flag_ckb": true
          },
          "category_chain": [
            644,
            939
          ],
          "authority": "explicit_local_policy_with_exact_native_archmonster_identity",
          "confidence": "high",
          "exclusions": []
        },
        {
          "definition_id": 3800,
          "objective_id": 11503,
          "required_kills": 1,
          "breed_ref": 5005,
          "family_id": 113,
          "family_names": {
            "fr": "Plantes des Champs",
            "en": "Field Plants",
            "es": "Plantas de los campos"
          },
          "names": {
            "fr": "Ros\u00e9e la matinale",
            "en": "Dew the Early Riser",
            "es": "Roc\u00edo la Matinal"
          },
          "native_role_id": 2,
          "native_role_name": "ARCHMONSTER",
          "min_level": 53,
          "max_level": 58,
          "objective": {
            "definition_id": 3800,
            "objective_id": 11503,
            "text_en": "Defeat the Archmonster \"Dew the Early Riser\"",
            "text_es": "Vencer al archimonstruo Roc\u00edo la Matinal",
            "criterion_ckc": "",
            "criterion_cke": "",
            "variable_rules": [],
            "markers": [],
            "raw_flag_ckb": true
          },
          "category_chain": [
            644,
            939
          ],
          "authority": "explicit_local_policy_with_exact_native_archmonster_identity",
          "confidence": "high",
          "exclusions": []
        }
      ]
    },
    {
      "definition_id": 4291,
      "event": {
        "kind": "original_breed_kill",
        "variable_ids": [
          697
        ]
      },
      "objectives": [
        {
          "objective_id": 8921,
          "variable_id": 697,
          "operator": ">=",
          "threshold": 444
        }
      ],
      "prerequisites": [],
      "rewards": [
        {
          "aeV": 5,
          "ckk": false,
          "ckl": [
            26360,
            1
          ],
          "d": 8040,
          "native_class": "aJP",
          "native_type_name": "GIVE_PLAYER_ITEM"
        }
      ],
      "authority": "proposed_explicit_local_policy_not_activated",
      "source_criteria": {
        "aHe": "",
        "cjI": ""
      },
      "native_repeatable": false,
      "native_period": 0,
      "mission_dependency": false
    },
    {
      "definition_id": 5164,
      "event": {
        "kind": "owned_original_breed_victory"
      },
      "objectives": [
        {
          "objective_id": 10631,
          "breed_id": 5526,
          "required_kills": 1
        },
        {
          "objective_id": 10632,
          "breed_id": 5527,
          "required_kills": 1
        }
      ],
      "prerequisites": [],
      "rewards": [
        {
          "aeV": 2,
          "ckk": false,
          "ckl": [
            761
          ],
          "d": 9720,
          "native_class": "aJP",
          "native_type_name": "GIVE_PLAYER_TITLE"
        },
        {
          "aeV": 3,
          "ckk": false,
          "ckl": [
            20011
          ],
          "d": 9721,
          "native_class": "aJP",
          "native_type_name": "GIVE_PLAYER_EMOTE"
        }
      ],
      "authority": "proposed_explicit_local_policy_not_activated",
      "source_criteria": {
        "aHe": "",
        "cjI": ""
      },
      "native_repeatable": false,
      "native_period": 0,
      "mission_dependency": false,
      "native_identity_proof": [
        {
          "definition_id": 5164,
          "objective_id": 10631,
          "required_kills": 1,
          "breed_ref": 5526,
          "family_id": 1115,
          "family_names": {
            "fr": "Extra Incarnam",
            "en": "Extra Incarnam",
            "es": "Extra Incarnam"
          },
          "names": {
            "fr": "Bouftou c\u00e9leste",
            "en": "Celestial Gobball",
            "es": "Jalat\u00f3 celestial"
          },
          "native_role_id": 2,
          "native_role_name": "ARCHMONSTER",
          "min_level": 8,
          "max_level": 8,
          "objective": {
            "definition_id": 5164,
            "objective_id": 10631,
            "text_en": "Defeat the Celestial Gobball",
            "text_es": "Vencer al Jalat\u00f3 Celestial",
            "criterion_ckc": "",
            "criterion_cke": "",
            "variable_rules": [],
            "markers": [],
            "raw_flag_ckb": true
          },
          "category_chain": [
            431,
            68
          ],
          "authority": "explicit_local_policy_with_exact_native_archmonster_identity",
          "confidence": "high",
          "exclusions": [
            5891
          ]
        },
        {
          "definition_id": 5164,
          "objective_id": 10632,
          "required_kills": 1,
          "breed_ref": 5527,
          "family_id": 1115,
          "family_names": {
            "fr": "Extra Incarnam",
            "en": "Extra Incarnam",
            "es": "Extra Incarnam"
          },
          "names": {
            "fr": "Dark Wapin",
            "en": "Darth Wodent",
            "es": "Dark wonejo"
          },
          "native_role_id": 2,
          "native_role_name": "ARCHMONSTER",
          "min_level": 8,
          "max_level": 8,
          "objective": {
            "definition_id": 5164,
            "objective_id": 10632,
            "text_en": "Defeat Darth Wodent",
            "text_es": "Vencer a Dark Wonejo",
            "criterion_ckc": "",
            "criterion_cke": "",
            "variable_rules": [],
            "markers": [],
            "raw_flag_ckb": true
          },
          "category_chain": [
            431,
            68
          ],
          "authority": "explicit_local_policy_with_exact_native_archmonster_identity",
          "confidence": "high",
          "exclusions": [
            4674
          ]
        }
      ]
    }
  ],
  "expanded_binding_provenance": {
    "source_sha256": "3c85bb9f77f9c1a2a3d6d053169d10c9591150f2e9f460446c0e14ad9c3f6998",
    "i18n_sha256": {
      "fr": "12cab5e8b0959cf4cbafa0b675a77da4305a3a45777454239c1cee53f0ba3530",
      "en": "a9a077c6805fbfc9caa28d1b398b1c1ec95e3df035f7f3853ace9d82e2d11830",
      "es": "7a1e3247388f5e771e31f2ea1e4db7a2c7dc48d4108b71dae04789e7966ce7c8"
    }
  }
}
$rules$::jsonb),
('admin_map_names', $names${
  "375": "Headquarters",
  "376": "Crusty Road - Center",
  "377": "Crusty Road - East",
  "378": "Swords Crossing - West",
  "379": "Swords Crossing - Center",
  "380": "Swords Crossing - East",
  "381": "Holey Forest - Pier",
  "382": "Holey Forest",
  "383": "Singing Fields North - North",
  "384": "Singing Fields North - South",
  "385": "Emelka Village",
  "386": "Traff Algar Square - West",
  "387": "Traff Algar Square - Center",
  "388": "Traff Algar Square - East",
  "389": "Headquarters",
  "390": "Cania Plains - West",
  "391": "Cania Plains - Center",
  "392": "5th Bond Avenue - North",
  "393": "5th Bond Avenue - Center",
  "394": "5th Bond Avenue - East",
  "395": "Cania Swamps",
  "396": "Kara",
  "397": "Arms Way - West",
  "398": "Arms Way - Center",
  "399": "Arms Way - East",
  "400": "Pancake Bridge - East",
  "401": "Pancake Bridge - Bonta",
  "402": "Pancake Bridge - West",
  "403": "Thicket of Yurbut",
  "404": "Weapons Bridge - West",
  "405": "Weapons Bridge - Center",
  "406": "Weapons Bridge - North",
  "407": "Mourning Wood - Center",
  "408": "Mourning Wood - East",
  "409": "Sidimote Moors",
  "410": "Scara Pass - North",
  "411": "Scara Pass - South",
  "412": "Scara Pass - East",
  "413": "Gnashville",
  "414": "Gobblard Boulevard - East",
  "415": "Gobblard Boulevard - Center",
  "416": "Gobblard Boulevard - West",
  "417": "Pabong Fields",
  "418": "Headquarters",
  "419": "Headquarters",
  "420": "Gutted Plaza - West",
  "421": "Gutted Plaza - South",
  "422": "Gutted Plaza - East",
  "423": "Fiery Walk - West",
  "424": "Fiery Walk - North",
  "425": "Unna Bridge - West",
  "426": "Fiery Walk - South",
  "427": "Unna Bridge - Center",
  "428": "Unna Bridge - East",
  "429": "Turfo Canyon - South",
  "430": "Turfo Canyon - North",
  "431": "Jumpin' Jungle",
  "432": "Steamulating Shore - North",
  "433": "Steamulating Shore - Center",
  "434": "Crusty Road - West",
  "616": "Amakna Village",
  "617": "Bonta Ruins",
  "618": "Brakmar Village",
  "619": "Sufokia Village",
  "620": "Dev-Land",
  "624": "Fertile Prairie - East",
  "625": "Fertile Prairie - West",
  "626": "Cania Plains - South",
  "627": "Cania Plains - Bay",
  "628": "Mourning Wood - North",
  "629": "Mourning Wood - South",
  "630": "Terrana Dune - East",
  "631": "Terrana Dune - West",
  "632": "Singing Fields North - Point",
  "633": "Singing Fields - West",
  "634": "Kara - South",
  "635": "Kara - Center",
  "636": "Pabong Fields - West",
  "637": "Pabong Fields - Passage",
  "638": "Turfo Canyon - Bay",
  "639": "Turfo Canyon - Center",
  "681": "Bay - Southeast",
  "682": "Seaside - East",
  "683": "Seaside - South",
  "684": "Disco",
  "685": "Bwork Village",
  "686": "Mountain",
  "687": "South Side",
  "688": "Whisper Crisper",
  "689": "Downtown - East",
  "690": "Downtown - West",
  "691": "Village - Southeast",
  "692": "Wagnar's Castle",
  "693": "Pier - North",
  "694": "Zaap - West",
  "695": "Pier",
  "696": "South",
  "729": "Bwork Dungeon",
  "730": "Bworkball Field",
  "731": "South",
  "732": "Temple",
  "733": "Point",
  "734": "West",
  "735": "Northwest",
  "736": "Northeast",
  "737": "Downtown",
  "738": "Stairs",
  "739": "Bay - Center",
  "740": "Bay - East",
  "741": "Pier - South",
  "742": "Zaap - East",
  "743": "Village - Northwest",
  "744": "Village - Southwest",
  "750": "Gobballfield",
  "751": "Singing Fields North - Dirty Trouffe",
  "752": "Holey Forest - Center",
  "753": "Emelka - North",
  "754": "Kara - Windy Village",
  "755": "Thicket of Yurbut - North",
  "756": "Thicket of Yurbut - Center",
  "757": "Thicket of Yurbut - South",
  "758": "Pabong Fields - North",
  "759": "Sidimote Moors - North",
  "760": "Gnashville - Bridge",
  "761": "Gnashville - Center",
  "762": "Jumpin' Jungle - Kokokobana",
  "763": "Jumpin' Jungle - North",
  "764": "Jumpin' Jungle - South",
  "765": "Steamulating Shore - South",
  "9": "Haven Bag",
  "31": "Larvicyd, the Wrong Kind of Tranquility",
  "68": "Arachnerium",
  "70": "Tofuhouse",
  "85": "Gobblidungeon",
  "98": "Incarnam",
  "99": "Incarnam - Souls' Crossing",
  "101": "Incarnam - Crozolily Meadow",
  "104": "Incarnam - Butt-Kicking Hall",
  "105": "Incarnam - Element Hall",
  "106": "Incarnam",
  "115": "Incarnam - Kanojedo",
  "116": "Incarnam",
  "117": "Incarnam",
  "120": "Parallax",
  "131": "Amakna",
  "132": "Three Pistes' Cave",
  "133": "Gobball Pastures",
  "134": "Amaknian Fire of Love",
  "138": "Amakna Prison",
  "139": "Amakna Tunnels",
  "141": "Incarnam - The Xyts",
  "146": "Celestial Prairies",
  "147": "Parallax",
  "148": "The Black Crow's Lair",
  "149": "Riktus Bridge",
  "150": "Nation Commune",
  "151": "Parallax",
  "152": "Riktus Bridge",
  "153": "The Cro-Cave",
  "154": "Miss Ugly Tower",
  "155": "Magik Riktus Den",
  "156": "Maya Bay",
  "157": "Parallax",
  "158": "Unknown Island",
  "159": "Bonta",
  "160": "Bonta Prison",
  "161": "Bontarian Fire of Love",
  "162": "Bonta Tunnels",
  "163": "Dirty Trouffe Estate",
  "164": "Gobball Pastures",
  "165": "Tsu's Palace",
  "169": "Astrub",
  "170": "Astrub",
  "171": "Astrub",
  "172": "Astrub",
  "173": "Astrub",
  "174": "Astrub",
  "175": "Astrub",
  "176": "Astrub",
  "177": "Bilbiza",
  "178": "Dragodrome",
  "179": "Conquerable Island Tunnels",
  "180": "Eliatrope",
  "181": "Parallax",
  "182": "Parallax",
  "184": "Wabbit Islands",
  "185": "Bilbiza",
  "186": "Astrub",
  "187": "Amaknastrub",
  "188": "Bontastrub",
  "189": "Brakmastrub",
  "190": "Sufokiastrub",
  "191": "Astrub - Center",
  "192": "Astrub - Underground",
  "193": "Astrub Cave",
  "194": "Incarnastrub",
  "195": "Parallax",
  "196": "Parallax",
  "198": "Incarnastrub",
  "200": "Shustuft Crust",
  "201": "Tree of Life Dungeon",
  "202": "Treechnid Dungeon",
  "204": "Parallax",
  "205": "Parallax",
  "206": "Fertilizator Dungeon",
  "207": "Shustuft Crust",
  "208": "Brakmar",
  "209": "House of Destiny",
  "210": "Shustuft Crust",
  "211": "Brakmar Prison",
  "212": "Parallax",
  "213": "Shustuft Crust",
  "214": "Shustuft Crust",
  "215": "Shustuft Crust",
  "216": "Shustuft Crust",
  "217": "Shustuft Crust",
  "218": "Shustuft Crust",
  "219": "Shustuft Crust",
  "221": "Incarnastrub",
  "222": "Gobball Pastures",
  "223": "Wakfu Source",
  "224": "Stasis Source",
  "225": "Parallax",
  "228": "Brakmar Tunnels",
  "229": "Parallax",
  "231": "Parallax",
  "232": "Chompicana",
  "233": "Brakmarian Fire of Love",
  "234": "Boarthroom Estate",
  "235": "Sufokia",
  "236": "Gobball Pastures",
  "237": "Stoodeep Mine",
  "240": "Stoodeep Mine",
  "243": "Stoodeep Mine",
  "247": "Stoodeep Mine",
  "248": "Stoodeep Mine",
  "249": "Stoodeep Mine",
  "250": "Stoodeep Mine",
  "251": "Stoodeep Mine",
  "252": "Stoodeep Mine",
  "253": "Stoodeep Mine",
  "254": "Stoodeep Mine",
  "255": "Stoodeep Mine",
  "256": "Stoodeep Mine",
  "257": "Stoodeep Mine",
  "258": "Stoodeep Mine",
  "259": "Stoodeep Mine",
  "262": "Incarnastrub",
  "263": "Sufokia Prison",
  "264": "Sufokia Tunnels",
  "265": "Sufokian Fire of Love",
  "266": "The Snaptrap",
  "267": "Abandoned Scarapit",
  "268": "Sureberry Fields",
  "274": "Parallax",
  "275": "House of Respite",
  "276": "Owl Council",
  "277": "Mount Zinit",
  "278": "Mount Zinit",
  "279": "Parallax",
  "280": "Parallax",
  "281": "House of Trouble",
  "282": "Mount Zinit",
  "283": "Mount Zinit",
  "284": "Mount Zinit",
  "285": "Parallax",
  "286": "Parallax",
  "287": "Parallax",
  "288": "Parallax",
  "290": "The Black Purr",
  "291": "Parallax",
  "292": "Parallax",
  "293": "Parallax",
  "295": "Kokokobana",
  "296": "Morbax Neplopolis",
  "297": "Magik Riktus Den",
  "298": "Bonta Riktus Den",
  "299": "Brakmar Riktus Den",
  "300": "Sufokia Riktus Den",
  "301": "Elite Riktus Dungeon",
  "302": "Stoodeep Mines / Level -5",
  "303": "The Black Purr",
  "304": "The Black Purr",
  "305": "The Black Purr",
  "306": "Parallax",
  "307": "Mount Zinit",
  "308": "Parallax",
  "309": "Parallax",
  "310": "Parallax",
  "311": "Hoola Hoopiwi",
  "312": "Grandmeow's House",
  "313": "Bilbiza",
  "314": "Sadida Kingdom Backup",
  "315": "Kelba Backup",
  "316": "Mount Zinit",
  "317": "Mount Zinit",
  "318": "Mount Zinit",
  "319": "The Tofuhouse",
  "320": "Mount Zinit",
  "321": "Sadida Kingdom",
  "322": "Kelba",
  "323": "Monk Island",
  "324": "Boowolf Dungeon",
  "325": "The Undieworld",
  "326": "Mount Zinit",
  "327": "Forfut",
  "328": "Larventura",
  "329": "Mount Zinit",
  "330": "Wagnar's Castle",
  "332": "Mount Zinit",
  "334": "Mount Zinit",
  "335": "Mount Zinit",
  "337": "Trool Fair",
  "338": "Trool Fair - Tunnel of Love",
  "339": "Crimson Claw Island",
  "340": "Crimson Claw Island",
  "341": "Trool Fair - Rock-Paper-Scissors Contest",
  "342": "Trool Fair - Dark Vlad's Maze",
  "343": "Trool Fair - Gold Rush",
  "346": "Trool Fair - Gladiatrool",
  "347": "Trool Fair - Ghostof Mansion",
  "348": "Trool Fair - Enutrof Game",
  "349": "Trool Fair - Mystic Moe's",
  "350": "Trool Fair - Dopple Manor",
  "351": "Trool Fair - Cupe 'Em Up",
  "358": "Moowolf's Lair",
  "359": "Antechamber of the Moowolf's Lair",
  "360": "Excarnus's Lair",
  "361": "Antechamber of Excarnus's Lair",
  "363": "The Black Crow's Lair",
  "364": "Antechamber of the Black Crow's Lair",
  "365": "The Gobbalrog's Lair",
  "366": "Antechamber of the Gobbalrog's Lair",
  "436": "Temple of Scriptures",
  "437": "Temple of Scriptures",
  "438": "Temple of Scriptures",
  "439": "Temple of Scriptures",
  "440": "Temple of Scriptures",
  "441": "Temple of Scriptures",
  "442": "Crimson Claw Island",
  "443": "Witch's Lair",
  "444": "Shhhudoku Kingdom",
  "445": "Whisper Crisper",
  "446": "Crackapult Range",
  "447": "The Rock",
  "448": "Hushquarters",
  "449": "Lisper",
  "450": "Incarnam",
  "452": "Murmuring Tunnels",
  "453": "Whispering Fort",
  "455": "Unknown Island",
  "456": "Zeppelantern",
  "458": "Bilbiza",
  "459": "Calamari's Hideout",
  "460": "Puddly Dungeon",
  "461": "Macawker's Cache",
  "466": "Mollusky Dungeon",
  "467": "Selachiis Dungeon",
  "468": "Treechnid Dungeon",
  "471": "Dark Hurl Docks",
  "472": "Kwismas Island",
  "474": "Father Kwismas's Workshop",
  "475": "Gambling Joint",
  "476": "Father Kwismas's House",
  "477": "Rattagain",
  "478": "The Whirlway Station",
  "479": "Lemon Dimension",
  "482": "Blue Raspberry Dimension",
  "483": "Trool Academy",
  "487": "Training Room",
  "490": "Sea of Clouds",
  "493": "Royal Pasturizer",
  "495": "Abandoned Strichery",
  "496": "Cwab Dungeon",
  "497": "Celestial Piwi Dungeon",
  "504": "Chillberg Island",
  "506": "Stoodeep Mine",
  "507": "Ruins of the Asparah Gorge",
  "508": "Harebourg Castle",
  "510": "Hagen Daz's Pot",
  "515": "Ambassador's Wing",
  "516": "Frozen Tower",
  "519": "Inkama Jones's Cave",
  "520": "Hazieff's Cave",
  "521": "The Frozen Passage",
  "524": "Harebourg Castle Tunnels",
  "525": "Last Chance Saloon",
  "527": "Astrub",
  "529": "Pirates' Lair",
  "530": "Incarnam",
  "531": "Incarnam",
  "532": "Astrub Wall",
  "534": "Frigostian",
  "536": "Frigostian",
  "539": "Harebourg Pearl Access",
  "541": "Harebourg Tower Terrace",
  "544": "Astrub Tunnels",
  "545": "Dragon Pig's Den",
  "546": "Astrub Sewers",
  "547": "The Stalagmotel",
  "548": "Mussly Hammam",
  "549": "Dancehall Arena",
  "552": "Heraldtopia",
  "553": "Jellith Dimension",
  "554": "Jellix Show",
  "559": "Jelly Dungeon",
  "565": "The Wabbit Hutch",
  "571": "The Black Purr",
  "575": "Zinit",
  "576": "Zinit",
  "583": "Wun-Down Labowatowy",
  "584": "Black Wabbit Dungeon",
  "585": "Abandoned Cawwot Stowewoom",
  "586": "Gleat Clans' Dojo",
  "587": "Lenald Palace",
  "588": "Lenald Plison",
  "589": "Black Wabbit Headquawtews",
  "590": "Kween's Gawden",
  "591": "Wabbit Island",
  "592": "Tempowawy Thwone Woom",
  "593": "Fowbidden Labowatowy",
  "597": "Storeroom",
  "598": "Warehouse",
  "599": "Wa Wabbit's Castle",
  "600": "Wabbit Islands",
  "601": "Old Gallewy",
  "602": "Harebourg's Site",
  "603": "Wa's Chest",
  "604": "Lenald Plison",
  "609": "The Ingalsses' Cellar",
  "611": "Old Port Stockroom",
  "613": "Temple of Ogrest's Cult",
  "615": "Wabbit Tunnels",
  "621": "Incarnam",
  "622": "Wabbit Temple",
  "697": "Vault Door",
  "698": "Distance Dojo",
  "699": "Elemental Dojo",
  "700": "Butt-Kicking Dojo",
  "701": "Support Dojo",
  "702": "Garden of Rest",
  "704": "Supervillains' Lair",
  "705": "Decepticod's Weight Room",
  "707": "Alkatrool Island",
  "708": "Alkatrool Prison",
  "709": "Merkator's Boiler Room",
  "711": "Wild Estate",
  "712": "The Forgotten Lair",
  "714": "Brakmarian Archaosologists' Excavation Galleries",
  "715": "Sufokian Archaosology Camp's Reserves",
  "718": "Ancient Bwork Temple",
  "720": "Quarantine Zone",
  "723": "Brakmarian Excavation Site",
  "725": "The Zonzon",
  "726": "Bwork Chief Quarters",
  "727": "Incarnam",
  "728": "Larva Nest",
  "747": "Temple of Ogrest's Cult",
  "748": "Sisters of Dathura's Hideout",
  "749": "Temple of Scriptures",
  "766": "West",
  "767": "East",
  "768": "Hushquarters",
  "769": "The Rock",
  "770": "Crackapult Range",
  "771": "Moors - West",
  "772": "Moors - East",
  "773": "The Undieworld - West",
  "774": "The Undieworld - East",
  "775": "Dancehall Arena",
  "776": "Platform - East",
  "777": "Southeast",
  "778": "Under the bridge",
  "779": "Dig site",
  "780": "Seaside - South",
  "781": "Wa Wabbit's Castle",
  "782": "Cawwot - Northwest",
  "783": "Cawwot - North",
  "784": "Zaap",
  "785": "Amakna Bridge",
  "786": "Moors - South",
  "787": "Peaks - North",
  "788": "Amaknian Garrison",
  "789": "Bontarian Garrison",
  "790": "Brakmarian Garrison",
  "791": "Sufokian Garrison",
  "792": "Ohwymi",
  "793": "Sthulhu Territory",
  "794": "Shusnitch Reef",
  "795": "Tormentor Pit",
  "796": "The Fungopole",
  "798": "Castuc Dungeon",
  "799": "Abandoned Inn",
  "800": "Castuc Village",
  "801": "Castuc Cemetery",
  "802": "Ancestral Passageway",
  "803": "Spore Room",
  "804": "Contaminated Spring",
  "805": "Amybian Temple",
  "806": "Blackspore Dungeon",
  "807": "Amybian Temple",
  "813": "Underground Fountain",
  "814": "Castuc Grove",
  "815": "Craggy Passageway",
  "816": "Flaxhid's Sanctuary",
  "817": "Underground Fountain",
  "820": "Wild Estate - Secrets",
  "821": "Wabbit Island - Secrets",
  "822": "Forfut - Secrets",
  "823": "Frigost - Secrets",
  "824": "Monk Island - Secrets",
  "825": "Unknown Island - Secrets",
  "826": "Condemned Seed Storeroom",
  "827": "Amaknian Basement",
  "832": "Astrub - Secrets",
  "837": "Ingloriom",
  "838": "Workshop House \"Pandora's Place\"",
  "839": "Temple of Scriptures Machine Room",
  "840": "Service Entrance to Harebourg Tower",
  "841": "Service Passage",
  "842": "Trophy Room",
  "843": "Srambad",
  "844": "Tethdrap Alley",
  "845": "Shadowy House",
  "847": "Trickree Street",
  "848": "Dimensional Voyager's Headquarters",
  "849": "Somewhere in Srambad...",
  "850": "Srambad's Enutrof Bank",
  "851": "Srambad Dungeon",
  "853": "Enurado",
  "855": "Enutrof Temple",
  "856": "Ingloriom",
  "858": "Enurado Front Desk",
  "859": "Absynteeism Inn",
  "862": "Cap'n Atcha's Haven",
  "863": "Skrammerzell House",
  "864": "Enuradan Ambassador's House",
  "865": "Sadida Dimension",
  "866": "Filacia's Garden",
  "879": "Dragoturkey Enclosure",
  "880": "Amakna",
  "881": "Bonta",
  "882": "Brakmar",
  "883": "Sufokia",
  "888": "Mercenary Reserve",
  "889": "The Blasphemer's Crypt",
  "891": "E.Z. Yeast's Kitchen",
  "892": "Srambad House",
  "893": "Astrub Suburbs",
  "895": "Pal House",
  "897": "Riktus Clan",
  "898": "Unknown area",
  "899": "Training Room",
  "901": "The Raised Vault",
  "902": "Larventura",
  "903": "Riktus Boat Cargo Hold",
  "907": "Wikan Dewitt's Reserve",
  "909": "Abandoned Scarapit",
  "910": "Sureberry Fields",
  "911": "Blibli Dungeon",
  "912": "Snapper Dungeon",
  "913": "Vaporous Cloud",
  "914": "Bermuda Triangle",
  "916": "Mecha Factory",
  "919": "Explorancient's House",
  "920": "Xelorium",
  "922": "Xelorium - Past",
  "923": "Xelorium - Present",
  "924": "Xelorium",
  "925": "Xelorium",
  "926": "Ingloriom Temple",
  "929": "Time Observatory",
  "930": "Time Rift",
  "932": "Sage's House",
  "933": "Somewhere...",
  "935": "Xelorium - Present",
  "936": "Astrub Blasphemer's Crypt",
  "937": "Sage's House",
  "943": "Kelba",
  "944": "Kabrok's Shop",
  "945": "Kabrok's Shop",
  "946": "Kelba Port",
  "947": "On the road...",
  "948": "Hadibal's Hideout",
  "949": "The Black Crow's Lair",
  "950": "Dungeon of the Black Crow's Lair",
  "951": "Locker of the Black Crow's Lair",
  "952": "Kabrok's Cavern",
  "954": "Ush's Hiding Place",
  "955": "Temple of the Grand Orrok",
  "959": "High Wind Plateau",
  "960": "Abandoned Workshop",
  "961": "The Black Crow's Locker",
  "962": "Black Crow's Antechamber",
  "963": "The Stalagmotel",
  "965": "Miseryeum",
  "967": "Ecaflipus (Arenas)",
  "968": "Floating Forest",
  "969": "Waterfall Chase",
  "970": "Garbage Peak",
  "971": "Quick Jungle",
  "972": "White Slab",
  "973": "Monastery Dome",
  "974": "Holey Mine",
  "975": "Lukewarm Basin",
  "976": "Max Bay",
  "980": "Mount Zinit Reefs",
  "981": "Mount Zinit Ethereal Reefs",
  "982": "Pool of Sufokia",
  "985": "Brakmar Crypt",
  "986": "Zinit Beach",
  "987": "Ogrest's Cult's Blast Hole",
  "988": "Ogrest's Cult Cinematic",
  "989": "Ullu Cinematic",
  "999": "Moon",
  "1000": "Tropickle Dungeon",
  "1001": "Archaosological Excavation Site",
  "1002": "Bovis's Lair",
  "1003": "Oktapodas's Sunken Temple - Sufokian Shore",
  "1004": "The Ogre's Salines - Night",
  "1005": "Ancient Shepherd's Cellar",
  "1006": "Kannivore Dungeon",
  "1007": "Kanniball Dungeon",
  "1008": "Gengas Kin's Platform",
  "1009": "Koko Riko's Platform",
  "1012": "Amakna",
  "1017": "Rok Island",
  "1018": "Huppermage School - Downstairs",
  "1019": "Huppermage School - Upstairs",
  "1020": "Huppermage School Dormitories",
  "1021": "Huppermage School Greenhouse",
  "1022": "Huppermage School Garden",
  "1023": "Huppermage School Library",
  "1024": "Huppermage School Store Room",
  "1025": "Huppermage School Equipment Room",
  "1026": "Flooded Path",
  "1027": "A Pancentage of Labyrinth",
  "1028": "Hoodlums' Lair",
  "1029": "The Occullege",
  "1030": "Immaterial University of Bonta",
  "1031": "Immaterial University of Bonta",
  "1032": "Immaterial University of Bonta",
  "1033": "Old Bonta Ruins",
  "1034": "Old Bonta Ruins",
  "1035": "Gobbowl Stadium - Old Bonta",
  "1036": "Initiation Platform",
  "1039": "Registration Office",
  "1042": "Moon - Dofus Era",
  "1043": "Xelorium - Dofus Era",
  "1044": "Amakna - Dofus Era",
  "1045": "Astrub - Dofus Era",
  "1046": "Bonta - Dofus Era",
  "1047": "Brakmar - Dofus Era",
  "1048": "Sufokia - Dofus Era",
  "1050": "Wabbit Island - Dofus Era",
  "1051": "Enurado - Dofus Era",
  "1052": "Srambad - Dofus Era",
  "1053": "Moon Island Tunnels",
  "1054": "Crocodyl Dungeon",
  "1056": "Top of Giant Totem",
  "1057": "Dandy Mos Croc's Platform",
  "1058": "Event Area",
  "1063": "Brakmar Slums",
  "1071": "Incarnam",
  "1073": "Incarnam Dungeon",
  "1074": "The Stone Perch",
  "1075": "Märine Pälace",
  "1076": "Incarnam Plains",
  "1079": "The Villainy Vineyards",
  "1080": "Sidimotes & Co. Factory",
  "1081": "Charles-Henri of Vileardent's Office",
  "1082": "Charles-Henri's Laboratory",
  "1083": "Tunnel to the Mechamummy Palace",
  "1084": "Mechamummy Palace",
  "1086": "Gobball Pastures",
  "1087": "The Tofuhouse",
  "1089": "Temple of Scriptures",
  "1091": "Treechnee Dungeon",
  "1092": "Nogord Wungleezared's Lair - Past",
  "1093": "Nogord Wungleezared's Lair - Present",
  "1094": "Astrub Mines",
  "1095": "Oktapodas's Sunken Temple - Flooded Gallery",
  "1096": "Sufokia Submarine Hangar",
  "1097": "Fleebagh Boarding",
  "1098": "Nemotilus Interior",
  "1099": "Submarine Exterior",
  "1100": "Underwater Entrance to Oktapodas's Temple",
  "1101": "Pools of Oktapodas's Temple",
  "1102": "Oktapodas's Temple",
  "1103": "Sufokia Hangar Swimming Pool",
  "1104": "Amakna - Dofus Era",
  "1105": "Amakna - Dofus Era",
  "1106": "Bonta - Dofus Era",
  "1107": "Brakmar - Dofus Era",
  "1108": "Enurado - Dofus Era",
  "1109": "Moon - Dofus Era",
  "1111": "Srambad - Dofus Era",
  "1112": "Sufokia - Dofus Era",
  "1113": "Wabbit Island - Dofus Era",
  "1114": "Xelorium - Dofus Era",
  "1117": "Entrance to Oktapodas's Temple",
  "1118": "Wild Beach",
  "1119": "Schnek Cave",
  "1120": "Lower Slope",
  "1121": "Vessel",
  "1122": "Upper Slope",
  "1123": "Dor'Mor Cave",
  "1124": "Summit",
  "1126": "Schnekymosis Cavern",
  "1127": "The Whirlway Station",
  "1128": "Dirty Trouffe Estate",
  "1129": "Kali's Lair",
  "1130": "Badgeroxes' Lair",
  "1131": "Or'Hodruin Volcano",
  "1132": "Dreggons' Sanctuary",
  "1133": "Iced-Over Crest",
  "1134": "Amakna",
  "1135": "Sufokia",
  "1136": "Bonta",
  "1137": "Brakmar",
  "1138": "Wild Cave",
  "1139": "Mount Zinit Summit",
  "1140": "Harebourg's Cemetery Tower",
  "1141": "Lower Slope",
  "1144": "Grottoesque Passage",
  "1146": "Nap Passage",
  "1147": "Forgotten Dimension",
  "1149": "Tree of Life Room",
  "1154": "Sufokia - Interiors",
  "1156": "Mount Zinit Peak",
  "1157": "Ouginak Village",
  "1158": "Amakna - Interiors",
  "1159": "The Mineral Tower",
  "1160": "Battlefield",
  "1161": "The Great Escort",
  "1201": "Mineral Tower",
  "1202": "Mineral Tower Entrance",
  "1203": "Capture the Flowers",
  "1204": "The Mineral Tower",
  "1205": "Riktus Clan Prison",
  "1207": "Amakna Mine",
  "1208": "Sufokia Mine",
  "1209": "Bonta Mine",
  "1210": "Brakmar Mine",
  "1211": "Bonta - Interiors",
  "1212": "Brakmar - Interiors",
  "1213": "Hideout of Ogrest's Cult",
  "1214": "Astrub Court",
  "1215": "Astrub Court",
  "1216": "Hideout of Ogrest's Cult",
  "1217": "The Heroic Great Escort",
  "1218": "Heroic Capture the Flowers",
  "1219": "Free-for-Alls",
  "1222": "Dragon Pig Island",
  "1223": "Musical Blop Dungeon",
  "1224": "Crackler Dungeon",
  "1225": "Amakna Prison",
  "1226": "Bonta Prison",
  "1227": "Brakmar Prison",
  "1228": "Sufokia Prison",
  "1229": "Shadofang Ring",
  "1231": "Île au large",
  "1232": "Hall of Wagnar's Castle",
  "1237": "Amakna Governor's HQ",
  "1238": "Amakna Guard HQ",
  "1239": "Bonta Governor's HQ",
  "1240": "Bonta Guard HQ",
  "1241": "Brakmar Governor's HQ",
  "1242": "Brakmar Guard HQ",
  "1243": "Sufokia Governor's HQ",
  "1244": "Sufokia Guard HQ",
  "1245": "Amakna Sewers",
  "1246": "Bonta Sewers",
  "1247": "Brakmar Sewers",
  "1248": "Sufokia Sewers",
  "1249": "The Jolly Riktus",
  "1250": "Rogue Dungeon",
  "1252": "Pandalucia Valley",
  "1253": "Pandalucia House",
  "1254": "Wellspring of Evil",
  "1255": "Pandala Tomb",
  "1256": "Forbidden City",
  "1257": "Blightopard Canyon",
  "1259": "Pandalucia Mines",
  "1264": "Sadida Kingdom",
  "1266": "Boowolf Dungeon",
  "1267": "King Sheran Sharm's Palace",
  "1268": "Arachnee Dungeon",
  "1270": "Gerbean Dungeon",
  "1271": "Bubourg Factory",
  "1273": "Srambad Prison",
  "1274": "Xelorium",
  "1275": "Reminiscence",
  "1276": "Osamosa",
  "1281": "Sunsloth Dungeon",
  "1282": "Crabstacean Dungeon",
  "1283": "Tundrazor Dungeon",
  "1284": "Vandalophrenic Dungeon",
  "1285": "Osamodas's Palace",
  "1286": "Osamodas's Throne",
  "1287": "Osamodas's Throne",
  "1288": "Osamosa Mine",
  "1289": "Osamosa Antechamber",
  "1292": "Osamosa - Interiors",
  "1294": "The Mineral Tower",
  "1295": "Shhhudoku Kingdom",
  "1296": "Plantiguard Dungeon",
  "1297": "Pingwins' Ice Floe",
  "1298": "Inside Grampar",
  "1299": "Shhhudoprison",
  "1300": "Pingwin Dungeon",
  "1301": "Scramshell Dungeon",
  "1302": "Whisper Crisper",
  "1303": "Mount Zinit",
  "1304": "Summit",
  "1305": "Kingdom of Despair",
  "1308": "Phytomorph Dungeon",
  "1309": "Void Spiral",
  "1313": "Voidivion Dungeon",
  "1314": "Tainela Dimensional Rift",
  "1316": "Sufokia Dimensional Rift",
  "1318": "Frigost Dimensional Rift",
  "1320": "Bonta Dimensional Rift",
  "1322": "Moon Dimensional Rift",
  "1324": "Mount Zinit Dimensional Rift",
  "1326": "Citadel of Horror",
  "1328": "Horridemon Dungeon",
  "1329": "Amakna Dimensional Rift",
  "1330": "Osamosa Dimensional Rift",
  "1332": "Rushu's Palace",
  "1333": "Dementya",
  "1334": "Demonic Prison",
  "1336": "????",
  "1338": "Route of the Dead",
  "1341": "Destroyer Dungeon",
  "1342": "Fallen Souls' Crossing",
  "1345": "Shustuft Crust Dimensional Rift",
  "1347": "Shustuft Crust Ultimate Dimensional Rift",
  "1349": "Chapel",
  "1350": "Crypt",
  "1351": "Crypt",
  "1352": "Strange Place",
  "1353": "Weird Place",
  "1354": "Route of the Dead",
  "1355": "Tomb of the Forgotten",
  "1356": "Torture Chamber",
  "1358": "Pirate Beach",
  "1359": "Cursed Beach",
  "1360": "Ereboria Harbor",
  "1361": "Incarnam",
  "1364": "Bitter-Hammer Cavern",
  "1365": "New Sufokian Mine",
  "1366": "Mysterious Place",
  "1367": "Mysterious Place",
  "1368": "Ocean Prison",
  "1369": "Octopus Crew Dungeon",
  "1370": "Abyssal Creeper Dungeon",
  "1371": "Bitter-Hammer Dungeon",
  "1372": "Deathburn Dungeon",
  "1373": "Foggernaut Dungeon",
  "1374": "Inside",
  "1375": "Small Island",
  "1376": "Stubbyob Storeroom",
  "1377": "Inside the Ship",
  "1378": "Cemetery",
  "1379": "Ancient Forge",
  "1380": "Memory of Another World",
  "1381": "Final Moment of the Dream",
  "1382": "The Passage",
  "1383": "Proving Ground",
  "1384": "Wabbit Island",
  "1385": "Celestial Island",
  "1387": "Celestial Sanctuary",
  "1388": "Celestial Dojo",
  "1389": "Miss Ugly Tower",
  "1390": "Ghoulish Tunnels",
  "1391": "Rushu's Palace",
  "1393": "Interior of Wabbit Island",
  "1394": "Great Zomkin's Compost",
  "1395": "Sandyoptera Mother-Hive",
  "1396": "Womewo's Labowatowy",
  "1397": "Empelol's Palace",
  "1398": "Kween's Gawden",
  "1399": "The Wa's Fowtwess",
  "1400": "Depths of the Pyramid",
  "1401": "Misty Isle",
  "1402": "Mysterious Pyramid",
  "1403": "Necroworld",
  "1405": "Necroworld",
  "1406": "Summit of the Misty Isle",
  "1407": "Heart of the Island",
  "1408": "Forgotten Sanctuary",
  "1410": "Blop Memory",
  "1414": "Clock Exterior",
  "1415": "Primount Dungeon",
  "1416": "Ferociraptor Dungeon",
  "1417": "Crocodyl Temple",
  "1418": "Nox Machine Dungeon",
  "1419": "Bworkana Clan Dungeon",
  "1420": "Zurikat Hut",
  "1421": "Cave",
  "1422": "Starvannah Dungeon",
  "1423": "UGW Headquarters",
  "1427": "Cave",
  "1429": "Timeless Theater",
  "1430": "Clock Interior",
  "1431": "Bwork Herd",
  "1432": "The Misty Isle's Secret",
  "1435": "Clock Main Room",
  "1436": "Egg Cavern",
  "1437": "Crypt",
  "1438": "Grambo Mine",
  "1440": "Haven Place",
  "1441": "Celestial Island",
  "1444": "Celestial Island",
  "1445": "Celestial Island",
  "1446": "Neo Mount Zinit Peak",
  "1447": "Neo Black Crow's Lair",
  "1448": "Nox's Clock",
  "1449": "Misty Isle",
  "1450": "Neo Pasturizer",
  "1451": "Neo Rogue Dungeon",
  "1452": "Neo Wagnar's Castle",
  "1453": "Neo Wa's Fowtwess",
  "1454": "Neo Treechnid Dungeon",
  "1455": "Neo Bitter-Hammer Dungeon",
  "1456": "Neo Ambassador's Wing",
  "1457": "Neo Forbidden City",
  "1458": "Neo Blibli Dungeon",
  "1459": "Neo Gobball Pastures",
  "1460": "Neo Hoola Hoopiwi",
  "1461": "Neo Vessel",
  "1464": "Neo HQ",
  "1465": "Mount Zinit",
  "1476": "Neo Ship Wreckage",
  "1477": "Mysterious Place",
  "1488": "Aligias's Cave",
  "1492": "Hold of Xineigyhnu's Boat"
}
$names$::jsonb)
ON CONFLICT (name) DO NOTHING;
