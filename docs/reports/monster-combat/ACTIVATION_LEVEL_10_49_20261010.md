# Automated activation below level 50 — 2026-10-10–11

Deployed and healthy: **190 newly activated references**, preserving the previous 57 exactly; **247 activated references total**. Catalog `677062aedeeb9fa0deaad21e0c9a40989e5c8b64cc13b1ebba7200f684d3437d`. World and AI contain the complete current shared implementation. Fishing and mining pins were preserved.

## New range and denominators

There are 371 references with positive native ranges whose **maximum is 10–49 inclusive**. Of these, 303 have every effect family covered. The full-range 1–9 cohort was not re-previewed. Seventeen newly eligible references start below 10 but extend beyond 9; they were not activated wild references in the prior cohort. Counts are definitions/references, not deduplicated visual species.

| Status | References | % of 371 |
| --- | ---: | ---: |
| Newly activated, complete books verified | 190 | 51.21% |
| Covered but pending native execution/initialization/delivery | 107 | 28.84% |
| Covered but pending import dependencies | 6 | 1.62% |
| Missing one effect family | 21 | 5.66% |
| Missing multiple effect families | 6 | 1.62% |
| No native owned spellbook | 41 | 11.05% |

The automatic pass activated **190/303 statically compatible references (62.71%)**. The remaining **113** covered references remain disabled; incomplete books are never partially enabled. Across all positive native ranges below 50, the retained/new active count is 247/695 (35.54%). The all-level inventory still contains 2,874 references and preserves all 390 explicit exclusions, five earlier pending cases and every previously enabled record.

## Verification

- Final publication candidate: 190 references were evaluated on the current stable sources: **1151 native owned spell/actor-level cases**. Every activated reference has effectful execution for every owned spell at every native level, complete constructor evidence where required, real AI commit, immutable forecast and forced serializer-failure rollback.
- **366 class/shared/activation tests + 64 SDK/movement/remote-effect/microbot tests = 430 passing tests**, zero failures, errors or skips. This pass did not edit pre-existing tests or relax assertions; the complete checkout includes concurrent agents’ changes.
- Candidate/base/runtime/validator/test/native-source fingerprints matched throughout the final validation. Published unchanged documents and existing class rows are checked against the active baseline. The baseline 57 enabled policy rows remain byte-equivalent.
- world: `sha256:b0038d7080cee7b4f6c512ed273274cb616fcc4de76e788b6e8d26873d8b881a`; 775 current source files checked, zero differences; healthy after restart.
- ai: `sha256:274b9d6ade7fe6200080b9f4a7b26e2095dc4f57fc8a55bcf5a9ad7bf9c6c5c0`; 875 current source files checked, zero differences; healthy after restart.

## Pending cases and reusable automation

Six references were held before execution: 2096 (Bruja) summons profile 2107 with an empty owned book; 3752, 3756, 3813, 3905 and 3974 depend on one-parameter native 307 descriptors whose exact level domain the current importer cannot attest. Their client definitions exist; this is not evidence of corrupt client data. No descriptor default was guessed.

Other covered references retain exact execution errors in the cohort CSV and inventory. Blockers include resources, native criteria, constructor/area handling or native casting metadata. A finite scenario may also lack a genuine encounter prerequisite; pending does not establish that the original mechanic is impossible. No new shared combat or class handler was implemented for this pass.

The validator now omits exhausted scenario fixtures and discarded ordinary-spell empty-cell searches. Missing native casting roots in scene search mark a case pending; unexpected errors still fail the run. Seven additive tests cover those boundaries. An initial parallel attempt caused memory pressure and one read-connection interruption. A subsequent 297-reference screening pass completed 2,139 cases but its source fence detected a concurrent change in combat_microbot_path.py and rejected publication. Its 192 potential passes were selected into a narrower inactive candidate. A second source fence detected concurrent combat_start_events.py work and again rejected publication. Reference 3854 then failed the real AI-commit observability check. Reference 1 was withheld because its activation invalidates an existing tactical test’s explicit baseline-only NPC-root expectation; that test was kept intact. The final narrower candidate was validated again from scratch on the current complete checkout. The 105 screened failures remain disabled with diagnostic-only receipts. No unstable receipt is accepted as publication proof.

[Reusable workflow for later ranges](AUTOMATION_COHORTS.md) explains the same pipeline for maximum native levels 50–99 and beyond, without redoing earlier native cohorts or using per-monster LLM calls. Shared class regressions still run for each publication.

[New covered-reference inventory](LEVEL_10_49_STATUS.csv) lists all 303 candidate results. [Complete all-level inventory](ACTIVATION_STATUS.csv) retains all 2,874 definitions. Full private execution, staging, image and deployment receipts are under `.runtime/monster-level49-20261010/`.

[Manual acceptance](MANUAL_LEVEL_10_49_20261010.md) is the final in-client review; automated activation is not a claim that Hector has manually reviewed every monster.
