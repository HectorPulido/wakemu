# Normal spell execution context origin

The installed client jar proves scalar `eVt` construction and serialization,
but does not contain the original normal server spell entry point. An exact ASM
method-reference scan distinguishes real class references from unrelated
members named `eVt` in `aSy` and `cWi`.

Direct `eVt.<init>()` callers are only:

- `eVt.a`: the general context factory.
- `eZR.g(iN)`: restore received context13 through `ir`, then clone it. Its
  constructor defaults are overwritten by the received record.

Actual `eVt.a(ZZ,eZR)` callers are the client previews `aJu.a` and `fpN.y`,
`eVt.fLU` cloning, and child/group runners `eZM`, `eYx`, `eWu`, `eYg`, `eYj`,
`eYh`, `eYC`, `eXD`, `eXn`, `eXs`, `eYy`, `eYi`, `eXR`, `eYk`, `eZi`, `eZh`.
None is an ordinary normal-server cast entry. Exact SP/mb/SQ/mc/fLQ consumers
are recorded in `native-normal-execution-context-consumers-20261008.json`.

These child producers cannot establish root dispatch defaults. For example,
`eXn.d` creates a context with source-runner authority, selects that runner's
effective level with SP, forces SET to its current value, and disables `ban`.
Its separate `c` route may create a missing context and set fLQ. Substituting a
fresh all-default context for either route would erase real execution behavior.

The typed scalar serializer and supplied native context13 consumers remain
valid. A normal-root producer remains unavailable from these installed sources;
private Python plan flags, selected variants and client preview defaults are
not evidence of its original native PS identity. No production guard was
weakened and no normal-root context was fabricated.

The bounded scan used original bytecode only, with128MB JVM instances and no
combat catalogs, services or database access. Existing original scalar-byte
oracle evidence is in `native-execution-context13-20261007.md`.
