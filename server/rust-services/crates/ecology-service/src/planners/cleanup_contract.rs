//! Native cleanup planner coverage; all writes use an isolated test schema.
use super::*;
use anyhow::{ensure, Context as _};
use deadpool_postgres::Pool;
use tokio_postgres::{Config, NoTls};

fn config(name: &str) -> Result<Config> {
    let mut config: Config = std::env::var(name).context(name.to_owned())?.parse()?;
    if let Ok(path) = std::env::var("WAKFU_DATABASE_PASSWORD_FILE") {
        config.password(std::fs::read_to_string(path)?.trim());
    }
    Ok(config)
}
fn pool(config: Config) -> Result<Pool> {
    Ok(
        Pool::builder(deadpool_postgres::Manager::new(config, NoTls))
            .max_size(4)
            .build()?,
    )
}

#[tokio::test]
async fn native_cleanup_certifies_only_unassigned_surfaces_and_respects_cadence_and_ownership(
) -> Result<()> {
    let mut test = config("WAKFU_POSTGRES_TEST_URL")?;
    ensure!(
        test.get_dbname().is_some_and(
            |name| name.contains("test") && !matches!(name, "wakemu" | "wakemu_runtime")
        ),
        "Dedicated test database required"
    );
    let admin = pool(test.clone())?;
    let schema = format!(
        "cleanup_contract_{}_{}",
        std::process::id(),
        std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)?
            .as_nanos()
    );
    admin
        .get()
        .await?
        .batch_execute(&format!("CREATE SCHEMA {schema}"))
        .await?;
    test.options(format!("-c search_path={schema}"));
    let writes = pool(test)?;
    let db = writes.get().await?;
    db.batch_execute("CREATE TABLE combat_groups(map_id integer,instance_id bigint,group_id bigint,status text,members jsonb);CREATE TABLE environmental_owned_groups(map_id integer,world_instance_id bigint,group_id bigint);CREATE TABLE developer_item_test_groups(map_id integer,instance_id bigint,group_id bigint)").await?;
    let mut native = config("WAKFU_NATIVE_CATALOG_TEST_URL")?;
    native.options("-c default_transaction_read_only=on");
    let reads = pool(native)?;
    ensure!(
        reads
            .get()
            .await?
            .query_one("SHOW default_transaction_read_only", &[])
            .await?
            .get::<_, String>(0)
            == "on",
        "Native catalog must be read-only"
    );
    let catalog = crate::catalog::Catalog::new(
        reads,
        std::env::var("WAKFU_CATALOG_REVISION")?,
        Some(std::env::var("WAKFU_COMPILED_CATALOG_GENERATION")?),
    );
    catalog.verify().await?;
    let ctx = crate::Context {
        db: writes.clone(),
        catalog,
    };
    assert_ne!(ctx.catalog.surface_region(527, -162, -125, -4).await?, -1);
    assert_eq!(ctx.catalog.surface_region(527, -163, -125, -4).await?, -1);
    let roster = json!([
        {"id":-8101,"ref":6,"x":-162,"y":-125,"z":-4},
        {"id":-8102,"ref":6,"x":-163,"y":-125,"z":-4},
        {"id":-8103,"ref":6,"x":30000,"y":30000,"z":0}]);
    let bad = json!([{ "id":-8104,"ref":6,"x":-163,"y":-125,"z":-4}]);
    for (instance, group, status, members) in [
        (0i64, 8101i64, "available", &roster),
        (17, 8102, "available", &bad),
        (0, 8103, "fighting", &bad),
        (0, 8104, "available", &bad),
        (0, 8105, "available", &bad),
    ] {
        db.execute(
            "INSERT INTO combat_groups VALUES(527,$1,$2,$3,$4)",
            &[&instance, &group, &status, members],
        )
        .await?;
    }
    db.batch_execute("INSERT INTO environmental_owned_groups VALUES(527,0,8104);INSERT INTO developer_item_test_groups VALUES(527,0,8105)").await?;
    drop(db);
    let mut snapshot =
        json!({"world_epoch":schema,"planning_tick":1,"players":[],"excluded_ids":[-8102]});
    *SCAN.get_or_init(|| Mutex::new(None)).lock().unwrap() = None;
    assert!(prepare_cleanup(&ctx, &snapshot, 16).await?.is_empty());
    *SCAN.get().unwrap().lock().unwrap() = None;
    snapshot["excluded_ids"] = json!([]);
    let first = prepare_cleanup(&ctx, &snapshot, 16).await?;
    assert_eq!(first.len(), 1);
    assert_eq!(first[0]["group_id"], 8101);
    assert_eq!(first[0]["actor_ids"], json!([-8102]));
    assert_eq!(first[0]["expected_members"], roster);
    assert!(prepare_cleanup(&ctx, &snapshot, 16).await?.is_empty());
    SCAN.get().unwrap().lock().unwrap().as_mut().unwrap().at =
        Instant::now() - Duration::from_secs(60);
    assert_eq!(prepare_cleanup(&ctx, &snapshot, 16).await?, first);
    *SCAN.get().unwrap().lock().unwrap() = None;
    drop(ctx);
    drop(writes);
    admin
        .get()
        .await?
        .batch_execute(&format!("DROP SCHEMA {schema} CASCADE"))
        .await?;
    Ok(())
}
