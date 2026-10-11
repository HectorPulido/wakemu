# Daily and recurring missions: native inventory and server-only feasibility

Status: investigated and inventoried; no mission, achievement, event, reward or
monster population was activated. Mission-dependent achievements remain
**BLOCKED** by Hector's current instruction. This is separate from accepted
regional weather/population simulation and from the achievement implementation.

[Machine inventory](NATIVE-RECURRING-MISSIONS-INVENTORY-20261011.json) contains
700 candidate definitions with their native category, conditions, objectives,
reward parameters, cooldowns and calendar fields, plus protector challenge
memberships. Names alone are discovery hints, not executable event rules.

## What is actually installed

| Source scope | Exact count / interpretation |
| --- | --- |
| Shared native quest/achievement definitions |3278; category ancestor4 identifies1441 quest nodes, not the presentation enum.|
| Recurring/calendar/name candidates in this inventory |700:585 native quest nodes and115 outside quest root.|
| Repeat-after-completion flag `cjN` |582;572 have no separate cooldown.|
| Calendar-bound definitions `cjT/cjU` |625;480 have period86400. A calendar period is not itself a cooldown or proof of a daily mission.|
| Nonzero completion cooldown `cjL` |10:8 hourly3600,1 daily86400,1 thirty-day2592000.|
| Original protector challenge groups |187 groups,1509 memberships,1191 distinct challenge IDs; all1191 IDs are negative and belong to a separate challenge namespace.|
| Protector assignments |105 native records with two challenge-group fields; these do not specify a universal event schedule.|

Native `aZy` converts `cjL` seconds to cooldown milliseconds, separately from
`getDuration`. `cjT` supplies a calendar anchor and `cjU` its native period;
`eIj` evaluates the corresponding availability/reset windows. Completion time
and activation time serve different checks. `cjN` controls whether completed
content may be repeated; presentation type4 alone is not that authority.

Actual cooldown examples:1482 **Killew Wabbit** has86400seconds,1323 **Migrant
Song** has2592000seconds, and2723/2724/2858/5469–5473 have3600seconds. Many
period86400 records are scoreboard missions, so480 must not be advertised as
480 Almanax offerings or480 immediately playable daily quests.

## Almanax: three separate contracts

**State1770** is the known Almanax planting bonus state; **quest definition1770**
is **Ohwymi**, with objective3340 and different rewards. Equal numeric IDs across
these namespaces cannot establish an Almanax quest. The bonus state's two-hour
duration does not define a quest reset or eligibility rule.

Named native journal records include4249 **50 Shades of Almanax** and1508
**One Year of Almanax**. Neither has the repeat/calendar fields of a proven
daily offering in this catalog. Their completion/progression dependencies must
not be guessed or activated by this investigation.

The installed client's Almanax calendar is also a separate HTTP contract:
`bUj` calls original `AlmanaxApi.getEventRequest` with date and language; `bgo`
and `bgq` consume event/month models. Its rendered content is not evidence that
a quest exists or that a reward was granted. The current local Shop HTTP
implementation has no Almanax event route. No original day→offering item→
quantity→reward→reset authority was recovered in this bounded pass.

A server-only calendar endpoint could satisfy the original HTTP DTO when the
client already uses the local HAAPI base, but exact request path, full model,
client conditions and response parsing need a separate small oracle before
implementation. Returning calendar text alone would not implement daily quests
or the bonus state's grant/expiry lifecycle.

## Recurring monster invasions and environmental events

The original client has an environmental quest panel, goals, countdown and
ranking fields. Decoder `cAH` opcode12549 is consumed by `cio` into the current
`bhA/bhE` challenge; `cAK` opcode12276 updates its status. This is a real existing
UI route, requiring no client modification. These decoder/consumer identities
were inspected, not a complete byte-level server implementation or live proof.

Protector `aMD.ctD/ctF` join original `aKw/aKx` challenge groups and their
criteria. The1191 negative challenge identities are not IDs from the3278
journal-definition catalog. Neither those groups nor localized **Furious
Hordes**, **A Series of Unfortunate Invasions** or **Environmental Quests**
meta-achievement names prove actual spawn tables, event frequency, environmental
damage, credit rules or reward quantities. Those meta-achievements stay blocked.

Current ecology can schedule/persist ordinary population changes and record
owned gameplay facts. It does not provide an accredited general invasion-event
controller, start/end state machine, challenge participant ledger, native
countdown/ranking publication or environmental mission settlement. Ordinary
monster reproduction must not be relabelled an invasion implementation.

## General next implementation, without client changes

1. Implement one durable recurring-task authority with explicit policy revision,
   owner scope, event/period identity, start/end timestamps and unique progress/
   completion/reward receipts. Use authoritative server/SQL time; the cosmetic
   two-hour daylight cycle is not a daily reset clock. Declare UTC or another
   configured reset zone as local policy unless native evidence proves it.
2. Feed it committed gameplay events from settled fights, crafting and gathering.
   Credit actual eligible actors and original monsters once; reject summons,
   duplicate settlement, aborted actions and cross-account attribution. Reuse
   existing atomic inventory, XP and wallet award transactions.
3. For a native journal, choose only an installed definition/objective with
   accredited semantics and supported conditions, then send its existing state
   contract. For example1389 **Kill10 Monsters** is a candidate to investigate,
   not an activated or source-proven event evaluator. Unknown IDs/texts are not
   created by the proven ACHIEVEMENTS state snapshot. Server-authored custom
   tasks can instead use an existing server UI/message surface, with their
   custom balance clearly identified; arbitrary native journal definitions and
   arbitrary client text are not established by this contract.
4. Separately recover environmental challenge definitions and map/group joins,
   native12549/12276 field layouts and cancellation/reconnect behavior. A generic
   invasion scheduler then pins a qualified monster roster, region, duration,
   participation and reward policy; keep unqualified monster mechanics and all
   mission-dependent achievements disabled. Environmental destruction needs
   its own authoritative ecological transaction rather than visual-only mobs.
5. Qualify restart/replay, simultaneous completion, period rollover while
   offline, expiry, full inventory and hero/group credit on isolated PostgreSQL,
   then one complete native daily/event acceptance. Do not claim official rules
   from a fair custom formula or a successful countdown decoder.

The immediately useful deliverable is the shared durable authority and its
existing-event adapters; the remaining original schedules/offering/event-script
joins are explicit data dependencies. This report does not request a client
change or permission to invent official mechanics.

## Evidence and scope

Reused `native-quest-definitions.json` and the other agent's bounded native
classification/period contracts. New bounded128MiB original Java export reads
only `aKw/aKx` and `aMD`; private provenance is under
`.runtime/local/recurring-missions-audit-20261011/`, including exporter, exact
TSV and targeted bytecode. Machine inventory records source/client SHA256.
No heavy full-state export, database write, service operation or client launch
was performed. No gameplay test or rendered mission acceptance is claimed.
