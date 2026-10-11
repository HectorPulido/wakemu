# Scenario border and post-attack retreat

## Scope and diagnosis

Hector's reported glyph is the scenario perimeter that removes MP, not a range bonus. The recorded ref46 area owns root152027, MP-loss child3641 and the once-per-turn marker152028. The previous movement preview prepaid the complete path before delivering intermediate area callbacks. A two-step move with two MP could therefore reach the border with zero MP and conceal the resource loss.

This correction affects native NPC movement. The established player movement transaction remains unchanged. Class spells, effect definitions, source guards and the activated monster cohort remain intact.

## Implementation

`Fight.move` and `Fight.server_move` accept an optional step callback. Without that callback their existing movement path remains unchanged. With it, the complete route is validated first; rail eligibility and tackle costs are computed from the original complete route. Prefix costs are calculated before any callback can change actor authority. Each step then pays its resource costs, updates QI and delivers its callback before the next step. A route interrupted by loss of resources, death, combat completion or displacement reports only the executed prefix.

Step delivery and prefix interruption are explicit Wakemu movement policy; the exact official server call-site timing has not been recovered. Native effect execution, resource arithmetic, rail eligibility and tackle formulas remain authoritative.

The NPC oracle uses this operation inside its unpublished fight copy for both forecasts and commits. Voluntary movement and owned area events are delivered at each step. Movement animation uses the executed prefix; serialization and publication retain the existing atomic transaction.

The planner also applies a conservative navigation preference against the registered scenario perimeter (`native_border_cells`). This is an AI policy, not an invented native damage or resource-loss formula. It orders safer routes first and charges two utility points per traversed perimeter cell, while retaining dangerous routes when their certified tactical benefit justifies them. It does not infer that unrelated player-created glyphs are harmful.

Post-attack retreat uses the complete event ledger: positive damage sourced by the actor followed by its committed `npc_cast` in the current turn. Empty and support casts alone do not establish attack evidence. Turn boundaries reset that evidence; moving and replanning preserve it. After an attack, bounded separation utility replaces the approach preference and escape routes are explored first. Native damage, control, healing, resource costs and rival risk remain part of the same score. This is a general tactical policy, not a reconstruction of the official monster AI or a species-specific exception.

## Validation and deployment

Validation receipts, complete image/source proofs and deployment results are retained in `.runtime/monster-glyph-hitrun-20261010/`. Existing tests are preserved; new regression files exercise the additional behavior. Final targeted validation passed: 199 AI tests, 41 original movement/rail/tackle/Yopuka tests, and a 202-test native batch comprising 6 new regressions, 17 original oracle tests and 179 class/shared-combat tests. All these runs had zero failures, errors or skips. The native batch took 168.7 seconds.

All production hashes remained stable during the final native batch. Its broad fence noticed an external edit to `test_ecaflip_dice_passive_semantics.py`; the original receipt retains that fact. A separate AST dependency audit verified the 60 executed/transitive test and fixture files remained stable and the edited test was outside that closure. The derived scoped receipt therefore passes; no original assertion was changed by this correction.

Complete image proofs checked and compiled 766 shipped world files and 864 AI/world-copy files with no source mismatch. The images are world `af994a64bc39fe82ada08968143efc14f9b4b3114b42bd3bd5c3a7148a0ee588` and AI `c0dea31cb5d35f9713cc20d3c9fe71e2d0d45f91cc20a04acb6551054b898492`.

Deployment completed: AI started at `2026-10-11T01:34:25Z`, world at `2026-10-11T01:34:50Z`; both report healthy. World HTTP health and world-to-AI health pass. All 49 live mounted SDK Python sources match the checkout, startup logs contain no tracebacks/errors, the complete native catalog seal succeeded, and startup applied zero migrations. Only the existing world and AI services were recreated. The 30-reference activation cohort and catalog release remain unchanged.

## Manual acceptance

Use one fight at a time on the same arena previously used for acceptance. Spawn a Baby Tofu with `!mob 6 4 2`, then a Wonejo with `!mob 5525 1 2`, and finally a Jalatín with `!mob 2 4 2`.

1. Leave a reachable route around the scenario MP glyph. End your turn. Expect the monster to prefer that route rather than unnecessarily crossing the border.
2. Give Baby Tofu a reachable attack and free retreat cells. End your turn. Expect an actual attack followed by separation when remaining MP and native tackle allow it; it should not approach again during the same turn merely because the planner restarted.
3. Repeat with a summon or beacon present and inspect target choice and actual damage. Existing primary-target preference remains active; summons remain valid tactical targets.
4. Complete the fight and start another. Confirm that the next turn/fight can approach normally and has no stale retreat memory. Cast normal Feca, Sram and Huppermage spells and verify their normal effects and turn transitions.

Remaining MP, native tackle, blocked cells and useful additional attacks can legitimately change the exact retreat distance. Visual acceptance remains pending until Hector performs this complete check.

## Test fixture lessons

The first broad native attempt completed all 202 tests but could not certify this change: two new fixtures raised errors and concurrent source/test edits invalidated its fences. The original class/oracle assertions passed in that attempt. Receipts are retained rather than replaced with a claim of success.

- A captured PC snapshot cannot become an NPC by flipping `controlled`; the native actor-kind authority correctly rejects that mismatch. The shared step helper's ref46 test therefore retains the captured PC authority. Separate SDK tests use an actual owned NPC.
- A retreat corridor must retain its verified connection to the occupied enemy cell. Removing that edge makes every distance unreachable and correctly gives no additional separation utility; that is a malformed positioning fixture, not evidence that retreat scoring failed.
- A completed search can return an empty plan with an `end_turn` action. Replanning assertions must check that public action rather than indexing an absent plan entry.
- Complete native snapshots are large. The new retreat regression uses a short frozen corridor drawn from verified arena edges, retaining the attack, movement, commit, source-guard and no-oscillation assertions while avoiding a full-map search that caused memory pressure on a 16 GB host.

## User acceptance update

Hector confirmed that hit-and-run works in game on 2026-10-10. This confirms that behavior in his manual test, not every monster or encounter. He also asked whether border generation changed: comparison against the pre-fix world image found identical border/terrain generation sources. The correction changes NPC movement delivery and tactical preferences.
