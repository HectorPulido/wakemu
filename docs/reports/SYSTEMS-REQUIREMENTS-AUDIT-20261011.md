# Systems requirements audit — 2026-10-11

Scope: current authoritative issue tables, complete acceptance and linked source
investigations. This is a read-only gameplay audit; no service, database, client
or server implementation was changed. Documentation additions below do not
claim deployment or manual acceptance.

## Prioritized actionable findings

| Priority | Finding | Action / evidence |
| --- | --- | --- |
| 1 | The complete publication request excludes admin, while the bans concurrency correction is imported by that service as well as World. | Compare actual deployed `account_bans.py` in both service images against current source. Include admin only if its dependency differs; do not infer deployment from the readiness report. `ACCOUNT-BANS-READINESS-AUDIT-20261011.md` requires the corrected `FOR NO KEY UPDATE` guard and reports32 passing tests. Root compared the stopped admin container directly and confirmed the old stronger guard; admin is now included in the concrete coordinated publication request. |
| 1 | The one complete acceptance omitted public guest garden/crafting and ordinary level/build refresh. | Added canonical sections12/13 to `SYSTEMS-ACCEPTANCE-20261011.md`, with exact existing item/level commands, inventory ownership,51 unlock, fixed49 sheet at actual51→52, reconnect and combat. These remain manual pending. |
| 2 | Historical guest acceptance asks ACL revocation and describes account chest as absent. | Added an explicit superseding banner to `haven-bag/PERMISSIONS-AND-REMAINING-ACCEPTANCE-20261009.md`; current public access overrides historical deny settings, chest ownership stays restricted, Ranch is separate. |
| 2 | The main interactive inventory still describes Stool, Stele and RanchEntrance as lacking handlers although later appendices and new reports prove implementations. | Refresh those three authoritative table rows from `environment_seats.py`, `dungeon_steles.py`/current stele modules and `haven_ranch.py`, preserving staged/live distinctions. Root notified; worker must not turn other unsupported objects into supported claims. |
| 2 | Open E17 points to closed39 for the equipment zero-stat regression. | Root corrected the remaining reference to open17; accepted feeding/mount scope39 remains closed. |
| 3 | Area-bonus manual journey checks visible Wisdom/Prospection but not all four native provider outputs. | Added planting and harvesting profession XP checks and linked `AREA-BONUS-ACCEPTANCE-AUDIT-20261011.md`; stationary update alone does not prove them. No new implementation defect established. |
| 3 | Compass request cannot be marked fixed from actor Mostrar proof. | User's palette drag remains local-note registry behavior. Keep original note visibility limitation and genuine actor compass graphical check distinct; do not create invented server note acknowledgements. |

## Requirement disposition

- Explicit closures3,4,6,14,16,36,39,E09,E13 are represented in the green table.
  Weather27 and corpse40 also have explicit later user acceptance. Do not reopen
  them from unrelated acceptance failures.
- Drops10 has scoped score/rarity/stele proof and a deployment boundary. Only686
  opaque rows are explicitly disabled by user direction. The268 score rows now
  have local profiles; that does not certify monster playability or final drops.
- Nation13 backend, admin authorization and intergame have evidence. Native `/b`
  world eligibility and `/f` real government office remain actual constraints;
  command aliases would violate the user's correction.
- Rift25 currency is50× its same frozen ordinary baseline for actual killed
  original enemies. Separate random outside fights cannot verify the multiplier.
- Public bag26 and area28 remain graphical acceptance pending. Weather27 is
  accepted. Builds34/E06 have refresh/modulation implementation evidence and
  visible transitions still pending; E05 is closed after final source review.
- Issues21,29,33 remain expressly user-testing pending. Issue22 is another
  owner's implementation; the current table links its complete inventory.
- NPC recovery is genuinely incomplete beyond accredited position/root joins.
  Extracted dialogue/quest counts do not prove playable conversations or quests.
- Combat signals explicitly cover sender and all allies, including selected
  heroes, while excluding enemies/spectators. Random borders46/48 are qualified;
  the inventory of103 does not certify all103 for random enablement.
- All48 placed interactive types are inventoried; the request to activate other
  objects is not fully completed by the inventory. Unimplemented scripts,
  weighted rewards, exchange machines, chest rewards and transport contracts
  remain open. Preserve the full scope rather than closing on wells/lights/seats.
- Account bans/dashboard are implemented with HTTP/TLS evidence; visual editor
  and corrected service dependency publication remain separate checks.

## Verification performed

Inspected current README tables, WORLD coordination, canonical acceptance,
modulation/public-guest/bans/area reports and full interactive inventory.
Validated every local Markdown target in the two edited acceptance documents
exists. No tests were run: these changes are documentation, and no gameplay
behavior was modified. Root retains ownership of authoritative README updates.
