# Xelor semantic branch matrix — 2026-10-11

Source: current PostgreSQL-derived `xelor-current-catalog-20261011.json`, revision `677062aedeeb9fa0deaad21e0c9a40989e5c8b64cc13b1ebba7200f684d3437d`. The companion JSON preserves all21 owned actives and20 owned passives, their native roots, transitive effects, criteria, masks and external deck-guard consumers. This inventory does not infer execution from metadata presence.

## Passive qualification plan

| ID | Native name | Native external deck-guard refs | Current qualification |
|---|---|---|---|
| 756 | Memoria | No literal deck guard in effect closure; inspect own root/casting tables | Actual Ready numeric positive/baseline PASS; reactive consumers separately pending |
| 758 | Maestro de la Esfera | 349619 | Actual context pending |
| 761 | Relojería | No literal deck guard in effect closure; inspect own root/casting tables | Actual context pending |
| 764 | Tac Tic | 314195, 314202 | Actual Ready and two end/ACK/start alternations PASS |
| 785 | Curso del Tiempo | 314500, 316210, 349700, 349699 | Actual context pending |
| 5351 | Presagio | 349654, 313110 | Actual context pending |
| 5352 | Prontitud | No literal deck guard in effect closure; inspect own root/casting tables | Actual context pending |
| 5353 | Tic Tac | 314192, 314200 | Actual Ready and two end/ACK/start alternations PASS |
| 7184 | Contrahorario | 412995, 349618, 314349, 314230, 314347, 314346, 313255, 412994, 314251, 314253, 348538, 348537, 348547, 348546 | Actual Ready and two end/ACK/start alternations PASS |
| 7185 | Deja Vu | No literal deck guard in effect closure; inspect own root/casting tables | Actual context pending |
| 7186 | Conocimiento del Pasado | 413761, 413760 | Actual context pending |
| 7187 | Presagios Violentos | No literal deck guard in effect closure; inspect own root/casting tables | Actual context pending |
| 7188 | Dimensión Oscura | 314227, 164755, 314222, 164347, 349683, 312695, 312698, 164209, 312722 | Actual context pending |
| 7189 | Ralentización del Tiempo | 313485, 313460, 313199, 314108, 314083, 313226 | Actual passive/control native geometry PASS; independent explicit-point oracle |
| 7190 | Remanencia | 313455, 351622, 313453, 351623, 349482, 313457 | Actual two Sinistros versus baseline replacement PASS |
| 7191 | Mecanismos Especializados | No literal deck guard in effect closure; inspect own root/casting tables | Actual context pending |
| 7192 | Permutación Momentánea | 313403 | Actual context pending |
| 7193 | Mago de Combate | No literal deck guard in effect closure; inspect own root/casting tables | Actual context pending |
| 7195 | Marchitación | No literal deck guard in effect closure; inspect own root/casting tables | Actual context pending |
| 7196 | Asimilación | No literal deck guard in effect closure; inspect own root/casting tables | Actual Ready numeric positive/baseline PASS; reactive consumers separately pending |

Native literal-False roots are not sufficient to classify an entire passive as dormant: Maestro de la Esfera758, Conocimiento del Pasado7186 and Dimensión Oscura7188 have executable consumers elsewhere. Conversely, a transitive dependency is not evidence that its guard is reachable. Casting-table consumers require a separate current-table inspection.

## Active matrix

All21 owned actives were inventoried by the production Ready/deck-chunk normal-cast harness at level200 on unchanged release677:19 prepared transactions,2 no-eligible baseline contexts, no missing references. The two guarded references752/5344 require their separate actual dial/owned-area transition qualification, now queued. Evidence: `.runtime/xelor-readonly-20261011/normal-all21.json` and `.log`. Native-eligible-target misses, conditional prerequisites and actual execution failures will remain distinct. Resources, grant usage and dial lifecycle are owned by the separate Xelor runtime pipeline suite. No state/resource injection, forced critical result or alternate runtime server is used.

## Additional frozen lawful scenarios

`test_combat_xelor_dial_passive_runtime` compares7189 against a baseline at the same genuinely eligible sphere center. It requires all12 native hour references, the selected alternate native branches and a changed reference-to-position layout. `test_combat_xelor_remanence_runtime` creates two actual777 Sinistros separated by real turn advancement and compares native replacement against7190 retention. Both preserve the native casting permission, current resources and summon descriptors; execution is queued, not yet accepted.

The separate owner suite covers actualWP12 Ready, granted3909 usage/payment rollback,775/2839 receipts and5345 sphere creation/current-hour source. These tests do not substitute for reactive consumers such as7185 triggering damage thresholds,7193 close damage,7195 AP-loss-driven damage or7196 lethal reward. Those remain explicitly unqualified until actual positive and negative gameplay traces are obtained.

## Reactive contexts required next

- Presagio5351, Mago de Combate7193 and Marchitación7195 subscribe to native AP-loss event77 on reverse channel1, not ordinary damage2. Their actual positive must use an owned AP-loss spell such as775 against a living registered target.7193 additionally requires distance≤2; a distance3 control must preserve the same actual loss source.5351 requires positive triggering amount and absence of its own349653 marker, so repeated payments alone are insufficient evidence.
- Deja Vu7185 requires an actually established odd current-hour6759 and native direct-damage source; its two amount branches split at120000. A normal low-damage hit can qualify only the lower branch. The upper branch requires a lawful high-damage source, not an injected runner value.
- Presagios Violentos7187 uses actual own center1558 on1001 or2237. An actor standing on an hour1546–1557 is not a center target and does not establish this positive.
- Relojería761 requires the triggering effect caster to equal the owner under1001/2237; bare Ready presence does not prove its dynamic repositioning or7814 consumption.
- Asimilación7196 has a separate1010 lethal reward in addition to its Ready resource reduction. The queued numeric test qualifies only the latter.

## First runtime checkpoint

The first current677 focused run exposed a common fixture startup issue: native initiative selected the NPC before owner7, while the fixture attempted owner casts immediately. These casts correctly rejected with `Caster is not the owned active actor`; the missing initial Tic/Tac states and dial target misses are not classified as engine defects. The numeric Memoria/Asimilación controls passed. The fixture is being corrected to traverse real end/ACK boundaries into the owner's actual first turn before reactive and casting assertions. Evidence: `.runtime/xelor-readonly-20261011/focused-runtime-tests.log`. No positive class-completion claim follows from this checkpoint.

The corrected startup checkpoint passed13/15 methods on unchanged677 with stable source hashes. The queued numeric resource controls, all three Tic/Tac alternating passive branches and Remanence's actual two-Sinistro versus replacement control now passed. Both owner sphere pipeline tests also passed. Remaining errors are separately classified: the additional same-turn3909 attempt hits its native usage limit;7189's same-center layout test reaches missing native PV fight-property authority. The latter needs exact failing-recipient diagnostics before a production conclusion. Evidence: `focused-runtime-tests-corrected.log`. This still does not qualify all20 passive consumers or all21 active spells.

The next shared-core checkpoint passed the generic namespace, selected-PV and QK selection guards. The real7189 cast now selects313226=True/313199=False and reaches its native swap without either prior provider error. Its first same-center test clipped native hours1547/1549 only in the reversed layout, so the fixture is being restricted to a common genuinely valid center fitting both actual12-hour layouts. The full12-reference and positive/negative branch assertions are preserved; no terrain or gameplay guard is overridden. Evidence: `.runtime/class-closure-20261011/pv-population-elio-xelor.log`. The corrected one-method rerun remains pending.

### Additional executable qualification in progress

The following independent tests use actual published Ready, owned spell requests, native resource payment and ordinary movement/turn boundaries. They contain no state insertion or synthetic event emission:

- `test_combat_xelor_ap_loss_passives_runtime`: actual hostile 775 removal must reduce target AP; 5351 WP reward is compared with baseline; 7193 and 7195 require complementary distance2/distance3 child execution.
- `test_combat_xelor_assimilation_lethal_runtime`: actual 775 spends WP before actual 754 lethal damage; 7196 must execute its reward and respect the real maximum, with a baseline control.
- `test_combat_xelor_own_hour_runtime`: actual dial placement, path over attested native edges and real paid movement/turns to the current owned1558 area; 7187 entry child must execute only with the passive.
- `test_combat_xelor_dial_recast_runtime`: actual second dial cast on a different free native column must kill the old dial, remove every old owned-hour UID and install the new complete ordinary layout/current-hour state. Same-cell recasting was rejected by the native free-cell guard before root execution; that rejected setup is not a cleanup defect.

These tests are delegated for serial validation. Their presence is not a pass claim. Actual7189 geometry/control qualification is separately terminal green on release677, as recorded in `native-area-fight-property-namespace-20261011.md`.

Dial replacement terminal update: **1/1 PASS**, actual PostgreSQL release677 unchanged at start/end, test SHA256 `441c94a3dc407d035e5d6b91cd817c4cb9b435bb5d1195038a747c41ca65d40d`. Evidence `.runtime/xelor-readonly-20261011/dial-recast-corrected.log`. Actual old-dial death, owned-hour cleanup, new twelve-hour layout and state6759 level12 are verified. The other three additional modules above still await their own terminal results.

## Current source freeze

All owned server and test sources are frozen for the parent-coordinated Monsters60-minute window. Remaining queued semantic results will be recorded honestly; failing fixture or source changes wait for release of that window. Documentation and read-only inspection can continue.
