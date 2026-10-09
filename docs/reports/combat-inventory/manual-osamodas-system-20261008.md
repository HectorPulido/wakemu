# Osamodas complete manual acceptance

## Installed test character

Use the existing account that owns **Npers**. Select **Prueba Osamodas**, character **13**, level **200**. The account now contains seven characters; the six previous characters are unchanged. The new character starts on map1134 at(-12,-8,-1), with no equipment or passives and a legal twelve-action deck7307–7318. Tormenta de Arena7312 is included.

The read-only post-creation check confirmed ten empty Symbiot slots, selected slot0 and all availability flagsfalse. No creature was injected. Private setup provenance: `.runtime/combat-review-20261008/osa-manual-character-setup.json`.

Invocation7348 and dragon7349 are native combat-Ready grants. They are not normal deck entries; do not add them through a fabricated deck. Their absence after Ready is a failure to report.

## One complete sequence

1. Return to character selection and choose **Prueba Osamodas**. Open the Symbiot interface: all ten slots should be empty. Stay outside a dungeon and haven bag. Use `!pos` to confirm the ordinary map; if inside a dungeon, first use `!exitdungeon`.
2. In exploration, enter exactly `!mob 4 8 1`. This creates one original profile4 creature at level8. The published native capture catalog proves CAN_BE_CAPTURED property40, no CANNOT_BE_CAPTURED property28, and native minimum level8. It is not an injected captured descriptor.
3. Attack that group and complete placement/Ready. On your turn, locate **Invocación** (7348). Target the living creature to apply its capture branch **before killing it**. Expected payment for the verified unmodified mark: **1AP, 0MP, 0WP**. The cast must not immediately add a captured creature while the target remains alive.
4. Kill the marked creature using **Tormenta de Arena** (7312), moving into the client-indicated legal range first. The verified unmodified cast costs **4AP, 0MP, 1WP**. If insufficient resources remain, finish the turn normally and try on the next player turn. Do not substitute a console kill or modify HP. After actual death, exactly one profile4 entry should appear in the Symbiot. Combat must finish and return to exploration without hanging.
5. Return to character selection/reconnect, then select **Prueba Osamodas** again. The captured creature must still be present exactly once. This is the first persistence check.
6. Enter `!mob 4 8 2` for a new combat with two actual enemies. Complete Ready and select the captured entry in the Symbiot. Cast7348 on a legal **empty cell** to summon it. Exactly one allied creature should appear, with a timeline entry and its own native action bar. The selected captured slot remains populated but unavailable while deployed. Record the displayed summon cost and actual AP/MP/WP changes; the previous restored-summon audit proves actual324 creation but does not publish that branch’s payment, so this card does not invent a numeric expectation.
7. End the player turn. The timeline must reach the summoned creature, expose its own actions, allow a legal move/action and finish its turn, then return to the owner. Profile4’s native book contains549,7359,7360,7361; these are creature actions, not additions to the owner’s normal deck. Record any disabled action and its target/range rather than forcing it. Monster AI and monster-spell completeness are outside this class acceptance.
8. On a subsequent owner turn, cast **dragon7349 on the owner’s cell**. The verified class sequence costs **2AP, 0MP, 0WP** and installs state7123. Check the visible transformation and action bar. Finish turns normally until the same action is available again; cast it on the owner to return. The verified return branch costs **0AP, 0MP, 0WP** and removes7123. Report graphical/action-bar failures separately from resource/state failures.
9. Finish the fight normally. Reconnect through character selection again. The captured entry must persist, become available for the next fight, and contain no duplicate. Start one further combat if needed and summon it again on a legal empty cell. This checks capture, persistence, deployment, turn ownership, transformation, cleanup and reuse as one system.

## Report

Send the first failing numbered step, a screenshot showing target cell/timeline/action bar and AP/MP/WP before and after, and whether reconnect preserved the creature. A complete pass requires every stage, including actual creature turn and post-combat reuse; successful capture alone is not a system pass.

## Evidence and limits

Native profile4 authority: `server/protocol/native-class-captured-profiles.json`, profile4. Actual empty-roster capture: `.runtime/combat-review-20261008/capture-empty-symbiot-07.json` (7348 mark1AP, lethal7312 payment4AP/1WP). Actual captured-descriptor restoration and324 creation: `capture-restored-summon-08.json`; this is an offline component/creation proof, not a live client pass. Dragon round trip: `class-flow-checkpoint-20261007.md`, Dragon02, both actual7349 transactions committed. No account/password changes, main-character changes or service restart were performed for this setup.

## Shared native summon-registration regression gate

Cra fight73 exposed two living owned summons with correct controller identity but `dTE=false`, yielding native `NbSummons=0`. Apply the general registration correction to Osamodas as well; do not assume its different creation pathway is automatically affected or fixed. During acceptance, inspect count, `dTE`, death status, controller identity and property103 after summon creation, stat updates, a turn transition and reconnect. Count-dependent spells must enable only when their native criteria pass. Cra source evidence and correction tracking: [cra-desbalizaje-ui-criterion-20261008.md](cra-desbalizaje-ui-criterion-20261008.md).
