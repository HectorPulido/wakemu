# Captured summon fan scaling

Original `fan.a(ffa,float,float)` processes its main list first, then its
secondary list. The installed original enum identities are:

* main: 1, 92, 24, 21, 23, 22, 20, 31, 28, 30, 29, 27;
* secondary: 8, 7, 35.

For each PA it reads effective current, computes
`round(float(current)-abs(float(current)*float(1-factor)))`, and invokes
`PA.on` before reading effective maximum. It then invokes `PA.or` with
`round(float(maximum)*factor)`. Every arithmetic step follows float32.
Thus a factor greater than one can reduce current while increasing raw
maximum; this is not multiplication of current by the factor.

The implementation preserves original `fff` setter behavior: current uses
the old maximum (or hard maximum for expandable characteristics); raw maximum
cannot fall below raw minimum; maximum percentage remains installed; effective
maximum uses native integer overflow and hard bounds. The captured constructor
result must be the exact registered actor and carry actual `new bje` provenance.
All characteristic snapshots are checked before publishing any updates.
Frozen PA without explicit raw-current authority remains rejected, rather
than inferring that effective current is its raw value.

`ProbeNativeCapturedScaling.java` exports original groups and executes the
private original fan scaling method on actual `fff` instances. Factors 0,
0.5, 1 and 1.5 reproduce the current/raw/effective values. Five Python tests
pass, including both groups, negative current, and atomic rejection when the
last required PA is missing. Full family324 factory integration is owned by
the captured-roster handler agent and is a separate validation scope.
