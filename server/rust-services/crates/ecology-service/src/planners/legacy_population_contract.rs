//! Legacy startup planner boundaries exercised against the Rust implementation.
use super::*;
use anyhow::Context as _;

fn fixture() -> Value {
    json!({"version":1,"scope":"native pilot","plans":[{
        "map_id":1134,"instance_id":0,"region_id":79001,"members":[
            {"reference":5008,"level":1,"x":-163,"y":-125,"z":-4},
            {"reference":5008,"level":1,"x":-162,"y":-125,"z":-4}
        ]
    }]})
}

#[test]
fn malformed_catalog_identity_and_shape_fail_closed() {
    let cases = [
        ("/version", json!(2)),
        ("/scope", json!(null)),
        ("/plans/0/map_id", json!(0)),
        ("/plans/0/map_id", json!(2147483648_i64)),
        ("/plans/0/instance_id", json!(1)),
        ("/plans/0/region_id", json!(-1)),
        ("/plans/0/members", json!([])),
        ("/plans/0/members/0/level", json!(0)),
        ("/plans/0/members/0/level", json!(32768)),
        ("/plans/0/members/0/reference", json!(true)),
        ("/plans/0/members/0/x", json!(1.5)),
        ("/plans/0/members/0/y", json!(2147483648_i64)),
        ("/plans/0/members/0/z", json!(-32769)),
    ];
    for (pointer, value) in cases {
        let mut catalog = fixture();
        *catalog.pointer_mut(pointer).unwrap() = value;
        assert!(
            parse_plans(&catalog).is_err(),
            "accepted {pointer}: {catalog}"
        );
    }
    for pointer in ["", "/plans/0", "/plans/0/members/0"] {
        let mut catalog = fixture();
        catalog
            .pointer_mut(pointer)
            .unwrap()
            .as_object_mut()
            .unwrap()
            .insert("unexpected".into(), json!(true));
        assert!(
            parse_plans(&catalog).is_err(),
            "accepted extra field at {pointer}"
        );
    }
}

#[test]
fn configured_habitats_are_region_scoped_and_unique() {
    let mut catalog = fixture();
    let mut other = catalog["plans"][0].clone();
    other["region_id"] = json!(79002);
    catalog["plans"].as_array_mut().unwrap().push(other);
    let plans = parse_plans(&catalog).unwrap();
    assert_eq!(plans.len(), 2);
    assert_eq!(plans[0].habitat, (1134, 0, 79001));
    assert_eq!(plans[1].habitat, (1134, 0, 79002));
    assert_eq!(plans[0].members[0].point, (-163, -125, -4));
    let duplicate = catalog["plans"][0].clone();
    catalog["plans"].as_array_mut().unwrap().push(duplicate);
    assert!(parse_plans(&catalog).is_err());
}

#[test]
fn disabled_policy_is_explicit_but_corrupt_policy_never_pauses_silently() {
    for enabled in [true, false] {
        for field in ["version", "members_per_zone"] {
            for invalid in [json!(null), json!(true), json!(0), json!(-1), json!(1.5)] {
                let mut policy = json!({"version":1,"enabled":enabled,"members_per_zone":2});
                policy[field] = invalid;
                assert!(validate_policy(&policy, 2).is_err(), "accepted {policy}");
            }
        }
    }
    assert!(!validate_policy(
        &json!({"version":1,"enabled":false,"members_per_zone":1}),
        2
    )
    .unwrap());
    assert!(validate_policy(&json!({"version":1,"enabled":true,"members_per_zone":1}), 2).is_err());
    assert!(validate_policy(&json!({"version":1,"enabled":true,"members_per_zone":9}), 2).is_err());
}

#[test]
fn capacity_is_regional_and_unknown_population_cannot_authorize_birth() {
    let population = json!({"complete":true,"regions":{
        "79001":{"monster":{"42":249}}, "79002":{"monster":{"42":250,"43":8}}
    }});
    assert_eq!(population_count(&population, 79001).unwrap(), 249);
    assert_eq!(population_count(&population, 79002).unwrap(), 258);
    assert_eq!(population_count(&population, 79003).unwrap(), 0);
    for invalid in [json!(-1), json!(true), json!(1.5), json!("249")] {
        let mut value = population.clone();
        value["regions"]["79001"]["monster"]["42"] = invalid;
        assert!(population_count(&value, 79001).is_err());
    }
    let mut incomplete = population.clone();
    incomplete["complete"] = json!(false);
    assert!(population_count(&incomplete, 79001).is_err());
    let overflow = json!({"complete":true,"regions":{"79001":{"monster":{
        "42":i64::MAX,"43":1
    }}}});
    assert!(population_count(&overflow, 79001).is_err());
}

async fn native_context() -> Result<Context> {
    use deadpool_postgres::{Manager, Pool};
    use tokio_postgres::{Config, NoTls};
    let mut config: Config = std::env::var("WAKFU_ECOLOGY_NATIVE_TEST_URL")
        .context("Set WAKFU_ECOLOGY_NATIVE_TEST_URL to a read-only native catalog")?
        .parse()?;
    config.options("-c default_transaction_read_only=on");
    if let Ok(path) = std::env::var("WAKFU_DATABASE_PASSWORD_FILE") {
        config.password(std::fs::read_to_string(path)?.trim());
    }
    let pool = Pool::builder(Manager::new(config, NoTls))
        .max_size(4)
        .build()?;
    let revision = std::env::var("WAKFU_CATALOG_REVISION")?;
    let generation = std::env::var("WAKFU_COMPILED_CATALOG_GENERATION")?;
    Ok(Context {
        db: pool.clone(),
        catalog: crate::catalog::Catalog::new(pool, revision, Some(generation)),
    })
}

#[tokio::test]
#[ignore = "Requires pinned read-only native catalog environment"]
async fn all_configured_native_habitats_have_two_way_walkable_geometry() -> Result<()> {
    let ctx = native_context().await?;
    let catalog = ctx
        .catalog
        .document("initial-monster-population.json")
        .await?;
    let plans = parse_plans(&catalog)?;
    assert_eq!(plans.len(), 93);
    assert_eq!(plans.iter().map(|p| p.members.len()).sum::<usize>(), 186);
    let cold = std::time::Instant::now();
    validate_configured(&ctx, &plans, &HashSet::new()).await?;
    let cold = cold.elapsed();
    let last = plans.last().context("Missing configured native habitats")?;
    assert!(
        ctx.catalog
            .immutable_validation_cached(&format!(
                "initial-population:geometry:{}",
                identity::digest(&last.value)?
            ))
            .await?
    );
    let warm = std::time::Instant::now();
    validate_configured(&ctx, &plans, &HashSet::new()).await?;
    println!(
        "native population validation cold={cold:?} warm={:?}",
        warm.elapsed()
    );
    Ok(())
}

#[tokio::test]
#[ignore = "Requires pinned read-only native catalog environment"]
async fn completed_markers_skip_geometry_but_unfinished_habitats_fail_closed() -> Result<()> {
    let ctx = native_context().await?;
    let mut catalog = ctx
        .catalog
        .document("initial-monster-population.json")
        .await?;
    catalog["plans"].as_array_mut().unwrap().truncate(1);
    catalog["plans"][0]["members"][0]["x"] = json!(i32::MAX);
    let plans = parse_plans(&catalog)?;
    let completed = HashSet::from([plans[0].habitat]);
    validate_configured(&ctx, &plans, &completed).await?;
    assert!(validate_configured(&ctx, &plans, &HashSet::new())
        .await
        .is_err());
    Ok(())
}

#[tokio::test]
#[ignore = "Requires pinned read-only native catalog environment"]
async fn unfinished_habitat_requires_bidirectional_edge_even_on_valid_native_cell() -> Result<()> {
    let ctx = native_context().await?;
    let mut catalog = ctx
        .catalog
        .document("initial-monster-population.json")
        .await?;
    catalog["plans"].as_array_mut().unwrap().truncate(1);
    let original = parse_plans(&catalog)?;
    validate_configured(&ctx, &original, &HashSet::new()).await?;
    // Both members still have a valid native profile, walkable cell and region.
    // A self-pair cannot satisfy the two directional walking edge requirement.
    catalog["plans"][0]["members"][1] = catalog["plans"][0]["members"][0].clone();
    let plans = parse_plans(&catalog)?;
    let error = validate_configured(&ctx, &plans, &HashSet::new())
        .await
        .unwrap_err();
    assert!(error.to_string().contains("bidirectional"), "{error:#}");
    Ok(())
}

#[tokio::test]
#[ignore = "Requires dedicated test DB and pinned read-only native catalog"]
async fn native_preparation_enforces_policy_family_capacity_and_live_occupancy() -> Result<()> {
    use deadpool_postgres::{Manager, Pool};
    use tokio_postgres::{Config, NoTls};
    let mut ctx = native_context().await?;
    let mut config: Config = std::env::var("WAKFU_POSTGRES_TEST_URL")?.parse()?;
    let database = config
        .get_dbname()
        .context("Explicit test database required")?;
    ensure!(
        database.contains("test") && !matches!(database, "wakemu" | "wakemu_runtime"),
        "Refusing runtime database"
    );
    if let Ok(path) = std::env::var("WAKFU_DATABASE_PASSWORD_FILE") {
        config.password(std::fs::read_to_string(path)?.trim());
    }
    let (admin, connection) = config.connect(NoTls).await?;
    tokio::spawn(async move {
        let _ = connection.await;
    });
    let nanos = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)?
        .as_nanos();
    let schema = format!("rust_population_contract_{}_{}", std::process::id(), nanos);
    admin
        .batch_execute(&format!("CREATE SCHEMA {schema}"))
        .await?;
    config.options(format!("-c search_path={schema}"));
    let pool = Pool::builder(Manager::new(config, NoTls))
        .max_size(4)
        .build()?;
    ctx.db = pool.clone();
    let result: Result<()> = async {
        let db = pool.get().await?;
        db.batch_execute(
            "CREATE TABLE settings(name text PRIMARY KEY,value jsonb NOT NULL); \
             CREATE TABLE monster_initial_population(map_id integer,instance_id bigint,region_id integer); \
             CREATE TABLE combat_groups(map_id integer,instance_id bigint,group_id bigint,status text,members jsonb); \
             CREATE TABLE planted_resources(resource_uid bigint,map_id integer,instance_id bigint,x integer,y integer,z smallint,resource_reference integer,stage smallint); \
             CREATE TABLE environmental_owned_groups(map_id integer,world_instance_id bigint,group_id bigint,retired_at_ms bigint); \
             CREATE TABLE objectives_public_hunts(map_id integer,group_id bigint); \
             CREATE TABLE developer_item_test_groups(map_id integer,instance_id bigint,group_id bigint); \
             INSERT INTO settings VALUES('monster_initial_population','{\"enabled\":true,\"version\":1,\"members_per_zone\":2}');"
        ).await?;
        let catalog = ctx.catalog.document("initial-monster-population.json").await?;
        let plans = parse_plans(&catalog)?;
        let plan = &plans[0];
        let (map, instance, region_id) = plan.habitat;
        let regions = native_regions(&ctx).await?;
        let region = regions.get(&(map, region_id)).context("Missing fixture native region")?;
        assert!(prepare_zone(&ctx, plan, region).await?.is_some());

        db.execute("UPDATE settings SET value=jsonb_set(value,'{enabled}','false')", &[]).await?;
        assert!(prepare_zone(&ctx, plan, region).await?.is_none());
        db.execute("UPDATE settings SET value=jsonb_set(value,'{enabled}','true')", &[]).await?;
        db.execute("UPDATE settings SET value=jsonb_set(value,'{members_per_zone}','1')", &[]).await?;
        assert!(prepare_zone(&ctx, plan, region).await.is_err());
        db.execute("UPDATE settings SET value=jsonb_set(value,'{members_per_zone}','2')", &[]).await?;

        let mut foreign = region.clone();
        foreign["monster_families"] = json!([{"family_id":i64::MAX}]);
        assert!(prepare_zone(&ctx, plan, &foreign).await.unwrap_err().to_string().contains("foreign family"));
        let mut full = region.clone();
        full["monster_capacity"] = json!(1);
        assert!(prepare_zone(&ctx, plan, &full).await.unwrap_err().to_string().contains("regional capacity"));

        let member = &plan.members[0];
        let (x, y, z) = member.point;
        let roster = json!([{"id":-123,"ref":member.reference,"x":x,"y":y,"z":z}]);
        db.execute("INSERT INTO combat_groups VALUES($1,$2,123,'available',$3)", &[&map,&instance,&roster]).await?;
        assert!(prepare_zone(&ctx, plan, region).await.unwrap_err().to_string().contains("occupied"));
        db.execute("UPDATE combat_groups SET status='defeated'", &[]).await?;
        assert!(prepare_zone(&ctx, plan, region).await?.is_some());
        db.execute("UPDATE combat_groups SET status='available',members=jsonb_set(members,'{0,x}','2147483647')", &[]).await?;
        assert!(prepare_zone(&ctx, plan, region).await.unwrap_err().to_string().contains("unresolved native regions"));
        db.execute("DELETE FROM combat_groups", &[]).await?;

        db.execute("INSERT INTO planted_resources VALUES(1,$1,$2,$3,$4,$5,60,0)", &[&map,&instance,&x,&y,&z]).await?;
        assert!(prepare_zone(&ctx, plan, region).await.unwrap_err().to_string().contains("occupied"));
        db.execute("DELETE FROM planted_resources", &[]).await?;
        db.execute("INSERT INTO monster_initial_population VALUES($1,$2,$3)", &[&map,&instance,&region_id]).await?;
        assert!(prepare_zone(&ctx, plan, region).await?.is_none());
        Ok(())
    }.await;
    pool.close();
    admin
        .batch_execute(&format!("DROP SCHEMA {schema} CASCADE"))
        .await?;
    result
}

#[tokio::test]
#[ignore = "Requires pinned read-only native catalog environment"]
async fn constructor_proof_rejects_changed_reference_and_stays_catalog_local() -> Result<()> {
    let ctx = native_context().await?;
    let mut catalog = ctx
        .catalog
        .document("initial-monster-population.json")
        .await?;
    catalog["plans"].as_array_mut().unwrap().truncate(1);
    let plans = parse_plans(&catalog)?;
    let completed = HashSet::from([plans[0].habitat]);
    validate_configured(&ctx, &plans, &completed).await?;
    let member = &plans[0].members[0];
    let key = format!(
        "initial-population:constructor:{}:{}",
        member.reference, member.level
    );
    assert!(ctx.catalog.immutable_validation_cached(&key).await?);
    let other = native_context().await?;
    assert!(!other.catalog.immutable_validation_cached(&key).await?);
    catalog["plans"][0]["members"][0]["reference"] = json!(i64::MAX);
    let changed = parse_plans(&catalog)?;
    assert!(validate_configured(&ctx, &changed, &completed)
        .await
        .is_err());
    let invalid = format!(
        "initial-population:constructor:{}:{}",
        i64::MAX,
        member.level
    );
    assert!(!ctx.catalog.immutable_validation_cached(&invalid).await?);
    Ok(())
}

#[test]
fn compact_geometry_preserves_signed_coordinates_and_rejects_invalid_shapes() {
    let value = json!({"map_id":527,"cells":[[-163,-125,-4]],
        "edges":[[[-163,-125,-4],[-162,-125,-4]]],"unrelated_header":{"large":"ignored"}});
    let geometry: NativeWalkingGeometry = serde_json::from_value(value.clone()).unwrap();
    assert_eq!(geometry.cells, [(-163, -125, -4)]);
    assert_eq!(geometry.edges, [((-163, -125, -4), (-162, -125, -4))]);
    for (pointer, invalid) in [
        ("/cells/0", json!([-163, -125])),
        ("/cells/0/2", json!(32768)),
        ("/edges/0", json!([[-163, -125, -4]])),
        ("/edges/0/0/0", json!(true)),
    ] {
        let mut value = value.clone();
        *value.pointer_mut(pointer).unwrap() = invalid;
        assert!(
            serde_json::from_value::<NativeWalkingGeometry>(value).is_err(),
            "accepted {pointer}"
        );
    }
}
