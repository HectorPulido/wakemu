//! Native statistical/data gates migrated from test_ecology_balance_gate.py.
//! Uses the real planner and an explicitly pinned, read-only native catalogue;
//! generated seeds and SQL state are confined to Fixture's private test schema.
use super::*;
use rand::{rngs::StdRng, Rng, SeedableRng};
use wakemu_ecology::planners::{mobs, native_monster};

#[tokio::test]
async fn gobball_planting_initial_variants_are_uniform_and_reachable() -> Result<()> {
    let fixture = Fixture::create().await?;
    let ctx = native_context(&fixture).await?;
    let initial = plants::initial_candidates(&ctx, 68, None).await?;
    let mut refs: Vec<i64> = initial
        .iter()
        .map(|c| c["reference"].as_i64().unwrap())
        .collect();
    refs.sort();
    assert_eq!(refs, vec![2, 39]);
    let mut rng = StdRng::seed_from_u64(20261012);
    let mut draws = HashMap::<i64, usize>::new();
    for _ in 0..20000 {
        *draws
            .entry(refs[rng.random_range(0..refs.len())])
            .or_default() += 1;
    }
    assert_eq!(draws.len(), 2);
    assert!(draws[&2].abs_diff(draws[&39]) <= 400);
    let definitions = ctx.catalog.document("plant-resources.json").await?;
    let seeds = ctx.catalog.document("seed-actions.json").await?;
    let seed_resources: HashSet<i64> = seeds
        .as_array()
        .context("Native seed actions required")?
        .iter()
        .filter_map(|s| s["resource_reference"].as_i64())
        .collect();
    let resource = definitions
        .as_array()
        .context("Native resource definitions required")?
        .iter()
        .find(|d| {
            d["monster_resource"] == true
                && d["monster_family_ids"]
                    .as_array()
                    .is_some_and(|f| f.contains(&json!(68)))
                && d["resource_reference"]
                    .as_i64()
                    .is_some_and(|r| seed_resources.contains(&r))
        })
        .context("Native Gobball seed resource required")?["resource_reference"]
        .as_i64()
        .unwrap();
    fixture.pool.get().await?.execute("INSERT INTO planted_resources(resource_uid,map_id,instance_id,x,y,z,resource_reference,stage,creation_time) SELECT n::bigint,1,0,n::integer,2,0,$1,1,0 FROM generate_series(1,10000) n",&[&i32::try_from(resource)?]).await?;
    let mut snapshot = fixture.snapshot();
    snapshot["reserve_monster_births"] = json!(true);
    snapshot["world_epoch"] = json!(format!("{}:gobball-uniform", fixture.schema));
    let mut native_draws = HashMap::<i64, usize>::new();
    let mut seen = HashMap::<i64, i64>::new();
    for _ in 0..158 {
        for batch in plants::prepare(&ctx, &snapshot, 4).await? {
            for row in batch["resources"]
                .as_array()
                .context("Native birth batch required")?
            {
                let uid = row["expected"]["resource_uid"].as_i64().unwrap();
                let reference = row["member"]["ref"].as_i64().unwrap();
                assert!(refs.contains(&reference));
                if let Some(old) = seen.insert(uid, reference) {
                    assert_eq!(
                        old, reference,
                        "A durable seed identity rerolled its native variant"
                    );
                } else {
                    *native_draws.entry(reference).or_default() += 1;
                }
            }
        }
        if seen.len() == 10000 {
            break;
        }
    }
    assert_eq!(seen.len(), 10000);
    assert_eq!(native_draws.len(), 2);
    assert!(native_draws[&2].abs_diff(native_draws[&39]) <= 500);
    // A new epoch re-enumerates the first IDs; their deterministic selections
    // survive the planner-owner restart without introducing another draw.
    snapshot["world_epoch"] = json!(format!("{}:gobball-restarted", fixture.schema));
    for batch in plants::prepare(&ctx, &snapshot, 4).await? {
        for row in batch["resources"].as_array().unwrap() {
            let uid = row["expected"]["resource_uid"].as_i64().unwrap();
            assert_eq!(row["member"]["ref"].as_i64(), seen.get(&uid).copied());
        }
    }
    assert_eq!(fixture.count("planted_resources").await?, 10000);
    drop(ctx);
    fixture.cleanup().await
}

#[tokio::test]
async fn wabbit_near_level_male_female_are_initial_alternatives() -> Result<()> {
    let fixture = Fixture::create().await?;
    let ctx = native_context(&fixture).await?;
    let pool = plants::initial_candidates(&ctx, 1113, None).await?;
    let refs: HashSet<i64> = pool
        .iter()
        .map(|c| c["reference"].as_i64().unwrap())
        .collect();
    assert_eq!(refs, HashSet::from([5455, 5456]));
    let mut names = HashSet::new();
    let mut levels = Vec::new();
    for reference in &refs {
        let definition = ctx.catalog.monster_definition(*reference).await?;
        names.insert(
            definition["name"]
                .as_str()
                .context("Native Wabbit name required")?
                .to_owned(),
        );
        levels.push(definition["min_level"].as_i64().unwrap());
    }
    assert_eq!(
        names,
        HashSet::from(["Wonejo".to_owned(), "Mamá wonejo".to_owned()])
    );
    assert!(levels.iter().max().unwrap() - levels.iter().min().unwrap() <= 2);
    let mut rng = StdRng::seed_from_u64(1113);
    let refs = [5455, 5456];
    let mut counts = HashMap::<i64, usize>::new();
    for _ in 0..10000 {
        *counts.entry(refs[rng.random_range(0..2)]).or_default() += 1;
    }
    assert!(counts[&5455].abs_diff(counts[&5456]) <= 400);
    drop(ctx);
    fixture.cleanup().await
}

#[tokio::test]
async fn selected_ecology_forms_are_native_publishable_and_unnamed_ref_is_excluded() -> Result<()> {
    let fixture = Fixture::create().await?;
    let ctx = native_context(&fixture).await?;
    let unnamed = ctx.catalog.monster_definition(5405).await?;
    assert!(
        !native_monster::publication_viable(
            &ctx,
            5405,
            i32::try_from(unnamed["min_level"].as_i64().unwrap())?
        )
        .await?
    );
    let catalog = plants::normalize_growth_catalog(
        ctx.catalog.document("monster-growth-catalog.json").await?,
    )?;
    let configuration = json!({"base_probability":1.0,"stage_decay":1.0,"boss_probability":0.0});
    let decision = json!({"variant_seed":"ab".repeat(32)});
    let mut proofs = HashSet::new();
    let mut selected_count = 0usize;
    for family in catalog["families"]
        .as_array()
        .context("Native growth families required")?
    {
        let family_id = family["family_id"].as_i64().unwrap();
        for candidate in plants::initial_candidates(&ctx, family_id, None).await? {
            let reference = candidate["reference"].as_i64().unwrap();
            let level = i32::try_from(candidate["min_level"].as_i64().unwrap())?;
            assert!(native_monster::publication_viable(&ctx, reference, level).await?);
        }
        for candidate in family["tiers"]
            .as_array()
            .unwrap()
            .iter()
            .flat_map(|tier| tier["candidates"].as_array().unwrap())
        {
            let reference = candidate["reference"].as_i64().unwrap();
            if reference == 5405 {
                continue;
            }
            let source_level = i32::try_from(candidate["min_level"].as_i64().unwrap())?;
            for draw in [0.0, 0.2, 0.4, 0.6, 0.8, 0.999] {
                if let Some(selected) = mobs::choose_next(
                    &ctx,
                    reference,
                    &configuration,
                    draw,
                    &decision,
                    &[json!({"ref":reference})],
                    source_level,
                )
                .await?
                {
                    let target = selected["reference"].as_i64().unwrap();
                    assert_ne!(target, 5405);
                    let level = i32::try_from(selected["min_level"].as_i64().unwrap())?;
                    selected_count += 1;
                    assert!(
                        native_monster::publication_viable(&ctx, target, level).await?,
                        "Unpublishable reference {target} selected from {reference} at {draw}"
                    );
                    if proofs.insert((target, level)) {
                        let member =
                            native_monster::owned_instance(&ctx, target, level, -1, 1, 0, 0, 0)
                                .await?;
                        assert!(!native_monster::spawn_group(&ctx, &[member], 1)
                            .await?
                            .is_empty());
                    }
                }
            }
        }
    }
    assert!(selected_count > 0);
    assert!(!proofs.is_empty());
    drop(ctx);
    fixture.cleanup().await
}
