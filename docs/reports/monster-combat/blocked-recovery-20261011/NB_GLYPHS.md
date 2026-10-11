# Native glyph count predicate

References 3528, 1152, 2393 and 3612 use the numeric predicate `NbGlyphs`.
A representative original criterion compares the caster's trap characteristic
against `NbGlyphs("caster")`, optionally excluding state 7134.

Installed parser `eQd` maps token 364 (`NB_GLYPHS`) to `ePo`. Its `fyG`
returns `fbp.rNH.aIc()`, proved to be zero by a local Java witness.
Inherited `ePi.d` resolves the actual fight, iterates `Qs.bdm`, checks each
area's `Qq.aeV` type and optionally compares `Qq.bch().Sn` with the selected
native actor identity. With no selector it counts all glyphs. A proven null
selected actor matches no owner; unknown actor authority remains an error.

The general condition evaluator now supports this numeric predicate using an
explicit callback. The runtime adapter requires actual global area collection
authority, validates the registered population through existing `_rows`, and
reuses native state actor selector resolution. Missing Qs is never interpreted
as an empty population. Cell-to-fighter target resolution remains rejected
when that authority is unavailable. Constructor-private areas are not added
to Qs to satisfy this condition.

Four focused tests pass, covering native type filtering, owner filtering,
all-owner counting, null owner, invalid metadata, numeric criteria, callback
authority and invalid arguments. These tests contain no characteristic names
and isolate only the unrelated alias catalog lookup. Existing tests and native
catalogs were not modified. Independent adapter verification and actual
monster replay remain separate gates before activation.
