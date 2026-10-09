# Cra active casting code audit — 2026-10-08

This is a current-source and installed-catalog review, not a gameplay test or a certification. Breed9 contains exactly **21 active book definitions** and 19 passive definitions. The21 actives have casting records; their static dependency closure contains **838 effect definitions**, **28 condition functions**, and **18 conditional casting rules**. Every identified condition has a current source route and every dependency family has an identified consumer. That establishes routing presence only; conditional provider scopes remain explicit below.

Names come directly from installed Spanish `content.3.<reference>` translations. The JSON includes exact source hashes, per-spell ordered roots and costs/ranges at levels1/20/200/245, all conditional tables, raw effect criteria, state/area/profile dependencies, effect IDs mapped to consumers, exact guard lines/messages, and native selector/area/flags/timing/subscription metadata for all838 definitions. No tests were run and no runtime behavior was changed for this audit.

## Exhaustive active inventory

| Reference | Installed name | Unlock | Cost AP/MP/WP L20 | Range L20 | LOS | Conditional rules | Effect dependencies |
|---|---|---:|---|---|---|---:|---:|
| 4769 | Flecha Ardiente | 15 | 2/0/0 | 2–5 | True | 1 | 98 |
| 4774 | Voltereta | 3 | 0/0/2 | 1–3 | True | 0 | 2 |
| 4805 | Retirada Balizada | 15 | 2/0/0 | 3–6 | True | 0 | 2 |
| 4806 | Explorador | 30 | 2/0/0 | 0–0 | True | 0 | 77 |
| 4808 | Golpe Incisivo | 60 | 2/0/0 | 4–6 | True | 0 | 10 |
| 4809 | Flecha de Tempestad | 13 | 3/0/0 | 3–6 | True | 1 | 73 |
| 4810 | Flecha de Retroceso | 7 | 3/0/1 | 1–4 | True | 1 | 88 |
| 4811 | Flecha Acosante | 19 | 4/0/0 | 2–6 | False | 1 | 117 |
| 4812 | Flecha Estática | 25 | 5/0/1 | 5–8 | True | 1 | 88 |
| 4813 | Flecha Buscadora | 1 | 2/0/0 | 4–9 | True | 4 | 68 |
| 4814 | Flecha Destructiva | 23 | 6/0/1 | 3–5 | True | 1 | 82 |
| 4815 | Flecha Atravesadora | 17 | 5/0/0 | 2–4 | True | 1 | 76 |
| 4816 | Flecha Azotadora | 1 | 3/0/0 | 2–4 | True | 1 | 70 |
| 4817 | Lluvia de Flechas | 5 | 4/0/0 | 4–6 | False | 1 | 89 |
| 4818 | Flecha Perforante | 11 | 3/0/1 | 2–5 | True | 1 | 102 |
| 4819 | Flecha Explosiva | 21 | 5/0/1 | 3–5 | True | 1 | 43 |
| 4820 | Flecha Fulminante | 1 | 3/0/0 | 2–5 | True | 1 | 64 |
| 4821 | Flecha Flamígera | 9 | 4/0/0 | 2–5 | True | 1 | 53 |
| 4822 | Flecha de Inmolación | 3 | 2/0/0 | 2–5 | True | 1 | 84 |
| 6842 | Ráfaga | 90 | 1/0/1 | 0–0 | True | 0 | 20 |
| 7753 | Ojo de Topo | 45 | 0/2/1 | 3–6 | True | 0 | 4 |

## Casting, conditions and actual restrictions

`combat_cast.py:107` selects the actual owned actor/book reference; `combat_cast.py:123` selects the whole native conditional table and resolves live range. `combat_casting_range.py:23` reads live caster RANGE, carried status, property2 and eHl category modifiers. `combat_casting_context.py` supplies common QI, LOS, alignment and portal eligibility. Costs, insufficient resources, turn ownership, usage limits, forbidden targets, occupied required-free cells and genuine LOS failures are legal rejections, not missing handlers. Conditional state/deck predicates must be reached through actual production state/deck lifecycle; baseline attempts do not prove their positive branch.

The15 elemental arrows each have the native passive6949 table branch; Buscadora4813 has four explicit tables split by state7757, Precision7792 level≥30, and deck6949. Its native LOS=False positive branch and LOS=True independent control already have separate transaction evidence; this audit does not rerun that evidence or generalize it to every arrow. The full18 rule texts/tables are in the JSON.

Tooltip range and target-mask range are different native consumers: tooltip adds RANGE and clamps to minimum, while fcj also applies its modifiable gate, carried extra1 and property2 cap. A difference at those inputs is original-client behavior, not an authority gap. Conditional tooltip selection uses null target; actual target selection can choose a different table. See `native-client-casting-display-parity-20261008.md`.

## Concrete gaps and incomplete scopes

- **Selected-surface loss, resolved source bug:** Voltereta4774 reaches teleport family302. Fresh placement formerly discarded native surface indices/provenance in `combat_placement_policy._arena`. The shared producer is corrected and r14 has real map527 evidence; this audit does not claim live user acceptance. Retirada Balizada4805 shares family302 and benefits from that same authority.
- **Native terrain data missing on27 legacy archives:** `combat_qi_surface_catalog.py:56` rejects failed native decode. This affects selected-terrain/occupancy prerequisites generally, independently of a spell ID. No alternative walk-height or clear-ray fallback is present. The map527 dataset is available; it is not one of these missing exports.
- **Critical rolling is an explicit server policy:** `combat_critical.py:30` uses actual PC9 and transaction RNG; native variant availability is exported separately. Presence of normal and critical consumers does not prove every critical state/group/secondary branch. JSON records each spell’s attested critical level domain. Requests outside that domain reject rather than inventing availability.
- **Guarded effect/provider scopes:** each spell’s JSON `findings` lists exact effect IDs, consumer file and source guard lines. These include missing typed PV/state/PA/QI/geometry/timing/trigger authority and unsupported parameter variants. They are conditional source boundaries, not evidence that those guards reject this spell’s native configuration. No branch is labelled broken solely because a guard exists.
- **No demonstrated absent consumer in the21 active closures:** all identified families route through the production factory, characteristic registry or dispatcher groups. This does not establish retained removal, all target selectors, all critical branches, all states, or all maps as complete.

## Class-owned additional abilities and beacons

The21 book actives do not include every ability granted by class innates, passives or state/effect transitions. Actual Ready grant references from the prior normal-cast dataset are separately recorded in JSON. Beacon creation and reactions require those source-owned grants and owner innates; counting only book actives or equating a family400 visual/null outcome with damage would omit class mechanics. Static graph edges do not certify dynamic grant reachability.

## Reading the detailed findings

For each spell, `consumer_routes` maps every reachable effect ID to a current module and its literal guard locations. `effect_source_index` contains native selectors, target masks, area shape, execution/flags, raw parameters and subscription ownership. `condition_source_index` identifies current evaluator lines; the older condition-inventory provider annotations are explicitly marked as historical, not fresh proof. `previous_baseline_evidence` is retained as dated execution evidence only. Failed baseline criteria and legal resource/target rejections remain distinguishable from literal missing authority errors.

No restart, container, database operation, fresh casting test or fixes were performed for this audit.

## Parameter-count cross-check and innate supplement

Native raw parameters are base/growth pairs, not independent evaluated values. In particular effect347121/family321 stores `[7792,0,0,15]`: two logical parameters, accepted by `combat_state_decurse.py:35`. It is not an unsupported four-parameter variant. Current removal arithmetic evaluates the second parameter at the actual invocation level; the growth15 must not be erased or treated as a literal counter without native context proof. All family321 definitions reached by the21 active closures have one or two logical parameters. The JSON separately inventories321 definitions reached from actual Cra innates3419/4464, including exact raw pairs and count checks. No unsupported count was found. This does not certify every positive remainder/reapplication or protection interaction.

The normal owned-book denominator remains21, while the separate innate supplement includes transitive extra spell references. Current-source absence totals for the21 active closures are zero missing casting records, zero unidentified consumer families, zero unidentified condition functions, and zero missing static dependency nodes. These totals do not imply complete PvP, all retained states, all target variants or client behavior.
