# Reviewed local mining distribution plan

`LOCAL-MINING-VEIN-PLAN.json` is the validated source distribution. A copy checked
against the current gameplay catalog has now been installed; see
[deployment and manual acceptance](DEPLOYED-VEINS-20261010.md).
The distribution is an explicit local policy; it is not official mineral spawn
information. Stable slots become durable gameplay identities only when installed.

## Approved full coverage

The seeded `all_accessible` policy allocates every accessible, unambiguous
candidate XY, without a per-map cap or spacing limit. It reserves at least one
slot for each supported mineral species, then chooses remaining species with
weight `1 / (1 + minimum_level / level_scale)^level_power`. Low-level minerals
therefore remain more common while all51 species are represented.

The native mining product resolver supports fixed products and validated native
candidate products, including resource643. Common stages are preferred; alternate
terminal stages are selected with an explicit local2% probability. These stages
have no verified official rarity label or probability.

- 2881 fixed slots on46 maps;51/51 supported mineral species.
- 2816 common stages and65 alternate stages in this deterministic plan.
- All2881 accessible, unambiguous candidate slots are allocated.
- 18 species require one explicitly marked `local-mineral-ground-fallback`
  placement each. These use a verified positive mineral ground with native mineral
  eligibility, but compatibility with the assigned species is a local override.
- 196 candidate records are excluded because multiple native heights share an XY.
- One map189 candidate is excluded because the native approach resolver rejects it.
- No missing species minimum and no navigation loading error.
- The3078 native candidate records reconcile exactly with2881 placements plus197
  exclusions. The complete asset audit retains1509 rejected chunks and partial
  decoder evidence; it does not claim every rejected chunk has been recovered.

## Native approach authority

Mining uses the installed client's `cWn.gu` → `VF.a` profession73 approach
contract: cardinal neighboring cells resolved by native walkable-height logic.
The resource itself need not be walkable. Thus map527(74,-53,3), previously
incorrectly excluded by an incoming-edge requirement, has valid native neighboring
approaches. Combat topology and spell behavior are unchanged.

Inspection navigation comes from `--navigation-dir`; every document is validated
by `mining_navigation._incoming` for client/topology hashes, exploration profile,
ground metadata and approach authority. Runtime navigation must be published in
the SQL native catalog. There is no runtime filesystem fallback.

Provenance includes source evidence and asset hashes, native ground, eligible
species, selected action and `species_ground_policy`. All placements explicitly
mark `official_spawn=false`; fallback compatibility is never presented as native.

## Reproduction and verification

With existing read access to the native catalog, from the repository root:

```bash
PYTHONPATH=server .runtime/local/verification-venv/bin/python \
  client-tools/inspection/plan-mining-veins.py \
  docs/reports/mining/NATIVE-MINING-SURFACES-COMPLETE.json \
  docs/reports/mining/LOCAL-MINING-VEIN-PLAN.json \
  --distribution local-native-terrain \
  --policy docs/reports/mining/LOCAL-MINING-DISTRIBUTION-POLICY.json \
  --navigation-dir .runtime/local/mining-full/world-navigation
PYTHONPATH=server .runtime/local/verification-venv/bin/python \
  server/tools/install_mining_veins.py \
  docs/reports/mining/LOCAL-MINING-VEIN-PLAN.json \
  --navigation-dir .runtime/local/mining-full/world-navigation
PYTHONPATH=server:server/tests .runtime/local/verification-venv/bin/python \
  -m unittest test_mining_surface_inspection test_mining_navigation
```

The installer dry-run validated2881 placements with `applied=false`; no gameplay
DB write occurred. Ten planner/navigation tests pass, covering compact-mode
compatibility, full coverage, explicit species fallback, native nonwalkable target
approaches, missing evidence and publication revision changes. Runtime lifecycle
and database acceptance are validated separately.
