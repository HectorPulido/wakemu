# Issue34 modulation profile and deck acceptance

This source audit covers manual sheet levels, deck publication, automatic competitive projection and effective-level consumers. Health persistence and dungeon lifecycle transitions are owned by the separate build-health audit. No client, Store, wire, dispatcher, combat, service or population change was made here.

## Source findings

`builds.effective_sheet_level` resolves an owned native sheet level; -1 follows actual character level and explicit levels must not exceed it. Equipment and aptitude reducers validate against that selected level. Save ACK and the complete deck registry both create absent default decks with the corresponding sheet level. Combat actor initialization rejects a level different from the selected owned sheet and evaluates the reducer at the actor effective level.

Automatic dungeon modulation uses authoritative durable membership/difficulty, never client-provided caps. Its level is `min(actual_character_level, native_band)`, independent of a lower manually selected sheet. The temporary profile uses a free native index, preserves owned metadata/equipment/selection revision, rejects duplicate projection and does not overwrite durable sheets. Its deck retains legal owned choices and slot positions; unavailable spells and locked slots become empty. Leaving the competitive context must rehydrate the original owned selection through the lifecycle managed by the build-health audit.

The automatic stat formula is an explicit configurable local policy. It is not certified as the official automatic build balance. Native bands above200 currently cap an actual level200 character at200; this audit does not add higher character levels.

No concrete production defect was found in these profile/deck paths. A new cross-catalog regression matrix exercises every installed positive breed, all15 native bands and owned manual sheet levels20/200. It checks native deck validity, preservation of owned data, actual versus effective level, retained spell positions and temporary selection. Execution is delegated; passing results must be recorded separately.

## Complete manual acceptance

Keep the same account and record actual level, selected sheet name/index, effective level, HP, equipment, aptitudes and spell deck before each transition.

1. With characters at actual levels49,50 and51, open the build manager after fresh login. Compare native availability; the documented native unlock is51. If using a character that levels during the session, reopen the manager after crossing50 and51 without reconnecting; availability must update coherently with actual level.
2. At an unlocked level, select the normal sheet, create a lower-level manual sheet, give it a distinct name and choose legal equipment/aptitudes/spells for its cap. Save, select it, switch to the normal sheet and back. Expect the lower effective level and its own choices, while the actual character level remains unchanged. Values must not stack.
3. Reconnect and reopen both sheets. Check selection, level, deck, equipment and aptitude allocations persist. Start a normal fight using the lower sheet: only its legal selected deck and effective level should apply. Finish and confirm the same exploration sheet.
4. Enter a competitive dungeon with a band lower than actual level while that manual sheet is selected. Expect the authoritative competitive level, temporary automatic profile and only legal spells/slots. Owned manual sheet metadata and contents must remain intact. Compare world and combat effective level.
5. Leave normally, reconnect, and verify the original selected manual sheet and its exact owned choices return. Repeat through each supported exit lifecycle covered by the build-health audit (normal exit, automatic finish, recovery/reconnect), checking HP continuity alongside restored metadata.
6. Enter an ordinary noncompetitive dungeon. Expect the selected manual sheet, without an automatic competitive profile. Editing or switching while combat is active must be rejected without changing the live deck/resources.
7. Exercise the configured nonpermanent capacity in the manager (maximum24), delete one sheet and create another. No owned equipment may disappear or duplicate. Permanent/default sheets must not consume nonpermanent capacity or allow client reclassification.

No administrative item or level-changing command is required by these instructions. If the three threshold characters or competitive entry are unavailable, mark those cases untested rather than claiming complete graphical acceptance. Existing accepted creation/editing/deletion evidence remains valid; this pass targets the unresolved thresholds and modulation lifecycle.
