# Eliotrope implementation inventory and next qualification plan

Authority: PostgreSQL published revision `677062aedeeb9fa0deaad21e0c9a40989e5c8b64cc13b1ebba7200f684d3437d`, read-only extraction on 2026-10-11. This supersedes the prior548e source snapshot. No engine edits, tests, catalog activation or service operations were performed.

## Current closure

41 class-owned actions (21 actives/20 passives),8 common passives,3 derived granted actions,1080 effect definitions,38 states and12 areas. Closure resolver reports `missing=[]`; this means source records are present, not that their gameplay is verified. Exact per-action dependency IDs and document checksums are in [eliotrope-closure-current.json](eliotrope-closure-current.json).

## Complete roster and source qualification

| ID | Name | Kind | Dependency count | Qualification |
|---:|---|---|---:|---|
|4668|Égida Ardiente|active|78|Catalog closure; class semantic case pending|
|4669|Escudo Quebrantador|active|17|Catalog closure; class semantic case pending|
|4670|Seísmo|active|51|Catalog closure; class semantic case pending|
|4671|Tunda|active|19|Catalog closure; class semantic case pending|
|4680|Torbellino|active|37|Catalog closure; class semantic case pending|
|4683|Brecha Temporal|active|12|Catalog closure; class semantic case pending|
|4684|Éxodo|active|48|Catalog closure; class semantic case pending|
|4685|Incandescencia|active|22|Catalog closure; class semantic case pending|
|4686|Rabia|passive|14|Catalog closure; class semantic case pending|
|4687|Celada|passive|2|Catalog closure; class semantic case pending|
|4688|Efervescencia|passive|2|Catalog closure; class semantic case pending|
|4689|Medio|passive|3|Catalog closure; class semantic case pending|
|4690|Resiliencia|passive|5|Catalog closure; class semantic case pending|
|4691|Wakmeha|active|25|Catalog closure; class semantic case pending|
|4692|Pulsación|active|15|Catalog closure; class semantic case pending|
|4693|Diluvio|active|47|Catalog closure; class semantic case pending|
|4694|Cataclismo|active|35|Catalog closure; class semantic case pending|
|4695|Colisión|active|15|Catalog closure; class semantic case pending|
|4697|Flujo Torrencial|active|62|Catalog closure; class semantic case pending|
|4698|Sifón|active|13|Catalog closure; class semantic case pending|
|4699|Salva Etérea|active|13|Catalog closure; class semantic case pending|
|4700|Tormenta|active|27|Catalog closure; class semantic case pending|
|4701|Hoja Desencadenada|active|7|Catalog closure; class semantic case pending|
|5056|Discípulo del Portal|passive|15|Catalog closure; class semantic case pending|
|5131|Transitorio|passive|26|Catalog closure; class semantic case pending|
|5132|Reminiscencia|passive|44|Catalog closure; class semantic case pending|
|5143|Portal Celestial|passive|4|Catalog closure; class semantic case pending|
|7198|Huella de Wakfu|active|16|Catalog closure; class semantic case pending|
|7199|Coalición|active|28|Catalog closure; class semantic case pending|
|7200|Parapeto|active|11|Catalog closure; class semantic case pending|
|7202|Interestelar|passive|34|Catalog closure; class semantic case pending|
|7203|Dimensión Blanca|passive|6|Catalog closure; class semantic case pending|
|7204|Quietud|passive|3|Catalog closure; class semantic case pending|
|7205|Espaciotiempo|passive|30|Catalog closure; class semantic case pending|
|7206|Portalivio|passive|2|Catalog closure; class semantic case pending|
|7207|Escudo del Fin|passive|18|Catalog closure; class semantic case pending|
|7208|Espada del Inicio|passive|2|Catalog closure; class semantic case pending|
|7209|Cicatrización|passive|5|Catalog closure; class semantic case pending|
|7210|Concentración|passive|2|Catalog closure; class semantic case pending|
|7720|Meditación|passive|5|Catalog closure; class semantic case pending|
|7814|Aliento de la Diosa|passive|7|Catalog closure; class semantic case pending|

Granted actions: 7813 (7813) roots [351697, 351739, 351762, 397190], 4682 (4682) roots [148897, 346206, 346464, 346643, 347438], 4678 (4678) roots [145038, 346492].

## Implemented shared routes and limits

- `combat_portal_casting.py:66` evaluates portal-assisted cast eligibility from actual area/QI/affiliation/range/LOS facts. This is eligibility, not an actor relocation operation.
- `combat_gate_conditions.py:18` and `:86` implement gate presence/count predicates with explicit authoritative occupancy and affiliation.
- `combat_effect_area.py:236` validates GATE as native bcS/type19 with the audited faX contract; missing creation affiliation rejects at:271. Generic ownership/removal is at:18.
- Current source scans of combat_state movement, combat_area_transaction and combat_movement_runtime found no portal-specific crossing destination consumer. This is a scoped source absence. Whether ordinary walking should teleport is NOT established by that absence: recover native passage activation/caller semantics before implementing movement redirection.
- Existing focused modules: test_combat_portal_casting, test_combat_gate_conditions, test_combat_use_gate_conditions, test_combat_gate_area_lifecycle. No new execution was performed by this inventory. Earlier parent-supplied shared36/36 result is historical, not a current full-class gate.

## Demonstrated gaps versus unverified behavior

| Finding | Classification | Next evidence/action |
|---|---|---|
| No class-specific actual Ready→Portal pair→cast→removal acceptance module found | Test coverage gap | Build real owned grant fixture using4678/4682/7813; keep all native cost/eligibility rules |
| No actor gate crossing destination consumer in reviewed movement callers | Scoped source absence; native required caller unknown | Recover original gate traversal conditions/activation request before proposing shared implementation |
| All20 passives lack current branch-level positive/negative acceptance in this inventory | Qualification gap, not proved missing implementation | Derive enabled criteria/subscriptions from each action dependency and compare actual legitimate contexts |
| Exaltation3303/3386/8908/7747 and current7835 inverse/HUD/book lifecycle | Unverified | Real toggle/resource/death/reconnect/rollback sequence |
| Gate placement cap/replacement/removal and blocked destination | Unverified | Real4678 first/second/replacement, occupancy and843/911 removal assertions |
| Portal-associated glyph/wall ownership/expiry | Unverified |12 prototype checks through actual cast/turn/removal |

## Ordered implementation plan

1. Establish real breed18 Ready fixture with legal owned deck, published full-resource costs, QI and native surface provenance. Observe all three granted actions without synthetic UIDs/states.
2. Run bounded all-active/20-passive nominal matrix; report no-eligible contexts separately and preserve actual source revision/hash stability.
3. Prove portal4678 placement/removal/affiliation and portal-assisted projectile selection before adding any traversal behavior. Pair identity or walk teleport must follow native source rather than an assumed portal model.
4. Exercise4682 normal/exalted inverse, WP payment/recovery, actual damage/heal/armor and granted7813 prerequisites.
5. Exercise all20 passive enabled branches and literal-False negatives with state/event producer mapping. Audit external subscriptions against actual publisher boundaries, not function names alone.
6. Verify area replacement/expiry, owner/death/surrender/reconnect and failed delivery rollback; then prepare one complete client manual battery. Shared production proposals go to parent before editing.

The earlier65±15 practical estimate remains a dated source judgment, not an updated functional percentage. No new percentage is inferred from dependency completeness.
