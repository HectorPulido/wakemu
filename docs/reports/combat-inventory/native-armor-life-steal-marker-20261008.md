# Armor life-steal marker admission

The normal class11 spell5028 trace reaches original effect353422, family1013
(eWx), parameters `[0, 0.25, 0, 0]`, variant0, with native effect flag29.
The previous generic armor admission rejected this original class definition.

Original eVl static initialization offsets479–490 identifies flag29 as
`LIFE_STEAL_HEAL_EFFECT` (`rwZ`). Original eWx arithmetic reads single-target
flag22 and area flag4, and delegates range mastery to eYE. Neither eWx nor its
eWQ/eWW superclass arithmetic reads rwZ. The marker can therefore be retained
without changing coefficients, elemental mastery, final modifiers or armor cap.
The common event producer still receives the original flag; no flag is stripped.

Armor now admits flag29 in addition to its existing supported set. Unknown flags
still reject. Nine focused NativeArmorTests pass, including the actual parameter
shape at levels1/20/200 and marker equivalence with final modifiers0/37/111.
This is bounded arithmetic/application regression coverage; the full actual
class11 cast5028 trace remains a separate validation step.
