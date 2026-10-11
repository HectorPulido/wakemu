# User-excluded low-level actors

The user requested ignoring the 382 references without native owned spellbooks whose entire native level range lies below 10, and the incomplete test actor 3118 (`Monstre Cellule Test`, missing state 3767). They remain in the complete 2,874-reference source inventory, but are excluded from activation work and actionable totals.

This is a workflow decision, not a verified classification of all 382 actors as NPCs, beta content or mission actors. Names and levels alone do not prove their purpose.

The policy snapshots explicit reference IDs in `server/tools/monster_activation_exceptions.py`. It does not silently exclude higher-level actors with empty books. Even if a later coverage report calls an ignored reference fully covered, automatic activation still rejects it until this explicit policy is revised. The seven trainer/racing encounter exceptions remain a separate category.

Current statuses:

| Status | Count |
| --- | ---: |
| `excluded_no_owned_spells` |382|
| `excluded_incomplete_data` |1|

The full native-below 10 inventory still contains 487 references. Removing these 383 ignored entries leaves 104 for review, including 57 activated, seven encounter exceptions, five pending native prerequisites, 23 covered references with ranges starting at zero, seven missing one effect family and five missing multiple families. Within positive native ranges 1–9, the remaining total is 73: 57 activated, seven encounter exceptions, five pending, two missing one family and two missing multiple families.

No runtime spell, class, active catalog or service changed. The active 57 references remain enabled. Historical deployment receipts remain immutable; the current JSON/CSV inventory additionally records this later policy decision.

Validation: 17 selection, explicit-exclusion, pipeline-safety and automation tests passed. Existing tests were unchanged. The three new tests verify the complete 382-reference snapshot, exclusion at maximum levels 9/100/30000 even under a synthetic covered classification, and distinct reasons for ignored actors versus encounter exceptions.
