# Damage-only flags on native healing

The Ready granted-spell audit rejected Sacrier 5046 with `Unhandled native
healing flags`. Its installed HP-gain children 417444, 417447, 416864 and 416867
are ordinary healing family25 definitions carrying flags2 and28.

Actual `eVl.fLK()` identifies these as `DONT_USE_BLOCK` and
`BYPASS_ARMOR_AND_BARRIER`. Their native consumers govern `eXt` HP loss;
`eXs.fOC` delegates HP gain to `fat`, which applies the declared coefficient
mode, healing mastery/final modifiers and target healing resistance without
using either damage-only flag. The shared healing handler now accepts those
semantically inert HP-gain flags. Spell IDs do not select this behavior.

`ProbeNativeHealingDamageFlags.java` executes actual native `fat` against
empty, flag2, flag28 and combined definitions across all four coefficient
modes: **16 cases passed**. The server regression also checks current HP,
virtual HP, healing-resistance growth and the delivered healing value. KO,
undead conversion and unknown flag guards remain required.

The nominal granted5046 Ready cast is delegated for a fresh immutable
validation snapshot; this source change alone does not establish graphical
or complete Sacrier gameplay verification.
