# Socket and enchantment status review — 2026-10-09

Identification is accepted by Hector. Socket bonus installation, socket mutations,
and sublimations still need graphical acceptance. Do not use the older pending
identification entries as evidence that identification is broken.

## Runtime evidence

Read-only review found one healthy world running
`wakemu-world:performance-20261009-r60`, rather than r59. SHA-256 comparisons
confirmed that its `socket_enchantment.py` and `inventory_shards.py` match the
shared checkout, including stack consumption and initialized native response
fields. This comparison covers those files, not every server file.

The active policies were read from PostgreSQL without modification:

- All eight socket mutation operations are enabled; all cost zero kamas.
- A sacrifice must be one unequipped unit of the same item reference.
- Sacrifice adds one charge, capped at 255.
- Workshop increase-count, change-colors and change-order each cost one charge.
- Sublimation removal refunds nothing.
- Bonus installation is enabled, costs zero kamas and refunds nothing on decrease.
- The short request deduplication window is 3,000 ms.

These are explicit local policies, not certified official-server economics.

## Implemented scope and remaining acceptance

| Operation | Implemented behavior | Remaining acceptance or limitation |
| --- | --- | --- |
| Identification | Native request and persisted socket carrier | Accepted by Hector; avoid repeating basic identification |
| Add charges | Consume same-reference unstacked equipment; add one charge | Graphical sacrifice selection, inventory consumption and reconnect |
| Add slot | Sacrifice equipment; random color; respect native template maximum | Graphical selection and native maximum behavior |
| Change one color | Selected slot and valid native color; consume sacrifice | Graphical selector and inventory refresh |
| Workshop increase count | Spend one charge, random new color, template bound | Workshop UI access and full graphical round trip |
| Workshop change colors | Spend one charge and reroll each color | Graphical action, refresh and persistence; colors can repeat |
| Workshop change order | Spend one charge and shuffle colors | Graphical action and persistence; shuffle can preserve order |
| Install ordinary bonus | Native opcode 13269; validate color, level and aggregate inventory; consume incremental count for unchanged bonus | Full graphical acceptance and equipped-stat comparison |
| Clear/change bonus | No refund; a changed bonus consumes its full requested count | Graphical acceptance; do not expect material recovery |
| Apply sublimation | Enabled contiguous ordered native pattern; white target wildcard; consume one scroll from a stack; already-attached same-scroll retry consumes none | Graphical installation and reconnect |
| Remove sublimation | Clear selected attachment field; no refund | Graphical acceptance; attachment is destroyed |
| Ordinary bonus stats | `equipment_stats` invokes `shard_bonuses`; native evaluation and family multiplier exist | Confirm displayed/equipped effects and absence of duplication |
| Sublimation combat effects | Reusable native-source planner exists | No runtime combat hook; installation does not activate combat states |
| Recycling | Not established by this review | No complete material-production acceptance route certified |

The mutation service enforces ownership/session, character level, combat guards,
unequipped targets, exchange exclusions, native eligibility and transactionally
persisted receipts. Existing SQL tests cover these paths; they were not rerun
against the live database in this review.

## Immediate manual test: sublimation installation

Read-only SQL confirmed that Audiluna still owns La Cola, reference 25069,
UID 1099511633623, with BLUE/GREEN/BLUE slots and no attached sublimation.
This is a specific prepared object, not a universal recipe for every La Cola.

1. Select Audiluna and leave that La Cola unequipped.
2. Confirm its colors are still blue, green, blue; do not reroll them first.
3. In general chat run `!item 27123 1` for Topología II.
4. Open the item's enchantment window, select Sublimations, choose Topología II
   and apply it.
5. Expect exactly one scroll consumed, the attachment displayed, and unchanged
   socket colors.
6. Close/reopen inventory, then reconnect. The attachment must persist.

This tests attachment and persistence only. Do not use its combat effect as a
pass condition: the combat integration is missing.

## Ordinary blue bonus: failed acceptance; previous material advice withdrawn

Hector's subsequent Capa Jalosa test failed. Do not repeat the earlier material
recipe below as a valid native acceptance procedure: reference 27094 identifies
the bonus, whereas the UI reserve is the common shard material 27083. The
current implementation incorrectly consumes the bonus item reference itself.

Read-only database evidence: character 6 is Npers, level 50 (not Prueba
Oficios). Capa Jalosa reference 2024, UID 1099511632524, has persisted bonus
27094 at cumulative amount 1 in its blue slot. The receipt at
2026-10-10 00:57:12.993417 UTC consumed one item 27094; six remained. The
27083 reserve remained one. Thus an initial application did commit, while
later unchanged confirmations were rejected with
`Native socket bonus request contains no changes`.

The deployed pure evaluator returns characteristic 20 delta +2 for this exact
socket state on equipment family BACK (13), without unsupported effects.
The cape's base native characteristic 20 is +12. This supports an expected
equipped contribution of +14, but does not certify character snapshot delivery.
The success dispatcher refreshes inventory only; it does not explicitly publish
new characteristic packets. Equal base-item comparison tooltips alone do not
prove the server evaluator discarded the socket bonus.

Cape native level is 9. The UI reported maximum bonus level 1, while the server
validates unlocked bonus levels against character level 50. This discrepancy
requires verification of the native caller's level authority before repair;
the exported array name `minimum_player_level_by_bonus_level` is not sufficient
evidence of which level the native UI uses.

Remaining work: separate bonus identifiers from material 27083, make repeated
unchanged confirmation synchronize authoritative state, verify target-level
limits, and trace character-stat refresh. No further user repetition requested.

### Source repair prepared; deployment withheld

Following Hector's authorization to fix this without restarting world, the
shared source now consumes common shard material 27083 instead of bonus
identifiers. Native `bqI.dGz` counts only reference 27083 in inventory;
`bqG` builds selectable bonuses from the global `fpH` catalog, independently of
ownership of bonus-reference objects. No initial bonus-object consumption was
added without native evidence.

Unchanged confirmation after the deduplication window returns authoritative
state without consumption, fee or new receipt. Bonus levels now use the target
item's native level: `bqG.c(bqx)` passes `fnR.cmZ()` to `fpG.WB`, which checks
the native unlock array. Character ownership/level eligibility remains a
separate existing gate.

The response now sends BAGS 13713 first, followed by native identification
state carrier 13766. Native consumer `chK` updates the existing item's `fpI`
and calls `daI.q(item)` to refresh an open enchantment window. The response
preserves authoritative elemental choices; no fabricated action enum is used.

Regression tests cover material 27083 consumption with a bonus-reference item
left untouched, incremental upgrade, unchanged retry after receipt expiry,
low-level equipment on a high-level character, and BAGS/13766 ordering and
element preservation. Luna's isolated targeted gate passed all 28 tests
in 22.489 seconds, with no skips, failures or errors. The gate covers
`test_socket_enchantment`, `test_socket_enchantment_concurrency`,
`test_socket_enchantment_wire` and `test_socket_enchantment_dispatch`.
Its first run exposed two invalid concurrency fixtures without the required
native slot position; the fixtures were corrected without weakening production
validation. No full suite was run. This is source-only work; no world restart
or live database repair was performed.

The existing native `VerifyItemIdentificationResponse` parser accepted an
actual packet generated by the repaired `bonus_installation_packets`: opcode
13766, status OK, one socket, elemental state present and no pending marker.
This confirms native decoding, not graphical acceptance. A subsequent read-only
comparison found world r61 running externally; both repair modules still
differ from its image. The repair was not deployed by this reviewer.

### Superseded procedure (retained as diagnostic history)

The deployed native catalog identifies reference 27094 as selectable BLUE.
Its cumulative costs are 1, 3, 7, 15, 31, 63, 127, 319, 895, 3199, 12415;
the corresponding minimum character levels are 0, 36, 51, 66, 81, 96,
126, 141, 171, 186, 216. Material consumption uses that item reference itself.

1. The earlier advice used the unequipped blue-slot item and `!item 27094 7`.
2. In the ordinary socket-bonus selector choose bonus reference 27094 for one
   blue slot. Install the first level (cumulative amount 1).
3. Expect six materials remaining and the slot showing the selected bonus.
4. If character level is at least 51, upgrade that same bonus to the third
   level (cumulative amount 7). Expect the remaining six materials consumed;
   the upgrade must charge the increment, not another seven.
5. Close/reopen and reconnect. The installed level must persist.
6. Compare the tooltip and equipped characteristic delta, then unequip and
   re-equip. The delta must apply once and disappear on removal.

The precise visual label and selector reachability have not been accepted.
If the selector is absent or does not list the owned compatible bonus, capture
that concrete failure; do not guess another material command. Avoid mixing
this stat comparison with the known dragoturkey characteristic-zero failure.

## Verification performed in this review

- Offline dispatcher test: one passed.
- Six codec tests passed inside existing world with
  `docker compose exec -T world python -B < server/tests/test_socket_enchantment_wire.py`.
  They validate pure response encoding, not gameplay or database writes.
- The initial local combined attempt could not import the codec dependencies
  because host Python lacks `psycopg`; its dispatcher case passed. The container
  run above resolved that environment limitation.
- No full suite was run. No live database writes, inventory grants, service
  restarts or gameplay changes were performed by this review.

Relevant existing tests: `test_socket_enchantment.py`,
`test_socket_enchantment_concurrency.py`, `test_socket_enchantment_wire.py`,
`test_socket_enchantment_dispatch.py`. SQL suites require an isolated disposable
database; do not run their setup against the active game database.
