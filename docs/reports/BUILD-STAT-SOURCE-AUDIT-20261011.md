# Bounded build and equipment-stat audit — 2026-10-11

Scope: original issues17/34 and dependentE06. This review changes documentation,
not combat, spells, client files, services or item arithmetic. Source inspection
is distinct from deployed-image identity and graphical acceptance.

## Current authoritative behavior

- `server/local_game_server.py`, successful `nivel` action: existing committed
  progression packets precede `level_publication.refresh`. The helper receives
  the owned format10 template and current account roster. It returns15548 for
  the same actor, then23548 for real-level roster availability. No activation or
  map reset occurs in this branch. Earlier E06 claims of format3-only publication
  are historical and have been corrected.
- `characters/level_publication.py` rejects templates without spell inventory
  and deck sections, missing/duplicate or stale roster identity, and foreign
  account entries. This is a publication contract, not a graphical unlock proof.
- `items/builds.py` validates equipment, aptitudes and deck at each selected
  sheet's effective level. Missing decks are generated independently at that
  effective level in both response and multi-build registry publication.
- `items/equipment_stats.py` resolves equipment through the authoritative active
  sheet and owned UID collection. A mount's parameters use its own persisted XP
  and native level model, rather than the character level. Aptitudes, shards,
  explicit dungeon modulation and territory bonuses compose through the same
  evaluator. Unsupported effects remain explicit; this audit does not certify
  all native item effects or every combat consumer.

## Mount arithmetic is already accepted

The [historical incident evidence](health/MOUNT-IDENTITY-REVIEW-20261009.md)
records Hector's acceptance of fresh Dragopavo18682: level0 gives0 mastery;
level2 gives1. This agrees with the native coefficient0.8 and integer conversion.
`test_equipped_dragopavo_effect_scales_by_pet_level_only` covers levels0/1/2/35/50
and excludes unequipped mount XP from unrelated equipment statistics.
Changing this arithmetic to force a nonzero starter bonus would contradict that
accepted contract. No new zero-stat defect was established by current source.

## Remaining UID and graphical boundaries

The historical incident distinguishes two different units: deletion of one
UID succeeded; deletion of another was rejected because inactive build3 still
referenced it. This is not evidence of shared mount XP or accidental durable
loss of the newly granted Dragopavo. Current mount persistence/hydration and
feeding updates are keyed by owned UID, and deletion guards all saved builds.

Successful feeding publishes physical removal/reinsertion, then the rich
item registry. The actual dispatcher subsequently refreshes actor/PET,
outside-combat characteristics and the mount panel snapshot. Thus a proposed
fix that merely adds an already-existing character-stat refresh is unsupported.
Domain rejection and post-commit transport failure have separate paths; the
latter propagates rather than retrying additive inventory deltas.

Immediate two-unit panel isolation and the full physical-item/selected-panel
chain still need graphical acceptance. The original-JAR registry replay and
actual Store ownership regression below now cover their stated narrower paths.
The existing Java `VerifyNativePetStateRefresh` exercises
a reconciliation helper, not an unmodified original-client two-UID registry
sequence. It must not be promoted as proof of that broader requirement, and no
client modification is authorized to resolve it.

## Bounded verification

Luna completed the serial follow-up: **9/9 passed in0.019s**: three
`test_level_publication` methods (wire mocked), one exact mount scaling method
(actual imported native catalog), and five `test_mount_feeding_dispatch` methods
(mocked domain). Scoped dispatcher AST and relevant module hashes are recorded
in `.runtime/local/verification-build-stat-publication-20261011/evidence.json`;
the terminal log is alongside it. These establish the stated helper contracts
and accepted arithmetic; they do not certify live level commands/feeding, all
runtime consumers, SQL mutations, complete gameplay, or the GUI. No broad class,
monster or original17 suite was repeated.

## Complete manual acceptance

Use section17 of the [complete systems journey](SYSTEMS-ACCEPTANCE-20261011.md),
then verify49/50/51 with one unrestricted sheet and a fixed49 sheet: the real
roster level must advance immediately, the fixed sheet must remain49, and the
library/deck must reflect its appropriate real/effective-level contracts without
reselection. Switch sheets and reconnect; ownership and each UID's XP must
persist independently. Graphical acceptance remains pending.

The real PostgreSQL same-reference two-UID regression subsequently passed1/1:
feeding A preserves B, inactive build ownership rejects B destruction, clearing
that reference permits B-only deletion, and reopening retains A/food/receipt.
It uses a fresh schema through143 and does not bypass XP, ownership or deletion.
Its scope and evidence are recorded in the
[native registry follow-up](NATIVE-MOUNT-TWO-UID-REGISTRY-20261011.md).


## Original-JAR two-UID follow-up

The [native registry audit](NATIVE-MOUNT-TWO-UID-REGISTRY-20261011.md) adds actual
server snapshots replayed through unmodified original decoders, UID registries
and mount state, plus an original panel constructed before refresh. These prove
independent A/B XP/levels and authoritative rejection/deletion snapshots. The
complete13078 handler runs; selected GUI-panel rebinding, physical actor/container
handlers and PET actor application remain unproven. No server arithmetic or
serialization defect was established, so no speculative runtime fix was added.
