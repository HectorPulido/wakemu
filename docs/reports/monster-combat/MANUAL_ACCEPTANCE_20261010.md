# Manual acceptance observations, 2026-10-10

**Current deployment:** the [scenario MP-glyph and retreat correction](GLYPH_AND_RETREAT_20261010.md) is deployed with world and AI healthy. Native ref46 interruption, actual cast→retreat→replan, movement costs and serialization rollback pass; 179 class/shared-combat regressions also pass. Follow the linked complete manual check. The observations below are retained as investigation history; visual acceptance of the latest correction remains pending.

The first manual pass of the activated low-level cohort is partial acceptance, not a complete tactical validation. Existing class test assertions remain unchanged during this investigation.

| Monster | User observation | Investigation status |
| --- | --- | --- |
| Wonejo | Passed initially, subsequently approached and attacked | First-turn source guard rejection confirmed in live diagnostics; producer not yet isolated |
| Miaumiau | Sought the back and removed resistance; frequently selected summons | Native attack works; generic scoring values summon and player damage equally |
| Baby Tofu | Passed initially, later attacked; stayed adjacent instead of retreating | First-turn rejection under investigation; generic position utility rewards approach |
| Black Jalatín | Entered glyphs unnecessarily and passed | First-turn rejection confirmed; future glyph risk is not established by current planning |
| White Jalatín | Removed AP correctly; one spit appeared aimed at nothing | Actual empty-cell action recorded; complete source and preview graphs retained for attribution |

## Evidence and limits

Live diagnostics for fights 174–177 show `native_ai_query_or_commit_rejected`, detail `Native oracle source changed during decision`, during search after the first repertoire query. This protection must remain strict. Bare activation fixtures do not yet reproduce the mutation; a cast-only immutability probe did not exercise this query path.

Fight 177, turn 7 selected a two-cast plan: spell 5768 at `[-20,-13,-1]` without a target ID, followed by a cast at player 10 at `[-19,-9,-1]`. Its forecast damage was 6. The subsequent search, after the empty-cell action committed, forecast damage 5 for the occupied-cell action. These are not proven equivalent outcomes. A tie-breaking change would not establish the cause. Deferred effects, states, physical footprints and launch events must be checked against the retained full graphs before changing target selection.

The exported roots for spell 5768 are point damage/AP effects. `free_cell=false` alone does not prove that occupied cells are mandatory: the native meaning of the flag and target resolution remain authoritative. Animation packets encode the planned target coordinates, so an empty-cell plan also explains the visible direction without proving an animation codec defect.

Retained private context hashes:

- Root: `022db610a65cb3d8aceab2ab0195eb72ac67a844abb5e0a5afe558dfef504784`.
- After the empty-cell preview: `bd636e239ff2d51d4f2bfb99d96fe15092c3b4e687329411e42dee7c1da16d9b`.
- After the subsequent occupied-cell preview: `78944852a8b57f4f06816193d17a59a3c5b59baf0897c0aa3a8e021c70216248`.

Inspection of those graphs establishes that the empty-cell preview causes **zero damage**: player 10 remains at HP 111, while the NPC spends 3 AP and changes facing. The following occupied-cell preview reduces player HP from 111 to 105. Both actors have physical radius zero. The difference from the separately predicted five-damage cast is therefore not an immediate hit from the empty cast. The forecast RNG is seeded from fight state plus action; a no-effect cast changes that state and may change subsequent damage rounding. This is a concrete candidate for forecast exploitation, pending direct comparison of both occupied-cast branches. Do not fix it by forbidding all ground casts or pruning all preparatory spells.

## Corrections and deployment boundary

NPC cast forecasts now use common random samples keyed by encounter, turn, caster, spell, target and successful same-target cast ordinal. Costs, position, facing and buffs still feed native execution; they no longer reseed a future occupied-target cast. Repeated useful attacks and later turns retain distinct streams. Player forecasts, movement/boundary sampling and live commit RNG are unchanged. A real ref. 39 level 4 regression verifies equal occupied-target damage before and after an empty-cell cast, no empty-cell damage, AP payment and source immutability. Four native transaction/commit/rollback/death tests pass.

The planner reserves up to 500 ms, capped at 25% of its existing decision slice, for native rival projection. It does not extend the owner deadline or commit reserve. This makes forecast scheduling possible after own search consumes its exploration allowance; it does not prove correct glyph exposure or Tofu retreat. The complete query-search module passes 55 tests, including new reservation/zero/invalid-value tests without changing original assertions.

The source mutation mechanism is a lazy `ImmutableCatalog._views` cache reachable through the fight's retained rail authority. A cold catalog read modifies the protected graph. Lazy views now live in an external weak cache, keeping the serialized catalog unchanged and preserving strict detection of real source edits. A real factory-backed ref. 39 cold repertoire probe accepts two queries with identical target envelopes, verified metadata hashes, unchanged complete source fingerprint and no changed runtime fields. Diagnostic baseline overhead was approximately 4 ms. This domain-code correction requires the next complete world image.

The user explicitly restricted this deployment to **ai-service only**, pending their notice for world. AI image `sha256:4cb5d704a345fb2653734cf78f5e20f1e93ff1db80b91187cecfde6a6b6c5790` contains all 69 current AI production files, verified by hash, and compiles successfully. It copies the currently deployed world core for compatibility and retains catalog revision `c97c921c35f4b1f808f0bc84970cba2aa09652763394440429a85e9f7f0fee46`; concurrent mining's draft Compose/catalog settings are not overwritten. World is not restarted by this operation. The first AI-only deployment was interrupted by the concurrent deployment, which stopped and then recreated both services. The verified image remains available, but it must not be described as the final running image until service identity and health are checked again. No world restart was issued by this correction task.

The complete graphs are private diagnostic data in the AI context store. They must not be committed. Tactical summon preference, certified future glyph exposure and Tofu hit-and-run remain acceptance limitations; no blanket target exclusion or speculative glyph rule was added.

## Final AI-only service verification

After coordination, the concurrently built AI image `sha256:227e18d56010a320ef5a6163636f7faa6be0dfe57abbe954ef1671e13da03ac1` was retained: all 69 production Python files match the current checkout exactly. The service was started without starting world, reached Docker `healthy`, and its internal `/health` returned `status=ok` with protocols 1, 2 and 3. The private `ai-only-deployment.json` records container identity, image and health. The separately verified `4cb5…` image remains a backup candidate, not the running image.

At this verification, the concurrent deployment had left world in `created` state. This task did not start or restart it. The user will announce the world deployment window; the domain cache fix remains uncertified in live world.

The isolated final policy, forecast RNG and static-cache batch passes 73 tests. The first combined class batch ran 179 tests with one deadline failure and 20 optional native skips. A separate trace preserves the failure: rejecting an unsupported NPC cast took 9,176 ms, exceeding its unchanged 5,000 ms budget before the generated movement could be previewed. The original test passes after the catalog is warm. The repeat with `WAKFU_TEST_GRANTEDCAST=1` passed all 179 tests with no skips, failures or errors. Its broad source fence detected one concurrently changed mining-navigation module, while all test hashes remained unchanged; a final repeat after coordination is recorded separately. The separate IA contract batch passed another 98 tests (171 AI/cache tests in total). No original assertions or budgets were changed.

## Client acceptance after the world deployment window

Use the full sequence in [MANUAL_ACCEPTANCE.md](MANUAL_ACCEPTANCE.md), one fight at a time. For White Jalatín (`!mob 39 4 2`), keep the player in legal range and watch whether the monster spends AP on an empty-cell spit before attacking the player. The regression removes the forecast incentive for that padding; it does not forbid every legal ground cast. For the other four species, record the first monster turn and whether it attacks without the source-guard rejection. That second check requires the pending world cache correction. Confirm normal Huppermage, Sram and Feca mechanics and complete victory/new-fight transitions.

Tofu retreat, avoiding all glyph exposure and preferring an invoker over a summon are still open tactical behaviors, not expected pass conditions of this limited correction. Do not begin this client sequence while world is stopped.

## Final regression closure

The coordinated final repeat passed **179 class/shared-combat tests**, with `WAKFU_TEST_GRANTEDCAST=1`, zero failures, errors or skips, and unchanged complete runtime/test hashes (`stable=true`, no changed files). Runtime: 184.612 seconds. This includes native Huppermage, Sram and Feca cases. Together with the isolated 73 policy/RNG/cache and 98 AI-contract cases, the final scoped batches total **350 passing test executions**. Four separate native attack/commit/rollback/death checks and the cold repertoire source-immutability probe also passed. This is scoped validation, not an assertion that every legacy repository test is green.

The retained cold Jalato failure remains a known forecast-budget/startup limitation; the green warmed suite does not erase it. No original tests or their assertions/budgets were modified for this correction. AI is healthy; live-world cache correction and the full client acceptance sequence await the user's world deployment window.

## Authorized world deployment completed

After explicit user authorization, the complete current world checkout was built and deployed as `sha256:f6d520684304f84658b8191bbad1dce7e64e7213b51ef556cacdad0f53ee5abf`. All 756 shipped source/configuration/migration files match the checkout, compilation passes, and all shipped Python files retain the final class-validation hashes. A separately changed profiler-service file is not shipped in the world image. Mining implementation and its separate catalog revision/configuration are preserved.

The single world container was recreated and reached `healthy`; its HTTP health endpoint responds successfully. Startup applied zero new migrations, retained combat catalog `c97c…`, loaded 63,020 effect definitions, and sealed its complete startup context with AI successfully. An in-container smoke check verifies unchanged owned catalog state across lazy reads and successful world-to-AI health access. AI remains healthy. The private `world-deployment.json` and `world-image-source-proof.json` record the deployment evidence. The cache correction is now deployed; client acceptance can proceed using the sequence above.

## Post-world client feedback

Hector confirmed that Wonejo uses its range increase and finds a flank when the back is unavailable; White Jalatín also uses its range increase and no longer wastes the observed empty-cell cast. Wonejo and Baby Tofu still enter glyphs; Baby Tofu still remains in melee and attacks a beacon. These remaining cases are not accepted as fixed.

Live fights 179–181 contain 233 rival forecasts; none complete. Only one has a positive known risk lower bound. A baseline with known risk 0.5 and an unevaluated movement with lower bound zero reveals a coverage asymmetry: missing exploration can look safer. Retaining actual lifecycle projection deltas and preventing unevaluated alternatives from receiving a safety advantage are necessary general planner corrections. Target priority also currently values registered summons like primary opponents and uses nearest-opponent approach utility.

## Corrected attribution: movement-point border

Hector clarified that the observed hazard is the scenario glyph which removes MP, not a range glyph. The previous attribution to interior area 910 did not explain that observation and must not be used to dismiss it. Fight 179 supplies a concrete border-46 crossing: the actor started at (-17,-7) with 2 MP and moved through (-16,-7) to border cell (-16,-6). The area then retained marker 152028 for that actor. Border root152027 includes MP-loss child3641 and the once marker.

Both the NPC SDK preview and the shared player area movement path debit the complete movement route before replaying intermediate callbacks. In this recorded two-step route, the callback therefore observes zero remaining MP; native loss clamps to zero. This explains why the final scalar MP delta alone cannot distinguish movement cost from the glyph. It does not establish that the local ordering matches the unavailable official server movement producer. Changing only the forecast would risk divergence from real commit; a shared ordering change requires dedicated movement/resource/area transaction checks. No such engine change is included in the target-priority deployment. Hit-and-run and the MP-border behavior remain unresolved.

## Validated target/risk correction

Registered summons receive default utility value 0.25 in native query search, including damage, armor and hostile control. Discounted summon kills do not receive the primary-opponent finish bonus. Summons remain legal targets; sole-summon encounters and callers using the historical scoring default remain supported. Primary-opponent topology excludes summons only as pursuit goals, retaining them as obstacles; no duplicate BFS is run when those goals match the ordinary goals.

Rival lifecycle projection deltas are retained even if subsequent exploration times out, primary rivals are evaluated before registered summons, and unevaluated alternatives cannot claim a safety advantage over a rival's observed risk. Native forecast completeness remains explicit. Final validation passes 186 isolated AI/cache/contract tests and 179 native-opt-in class/shared-combat tests with unchanged runtime/test hashes; the Jalato producer trace also passes. No original test assertions or budgets were changed for this correction.

The target/risk correction is deployed: world `478d1163b1c5…` and AI `cd2d9821a4cb…` both reached healthy. The complete world image preserves current mining and fishing changes; 764 shipped world files match the checkout and all shipped Python hashes match the 179-test validation. All 70 AI production files match the checkout. World health and world-to-AI health respond successfully; startup sealed its complete context and applied zero migrations. Evidence: private `target-priority-deployment.json` and `target-priority-image-proofs.json`. Reconnect before the next client fight. Test the beacon-versus-player choice with both reachable, then check class mechanics and victory/new-fight behavior. Do not report MP-border avoidance or Tofu retreat as fixed by this deployment.
