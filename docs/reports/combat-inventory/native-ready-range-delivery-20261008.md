# Ready characteristic and range delivery order

The Ready boundary previously sent12873 authoritative baseline characteristics
before13912 empty running effects. That order can discard equipment RANGE11 on
an attached client fighter. `cuV` invokes `big.dU`, which calls
`big.a(bytes,true,null)`; this calls `bjo.dpQ` before effect replay. When `dnz()`
confirms the attached fighter (`igz`/`igA` and `pGz`), `dpQ` calls `frm.aYY`.
`ffh.aYY` visits every characteristic and `fff.aYY` restores native reset
minimum, maximum and current, clears percentage and active modifiers. Replaying
an empty population cannot restore flat equipment characteristics supplied only
by the authoritative characteristic snapshot.

The native combined `big.a(buH,stats,effects)` method deliberately applies effects
first and statistics second. Ready now follows that same order:13912 then12873
for each baseline actor, followed by fight start and actual initialization
packets. Thus flat RANGE and other equipment characteristics survive the reset,
while subsequent native passives/states still apply once through their existing
effect delivery. The baseline is still captured before initialization.

This correction is common to all classes and characteristics. Category1066 range
modifiers remain native running effects, distinct from RANGE11. No spell-specific
range adjustment, shortcut grant or condition bypass was introduced. Existing
Ready/runtime packet-order assertions were updated; validation is queued.

Source excerpts: `spell-access-big-native.txt` (`dnz`, `dU`, `a(byte[],boolean,fcb)`,
`a(buH,byte[],byte[])`) under `.runtime/combat-review-20261007/`, and original
`bjo.dpQ`, `ffh.aYY`, `fff.aYY` disassemblies. No services or DB were changed.
