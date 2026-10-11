# Conservative native opponent discovery

Offline work only; no activation, deployment, or runtime replay is claimed.

Representative: Nemotilus mechanic 4155, spell 5865, requires
`IsBreedId("target", 4152)`. Ordinary player targets cannot satisfy this.
The sealed native monster extraction contains reference 4152 at level 100,
with initial state triple `[4490, 1, 0]`. The normal fixture already supports
constructing a native opponent through `owned_instance` and ordinary initial
state installation. The recipe therefore supplies that actual native reference
and descriptor level, without changing caster criteria or creating states.

The generalized helper recognizes necessary positive `IsBreedId("target", id)`
and `HasState(id, "target")` calls under conjunctions. Entire expressions with
negation or disjunction are conservatively excluded. Conflicting breeds,
missing profiles, malformed triples and invalid level ranges yield no recipe.
State candidates must carry the state in the actual native initialization plan;
`prepare_scenario` subsequently checks the real initialized state ledger.
Native eligibility and all normal commit paths remain authoritative.

The helper returns at most four proposals using actual native minimum/maximum
levels. Recovery search explicitly enables it; default validation does not
query companion discovery. Imported initial-state authorities delimit runtime
candidates; the sealed extraction was used only for the offline structural
representative receipt.

Observed structural groups: six Nemotilus definitions require 4152; three sport
actors require 2783 (native level 50); Old Binson 1751 requires 1753 (level 65).
These are candidate scenes, not ten newly functioning monsters. Reference 2325
is absent from the sealed extraction and receives no invented substitute.
The existing special-encounter exclusion policy remains unchanged.

Validation: `PYTHONPATH=server .runtime/local/verification-venv/bin/python -m
unittest discover -s server/tests -p 'test_monster_native_opponent*.py'`:
9 tests passed (five discovery cases, one new integration case and three
inherited unchanged baseline budget cases). No existing tests were edited.
Actual native combat replay remains pending because the current environment
cannot connect to the read-only local PostgreSQL service.

Private structural receipt:
`.runtime/monster-blocker-recovery-20261011/native-opponent-discovery.json`.
