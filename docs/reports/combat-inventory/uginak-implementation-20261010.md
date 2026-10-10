# Ouginak implementation and acceptance — 2026-10-10

Status: investigation and offline validation in progress. Native breed 15. Preserve the five provisionally accepted classes. No deployment or service operation is part of this workstream.

## Acceptance requirements

- All 21 owned actives: legal costs, targets, normal/critical branches, secondary effects, rejection rollback and client delivery.
- All 19 owned passives: legal deck ownership, initialization, positive/negative triggers, stack/duration limits and cleanup.
- Presa 6283: target and mark ownership, replacement, death/removal, passive reactions and reconnect.
- Wauwau 6286/profile4559: creation, controller/team, four owned abilities6291–6294, resources, turns, death/retirement and reuse.
- Uginikántropo6855/state7526: actual prerequisites, resource conversion, appearance, temporary grants/book, return/removal and reconnect.
- Perseguidor6856: native grant sources and ownership, target behavior and duplicate suppression.
- Shared map/LOS/QI, effect/event order, finish/abandon/reconnect and next-fight cleanup.
- Automated regression coverage for Cra, Iop, Sacrier, Eniripsa and Osamodas; one complete manual acceptance card.

## Work register

| ID | Name | Kind | Current verification |
|---:|---|---|---|
| 6256 | Emplomado | active | Current production baseline pending |
| 6257 | Plaga | active | Current production baseline pending |
| 6258 | Ruptura | active | Current production baseline pending |
| 6259 | Cuchillada | active | Current production baseline pending |
| 6260 | Disturbio | active | Current production baseline pending |
| 6261 | Zascadilla | active | Current production baseline pending |
| 6262 | Rayadura | active | Current production baseline pending |
| 6263 | Apaleamiento | active | Current production baseline pending |
| 6264 | Tirón | active | Current production baseline pending |
| 6265 | Moloso | active | Current production baseline pending |
| 6266 | Barrido | active | Current production baseline pending |
| 6267 | Contusión | active | Current production baseline pending |
| 6268 | Gran Can | active | Current production baseline pending |
| 6269 | Fracturahuesos | active | Current production baseline pending |
| 6270 | Bulla | active | Current production baseline pending |
| 6284 | Cazador | active | Current production baseline pending |
| 6285 | Persecución | active | Current production baseline pending |
| 6287 | Colmillo | active | Current production baseline pending |
| 6288 | Amaine | active | Current production baseline pending |
| 7551 | Manada | active | Current production baseline pending |
| 7552 | Bote | active | Current production baseline pending |
| 6271 | Cubil | passive | Current production baseline pending |
| 6272 | Arte Canino | passive | Current production baseline pending |
| 6273 | Maestro Perrero | passive | Current production baseline pending |
| 6274 | Compañero | passive | Current production baseline pending |
| 6275 | Ardor | passive | Current production baseline pending |
| 6276 | Agotamiento | passive | Current production baseline pending |
| 6277 | Pillaje | passive | Current production baseline pending |
| 6278 | Colmillos Agudos | passive | Current production baseline pending |
| 6279 | Olfacción | passive | Current production baseline pending |
| 6280 | Regateo | passive | Current production baseline pending |
| 6281 | Busca | passive | Current production baseline pending |
| 6282 | Fuerza Sabia | passive | Current production baseline pending |
| 7553 | Acérrimo | passive | Current production baseline pending |
| 7554 | Veda Abierta | passive | Current production baseline pending |
| 7555 | Digestión | passive | Current production baseline pending |
| 7556 | Energía Canina | passive | Current production baseline pending |
| 7557 | Furor | passive | Current production baseline pending |
| 7558 | Rastreador Canino | passive | Current production baseline pending |
| 7596 | Sa Hueso | passive | Current production baseline pending |
| 6283 | Presa | granted | Native lifecycle investigation pending |
| 6286 | Wauwau | granted | Native lifecycle investigation pending |
| 6855 | Uginikántropo | granted | Native lifecycle investigation pending |
| 6856 | Perseguidor | granted | Native lifecycle investigation pending |

## Evidence policy

Published PostgreSQL definitions and the current shared runtime are authoritative. The existing inventory is a dependency map, not functional completion. Historical rejection/no-effect rows must be reproduced before changes; valid prerequisite rejections must remain rejected. No class-specific ID patch should replace a shared native contract.

## First production baseline

At levels90 and200, all four legal deck chunks passed Ready/start; all42 owned normal spell/level pairs were inventoried.38 pairs prepared, with74/74 selected attempts committed and no effect-transaction rejection. Cazador6284 and Manada7551 at both levels remained unprepared because the bounded baseline lacked their obstacle/allies prerequisites. Granted6283,6286,6855 prepared; Perseguidor6856 requires a resource/state/obstacle sequence not present in fresh Ready. These are pending positive-context cases, not defects. Evidence: `.runtime/uginak-review-20261010/baseline-normal.json`.

The focused HUD producer fixture was updated to production snapshot/QI/global-PV initialization. No runtime guard was weakened. The HUD and maximum-reduction gate now passes nine tests with one explicit skip.

## Positive resource and form lifecycle

The regression in `server/tests/test_combat_hud_producers.py` produces resource117=20 through Manada7551, casts the actually granted Uginikantropo6855, verifies state7526 and delivery12613 plus the active effect snapshot, then consumes the resource through Amaine6288. It verifies removal of state7526 and delivery13560 for the exact retained visual UID. This fixture retains group339778; it must not assert that every visual carrier is group339772. The focused lifecycle test passed; this is offline protocol evidence, not manual client certification.

## Passive baseline and unresolved checks

The passive baseline completed54 cases:19 class passives and8 global passives, each at unlock level and level200. All class-passive initialization cases passed. Two global4956 cases fail at turn-start serialization: actor7 has live initiative0 but characteristic35=12. HP/AP/MP agree. The mismatch is under investigation; this evidence does not establish a4956 effect-dispatch defect. Artifact: `.runtime/uginak-review-20261010/diagnostic-4956-error-class.json`.

Cazador and Perseguidor positive target contexts, Wauwau controlled lifecycle, Presa team uniqueness, and the five previously accepted class regression gate remain pending. The current work has not restarted or deployed world.

## External behavior references

Official WAKFU announcements on Steam confirm that update1.77 reworked Ouginak: https://store.steampowered.com/news/posts/?appids=215080&enddate=1687881606&feed=steam_community_announcements . The linked official changelog is https://www.wakfu.com/en/mmorpg/news/patch-notes/1514507-update-1-77 ; during this review it returned an anti-bot page, so its detailed spell rules were not verified. Older community descriptions must not override the currently published native catalog or prove a missing team-cap implementation by themselves.
