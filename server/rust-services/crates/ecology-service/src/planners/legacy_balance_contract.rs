//! Statistical gates migrated from EcologyBalanceStatisticalGate in Python.
//! The harness supplies qualified fixtures; all policy decisions use native Rust.
use super::*;
use rand::{rngs::StdRng, Rng, SeedableRng};

#[test]
fn seeded_population_trajectory_never_regresses_and_respects_soft_sizes_and_caps() -> Result<()> {
    // Same qualified family as the frozen 240-draw selection contract.
    let c10 = json!({"reference":10,"min_level":10,"boss_classification":"regular"});
    let c11 = json!({"reference":11,"min_level":10,"boss_classification":"regular"});
    let boss = json!({"reference":99,"min_level":15,"boss_classification":"boss"});
    let c20 = json!({"reference":20,"min_level":20,"boss_classification":"regular"});
    let c30 = json!({"reference":30,"min_level":30,"boss_classification":"regular"});
    let ordinary = vec![
        vec![c10.clone(), c11.clone()],
        vec![],
        vec![c20.clone()],
        vec![c30.clone()],
    ];
    let catalog = json!({"families":[{"family_id":68,"tiers":[{"candidates":[c10,c11]},{"candidates":[boss]},{"candidates":[c20]},{"candidates":[c30]}]}]});
    let configuration = json!({"base_probability":0.72,"stage_decay":0.92,"boss_probability":0.0});
    let mut rng = StdRng::seed_from_u64(681113);
    let refs = [10, 11, 20, 30];
    let mut roster: Vec<Value> = (0..4)
        .map(|_| json!({"ref":refs[rng.random_range(0..refs.len())]}))
        .collect();
    let mut up = 0usize;
    let mut down = 0usize;
    for cycle in 1..=60000 {
        let index = rng.random_range(0..roster.len());
        let old = integer(&roster[index], "ref")?;
        let (_, old_rank, current) = stage(&catalog, old)?.context("Missing fixture stage")?;
        let level = i32::try_from(integer(current, "min_level")?)?;
        let decision = mob_lifecycle::event(&"ab".repeat(32), cycle)?;
        if let Some(candidate) = choose_prepared(
            &catalog,
            old,
            &configuration,
            rng.random::<f64>(),
            &decision,
            &roster,
            level,
            ordinary.clone(),
            vec![],
        )? {
            let new_reference = integer(&candidate, "reference")?;
            let (_, new_rank, _) =
                stage(&catalog, new_reference)?.context("Missing selected stage")?;
            up += usize::from(new_rank > old_rank);
            down += usize::from(new_rank < old_rank);
            assert!(integer(&candidate, "min_level")? >= i64::from(level));
            roster[index] = json!({"ref":new_reference});
        }
    }
    assert!(up > 0);
    assert_eq!(down, 0);

    let reproduction = json!({"interval_ms":60000,"birth_probability":0.25,"birth_stage_decay":0.85,"new_group_probability":0.5,"max_members":8,"max_zone_members":500,"max_zone_groups":100});
    let mut groups: Vec<usize> = (0..24).map(|_| rng.random_range(2..=5)).collect();
    let mut external = 0;
    for _ in 0..300000 {
        let population: usize = groups.iter().sum();
        if population >= 500 {
            break;
        }
        let index = rng.random_range(0..groups.len());
        let size = groups[index];
        if !reproduction_has_capacity(population, groups.len(), size, &reproduction)? {
            continue;
        }
        let probability = mob_lifecycle::birth_probability(0, false, &reproduction, size)?;
        if rng.random::<f64>() >= probability {
            continue;
        }
        if groups.len() < 100
            && rng.random::<f64>() < mob_lifecycle::new_group_probability(size, &reproduction)?
        {
            groups.push(1);
            external += 1;
        } else if size < 8 {
            groups[index] += 1;
        }
    }
    assert!(external > 0);
    let total: usize = groups.iter().sum();
    assert!(total <= 500);
    assert!(groups.len() <= 100);
    assert!(groups.iter().all(|size| *size <= 8));
    let count = |wanted| groups.iter().filter(|size| **size == wanted).count();
    assert!(count(4) + count(5) > count(1));
    assert!(count(8) < 2.max(groups.len() / 10 + 1));
    let fourth = mob_lifecycle::new_group_probability(4, &reproduction)?;
    let fifth = mob_lifecycle::new_group_probability(5, &reproduction)?;
    let seventh = mob_lifecycle::new_group_probability(7, &reproduction)?;
    assert!(fourth > 0.0);
    assert!(fifth > fourth);
    assert!(seventh > fifth);
    Ok(())
}
