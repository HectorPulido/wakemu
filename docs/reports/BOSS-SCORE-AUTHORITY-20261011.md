# Boss score authority and implementation boundary

The current native drop catalog has268 score-conditioned rows: Ogrest4378
(97), Rushu5306 (72), Neoogrest5806 (98), and Jalató Real del Amor5608
(1, threshold15000). The first three references are level230, the last30.

Secondary gameplay documentation describes a boss-damage challenge lasting20
rounds for Ogrest/Rushu; it does not specify authoritative accounting details
for armor, indirect damage, summons or overkill. These pages guide the intended
encounter behavior, rather than proving installed server arithmetic:
[Ogrest](https://methodwakfu.com/pvm/boss-ultimes/pointe-du-mont-zinit/) and
[Rushu](https://methodwakfu.com/pvm/boss-ultimes/palais-de-rushu/).

Installed primary evidence supplies an important constraint. Ogrest's initial
state5022 contains effect240730; Rushu's initial state7000 contains324485.
Both are class877 with parameters `[1,0]`. The generic native877 implementation
sets minimum HP. Therefore a score based solely on committed HP loss can stop
counting at minimum HP and cannot reconstruct a sustained boss-damage challenge.
Nor can total fight damage distinguish damage to adds from damage to the boss.

Private primary evidence:
`.runtime/monster-combat-final-20261010/monsters.json`, `states-effects.tsv`,
`.runtime/drop-criteria-20261011/boss-score-effect-closure.json` (273 effects).
Existing server primitive: `combat/combat_minimum_resource.py`.

A qualified local scoring policy needs an immutable encounter profile pinning
boss actor IDs, ownership/team eligibility and termination rule. Its accounting
boundary must explicitly choose validated damage before minimum-HP clamping,
armor contribution and attribution of indirect/summon damage. These choices
must be documented as local policy unless an original evaluator is accredited.
Record only committed successful executions, exclude unrelated monster damage,
and freeze the final score before reward resolution. Preserve opaque complex
criteria exclusions and ordinary-fight behavior.

## Explicit local adaptation now staged

Hector authorized a local configurable implementation. Migration134 pins
profiles for Ogrest4378 and Rushu5306 only, each20 rounds; it does not infer
Neoogrest or Jalató Real del Amor from their drop criteria. `maps/boss_score.py`
records validated post-mitigation damage before minimum-HP clamping, including
validated armor absorption. Sources must be an owned participant or a registered
summon attributed to one; targets must be the single configured enemy boss.
Damage to adds, unrelated actors, unregistered summons and rounds beyond the
configured limit is excluded. These attribution/accounting choices are the
explicit local adaptation, not a claim of exact original server behavior.

Each runner/target delivery has a unique immutable receipt; changed retries
reject and transaction rollback removes all effects on score. The encounter
profile and final receipt are immutable. Finalization requires a durable
finished fight, actual winning participant team, survival and the configured
round limit. It never manufactures a victory or advances the combat loop.
Only an eligible terminal receipt supplies `score` to drop settlement; existing
MIN_SCORE thresholds still decide each native item's condition.

Integration requires the combat owner to call the executor-only damage hook
with real post-mitigation/pre-minimum values and registered summon attribution
inside the same successful action transaction. Root must implement the actual
20-round challenge termination, then finalize before shared settlement. The
staged helper alone cannot make a boss encounter or its rewards operational.


Automated gate passed15/15 against the complete current135-migration snapshot
with12 watched source/migration fingerprints unchanged. It covers score receipt
rollback/replay/exclusions/finalization, selected Stele item isolation and the
reward context regressions. Evidence:
`.runtime/local/verification-boss-score-20261011/tests.log` and `fingerprints.json`.
This validates the staged domain APIs; damage-executor hooks and actual boss
challenge termination remain integration requirements.

## Integrated local runtime (validation pending)

The domain exposes
`boss_score.prepare_snapshot(db, fight_id, monsters=..., player_ids=...)`.
Readiness prepares authority without publishing it. `runtime.install` accepts
placement or the strict first-turn initialization boundary. Checkpoint CAS
publishes the exact prepared profile and damage receipts in one transaction.
A failed readiness/action preview leaves neither an encounter nor damage rows.

The native damage executor stages the validated HP request before minimum-HP
clamping, plus virtual-HP and armor absorption. Source barrier absorption is
excluded. Only configured boss targets and owned players or their registered
summon chains qualify. Staged events remain part of the copied fight checkpoint;
SQL receipts deduplicate runner/target deliveries. No additional RNG is used.
The configured fight ends at the boundary after twenty complete rounds;
ordinary fights retain their existing lifecycle. Terminal settlement freezes
score before drop eligibility, including defeat/withdrawal paths. NPC level230
uses the existing migration099 reward authority, with no new XP formula.

New regressions cover the actual native executor (101 damage,15 barrier,
20 armor,30 virtual HP,36 requested HP yields86 score), preview discard,
round20 versus round21, foreign/add/unregistered exclusions, and durable replay.
These additions require a new Luna gate before being claimed verified or live.

Rarity limits are a separate explicit local allocation policy documented in
[LOCAL-DROP-RARITY-ALLOCATION-20261011.md](LOCAL-DROP-RARITY-ALLOCATION-20261011.md).
They do not reinterpret native rollMax or enable the686 opaque criteria rows.

The first integrated Luna gate executed60 tests against migrations through137:
58 passed, including actual damage staging, durable score, concurrent allocation,
NPC reward levels and terminal dungeon drop settlement. Two preexisting lifecycle
expectations assumed terminal12238 before report12755. The accredited native
contract in [native-fight-result-order-20261008.md](combat-inventory/native-fight-result-order-20261008.md)
requires12755 before12238; assertions now use that order and locate the report
by opcode while preserving protobuf decoding checks. An affected-module rerun
and an additional actual40-turn/20-round timeline regression are pending.

Final clean integrated Luna rerun: **61/61PASS**, migrations1–137,80.711s,
selected source hashes unchanged. Evidence:
`.runtime/local/verification-drops-137-20261011/tests.log`.
The actual World nested readiness initializer additionally passed3/3 executed
AST regressions: complete owned roster, rift exclusion without database/score
calls, and preserved independent dungeon Stele initialization. Evidence:
`.runtime/local/verification-boss-score-dispatcher-20261011.log`.
These are automated candidate-source proofs, not a claim of deployment or
completed graphical acceptance.

Critical terminal ordering regression additionally passed1/1 in11.344s:
actual PostgreSQL `Checkpoints.save/save_prepared` persists an event, terminal
score and award commit, then a later checkpoint flushes the same event again.
Exactly one damage receipt and unchanged score120 remain. Evidence:
`.runtime/local/verification-boss-score-checkpoint-20261011.log`.

## Remaining99 rows: additive local profiles (SQL140)

Neoogrest5806 owns the same initial states4894/4979/5022/7998 as Ogrest4378,
plus9104Neocorruption. Both have the same five spell references,50million HP,
AP20/MP4, initiative10,000 and fight properties102/69. State5022 includes native
minimum-HP effect240730, class877, parameters[1,0]. The configured local
20-round Ogrest policy therefore extends coherently to Neoogrest's98score rows.
This does not certify Neoogrest's additional environmental mechanics.

Love Gobball5608 has native level30, HP1million, state8601 and fight property16.
Its state closure is385962(class330, GetTriggeringEffectValue()>0) →385963(330)
→385965(400, HasState(8601,"target")); no minimum-HP877 occurs in this closure.
Its sole score row is item13717, quantity1, probability1, MIN_SCORE>=15000.
Primary sources: installed monster/state exports under
`.runtime/monster-combat-final-20261010/`; bounded extraction is private at
`.runtime/drop-criteria-20261011/remaining-score-states.json`.

The [MethodWakfu Foire du Trool guide](https://methodwakfu.com/divers/utilitaires/foire-du-trool/),
Neige,26April2026, section2.4, describes Shoot'Aime Hall: the boss arrives at the
beginning of round19 and the challenge ends after21, with a damage bonus above
15,000. It does not identify item13717 or define individual versus group damage,
armor, overkill or exact equality. Installed MIN_SCORE>=15000 remains the
threshold authority. The explicit local adaptation uses a three-round boss
window from an encounter that already contains5608; it does not fabricate19
waves, Cucupidon transformations, or native event parity.

Migration140 adds only absent profiles5806(round_limit20) and5608(round_limit3),
preserving existing operator profiles and all prior frozen encounters. It uses
the same qualified runtime, event attribution and durable terminal receipts.
All268native score rows then belong to configured species;686opaque conditions
remain disabled. Targeted tests cover actual three-round completion, native
threshold14999/15000, all four configured references and migration replay
preserving an operator-custom Neoogrest profile.

Separate playability limitation: the current published monster inventory enables
5608, while4378/5306/5806are pending native execution. Ogrest and Neoogrest fail
native area-PV initialization; Rushu requires an active actor turn during native
initialization. This scoring work does not bypass or enable those species.
See [published monster inventory](monster-combat/inventory-bulk-1297-20261011/ALL_MONSTERS.csv).

The local Love profile additionally defaults `allow_early_boss_defeat=true`.
The flag must be a JSON Boolean and is frozen with the encounter. Runtime
terminal authority supplies actual configured boss HP<=0 and excludes withdrawn
bosses. A durable legitimate player-team victory with a surviving owner may then
settle validated damage before round3. An alive boss plus `!winfight` cannot
qualify early; ordinary Ogrest/Neoogrest/Rushu profiles retain strict20rounds.
No winner, HP, minimum-HP effect or native damage calculation is altered.
An operator may disable this optional behavior for future encounters:

```sql
UPDATE settings SET value=jsonb_set(value,
  '{profiles,5608,allow_early_boss_defeat}','false'::jsonb)
WHERE name='boss_score_policy';
```

Source changes are limited to freezing that strict Boolean and passing actual
boss-death authority into existing terminal eligibility. The new targeted gate
covers actual native executor lethal damage, failed-transaction rollback,
identical terminal replay, alive forced victory rejection, strict Ogrest/Neo,
and the real three-round timeline. Candidate validation is pending for this
extension; earlier61-test proofs do not by themselves qualify the new flag.

Final score140 extension gate: **18/18PASS** in45.208s against exact migrations
1–141, including all six profile PostgreSQL methods and previous domain/runtime,
actual timeline, terminal checkpoint and actual dispatcher regressions. Initial
and final relevant hashes match. Evidence:
`.runtime/local/verification-fast-20261011/boss-score-140/gate-result.txt`.
The local configured score authority now covers all four native score species
and268rows; ordinary NPC playability remains a separately guarded dependency.
