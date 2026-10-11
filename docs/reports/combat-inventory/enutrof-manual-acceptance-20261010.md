# Enutrof complete manual acceptance — 2026-10-10

Native breed3. This is the client acceptance plan, not a report of a completed manual pass. PostgreSQL and deployed World/AI/Ecology currently use catalog `bd79c10d0f29de7a32fa29f5d91439388de9ace3f8c2b9ed73f8314856667ae1`. Automated Enutrof evidence is historical and is not a bd79 rerun. Keep the source-qualified `5075` / event74 producer boundary and other class-specific gaps explicit; deployment health does not close them. See the [current six-class gate](remaining-six-refresh-20261010/current-closure-20261011.md).

The published owned roster is21 active spells and17 passives, with four granted actions and seven Drheller-book actions. See the [typed class inventory](remaining-six-refresh-20261010/enutrof.md), [passive branch report](enutrof-passive-branches-20261011.md) and [qualification receipt](enutrof-passive-qualification-20261010.json). These reports retain their stated historical pins; event74 remains an explicit unqualified producer boundary.

## Preparation

Use a disposable Enutrof outside combat. If needed use `!nivel 200`, then return to character selection and reconnect. This permanently raises the level. Equip ordinary spells/passives using the native spell book, never commands that add states, AP, HP, summons or granted actions.

Use `!mob 4 8 3` in exploration for three profile4 level8 enemies. They are weak at level200; recreate the group between rotations. For several-turn deposit/companion tests use a normal sufficiently durable enemy or an allied player's normal friendly challenge. Finish or surrender before creating the next group.

Use these ordinary decks in separate fights:

* Earth:2008,2010,2011,2012,2013,2026,2064.
* Water:2014,2015,2016,2017,2032,6324,6337.
* Fire:2018,2019,2021,2022,2037,8240,8242.

At Ready inspect automatic extra actions Excavation2063, Debt6405, Companion2027 and Perfórserker2038. They must arrive from the innate; do not equip them into ordinary slots. Record resources, current actor, deposits and the bar.

## Complete sequence

1. Cast every ordinary active in a legal highlighted context across the three decks. Compare damage, costs and state changes to the current native tooltip. Reject a self/occupied/blocked/out-of-range target where the corresponding native rule forbids it; resources and positions must remain unchanged and the next legal action must work.
2. Observe actual deposits at turn start. Mine an owned deposit with2063; verify consumption/replacement, actual AP cost and the resulting native state. Attempt a foreign deposit in a second-Enutrof fight. Check2026 with deposits present and2037/8240 on a real owned deposit, and the rejected corresponding context with none. Fire2018 must obey its native no-deposit-cell restriction.
3. Repeat mining with Geology2009, compare AP reimbursement and8895 limit; compare normal ore glyph207 with Cotización5076 glyph209. Check Codicia5071 against actual207/209. Avoid assuming that different deposit visual colors imply different raw grade values.
4. Ready already creates the native Drheller. Confirm correct owner/controller, model, HP and seven-action book2058/2077/3541/3542/8257/8258/8259 when applicable to its current profile. After its genuine death/removal, summon2027 on a native highlighted free cell. Move it and use its available abilities in legal contexts. Ability3541 creates203 only after the controller has no203: consume the existing203 through a legal action first. Compare Tuneladora8279: the companion loses3MP through its native3614 state and its ore abilities teleport the companion to the selected cell. Attempt a second companion while the first lives: the native one-companion criterion must reject atomically. Verify death/removal and a new legal summon.
5. Enter Perfórserker using2038 and inspect702, native AP-as-MP behavior, form costs and legal movement. Cast native form attacks only with sufficient8591 resource. Exit through2038: its native242970 MP-consumption effect lasts one target-clock turn; verify its expiry at the actual next turn instead of assuming immediate resource restoration. Check relevant passives5075/8272/8273/8274/8275 in separate legal builds.
6. Compare2039/6326/8276/8280 enabled and disabled through their actual treasure, debt, insurance and companion interactions. Check5059 investment states8553–8554,8277 protected ore absorption, and caps/reset of treasure8552. Follow current tooltips and supported native branches. A family400 marker alone does not prove an undocumented extra mechanic.
7. Finish with a real victory. Verify one reward result and one award, then reconnect: no duplicate reward. Prospection uses actual combat stat33; do not expect treasure8552 itself to create a prospection buff without a native source.
8. In a two-owner fight, reconnect while a companion and deposits exist. Both clients must retain actor identities, private bars, current resources, states and current turn without duplicated callbacks. Test surrender and a new fight: no old deposits, companion, grants or stale registration may leak.

Perform a short Cra beacon/Desbalizaje and Iop combo check after shared-engine changes. Report the exact action and turn when an expectation fails; a native prerequisite rejection is distinct from a runtime exception, resource loss on rejection, wrong recipient or a disconnected session.


## Additional current ownership and companion checks — 2026-10-11

These steps supplement the earlier sequence after the coordinated integrated
build passes. Automated evidence uses release677 and a staged generic resolver
correction; it is not a deployment receipt.

1. With a second actual Enutrof in the same friendly challenge, allow both
players a real turn so each produces its own deposits. Equip Protección
Mineral8277 on the test character. End its turn on its own deposit: expect
+100 resistance during the native protection callback and consumption of the
owned deposit. In another turn, end on the other player's distinct deposit:
expect no protection reward from8277 and no consumption of that foreign deposit.
2. During the actual companion turn, use2058 on an aligned enemy at distance2
or3. Expect a pull toward the companion, stopping before an occupied companion
cell; AP is paid once. Use3542 in its highlighted legal context and expect
positive armor. Use2077 on an actual deposit and expect its source conversion,
with the original deposit consumed. For8257/8258/8259, first remove the
controller's existing requested deposit through8240; the companion action
creates204/205/202 respectively at the selected cell. Existing3541 produces203.
The deposit belongs to the controller, while781 belongs to the companion.
3. Use Torpeza6337 on an eligible hostile in ordinary form and repeat in
Perfórserker form. Expect native target MP loss (the deterministic automated
fixture observes3→2), with the correct form cost. Reject self-targeting and
then perform a legal cast: rejection must not consume resources.
4. Compare ordinary and critical elemental attacks against an equivalent
target and unchanged build. Critical damage should follow the native critical
branch while the corresponding AP/WP payment remains unchanged. Do not compare
raw damage against a different target resistance or equipment build.

Companion appearances1381–1384 require their lawful cosmetic marker source;
do not use state-grant commands to manufacture it. Their published books and
initial-state payloads are identical to default1380. Appearance acquisition is
a separate manual prerequisite. The legitimate event74 producer needed by the
separate5075 route remains unrecovered; ordinary paid attacks are not evidence
of that event. Actual reconnect remains a client acceptance step even though
checkpoint JSON serialization and fresh-fight isolation pass automatically.
