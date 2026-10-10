# Native account emotes

Source implements all 319 installed emote definitions (295 ordinary, 24 targeted)
and the 314 native bIw learning-item mappings. Native account component10,
learning acknowledgment12266, play request13498 and occupation12088 are verified
against actual installed Java consumers; see [native protocol evidence](NATIVE-EMOTES-PROTOCOL-20261009.md).

`settings.emote_policy = {"unlock_all":true}` is the default DEV view. It exposes
the validated native universe without inserting permanent knowledge. Switching
to false restricts server play authorization immediately to emotes learned by
that account. The client list refreshes on account bootstrap/reconnect or after
a rejected play. Knowledge is shared across characters of the same account.

Learning locks the account and selected character lease, validates the published
bIw action, consumes one owned physical item, writes permanent knowledge and a
replay receipt in one transaction. Repeating the same request consumes nothing;
another already-learned item is rejected. The native client rejects learning
items it already considers known, so test learning with unlock_all=false.

Playing validates the selected session, combat and active gathering/crafting
occupations. Targeted emotes require another live player in the same map and
instance, alive, outside combat and outside a retained emote or gathering/crafting
occupation. Native targetId parameters are broadcast only in that location.
Late joins see an unexpired retained emote; movement sends native occupation
stop. Account reconnect restores knowledge rather than permanently granting all
emotes. Nation expression uses the server's current canonical nation0; no nation
membership is invented.

## Manual acceptance after deployment

1. Open emotes on two characters in the same map. With default policy, the
   installed list is available. Play `/hi`, then a looping emote such as `/read`;
   both clients should see it. Moving should stop the occupation. A late joining
   peer should see an active, unexpired occupation.
2. Play a targeted emote on another visible player. It should animate with that
   target. A player in another map/instance, combat, or an active gathering or
   crafting occupation must be rejected without disconnecting the requester.
3. Set the persistent policy using the database service:
   ```sh
   docker compose exec -T postgres psql -U wakemu -d wakemu_runtime -c \
     "UPDATE settings SET value=jsonb_set(value,'{unlock_all}','false'::jsonb) WHERE name='emote_policy';"
   ```
   Reconnect. Only explicitly learned emotes should remain. A formerly available
   unlearned request must fail immediately and refresh the client list.
4. Run `!item 8189 1` to obtain native learning item La Buena Educación, then use
   the item. Exactly one item should be consumed and emote20001 (`/hi`) learned.
   Reconnect or select another character of that account: it remains known.
   Learning another copy must leave it intact and reject the duplicate.
5. Restore `unlock_all` with the same command and JSON value `true`. Reconnect;
   the full list returns. Switching back to false must preserve only actual
   learned knowledge from step4.

This source change requires migration097 and a complete validated world build;
it has not been deployed by this task. No production database was modified.
