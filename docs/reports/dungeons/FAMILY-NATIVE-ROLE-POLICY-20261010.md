# Mandatory dungeon roster role policy

User clarification: generated or approximated family groups must contain no dominant monsters or archmonsters. Authentic documented native encounters, including optional archmonster rooms, may retain those actors when their identities and locations are verified. The generic family generator remains filtered; genuine optional encounters require separate explicit evidence and must not become mandatory main-route stages. Selected main-route family bosses remain final-only.

## Native authority

The existing read-only `javap` export `.runtime/local/native-world-property-eHQ.txt` explicitly constructs these native enum constants with numeric IDs:

| Native enum | Property ID | Evidence lines |
| --- | ---: | --- |
| BOSS | 43 | 1124–1128 |
| ARCH | 45 | 1140–1144 |
| DOMINANT_NPC | 115 | 1686–1690 |

The enum constructor receives name, Java ordinal, then native property ID. The ordinal must not be mistaken for the native ID. Monster export `raw_visual_arrays.csc` carries these native world property IDs. Example native dominant monsters have115; Archibuhatrás5139 and archmonster Patkilla5017 have45.

## Implementation

`server/tools/extract_dungeon_family_bosses.py` exposes `native_role`, `role_allowed` and `load_role_catalog`. Forbidden roles take precedence even if an actor is also BOSS-tagged. Metadata must contain an explicit integer property list; missing or malformed metadata is `unknown` and fails closed. Ordinary monsters are allowed. Selected bosses are allowed only with `final_room=True` and membership in `allowed_boss_references`.

The boss/family extractor itself filters forbidden and unknown roles and records `excluded_role_references`; names, levels and reference order never override native roles. This is an offline preparation policy, with no client hooks or runtime filesystem fallback.

## Audit and tests

`FAMILY-NATIVE-ROLE-AUDIT-20261010.json` audits all74 existing candidate configurations across seven batches: no dominant monsters, no archmonsters, no unknown native records and no unselected or premature bosses. Selected-boss authority comes from `REMAINING-FAMILY-BOSSES-20261010.json`, because some guide-derived compiled plans omit their own boss-reference field.

These are frozen existing batches; the progression regeneration agents must apply this policy again to new versioned outputs. No activation is implied by this audit.

`PYTHONPATH=server python3 -m unittest server/tests/test_dungeon_family_boss_evidence.py`: ten tests passed, covering forbidden-role precedence, malformed metadata, final-only selected bosses, ordinary actors and family/boss extraction.
