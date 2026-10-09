# Native temporary transformation book (family 933)

The scoped class domain contains effect 416860, class 11, with parameters `[5900, 0, 1, 0]`. The implementation is driven by `eWG`, `big.a` and `bPu`, rather than an exception for that reference.

`eWG.C` chooses profile parameter 0 (default -1) and the level mode (parameter 1 equals 1 selects actor level; all other values select the profile minimum). `big.a` narrows the profile ID to a signed short, iterates `blj.dvR` in source order, and constructs direct `bPO` instances with raw-reference UIDs. This route does not use captured-creature override-level pairs. Each direct instance clamps its requested level to the native definition maximum. `bPu.S` creates a new temporary `fyR` with capacity 80; duplicate and overflow insertions are caught by its constructor loop.

The server keeps that book as a distinct current pointer. Replacing a transformation creates a fresh pointer and grant/removal scope. The underlying book and its grants remain independently owned. `eWG.bbR` calls `PR/dov` and drops the **current** temporary pointer; it does not require matching the current profile or restore a copied deck. `eWn.bbR` likewise reads current `dok()` and removes its raw spell object there. Consequently a removal during a transformation affects the current form scope, not a hidden base-book scope.

The runtime factory now supplies family 933, its actual preparation and shared event phases, retained ledger, and removal route. The client application and removal preserve the original running payload, including AdditionalDatas field 14 for the exact `eGw` ordinal (`MONSTER_LEVEL=0`, `PLAYER_LEVEL=1`). The source running value remains the original evaluated profile integer, while profile lookup uses native short narrowing.

Ordinary and registered-summon authorities expose the current book. `GetSpellLevel` retains independent player progression and deck-cap semantics. Cast ownership still checks the actual active actor and account, then resolves a current form's raw UID and actual constructed level. Packed old-deck UIDs cannot access a form book.

The server's ordinary actors have no client `igz` visual state manager. The original `dou()` visual transition is represented by the source-proven eWG client delivery; no client manager or previous book snapshot is fabricated on the server. Actual profile metadata is required from `native-class-morph-profiles-v1`, whose seed proof must be `native-class-morph-profile-seeds-v1`. Missing scoped source rejects explicitly.

## Verification

`PYTHONPATH=server:server/tests /tmp/wakemu-combat-review-venv/bin/python3 -m unittest test_combat_morph_spellbook test_combat_redirect_runner test_combat_spell_grant test_combat_spell_grant_book test_combat_spell_level`: 35 tests passed in 1.214 seconds.

Six dedicated transformation tests cover direct-constructor clamping/order/capacity, preserved base and progression books, real owner-account/raw-UID cast resolution, isolated grants/tombstones across replacement/restoration, actual application/removal payload mode plus removal of a newer current book by an older retained carrier, and native eWn capacity-failure/null-object removal.

The original profile 5900 is now published with 15 direct-bPO native constructor checks. Its source-validated loader passed the five-level ordered-book comparison (0, 1, 20, 200, 245; 15 actions). An additional offline smoke passed actual handler application, owner-account access to raw references 8588/8589/8590 at level 20, and removal with packets 13497/13560. This proves book/access/removal; execution of the three child spells and client acceptance remain separate checks.

A new eWn grant into a full form book preserves native `fMO` behavior: insertion failure clears its actual spell object (`rAY`), the effect still delivers, and later `bbR` performs no raw-object removal. The retained record marks that actual object absence, preventing an invented tombstone in a later current book.
