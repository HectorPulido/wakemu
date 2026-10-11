# Automated under-level-10 activation — 2026-10-10

The reusable pipeline evaluated all 39 previously pending references. Ten passed every execution gate and are now enabled; 29 remain disabled. World and AI were rebuilt from the complete shared checkout and verified healthy after deployment. Manual acceptance is pending.

| Population | Enabled | Pending | Enabled percentage |
|---|---:|---:|---:|
| Previously pending, fully covered references below 10 | 10 | 29 | 25.64% |
| Entire fully covered native level 1–9 cohort | 40 | 29 | 57.97% |
| All 324 references whose entire native level range is 1–9 | 40 | 284 | 12.35% |

The last denominator includes pets, quest actors and variants, including 251 references without owned spells and four with uncovered families. These are native reference counts, not counts of wild species.

## New enabled references

2090 Jalatín de Haluín; 3264 Alma de arquera sin descanso; 3265 Alma de general sin descanso; 3266 Alma de lancera sin descanso; 4013 Alma agitada; 4014 Jalató stasiado; 4015 Tofu corrupto; 5251 Abuelito de hielo; 5252 El último viajero; 5656 Jinete.

See the [complete manual acceptance sequence](MANUAL_PENDING_COHORT.md) for exact spawn commands and expected behavior. [Enabled CSV](ACTIVATED_MONSTERS.csv), [pending CSV](PENDING_UNDER_10.csv), and [full inventory](ACTIVATION_STATUS.json) cover the final status of all 2,874 references, including higher levels and epic entries. The remaining 2,805 references are inventory-only.

## Why 29 remain pending

Each row gives one primary classification; individual references may have additional blockers.

| Primary blocker | References |
|---|---:|
| Native conditions, targeting or required scene not satisfied | 15 |
| Missing native resistance metadata | 5 |
| Insufficient native resources | 2 |
| Missing native cell-group metadata | 2 |
| Unsupported constructor context or finite timeline | 2 |
| Missing runtime casting table | 1 |
| Cannot form a living combat actor | 1 |
| Commit produces no observable gameplay change | 1 |

Luna (5361) passes preview but fails the observable commit gate and remains disabled. Implemented effect families alone do not certify executable spells. No costs, conditions or missing metadata were bypassed to increase the count. Ordinary initial placement is covered; Rift reinforcement construction is a separate path still requiring integration.

## Reuse and validation

[Pipeline instructions](AUTOMATED_ACTIVATION.md) document prepare, preview, forecast/rollback/commit, regression, finalize and inactive staging. Higher levels use the same tool with `--max-level 100` or another inclusive maximum. Every owned spell at every native actor level must pass. Publication requires a complete verified deployment after staging.

Final selected checks passed **461 tests**, with zero failures, errors or skips: 234 class/shared-combat/activation regressions, 27 native movement/effect checks, and 200 AI tests. Existing test assertions were not edited for this work. This is the selected validation suite, not a claim that the entire repository suite was run successfully.

Every constructor-dependent cast has native initial-state application and complete placement-effect serialization evidence. Preview sources, test dependencies and validator hashes remained stable. Final commit gates include unchanged forecast state, forced serializer-failure rollback and observable committed behavior.

## Deployment evidence

Active catalog: `13c8122abba26ca40757c48df137540a5f0e6defdc6676cde6fd19ac6b84b33d`. Only the NPC document changed; the other 7,483 documents are identical to the prior release.

- World image: `sha256:b7eadb1f73b7481547b6b64b1901979ca2f33b5760d68f767c779d39fe3430be`.
- AI image: `sha256:85168515d78084ae004a504e42c44c06963aa06255bbca94d47087f855c51079`.
- Image proof checked 773 world files and 871 AI/world-copy files against current sources, including compilation.
- Both services are healthy, world-to-AI health succeeds, all 49 live shared SDK sources match, and startup logs contain no exceptions.

Private reproducibility receipts are under `.runtime/monster-pending-activation-20261010/`: `previews.json`, `validation.json`, `native-regression.json`, `ai-unit-final.log`, `image-proof.json`, `deployment.json` and `validated/`. These generated receipts are not source-control artifacts.
