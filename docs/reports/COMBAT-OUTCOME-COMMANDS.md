# Combat outcome test commands

Source implementation only; this change does not restart or deploy the server.

- `!winfight`: end the current active fight with the issuing character's team winning.
- `!losefight`: end the current active fight with the issuing character's team losing.

Both commands use the existing database-backed console authorization. They are administrator commands unless explicitly allowed through `player_allowed_commands`, and require `WAKFU_TEST_CONSOLE` to be enabled. They accept no arguments or target player. Start the fight first: placement and exploration reject the commands.

The outcome applies to the entire team, including heroes and grouped players. Normal settlement produces the combat report, victory rewards where applicable, defeat health persistence and ordinary exploration cleanup. Rift commands end the current run using its existing wave progress; they do not manufacture additional completed waves.

## Manual acceptance

1. Add two heroes and initiate a normal PvM fight. Ready all participants and start combat.
2. Enter `!winfight` in chat. Expect the normal victory report and rewards, then return to exploration. Heroes remain assigned.
3. Start another PvM fight and enter `!losefight`. Expect the normal defeat report and return to exploration, with the normal defeat health handling.
4. Start a third fight. Expect all currently assigned heroes to participate and combat controls to work.
5. Outside combat, enter either command. Expect a chat rejection and no world or character changes.

Automated regression cases are in `server/tests/test_combat_test_commands.py`.
