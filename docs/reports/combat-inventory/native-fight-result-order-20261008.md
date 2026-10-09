# Native fight result presentation order

Fight66 completed at18:10:59 UTC after the final kill at18:09:38. Completion latency is investigated separately; this change concerns result presentation only.

The actual capture `.runtime/local/captures/2026-10-08T17-40-03.951216Z-c5bb05ba/events.jsonl` records cvF12238 at18:10:59.968 (seq4640) and cvJ12755 at18:11:00.295 (seq4642). The local client log at13:11:00.402/510 records57 kamas and139XP; aUH logs fight66 end at13:11:00.535 and cji removes the fight frame at13:11:00.569. Rewards therefore arrived; this does not prove the report dialog opened.

Original source: cvJ.dp parses the report; cju.a(cvJ) binds the actual live fight and queues aUI on buH.dLE. For report-enabled native models, aUI.cby calls daW.e/d and installs the result frame. daW loads `fightResultDialog` with `fightReport`. The terminal aUH cleanup removes the action owner through aUb.Af, clears the fight frames and produces the normal12925 continuation. Automatic12925 is a native terminal continuation, not proof of report visibility.

`combat_results.finish_messages` now queues12755 before12238. Report and terminal payloads, committed rewards, normal terminal animation, participant identity and the matching12925 ownership checks remain unchanged. This prevents terminal teardown from preceding report submission to the native action owner. Existing codec assertions verify ordering and unchanged terminal body.

The new ordering is a source-based production fix. A subsequent live victory must still confirm that the native result dialog is visible; the old fight66 capture cannot validate code that was not deployed. No service was restarted by this task.
