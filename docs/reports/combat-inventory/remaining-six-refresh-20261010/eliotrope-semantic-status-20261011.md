# Eliotrope semantic qualification status

Authority: PostgreSQL `677062aedeeb9fa0deaad21e0c9a40989e5c8b64cc13b1ebba7200f684d3437d`. This table tracks required semantic work independently of nominal casting and client manual acceptance.

| Passive | Current actual qualification | Explicit remaining boundary |
|---|---|---|
|4686 Rabia|Actual friendly gift negative preservation; no legacy3671 birth.|Positive legacy reward lacks an authentic producer; not qualified.|
|4687 Celada|Four actual facing-controlled attacks establish front75/back93 baseline with/without passive.|Passive bonus requires state3671→351709→159742→351766. Original greater-damage assertion remains failing; no positive passive claim.|
|4688 Efervescencia|Actual toggle creates7750L1, paired passive control passed.|Literal-False346466 is preserved.|
|4689 Medio|Actual7813 AP0 vs2; all eight casting combinations passed.|Legacy3671 reward remains unqualified.|
|4690 Resiliencia|Actual gift negative armor preservation.|Legacy3671-dependent armor positive lacks a producer; not qualified.|
|5056 Discípulo del Portal|Paired actual toggle creates823+1790; both expire at next owner turn, unlike persistent baseline823.|Additional placement/death/foreign interactions are not covered by this case.|
|5131 Transitorio|Actual Ready installs8177; baseline lacks it; owned turns preserve portal/HP.|Enabled1045 reactions have no recovered real publisher.|
|5132 Reminiscencia|Actual toggle creates7835L30 instead of ordinary immediate route; paired control passed.|Not every subsequent damage context is qualified.|
|5143 Portal Celestial|Paired actual owner-start teleports to portal; baseline remains stationary; second turn does not move again.|Carried/PB11 negatives remain unqualified.|
|7202 Interestelar|Actual Ready installs8178; baseline lacks it.|1049 authored publisher exists, but its full area lifecycle is not qualified;1044 external publisher unresolved.|
|7203 Dimensión Blanca|Four actual portal/mode/deck contexts validateFEROCITY ±40 on owned1001.|Death and multiowner combinations remain separate.|
|7204 Quietud|Actual equipped/baseline positive-negative AP restoration passed.|No claim for every capped-resource permutation.|
|7205 Espaciotiempo|Actual823+1606 advances to823+1607 next owner turn, then both expire; baseline823 persists.|Foreign ownership/death and marker permutations remain separate.|
|7206 Portalivio|Strict two-portal replacement and checkpoint roundtrip passed in35-distinct core gate.|Foreign-team capacity/replacement is not qualified.|
|7207 Escudo del Fin|Actual Ready installs8180; baseline lacks it.|Enabled1045 branch has no recovered real publisher;377043 is literallyFalse.|
|7208 Espada del Inicio|Actual current gift range/cost combinations and range4 atomic rejection passed.|Legacy7819 counter route remains source-inaccessible.|
|7209 Cicatrización|Paired actual owner-turn healing increases injuredHP60→358→607; baseline stays60.|On-portal amount, Exalted and exhausted-WP negatives are not yet asserted.|
|7210 Concentración|Actual exact-range/WP1 casting combinations and near-target atomic rejection passed.|Independent free-cell relocation351739 is queued; not grouped under legacy3671.|
|7720 Meditación|Actual next-owner1001 damage30→0/resistance0→50; AP correctly capped6.|No forced AP deficit was introduced.|
|7814 Aliento de la Diosa|Actual two-turn negative preservation; native scheduled351726 contains`and False`.|Enabled null marker is not a healing/removal positive; no missing1037 claim.|

Seven actual focal cases pass: Ready grants/Calm; atomic Calm Aegis rejection; Exaltation inverse; portal-dependent attack beyond ordinary range; owned portal recast removal; checkpoint JSON reconstruction; Quietude positive/negative AP restoration. Portalivio now replaces exactly one of two portals, preserving the native two-portal limit. These focal results do not qualify all twenty passives.

The full21-active/20-passive normal-cast matrix is queued. A nominal no-eligible context is recorded separately from production rejection. Foreign-owner interaction, actual owner death, and live reconnect are still open.

## Reproduced general Portalivio pipeline defects

The third Portal cast with Portalivio7206 enters346477 and selects the existing owned Portal PVs through345/346478 (mask bits0,6,51). The first blocker was `GetTeamEffectAreaCountInRange("target",19,0,0)` using the new placement cell when the selected target was a Qq rather than a fighter. Native eLw selects the target eHg and reads `baM()`; the adapter now resolves the registered area PV position. Unknown non-null PVs still reject; null and explicit cell arguments keep their original route. Source: `.runtime/eliotrope-review-20261011/native-eLw.txt`.

After that correction, the selected Portal was removed and a later345 child failed to resolve its position. Native eYC holds the selected PV object and reads its coordinates for each child, even after Qs unregistration. The dispatcher now uses the existing selected-PV scope for345's candidate population, and the runtime position lookup resolves that actual scoped area PV. This does not restore spatial membership and does not cache coordinates across movements. Source: `.runtime/eliotrope-review-20261011/native-eYC.txt`.

The frozen regression bundle passed 35 distinct tests (39 executions, including four duplicated scope tests), with zero failures, errors or skips. Strict actual7206 replacement and checkpoint reconstruction passed. Deployment is not claimed here. Pure tests exercise selected-area centers, unknown-PV rejection, raw-cell preservation, sibling removal, updated coordinates after movement, and scope cleanup after exceptions. The actual7206 acceptance test remains the required integration gate.

Portal use filters native captured fight affiliation, rather than individual owner identity. A same-team second owner's gate is therefore not automatically invalid; the negative case must use a different affiliation.

The next integration run completed removal but left only one Portal. The source graph requires marker346486 on SELF followed by creation346487 when the caster owns that marker. The345 child path now carries the same explicit Wakemu fresh-relationship selection policy as ordered groups, alongside the transmitted native PV. This is server reconstruction policy, not a recovered native aZX override. Generic tests distinguish fresh SELF selection from already-selected-PV replay; the unchanged strict two-Portal integration assertion passed.

Native ordering differs from this reconstruction: eYC passes the selected PV to eVE, which substitutes the caster only for cym; Qe selects candidates only for null PV or aZX, otherwise binds the supplied PV. Default `execute_pt` preserves that binding. Only the345 child caller opts into the named `fresh_relationship_policy`, after the unchanged allocation preflight and through the existing declared relationship-selector resolver. This deliberate server policy is not claimed as native-faithful PT behavior. Event-bound point selectors and ordinary selected leaves keep their existing invariants.

## Owned ten-passive source matrix during server freeze

The following observations use the pinned677 closure; the observation probe and three paired assertion methods have completed on the pinned release. Only the explicitly asserted outcomes below count as passes.

| Passive | Enabled route and required observation | Current evidence / remaining boundary |
|---|---|---|
|5056|346504 external1025 after4682 creates823+1790 and7808;346507 external1002 removes temporary823/1790|Paired toggle/expiry assertions pass:823+1790 at cast, neither at next owner turn.|
|5131|376989 external1028 installs8177;376993 external1045 applies3305 and395861|Ready8177 positive/baseline-negative assertions pass;1045 publication remains unresolved.|
|5143|351392 external1001 searches a free affiliated823 cell and351394 teleports uncarried actor without PB11|Actual owner-start movement vs stationary baseline passes; carried/PB11 negative remains unqualified.|
|7202|377000 external1028 installs8178;377002 external1049 creates1856;377010 external1044 returns/removes areas|Ready8178 positive/baseline-negative passes.1049 can be published by direct null400356103;1044 publication remains unqualified.|
|7204|346520 external1025 after4682 restores3AP capped by actual maximum|Actual equipped/baseline positive-negative passed.|
|7205|377027 external1028 installs8179;377016 external1001 advances1606→1607 then removes portal/marker|Actual1606→1607→expiry paired assertions pass; legacy316467 is literally False and does not disable the newer route.|
|7206|Native casting limit2;346478 removes one selected823 then marker346486 permits346487 replacement|Strict actual replacement passed in35-distinct core bundle.|
|7207|377044 external1028 installs8180;377041 external1045 applies7807 to same team|Ready8180 positive/baseline-negative passes;1045 publication unqualified.377043 armor child is literally False.|
|7209|346513 external1002 inCalm selects native healing25 parameter15 offportal or30 onone affiliatedportal;346515 spends1WP if available|Actual injured-recipient HP60→358→607 vs baseline60 passes; exact amount/resource and Exalted negatives remain unqualified.|
|7814|351726 external1037 has explicit `and False`; enabled395955 is a null marker|Source-dormant scheduled branch, not a missing1037 publisher. Actual two-turn negative preservation observed; no healing/removal success claimed.|

External1044/1045 are classified by nativeeFK and consumed by current enabled listeners. No original publication caller was recovered from the inspected client classes or current combat producers. A dispatcher able to accept these IDs is not evidence of a real producer. No event is injected by the probe, and no inferred portal-walking policy has been added.

## Current evidence receipts and Celada prerequisite review

- `.runtime/eliotrope-review-20261011/owned-passive-lifecycle-current.log`: three paired assertion methods passed, release677 start/end. This supersedes the earlier queued-only status for5056/5143/7205/7209 and startup5131/7202/7207.
- `.runtime/eliotrope-review-20261011/legal-gifts-full-arena.log`: two actual runtime probes passed, including all eight current gift casting combinations and Sword range4 rejection.
- `.runtime/class-closure-20261011/345-final-bundle.log`:35 distinct tests passed, including strict7206 replacement.
- `.runtime/eliotrope-review-20261011/source-qualified-final.log`: the original Celada test still fails93>93. Its other historical fixture errors are not silently converted to passes.

Read-only current677 `celada-current-source.json` proves3671 owns351709, which listens to1024 and creates159742. The latter listens to damage2/1025 and selects351766 only with deck4687, a backstabbed target, and no6500. Thus the passive is a conditional final modifier60, not an unconditional addition to ordinary backstab damage. Without state3671 the original facing test does not enter that native pipeline. This does not justify claiming that its failing positive assertion passed.

The current free-cell relocation root351739 is independent of the gift's legacy3671 roots. Its recursively read currentPG closure has17 effects, families315/330/339/345/400/402/843, and no304 birth of3671 or7819 (`concentration-relocation-closure.json`). Therefore a successful relocation cannot itself establish Celada's prerequisite. The all-catalog gift birth census and the explicit SELF+IN_AREA/nonself-cast mismatch remain a source qualification boundary; no state, event or criterion is injected to bypass it.
