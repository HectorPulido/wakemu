# Enutrof complete manual acceptance — 2026-10-10

Native breed3. This is the client acceptance plan, not a report of a completed manual pass. Automated qualification is tracked separately in `enutrof-passive-qualification-20261010.json` and `test_enutrof_runtime.py`; pending technical failures must be resolved before marking the class provisionally ready.

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
