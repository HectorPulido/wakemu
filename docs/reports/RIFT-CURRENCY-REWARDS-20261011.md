# Rift XP and kamas: fifty times ordinary rewards

## Formula and authority

For each eligible participant who survives the configured forty-round rift, calculate the ordinary combat XP and kamas reward for **all original native monsters actually defeated** in that fight, then multiply each resulting integer by fifty. Apply the existing signed64 total-XP/wallet limits and signed32 per-report kama limit afterward.

The ordinary baseline is the project's existing versioned reward policy, including its configured native-reference/level reward inputs, Wisdom snapshot, player levels, party scaling, global XP/kama rates and conquest multiplier. This policy currently uses the project's documented Dofus-reference formula with Wakfu character inputs; this change does not claim an official Wakfu XP formula. Challenge and star modifiers remain their existing explicit zero baseline because the runtime has no authoritative challenge/star subsystem.

There is exactly one ordinary inclusive kama roll per recipient, followed by multiplication of that result. Fifty new rolls are never generated. A different random outside fight can therefore yield a different ordinary kama amount; the recorded baseline and recorded draw are the exact comparison for acceptance.

## Actual monsters and participants

The resolver compares accumulated `fight.rift_monsters` against every durable `rift_wave_rosters` admission. Identity, native reference, level, instance, original-enemy status and actor ownership must agree. Only enemies with authoritative HP at or below zero enter the ordinary reward roster. Living enemies, merely planned waves and summons contribute nothing. Kills in the final partially cleared wave count; cleared-wave counters are not used as a substitute for the killed roster.

Actual nonwithdrawn player participants form the winning team. Frozen rift membership and the explicit eligible recipient set must agree. Existing selected-sheet level and Wisdom validation remain in effect. Loss, closure and withdrawal pay zero. Surviving without any actual kills pays zero.

## Atomicity and client delivery

The same settlement transaction freezes the ordinary policy decision, rewrites its receipt with the multiplied amounts and a nested complete ordinary baseline, and uses the existing combat award mechanism to update progression, level, level-dependent health and account wallet. Existing fight/character uniqueness prevents duplicate payout. Replays return stored amounts without another RNG draw or applying the multiplier again; historical settled amounts remain immutable.

Physical equipment, appearance, shards and enchantment reward pools remain independent and unchanged. The shared dispatcher returns this currency policy through its existing award/report path, which supplies `gained_kamas` and authoritative `xp_info.won_xp` to native client reports. Existing post-fight progression publication owns level/build refresh.

## Automated acceptance

`test_rift_currency_rewards` covers a real Fight and PostgreSQL rift with durable admission, completed wave and forty-round settlement. It checks fifty times the frozen ordinary baseline, one kama draw, report metadata, level gain, reopened replay, exactly-one payout, partial-wave kills, living/summon exclusion, loss/withdrawal, invalid reference rejection, zero-kill rewards, rollback and native/storage limits. Run with the project's isolated PostgreSQL test configuration; execution is delegated to Luna. At creation this report is a source handoff, not a passing-test or deployment claim.

Recommended companion suites: `test_rift_rewards`, `test_reward_policy`, `test_combat_rewards` and the dispatcher's rift currency integration assertions.

## Manual acceptance after deployment

Complete a forty-round rift while defeating enemies, including some enemies from its final unfinished wave. Record the XP and kama gains in the terminal report and verify that progression and wallet persist after reconnecting. The recorded `fight_reward_policy_receipts.snapshot.ordinary_baseline` must explain the ordinary amounts and their single kama draw; final XP/kamas must equal those amounts times fifty except where the documented native/storage limits apply. Reopening the report or reconnecting must never pay again. A separate surrendered/lost rift must award no currency. Equipment and shard rewards must still use their existing item policy.
