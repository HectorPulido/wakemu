# Aniripsa passive source pipelines — 2026-10-09

This implementation follow-up distinguishes passive registration from gameplay consequences. The earlier baseline's seventeen unobserved reactions did not mean seventeen absent handlers: eleven current passives have only a native family400 marker root, while their conditional behavior lives in the class innate, healing, mark or summon graph.

## Verified independent mechanics

`server/tests/test_aniripsa_passive_pipeline.py` uses the production snapshot initializer, legal equipped passive decks and original active779 through `prepare_server_spell`. Character wounds and TACKLE come from persisted character HP and a legal aptitude sheet before initialization, rather than injected combat notifications.

- **Paroxismo Vital1536:** a self-directed healing word at level200 changes actual healing42→54 through subscribed167898 and child371574/family1093. Equipping it does not increase healing sent to another actor. This is a received-healing modifier, not a blanket outgoing-heal multiplier.
- **Todos para Mí5453:** real initialization installs one state8032 at level1600 and raises both authoritative maximum/current HP by1600 against the identical baseline. A subsequent real heal neither duplicates the state nor raises maximum HP again.
- **Elixir de Viento7993:** two legal aptitude21 points supply TACKLE8. Fight-start1003 replays371831, its real913 context reads TACKLE, and child371832/family174 consumes exactly8, leaving TACKLE0. A zero-TACKLE baseline does not produce a negative characteristic. DODGE remains unchanged by that start branch; additional mark-dependent effects are separate consumers.

First run:5tests passed in71.115s. Command:

```sh
PYTHONPATH=server:server/tests:server/tools WAKFU_TEST_GRANTEDCAST=1 \
  /tmp/wakemu-combat-review-venv/bin/python3 -m unittest \
  test_aniripsa_passive_pipeline -v
```

The local catalog connection/password-file environment must already be configured. Private execution evidence is `.runtime/ani-passive-pipeline-tests.log`. These are local transaction tests, not GUI acceptance or deployment evidence.

## Data-defined event190

Marcador de Serie1537 subscribes root368107 to channel3/event190. It is **not missing merely because no literal190 occurs in a runtime producer**. Mark state applications167591/167596/167600/167604/167706/367431/367437 and related variants carry190 in native target mask6. `NativeStateHandler._phase` emits those exact definition-supplied identifiers through the shared state lifecycle. Actual645 mark application observed child368109 execute over its native cross ring1–2. Recipient healing and complete mark/passive interactions require the corresponding wounded recipient fixture; root execution alone is not counted as a health-consequence proof.

## Remaining branch ownership

Cunejo/Naturaleza Muerta5455/Súper Cunejo7991/Transgresión7992/Ambivalencia7998 are validated by the grant/summon pipeline work. Marca Anbareul7996, mark accumulation/consumption and the other marker passives must be assessed through actual spell/state consequences, not independent passive-root activation percentages. Contra Natura conditions, marked-target ownership and death ordering remain explicit source conditions.

## Semantic coverage matrix after implementation

The following matrix is intentionally branch-specific. A listed consequence does not certify every combination, tooltip condition or client delivery path. The expanded seven-test passive module passed, and the final combined regression gate passed134 executed tests without failures or skips. Numeric values below use level200, persisted injury300, native AP and the legal two-spell779/630 deck, with an unobstructed enemy cell. No turn, damage or healing notification is fabricated.

| Passive | Actual semantic evidence | Remaining limits |
|---|---|---|
|628|779 does not produce3869; subsequent630 deals125 and installs3878/40, versus baseline165 with accumulator consumed|Other mark/heal consumers and caps|
|644|Actual direct630 consumes the779 accumulator, deals165 and completes167935|All mark-specific conditional combinations|
|1415|After actual1001 turn start,779 self healing46→115 against identical baseline|Zone/indirect exclusions and other recipient combinations|
|1536|Self received healing42→54; other-recipient healing unchanged|Other received-heal sources and stack combinations|
|1537|Actual645 mark heals wounded caster in ring1–2 by21 versus0 baseline; ally outside ring unchanged|Other mark/ring positions and critical cases|
|5451|Separate mark pipeline proves actual779 heal42→21 and deferred21 restored/cleared by voluntary movement|Other expiry/interrupt combinations|
|5453|Maximum/current HP both+1600 once; subsequent heal cannot duplicate it|Other level breakpoints|
|5454|Actual779 allied heal costs caster4HP at >80%HP; below80% costs0; allied heal47 unchanged|Paroxismo threshold100% and further combinations|
|5455|Cunejo costs3AP instead of2 across four profiles; actual death creates1814; successive turns heal31 and renew3918; next death replaces the old area|Additional multi-owner combinations and client rendering|
|5463|779→630 deals155 versus baseline165;368124 executes; expanded test checks real self recovery|Other life-steal sources and overheal|
|7987|Actual779→turn-end totals64 self,24 ally8,22 ally9 versus42/0/0; consumes3869; enemy unchanged|Other radii and deferred combinations|
|7990|Actual779→turn regeneration rebuilds3869 from40 to80; baseline stays40; HP unchanged at boundary|Isolated no-neighbor branch and alternate3878 branch|
|7991|Separate summon pipeline proves base→super replacement in natural/dark modes with exactly one live summon|Remaining passive combinations|
|7992|Contra Natura adds75 resistance and toggle removal clears it; actual allied healing47→26 under its final-heal modifier|Further stacked modifiers|
|7993|Legal TACKLE8 consumed to0; zero does not become negative; healing temporarily adds DODGE120; direct attack consumes it to0 and applies enemy3903|Other mark conditions and durations|
|7994|Actual779 accumulator40→20; subsequent630 damage165→145|All mark/critical combinations|
|7995|Actual630 damage125, consuming accumulator and applying enemy3907 on even table; subsequent actual enemy turn-end damages through371902|Odd table3886 and Vampiripsa branch combinations|
|7996|645→actual granted7979 Repulsion consumes victim3882, damages neighboring enemy and does not push victim; neighboring mark remains|Other mark types and Contra Natura variants|
|7997|Actual779 accumulator40→80; subsequent630 damage165→205|Other Contra Natura interactions|
|7998|Granted7977 raises actual allied healing47→59; actual direct healing triggers enemy damage8/9, while direct damage779/630 is a negative control|Further combinations and client delivery|

The expanded test also checks that equipping7994 and7997 together leaves the actual accumulator at40, exercising their mutual conditional exclusion. Their independent scaling must not be added blindly. A zone645 negative-control probe does not consume3869 and deals the same69 across these marker configurations; it is not used as a substitute for a legal direct630 attack.


## Completed remaining passive gate

`test_aniripsa_passive_remaining_pipeline.py` passed7tests in39.824s using a GC-disabled unittest wrapper and explicit exit after reporting. The original expanded7test passive module also passed under the final independent Luna run (52.625s). Remaining branch tests use actual RuntimeMessages end/ACK/start cycles where1001 or table parity matters. Secreto de Produccion chooses3886 on odd native table turns and3907 on even turns; the delayed test advances the real cycle before casting, then observes enemy1002 and371902 damage. Anbareul is triggered by granted Repulsion7979 on an already marked target, not by repeatedly applying645. Resplandor turn-end RNG is seeded for reproducible ally healing.

Private logs: `.runtime/ani-passive-remaining-tests.log`, `.runtime/ani-passive-nativebranches.log`, `.runtime/aniripsa-implementation-20261009/passive-expanded-wrapped.log`. These tests do not require or perform a service restart.
