# Class304 parameters

Native registry eVi maps304 to eWu, not eZg. eWu.C(Qe) evaluates parameter0
(state reference) and parameter1(state level), narrowing both to signed short.
Its fNb evaluates parameter2. fNa interprets that as a separate application
chance: -1 returns100 directly; -2 returns0. Other values depend on the state
elk category and source/target characteristic bonuses, then clamp0..100.
This differs from generic effect probability in the exported effect profile.

bbH evaluates fNa and, below100, compares against UK.pT(100), alongside other
native eligibility guards. Therefore accepting parameter2 blindly would skip
a distinct chance mechanism. Runtime support intentionally covers only the
three-parameter -1 branch. Four/five-parameter spell-level inheritance and
six-plus-parameter state-dependent chance modes remain rejected.

All1869 class304 rows currently in spell-effect-trees.json have three evaluated
parameters and parameter2=-1 at level1. NativeStateHandler now checks that
sentinel and consumes all three parameters. Old two-parameter test fixtures
were invalid for this accredited subset and have been corrected.

ProbeStateApplicatorParameters.java uses real exported effect167716:
[3896,1,-1] yields native eWu state3896/level1/chance100. It also confirms
reference/level signed-short narrowing and -2's zero chance. Runtime -2 stays
unsupported until the exact random/eligibility path is implemented.

The real167716 criteria are evaluated by the dispatcher; the handler test
calls it directly to verify parameters and state application, not to certify
eligibility for an actual player cast.
