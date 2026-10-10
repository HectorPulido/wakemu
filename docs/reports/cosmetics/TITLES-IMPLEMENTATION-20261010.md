# Native title learning and selection

Status: source implemented; deployment and client acceptance pending. No service
restart or runtime database write was performed for this implementation.

Manual testing confirmed that scrolls 11431 and 7749 were consumed and their
titles persisted, but the client could not list them after reconnecting. The
publication regression is now corrected in source: title ownership is encoded in
the native owned-entry list, rather than the notification list. Existing grants
remain valid and will be republished on login after deploying this correction;
players must not consume replacement scrolls. The native oracle now checks the
actual `eST.E` list used by `bkK.c(fn.pB)` and rejects notification-only ownership.

The installed client has 467 `bIs` title-learning actions. Each action's `jiK`
value is the learned title ID, which differs from the source scroll item reference.
For example, item 11431 / action 1619 grants title 137. Native account category 7
ownership uses `ft.zR` repeated `fC` entries containing title IDs, just like other
cosmetic categories. `ft.zU` contains notification/new flags and cannot grant
ownership. Appearance presets also use category 7 `fC` selections. The actor component carries the selected title as an unsigned
16-bit value. The native Java `eST/eSX/pq` consumer oracle passes for title 137.

Learning locks the account and consuming character, verifies session and inventory
ownership, consumes exactly one source item and persists account ownership and a
receipt in one transaction. Retrying the same consumed item is idempotent. An
already-owned title does not consume another scroll. Foreign, equipped, malformed
or unsupported action requests fail without consuming the item.

All 467 extracted title actions have no native USE criterion. The generic legacy
catalog's `use_has_criteria` flag can include EXCHANGE restrictions and is not
used as a title USE criterion. Item 14199 is the regression example: its exchange
criterion is false, but action 12302 legitimately teaches title 656.

Selection uses the existing native category 7 preset route and requires account
ownership of the title ID. It persists selection, refreshes the owner and nearby
players, and rebuilds the same value on reconnect. A legacy `currentTitle` value
without account ownership is not displayed. Character selection provisions an
empty appearance preset for an alternate character when its account owns
cosmetics; it preserves existing characters' selections and inactive flags.

## Manual acceptance after deployment

Use two clients on the same map and an account that does not own title 137.

1. Run `!item 11431 2` on the first character. Use one scroll from inventory.
   Exactly one scroll disappears and title 137 becomes available in the title
   collection. The remaining scroll must not be consumed if used again.
2. Select the learned title in the appearance preset. Both clients should see
   the title on the first character. The server must never display item 11431
   as a title ID.
3. Run `!item 7749 1`, learn title 68, and replace title 137 with title 68.
   Clear the title, restore it, deactivate and reactivate the preset. Both
   clients should agree after each action. Costume, aura, sprint, finisher and
   mount appearance selections must remain unchanged.
4. Reconnect the first character. The selected title must remain visible to both
   clients. Select another character on the same account: the learned titles
   should be available there without consuming another scroll. Its selection
   must not replace the first character's preset.
5. Run `!item 14199 1` and use it. Its bound/exchange-restricted status must not
   prevent learning title 656. Exactly one item is consumed.
6. Repeat title selection while inside an owned or invited haven bag. The
   character must remain in its current room and position.

Emote policy, SQL toggles, relogin requirements and the complete emote acceptance
procedure are documented in [EMOTES-IMPLEMENTATION-20261010.md](EMOTES-IMPLEMENTATION-20261010.md).

## Automated evidence

Regression coverage includes exact title ID ownership, unsigned actor encoding,
wrong-action and foreign-item rejection, rollback, idempotent consumption,
account sharing, alternate-character preset provisioning, legacy-title rejection,
and preservation of other cosmetic categories. Migration 097 contains the native
learning catalog and shared title/emote persistence schema.

Native oracle:

```sh
javac -proc:none -cp 'client/lib/*' -d .runtime/local/cosmetic-review sniffer/java/VerifyOwnedTitleComponents.java
java -cp '.runtime/local/cosmetic-review:client/lib/*' VerifyOwnedTitleComponents .runtime/local/cosmetic-review/title-inventory.bin .runtime/local/cosmetic-review/title-preset.bin .runtime/local/cosmetic-review/title-actor.bin 137
```

Result: `PASS native eST/eSX/pq account category7 title=137 source item11431 not owned as title`.
