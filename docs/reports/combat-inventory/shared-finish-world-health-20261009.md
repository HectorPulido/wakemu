# Shared fight finish: world regeneration must wait for native return

Two live disconnects share the same concrete failure:

- Fight88, character4, 2026-10-09 04:47:06.403 UTC: `ValueError: Stale health update`, `idle → health_store.tick → evaluate`. Shared victory awarded a level; the socket still cached level1/HP60 while settlement changed durable health. The client lost its world socket before its native end88/12925 cleanup completed.
- Friendly fight89, character4, 04:50:01.336 UTC: identical exception while the attached fight was finished and the socket cached worldHP51. This is not a dungeon teleport failure or a malformed XP notification.

The idle regeneration branch now requires both `fight is None` and `combat_session is None`. Combat HP remains owned by the combat actor and settlement; exploration regeneration must not compare a stale pre-settlement world HP snapshot while the client still owns its combat FSM. The expected-HP CAS and account/session validation in `health_store.tick` are unchanged.

Both normal PvE `return_to_world` and friendly `return_packets` obtain the fresh persisted character under their existing owned transaction. The12925 dispatcher updates the socket character before clearing combat ownership, so exploration regeneration resumes with that fresh HP after native return.

Regression module: `test_world_regeneration_dispatcher`, executing the actual production AST branch. It checks placement/active/finished ownership skips stale regeneration, a retained session without a local fight also skips it, and exploration still calls the owned expected-HP tick and sends12436.

Manual acceptance: finish a two-player dungeon fight with a participant gaining a level; both players should remain connected, receive their own result, complete native return and advance together. Repeat with a friendly duel forfeit; both participants should return to exploration without login disconnection. No manual HP or state injection is required.

Delegated focused verification passed: `test_world_regeneration_dispatcher`3/3, `test_pve_withdraw_dispatcher`7/7 and runtime-message8/8. Live manual acceptance remains pending deployment of the complete current checkout.
