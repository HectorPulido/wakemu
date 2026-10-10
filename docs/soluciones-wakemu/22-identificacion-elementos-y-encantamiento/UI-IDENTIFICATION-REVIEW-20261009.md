# Identification UI review — 2026-10-09

Status: **fresh identification graphically accepted by Hector on r55;
reconnect persistence not yet accepted**. The original report described clicking identification
does not show the expected result; reopening the inventory reveals identified
state. A durable state change alone does not satisfy acceptance.

Hector subsequently tested a new La Cola on r55: the question overlay cleared,
three sockets appeared, and the chosen AIR mastery displayed 23. This accepts
the combined identification UI path. It does not accept sublimation behavior
or imply that he completed the reconnect persistence step.

## Latest live acceptance: element choice works; full identification fails

Hector's fresh La Cola (reference 25069) probe showed the selection modal with
the skip-dialog checkbox unchecked. He chose FIRE; the live tooltip changed
from WATER to FIRE. **The modal and live elemental update are accepted.** The
question overlay remained and no socket slots appeared: full identification
still fails on the deployed implementation.

Correlated runtime event: 2026-10-09 18:46:28.026 UTC,
`inventory_elements_selected`, opcode 12487, actor 1 (Audiluna),
UID 1099511633590, applied true. SQL shows damage mask 2 (FIRE), resistance 0,
no `inventory_item_shards` row and no socket-identification receipt. The
element-choice receipt timestamp is 18:46:27.996 UTC.

Read-only inspection of the running r54 image confirms random initial element
creation remains active and combined socket identification is absent from its
12487 handler. The source correction described below is therefore not yet
running. No further user probe is needed until a complete image includes it.

## Native client evidence

Inspected the installed `client/lib/wakfu-client.jar` with `javap -c -p`:

- `cKS` routes an unidentified item click to `cZI.a(fnR, fLc)`.
- `cZI` checks `fpC.gjx()`, which detects selectable damage/resistance effects.
  Those items enter the element-selection flow (`chooseItemElementsDialog`),
  subject to the client's automatic element-choice preference.
- Items requiring socket identification alone send request 13787 directly;
  a selection modal is not a universal requirement for this path.
- `cxh.dp` decodes response 13766 and parses its shard blob through `fpK.eQ`
  (`lD` protobuf, then `fox.f`). The current Python response uses this carrier.
- `chK.a(cxh)` finds the live inventory item by UID, applies the received shard
  and elemental state, refreshes `identificationNeeded` and
  `slotsIdentificationNeeded`, and updates the current detail popup.
- For a new nonempty socket layout it queues `cco`, which displays
  `slotsToastDialog` with 250 ms entrance, 1100 ms display, and 250 ms exit.

Therefore distinguish the element-selection modal from the brief socket-result
toast. Neither distinction excuses stale state until inventory reopening.

The inspected local active-client logs contained no matching
`Unable to unserialize Shards from proto` or unknown-item roll notification.
That absence does not establish that Hector's specific interaction was captured.
No server mutation, restart, or deployment was performed for this review.
The observed world image was `wakemu-world:shared-aptitude-recovery-20261009-r54`.

## Concrete receipt and native reproduction

The database contains one identification receipt, for Npers, item reference
2024, UID 1099511632524, applied at 2026-10-08 21:31:59 UTC. The associated
server log records success and a retry two seconds later. Its stored socket
blob is `0a04500060010a0450016003`: both empty slots lack required `lK`
field 11 (item reference).

Passing that historical blob directly to native `cxh.dp` fails during `lD`
initialization, before `chK` can update inventory or show the socket toast.
This explains a durable item that appears identified only after reopening.
`VerifyItemIdentificationResponse.java` reproduced exit 1 on that blob.

The already-deployed r54 `shard_identification_wire.response` calls
`initialized_wire_state`, adding empty item reference zero without changing
stored receipt bytes. Its response for the exact receipt contains
`0a065000600158000a06500160035800`. The native verifier passes with
`status=OK sockets_present=true socket_count=2` (exit 0). No new server fix or
deployment was needed in this review; the correction predates it. No newer
identification receipt or matching identification event was present in the
inspected current database/log. Retest on r54 remains required before closure.

Regression coverage in `test_shard_identification_wire.py` now includes that
exact historical receipt and checks that the response repairs it without
mutating the saved bytes.

## Focused manual acceptance

Use a character of level 80 or higher, outside combat and exchange:

1. Run `!item 2869 1` to create one Espada Mento and keep the inventory open.
2. Record whether the item initially shows an identification overlay. Click
   identification once and watch immediately for the short socket toast.
3. Without closing inventory, move the pointer away and back and inspect the
   item detail. The overlay must clear and the generated sockets must appear.
4. Close/reopen inventory, then reconnect. The same item and socket layout must
   remain; the operation must not repeat or consume another item.
5. If the live display fails, preserve the item reference, character name,
   approximate click time, and a screenshot before reopening. Those identify
   the concrete 13787/13766 event and separate failed native response handling
   from an expected absence of the elemental-choice modal.

Do not announce this issue fixed until the live UI refresh is demonstrated.

## General fresh-item correction (source only)

Hector clarified that this is recurring: fresh unidentified item, double-click,
no modal/live refresh, then reopening shows randomly assigned elements. The
historical socket receipt is not sufficient to explain or accept this report.

`inventory_elements.create` randomly chose elemental masks before identification.
This shared function serves direct grants, combat drops, and crafting. New
selectable items now receive explicit zero masks, which the native `foX.aKv`
considers pending. They provide no selected elemental bonuses until the player's
12487 request. Already saved choices are preserved; no reset migration is used.

There was also an incomplete combined route: element selection returned only
elements for a fresh item. The native double-click route prioritizes selectable
elements, so leaving sockets unidentified could send the player back to the
same picker. `element_selection.select` now reuses socket identification within
the same existing SQL transaction. Level rejection returns native status 2
before applying choices; insufficient funds rolls back. Successful first choice
returns both elemental and socket blobs. Retries and subsequent valid element
choices keep the existing sockets and do not charge again.

Both identification response encoders initialize required fields on legacy
empty slots. The element-choice response therefore retains previously identified
sockets instead of sending an invalid historical protobuf. A paid first choice
also updates the native wallet display.

Native decoder checks: zero masks decode with `elements_pending=true`; masks
26/0 plus two socket slots decode with `elements_pending=false` and
`socket_count=2`. The selection modal is governed by the native client's
`dontOpenElementsSelectionOnIdentification` preference. This review does not
modify that preference or claim that every item must show a modal.

After deployment, prefer a low-level selectable item for acceptance:
`!item 25069 1` (La Cola, level 15), on a character level 15 or higher. Keep the
inventory open, double-click the new unit, explicitly choose the offered
elements if the picker is enabled, and confirm once. Without closing inventory,
the unidentified overlay must clear, chosen elements and generated sockets must
appear, and no random substitute choice may appear after reconnect. Reopening
and reconnecting must preserve the same choice and sockets. Repeat with a fresh
drop or crafted selectable item to cover their shared creation path.

## Automated verification of the source correction

Luna verified 10 codec/dispatcher/pending-state tests and 14 SQL integration
tests (`test_inventory_elements`, `test_shard_identification`). SQL tests use
temporary schemas in the existing isolated `wakemu_migration_test` database,
never the runtime database. They include initial paid selection, retry and
choice changes without another charge/reroll, ownership checks, low-level
rejection, and insufficient-funds rollback.

The successful SQL test's actual 13766 body was captured privately at
`.runtime/identification-ui-review/sql-choice-body.hex` and decoded with the
installed native client: `status=OK sockets_present=true socket_count=1
elements_present=true elements_pending=false`. This verifies the combined wire
response; it does not replace graphical acceptance or claim deployment.

Three additional targeted SQL cases passed: crafting product/XP delivery once,
combat-drop delivery/reopen, and split exchange metadata preservation. These
exercise the shared creation and metadata-copy paths without a broad test run.
