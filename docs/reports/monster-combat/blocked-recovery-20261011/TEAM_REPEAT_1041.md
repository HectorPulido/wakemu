# Family 1041: repeat an effect script by team population

## Representative and shared scope

Escario (2828) has family 1041 as its sole missing effect family in the sealed inventory. The same pattern affects Zíar (2830), Cuerbax (2831), Lúmino (2832), Sombra (2833), and Protoflex (3065). These definitions span levels 1–245; Protoflex also depends on family 1049. Companion identity does not by itself establish ordinary-monster eligibility.

## Installed behavior

The registered runner is `eXM extends eXN extends eZM`. `eXM.G` requires an `amO` caster, an `eVw` context, and a non-null `fbX` team manager. Otherwise its result is zero. With valid authority, it computes `max(0, fbX.bL(caster.bcM()).size() - 1)`. `eXN.C` caps the repetition count at 12; `eXM.H` is false, so there is no successful-result early exit.

The inherited `eXN.c` clears its result state and calls `eZM.l` once per repetition. This is script execution, not repetition of a player's spell cast. `eZM.l` resolves the effect script through `fyE.aag(effect.aZE())`, derives the nested `eVt` context, and invokes each native script effect against the selected target actor (`bbA` is true). It tracks produced and successful `PT` results and clears their temporary objects. Missing scripts follow the native failure/reset path.

Installed bytecode is retained in the offline recovery directory as `next-family-runners/eXM.txt`, `eXN.txt`, and `eZM.txt`.

## Implementation requirements

Reuse existing effect-script dispatch and native context construction where their contracts match. A runtime team snapshot must reproduce `fbX.bL` membership semantics; counting arbitrary fight actors, filtering living actors by assumption, or using party size is insufficient evidence. Preserve the 12-repeat cap, zero-repeat cases, target identity, nested context, script order, and result accounting. Do not charge spell costs or publish cast events merely because the script repeats.

This audit registers no handler and qualifies no monster. It identifies a shared implementation path for six definitions and the exact remaining authorities to recover.

## Team membership recovered

Installed `fcb.bL(byte)` calls `fdt.a(fdD.fF(team))`. The resulting `fdZ` predicate compares **current** `fdy.bcM()` to the requested team and applies no alive/dead filter. The population is the registered `fdt.saq` actor map; explicit actor removal deletes entries. Thus a dead but still registered actor is not excluded merely because it has zero HP. This evidence removes the membership ambiguity; the runtime producer must preserve registration and current-team semantics. Source hashes are recorded privately in `family1041-team-membership-audit.json`.
