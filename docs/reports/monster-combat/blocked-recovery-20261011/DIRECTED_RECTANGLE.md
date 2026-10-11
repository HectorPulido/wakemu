# Directed rectangle recovery

References 4730, 4729 and 4738 encounter native `anz` rectangles. A concrete
candidate example is effect 256225 (family 304, `Directed rectangle-1x2`).
Effects 256233, 256443 and 256444 use lengths five and six. The candidate also
contains their 279xxx variants.

Installed `anz` bytecode establishes:

* Constructor parameters are a nonnegative half-width and positive length.
* `bEm` prints full odd width `2 * half_width + 1` and length.
* `bEx` enumerates Y from negative to positive half-width, then X from zero
  through length minus one. This order matters for cell-group children.
* `bEj` is false; existing `anc` directional transforms apply unchanged.

The general shape resolver now recognizes this exact printed representation,
preserves Y-major order and delegates orientation, actor membership and group
cell routing to existing native geometry. Impossible printed dimensions fail
closed. No catalog changes or per-monster special cases are involved.

Verification:

* Native Java differential witness: nine of nine ordered point lists agree,
  covering full widths one, three and five, each at lengths two, five and six.
  Private receipt: `.runtime/monster-blocker-recovery-20261011/anz-native-witness.txt`.
* Four new focused tests verify ordering, orientation, forward membership,
  terrain height selection and invalid inputs. Together with existing effect
  target tests, 18 tests pass.
* The adjacent group-cell suite has one environment failure loading its live
  catalog without `WAKFU_DATABASE_URL`; the remaining tests passed. Existing
  tests were not modified and this failure is not reported as a passing gate.

Native monster replay remains pending; geometry support alone does not make a
whole monster ready for activation. No services or catalog were changed.
