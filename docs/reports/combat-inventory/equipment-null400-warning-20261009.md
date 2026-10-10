# Standard null equipment effects

The reported Dragopavo18682 / itemUID1099511633734 warning identifies effect119215, family400. Published equipment metadata identifies native runner eXE, zero parameters, no characteristic, no criterion or trigger, targetmask0, passive variant0 and active-effect=false. Native eXE.C does nothing when there are no parameters; eXE.c(Qe,boolean) is an immediate return. This is a recognized standard null effect, not an unsupported statistic.

The warning originates in equipment_stats.bonuses: _flat recognizes eWN/eWQ statistics but returns None for eXE. The caller previously labeled every such result unsupported. The unrelated Dragopavo damage effect119202/eWQ/stat20 already scaled correctly with pet level. Existing tests checked only that statistic and did not assert that the unsupported list was empty. The shared Sacrier target-selection change does not modify this path.

The fix recognizes the complete unconditional, zero-parameter native eXE400 contract and leaves its statistic contribution empty. Conditional, triggered, targeted, unknown-runner and status-parameter variants remain explicitly unsupported. The separate native equipment planner has no established production caller and is unchanged; this correction does not claim additional effect initialization or retention.

Validation: test_equipment_stats and test_combat_equipment_initialization,16tests passed. The real18682 test verifies no initialization warning and unchanged damage scaling at pet levels0/1/2/35/50. Negative variants remain rejected. Log: `.runtime/equipment-null400-focused.log`. No services were restarted or code deployed.
