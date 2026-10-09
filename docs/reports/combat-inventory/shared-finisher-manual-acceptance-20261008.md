# Shared finisher manual acceptance

This test covers the shared category-5 account selection, innate4464 native criteria, 1099 client script installation, and lethal presentation. It applies to all18 classes; it is not a new class spell or a damage modifier. Delivered in `shared-finisher-complete-20261008-r34` with migration078 applied and world healthy. Final integration35/35 and complementary24/24 checks pass. The test-grant command below has not been executed for the user account; visible Lua acceptance remains pending.

After migration078 and the matching world code are installed, explicitly grant and equip one native-valid test item for the intended character:

```sh
docker compose exec -T world env PYTHONPATH=/app python /app/tools/equip_test_finisher.py --character-id 6 --finisher 20753 --grant-for-test
```

Replace6 with the actual character ID. The command validates20753 against the native finisher catalogue and grants only that item to the owning account. Expected output identifies the character, finisher20753, and script1100010. Without `--grant-for-test`, an unowned item is rejected.

1. Log the character out and back in so its owned inventory, preset, and actor cosmetic component are loaded. The account should show only its owned finishers, with20753 selected.
2. Start a normal fight with an eligible enemy. Reach fight round4 or later. Kill the last non-summoned enemy when its KO-time-before-death is nonpositive, or use the native PvP eligibility path. Preserve normal native kill conditions; an early-round kill is a negative case.
3. Expect ordinary damage, death, rewards and the victory modal, plus the selected1100010 finisher presentation. No AP/MP/WP cost changes come from equipping it.
4. Repeat with a different class using its own character ID and the same explicit one-item command. The shared handler and innate criteria must behave identically; no class-specific exception exists.
5. Unequip or deactivate the owned preset in exploration. Log out and back in before the next fight because the native empty finisher-array update does not clear the existing client list. The next eligible kill must use the ordinary breed death presentation.
6. Attempt selecting a finisher not owned by the account, an invalid reference, or another account's character. Expect rejection without inventory or selection changes.

Automated coverage checks account ownership, int64 identities, stable preset activation, exact account/actor codecs, shared event policy, immediate versus retained1099 delivery, and reconnect source validation. Visible Lua presentation still requires the manual test above; passing Python tests alone does not establish it.
