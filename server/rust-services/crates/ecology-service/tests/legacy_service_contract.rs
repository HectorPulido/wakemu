//! Contracts migrated from the retired Python ecology worker's test harnesses.
//!
//! SQL cases exercise the production Rust repository in a private schema of an
//! explicitly named test database. They never connect to a gameplay database.
//! The worker's scheduling cases live in worker_tests.rs alongside its private
//! scheduling seams. No Python worker or executable oracle is retained.
use std::collections::HashSet;
use std::sync::Arc;
use std::time::{Duration, Instant};

use anyhow::{ensure, Context as _, Result};
use axum::body::Body;
use axum::http::{header, Request, StatusCode};
use axum::response::IntoResponse;
use axum::routing::{get, post};
use axum::Router;
use deadpool_postgres::Pool;
use http_body_util::BodyExt;
use serde_json::{json, Value};
use tokio::sync::{mpsc, oneshot};
use tokio_postgres::{Client, Config, NoTls};
use tower::ServiceExt;
use wakemu_ecology::catalog::Catalog;
use wakemu_ecology::identity;
use wakemu_ecology::protocol::{self, proposal, MAX_BODY_BYTES, MAX_RESPONSE_BYTES};
use wakemu_ecology::repository::{Repository, OWNER_LOCK};
use wakemu_ecology::world_client::WorldClient;
use wakemu_ecology::{http, worker::Worker, Context};

struct Fixture {
    admin: Client,
    schema: String,
    pool: Pool,
}

impl Fixture {
    async fn create() -> Result<Self> {
        let dsn = std::env::var("WAKFU_POSTGRES_TEST_URL")
            .context("Set WAKFU_POSTGRES_TEST_URL to a dedicated test database")?;
        let mut config: Config = dsn.parse()?;
        let database = config
            .get_dbname()
            .context("Explicit test database required")?;
        ensure!(
            database.contains("test") && !matches!(database, "wakemu" | "wakemu_runtime"),
            "Refusing a runtime database"
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
        let schema = format!("rust_legacy_ecology_{}_{}", std::process::id(), nanos);
        admin
            .batch_execute(&format!("CREATE SCHEMA {schema}"))
            .await?;
        config.options(format!("-c search_path={schema}"));
        config.application_name(&schema);
        let pool = Pool::builder(deadpool_postgres::Manager::new(config, NoTls))
            .max_size(8)
            .runtime(deadpool_postgres::Runtime::Tokio1)
            .build()?;
        let client = pool.get().await?;
        client.batch_execute(
            "CREATE TABLE settings(name text PRIMARY KEY,value jsonb NOT NULL); \
             CREATE TABLE planted_resources(resource_uid bigint PRIMARY KEY,map_id integer NOT NULL,instance_id bigint NOT NULL,x integer,y integer,z smallint,resource_reference integer,stage smallint,creation_time bigint); \
             CREATE TABLE combat_groups(map_id integer NOT NULL,instance_id bigint NOT NULL,group_id bigint,members jsonb NOT NULL,status text); \
             CREATE TABLE territory_weather(map_id integer NOT NULL,instance_id bigint NOT NULL,region_id integer NOT NULL,weather text,revision bigint NOT NULL DEFAULT 1,native_payload bytea,updated_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP); \
             CREATE TABLE resource_harvest_occupations(resource_uid bigint); \
             CREATE TABLE environmental_owned_groups(map_id integer,world_instance_id bigint,group_id bigint,retired_at_ms bigint); \
             CREATE TABLE objectives_public_hunts(map_id integer,group_id bigint); \
             CREATE TABLE developer_item_test_groups(map_id integer,instance_id bigint,group_id bigint)"
        ).await?;
        // Use the real queue and dirty-trigger migrations, including their exact
        // transactional trigger behavior, rather than inventing a test queue.
        client
            .batch_execute(include_str!(concat!(
                env!("CARGO_MANIFEST_DIR"),
                "/../../../migrations/104_ecology_service.sql"
            )))
            .await?;
        client
            .batch_execute(include_str!(concat!(
                env!("CARGO_MANIFEST_DIR"),
                "/../../../migrations/110_ecology_delivery_recovery.sql"
            )))
            .await?;
        client
            .batch_execute(include_str!(concat!(
                env!("CARGO_MANIFEST_DIR"),
                "/../../../migrations/123_regional_bonus_proposals.sql"
            )))
            .await?;
        drop(client);
        Ok(Self {
            admin,
            schema,
            pool,
        })
    }

    fn repository(&self, attempts: u32) -> Result<Repository> {
        Repository::new(self.pool.clone(), attempts)
    }

    async fn document(&self, id: &str) -> Result<Value> {
        Ok(self.pool.get().await?.query_one(
            "SELECT jsonb_build_object('id',id,'payload',payload,'attempts',attempts,'last_error_code',last_error_code,'delivered',delivered_at IS NOT NULL,'delayed',next_attempt_at>CURRENT_TIMESTAMP) AS document FROM ecology_service_proposals WHERE id=$1",
            &[&id],
        ).await?.get("document"))
    }

    async fn cleanup(self) -> Result<()> {
        self.pool.close();
        self.admin
            .batch_execute(&format!("DROP SCHEMA {} CASCADE", self.schema))
            .await?;
        Ok(())
    }

    fn context(&self) -> Arc<Context> {
        Arc::new(Context {
            db: self.pool.clone(),
            catalog: Catalog::new(self.pool.clone(), "a".repeat(64), None),
        })
    }
}

fn id(row: &Value) -> &str {
    row["id"].as_str().expect("proposal ID")
}
fn growth(uid: i64, reference: i64) -> Value {
    json!({"kind":"resource_growth","expected":{"resource_uid":uid,"stage":1},"member":{"id":-uid,"ref":reference},"draw":0.1})
}
fn wander() -> Result<Value> {
    proposal(
        "mobs",
        json!({"kind":"wander","world_epoch":"boot","scope":[527,0],"group_id":1,"expected_members":[]}),
        "boot",
    )
}
async fn ack(repository: &Repository, id: &str, status: &str) -> Result<()> {
    repository
        .acknowledge(&[json!({"id":id,"status":status})])
        .await
}

#[tokio::test]
#[ignore = "Requires dedicated WAKFU_POSTGRES_TEST_URL; run SQL cases serially"]
async fn exhausted_semantic_decision_survives_history_pruning_and_cannot_resurrect() -> Result<()> {
    let f = Fixture::create().await?;
    let r = f.repository(3)?;
    let payload = growth(991, 10);
    r.save(&[proposal("plants", payload.clone(), "boot")?], &[])
        .await?;
    let durable = r.pending().await?[0]["id"].as_str().unwrap().to_owned();
    for _ in 0..3 {
        ack(&r, &durable, "retry").await?;
    }
    let db = f.pool.get().await?;
    db.execute("UPDATE ecology_service_proposals SET delivered_at=CURRENT_TIMESTAMP-interval '8 days' WHERE id=$1", &[&durable]).await?;
    db.execute("INSERT INTO ecology_service_proposals(id,domain,payload,world_epoch,delivered_at) SELECT 'history-'||i,'weather','{}'::jsonb,'boot',CURRENT_TIMESTAMP FROM generate_series(1,4400) AS i", &[]).await?;
    drop(db);
    r.acknowledge(&[]).await?;
    let mut fresh = payload;
    fresh["member"] = json!({"id":-992});
    r.save(&[proposal("plants", fresh, "boot")?], &[]).await?;
    let saved = f.document(&durable).await?;
    assert_eq!(saved["attempts"], 3);
    assert_eq!(saved["last_error_code"], "retry_exhausted");
    let ordinary: i64 = f
        .pool
        .get()
        .await?
        .query_one(
            "SELECT count(*) FROM ecology_service_proposals WHERE domain='weather'",
            &[],
        )
        .await?
        .get(0);
    assert!(ordinary < 4400);
    assert_eq!(r.pending_count().await?, 0);
    f.cleanup().await
}

#[tokio::test]
#[ignore = "Requires dedicated WAKFU_POSTGRES_TEST_URL"]
async fn late_stale_ack_cannot_reclassify_successful_semantic_decision() -> Result<()> {
    let f = Fixture::create().await?;
    let r = f.repository(3)?;
    let row = proposal("plants", growth(991, 10), "boot")?;
    r.save(&[row.clone()], &[]).await?;
    let durable = id(&r.pending().await?[0]).to_owned();
    ack(&r, &durable, "applied").await?;
    ack(&r, &durable, "stale").await?;
    r.save(&[row], &[]).await?;
    let saved = f.document(&durable).await?;
    assert_eq!(saved["attempts"], 1);
    assert!(saved["last_error_code"].is_null());
    assert_eq!(r.pending_count().await?, 0);
    f.cleanup().await
}

#[tokio::test]
#[ignore = "Requires dedicated WAKFU_POSTGRES_TEST_URL"]
async fn successful_random_decision_is_not_rearmed_by_fresh_random_output() -> Result<()> {
    let f = Fixture::create().await?;
    let r = f.repository(3)?;
    let original = growth(99, 10);
    r.save(&[proposal("plants", original.clone(), "boot")?], &[])
        .await?;
    let durable = id(&r.pending().await?[0]).to_owned();
    ack(&r, &durable, "applied").await?;
    let mut fresh = growth(99, 11);
    fresh["member"]["id"] = json!(-100);
    fresh["draw"] = json!(0.9);
    r.save(&[proposal("plants", fresh, "boot")?], &[]).await?;
    let saved = f.document(&durable).await?;
    assert_eq!(r.pending_count().await?, 0);
    assert_eq!(saved["payload"]["member"], original["member"]);
    assert_eq!(saved["attempts"], 1);
    f.cleanup().await
}

#[tokio::test]
#[ignore = "Requires dedicated WAKFU_POSTGRES_TEST_URL"]
async fn stale_reproduction_refreshes_roster_without_rerolling_or_resetting_retry_limit(
) -> Result<()> {
    let f = Fixture::create().await?;
    let r = f.repository(3)?;
    let original = json!({"kind":"reproduction","world_epoch":"boot","scope":[527,0],"ticket":{"map_id":527,"instance_id":0,"group_id":7,"monster_id":-71,"reference":10,"cycle":3},"expected_members":[{"id":-71,"ref":10}],"draw":0.2,"group_draw":0.3,"destination":[1,2,0],"child":{"id":-900,"ref":11,"x":1,"y":2,"z":0}});
    r.save(&[proposal("mobs", original.clone(), "boot")?], &[])
        .await?;
    let durable = id(&r.pending().await?[0]).to_owned();
    for attempt in 1..=3 {
        ack(&r, &durable, "stale").await?;
        if attempt == 1 {
            let mut same = original.clone();
            same["draw"] = json!(0.97);
            r.save(&[proposal("mobs", same, "boot")?], &[]).await?;
            assert_eq!(r.pending_count().await?, 0);
        }
        let mut fresh = original.clone();
        fresh["expected_members"] = json!([{"id":-71,"ref":10},{"id":-72-attempt,"ref":10}]);
        fresh["draw"] = json!(0.99);
        fresh["group_draw"] = json!(0.98);
        fresh["destination"] = json!([3, 4, 0]);
        fresh["child"] = json!({"id":-999,"ref":12,"x":3,"y":4,"z":0});
        r.save(&[proposal("mobs", fresh.clone(), "boot")?], &[])
            .await?;
        let saved = f.document(&durable).await?;
        assert_eq!(saved["attempts"], attempt);
        assert_eq!(saved["payload"]["draw"], 0.2);
        assert_eq!(saved["payload"]["group_draw"], 0.3);
        assert_eq!(saved["payload"]["child"]["id"], -900);
        assert_eq!(saved["payload"]["child"]["ref"], 11);
        if attempt < 3 {
            assert_eq!(saved["delivered"], false);
            assert_eq!(
                saved["payload"]["expected_members"],
                fresh["expected_members"]
            );
            assert_eq!(saved["payload"]["destination"], json!([3, 4, 0]));
            assert_eq!(saved["payload"]["child"]["x"], 3);
        } else {
            assert_eq!(saved["delivered"], true);
        }
    }
    assert_eq!(r.pending_count().await?, 0);
    f.cleanup().await
}

#[tokio::test]
#[ignore = "Requires dedicated WAKFU_POSTGRES_TEST_URL"]
async fn maximum_population_repeated_random_cycles_keep_one_durable_entry_each() -> Result<()> {
    let f = Fixture::create().await?;
    let r = f.repository(3)?;
    // Three distinct observations at the original maximum 500-member workload
    // prove coalescing without repeating the same assertion for 100 ticks.
    for tick in 0..3 {
        let rows=(0..500).map(|i|proposal("mobs",json!({"kind":"maturation","world_epoch":"load","scope":[527,0],"ticket":{"map_id":527,"instance_id":0,"group_id":i/5,"monster_id":-i-1,"reference":10,"cycle":7,"due_at":1000},"expected_members":[{"id":-i-1,"ref":10}],"draw":f64::from(tick*500+i)/1500.0,"grown":{"ref":11+tick%2}}),"load")).collect::<Result<Vec<_>>>()?;
        r.save(&rows, &[]).await?;
    }
    assert_eq!(r.pending_count().await?, 500);
    let row=f.pool.get().await?.query_one("SELECT count(*) AS total,count(DISTINCT payload->'ticket'->>'group_id') AS groups FROM ecology_service_proposals",&[]).await?;
    assert_eq!(row.get::<_, i64>("total"), 500);
    assert_eq!(row.get::<_, i64>("groups"), 100);
    f.cleanup().await
}

#[tokio::test]
#[ignore = "Requires dedicated WAKFU_POSTGRES_TEST_URL"]
async fn default_three_failures_exhaust_once_and_replanning_cannot_resurrect() -> Result<()> {
    let f = Fixture::create().await?;
    let r = f.repository(3)?;
    assert_eq!(r.max_attempts(), 3);
    let row = wander()?;
    r.save(&[row.clone()], &[]).await?;
    for attempt in 0..3 {
        ack(&r, id(&row), "retry").await?;
        assert_eq!(r.pending_count().await?, if attempt < 2 { 1 } else { 0 });
    }
    r.save(&[row.clone()], &[]).await?;
    let saved = f.document(id(&row)).await?;
    assert_eq!(r.pending_count().await?, 0);
    assert_eq!(saved["attempts"], 3);
    assert_eq!(saved["last_error_code"], "retry_exhausted");
    f.cleanup().await
}

#[tokio::test]
#[ignore = "Requires dedicated WAKFU_POSTGRES_TEST_URL"]
async fn pending_flora_growth_does_not_consume_reserved_monster_birth_capacity() -> Result<()> {
    let f = Fixture::create().await?;
    let r = f.repository(3)?;
    let flora=(0..16).map(|uid|proposal("plants",json!({"kind":"resource_growth","expected":{"resource_uid":uid,"stage":1},"resource":{"resource_uid":uid},"member":null}),"boot")).collect::<Result<Vec<_>>>()?;
    r.save(&flora, &[]).await?;
    assert_eq!(r.growth_pending_count().await?, 0);
    r.save(&[proposal("plants", growth(99, 10), "boot")?], &[])
        .await?;
    assert_eq!(r.growth_pending_count().await?, 1);
    assert_eq!(r.pending_count().await?, 17);
    f.cleanup().await
}

#[tokio::test]
#[ignore = "Requires dedicated WAKFU_POSTGRES_TEST_URL"]
async fn seed_growth_precedes_ambient_and_deduplicates_random_offspring() -> Result<()> {
    let f = Fixture::create().await?;
    let r = f.repository(3)?;
    let ambient = proposal("mobs", json!({"kind":"ambient_test"}), "boot")?;
    let first = proposal("plants", growth(7, 2), "boot")?;
    let mut other = growth(7, 39);
    other["member"]["id"] = json!(-8);
    r.save(
        &[
            ambient.clone(),
            first.clone(),
            proposal("plants", other, "boot")?,
        ],
        &[],
    )
    .await?;
    let rows = r.pending().await?;
    let durable = identity::proposal_identity(&first)?.2.unwrap();
    assert_eq!(rows.len(), 2);
    assert_eq!(rows[0]["id"], durable);
    assert_eq!(rows[1]["id"], ambient["id"]);
    assert_eq!(r.growth_pending_count().await?, 1);
    assert_eq!(rows[0]["payload"]["member"]["ref"], 2);
    f.cleanup().await
}

#[tokio::test]
#[ignore = "Requires dedicated WAKFU_POSTGRES_TEST_URL"]
async fn reserved_player_proposals_are_read_before_older_background_backlog() -> Result<()> {
    let f = Fixture::create().await?;
    let r = f.repository(3)?;
    let background = wander()?;
    r.save(&[background.clone()], &[]).await?;
    let player = proposal(
        "plants",
        json!({"kind":"planting_begin","intent_id":71}),
        "boot",
    )?;
    let rejection = proposal(
        "plants",
        json!({"kind":"planting_rejected","intent_id":72}),
        "boot",
    )?;
    r.save(&[player.clone(), rejection.clone()], &[]).await?;
    let rows = r.pending().await?;
    let first = rows[..2]
        .iter()
        .map(|r| id(r).to_owned())
        .collect::<HashSet<_>>();
    assert_eq!(
        first,
        HashSet::from([
            identity::proposal_identity(&player)?.2.unwrap(),
            identity::proposal_identity(&rejection)?.2.unwrap()
        ])
    );
    assert_eq!(rows[2]["id"], background["id"]);
    f.cleanup().await
}

#[tokio::test]
#[ignore = "Requires dedicated WAKFU_POSTGRES_TEST_URL"]
async fn background_deferrals_never_consume_retry_budget_or_drop_work() -> Result<()> {
    let f = Fixture::create().await?;
    let r = f.repository(2)?;
    let row = wander()?;
    r.save(&[row.clone()], &[]).await?;
    for _ in 0..8 {
        ack(&r, id(&row), "deferred").await?;
    }
    let saved = f.document(id(&row)).await?;
    assert_eq!(r.pending_count().await?, 1);
    assert_eq!(saved["attempts"], 0);
    assert_eq!(saved["delivered"], false);
    assert_eq!(saved["delayed"], true);
    ack(&r, id(&row), "applied").await?;
    assert_eq!(r.pending_count().await?, 0);
    f.cleanup().await
}

#[tokio::test]
#[ignore = "Requires dedicated WAKFU_POSTGRES_TEST_URL"]
async fn retry_exhaustion_persists_without_resurrection_and_final_attempt_can_succeed() -> Result<()>
{
    let f = Fixture::create().await?;
    let r = f.repository(2)?;
    let rows = (701..=703)
        .map(|uid| proposal("plants", json!({"uid":uid}), "boot"))
        .collect::<Result<Vec<_>>>()?;
    r.save(&rows, &[]).await?;
    for row in &rows[..2] {
        ack(&r, id(row), "retry").await?;
    }
    ack(&r, id(&rows[0]), "retry").await?;
    ack(&r, id(&rows[1]), "applied").await?;
    f.pool
        .get()
        .await?
        .execute(
            "UPDATE ecology_service_proposals SET attempts=85 WHERE id=$1",
            &[&id(&rows[2])],
        )
        .await?;
    let reopened = f.repository(2)?;
    assert_eq!(reopened.expire_exhausted().await?, 1);
    assert_eq!(reopened.pending_count().await?, 0);
    reopened.save(&rows, &[]).await?;
    assert_eq!(reopened.pending_count().await?, 0);
    assert_eq!(
        reopened.retry_stats().await?,
        json!({"attempts":89,"exhausted":2})
    );
    let success = f.document(id(&rows[1])).await?;
    assert_eq!(success["attempts"], 2);
    assert!(success["last_error_code"].is_null());
    assert_eq!(success["delivered"], true);
    f.cleanup().await
}

#[tokio::test]
#[ignore = "Requires dedicated WAKFU_POSTGRES_TEST_URL"]
async fn dirty_scope_is_transactional_and_new_revision_survives_ack() -> Result<()> {
    let f = Fixture::create().await?;
    let r = f.repository(3)?;
    f.pool
        .get()
        .await?
        .execute(
            "INSERT INTO planted_resources VALUES(991,527,0,1,2,0,1,0,0)",
            &[],
        )
        .await?;
    let first = r
        .dirty()
        .await?
        .into_iter()
        .find(|v| v["map_id"] == 527)
        .unwrap();
    f.pool
        .get()
        .await?
        .execute(
            "UPDATE planted_resources SET stage=1 WHERE resource_uid=991",
            &[],
        )
        .await?;
    r.save(&[], &[first.clone()]).await?;
    let second = r
        .dirty()
        .await?
        .into_iter()
        .find(|v| v["map_id"] == 527)
        .unwrap();
    assert!(second["revision"].as_i64() > first["revision"].as_i64());
    let mut db = f.pool.get().await?;
    let tx = db.transaction().await?;
    tx.execute(
        "INSERT INTO planted_resources VALUES(992,528,0,1,2,0,1,0,0)",
        &[],
    )
    .await?;
    tx.rollback().await?;
    drop(db);
    assert!(!r.dirty().await?.iter().any(|v| v["map_id"] == 528));
    f.cleanup().await
}

#[tokio::test]
#[ignore = "Requires dedicated WAKFU_POSTGRES_TEST_URL"]
async fn pending_proposal_survives_reopen_duplicate_and_stale_epoch_replan() -> Result<()> {
    let f = Fixture::create().await?;
    let r = f.repository(3)?;
    let row = proposal("plants", json!({"uid":991,"revision":1}), "boot-one")?;
    r.save(&[row.clone()], &[]).await?;
    r.save(&[row.clone()], &[]).await?;
    let reopened = f.repository(3)?;
    assert_eq!(reopened.pending().await?, vec![row.clone()]);
    ack(&reopened, id(&row), "stale").await?;
    assert!(reopened.pending().await?.is_empty());
    let mut fresh = row;
    fresh["world_epoch"] = json!("boot-two");
    reopened.save(&[fresh.clone()], &[]).await?;
    assert_eq!(reopened.pending().await?, vec![fresh]);
    f.cleanup().await
}

#[tokio::test]
#[ignore = "Requires dedicated WAKFU_POSTGRES_TEST_URL"]
async fn pause_is_durable_and_retry_rows_do_not_starve_new_work() -> Result<()> {
    let f = Fixture::create().await?;
    let r = f.repository(3)?;
    r.set_enabled(false).await?;
    assert!(!f.repository(3)?.enabled().await?);
    r.set_enabled(true).await?;
    assert!(r.enabled().await?);
    let rows = (0..20)
        .map(|uid| proposal("mobs", json!({"uid":uid}), "boot"))
        .collect::<Result<Vec<_>>>()?;
    r.save(&rows, &[]).await?;
    let first = r.pending().await?;
    assert_eq!(first.len(), 16);
    let before = first
        .iter()
        .map(|v| id(v).to_owned())
        .collect::<HashSet<_>>();
    for row in &first {
        ack(&r, id(row), "retry").await?;
    }
    let second = r
        .pending()
        .await?
        .iter()
        .map(|v| id(v).to_owned())
        .collect::<HashSet<_>>();
    let all = rows
        .iter()
        .map(|v| id(v).to_owned())
        .collect::<HashSet<_>>();
    assert!(all.difference(&before).all(|id| second.contains(id)));
    assert!(before.is_disjoint(&second));
    let delayed = f.document(id(&first[0])).await?;
    assert_eq!(delayed["delayed"], true);
    assert_eq!(delayed["attempts"], 1);
    f.cleanup().await
}

#[tokio::test]
#[ignore = "Requires dedicated WAKFU_POSTGRES_TEST_URL; run serially for advisory lock"]
async fn only_one_worker_session_owns_database_until_owner_closes() -> Result<()> {
    let f = Fixture::create().await?;
    let first = f.repository(3)?;
    let second = f.repository(3)?;
    first.acquire().await?;
    first.assert_owner().await?;
    assert!(second.acquire().await.is_err());
    let pid:i32=f.admin.query_one("SELECT l.pid FROM pg_locks l JOIN pg_stat_activity a ON a.pid=l.pid WHERE l.locktype='advisory' AND l.classid=($1::bigint>>32)::oid AND l.objid=($1::bigint & 4294967295)::oid AND a.datname=current_database() AND a.application_name=$2",&[&OWNER_LOCK,&f.schema]).await?.get(0);
    // Terminate only this test's unique owner session, in its dedicated test DB.
    f.admin
        .execute("SELECT pg_terminate_backend($1)", &[&pid])
        .await?;
    assert!(first.assert_owner().await.is_err());
    assert!(!first.owns_database().await);
    first.acquire().await?;
    assert!(second.acquire().await.is_err());
    first.close().await?;
    second.acquire().await?;
    second.assert_owner().await?;
    second.close().await?;
    f.cleanup().await
}

#[tokio::test]
#[ignore = "Requires dedicated WAKFU_POSTGRES_TEST_URL"]
async fn query_returns_real_weather_and_empty_population_with_snapshot_metadata() -> Result<()> {
    let f = Fixture::create().await?;
    let r = f.repository(3)?;
    f.pool.get().await?.execute("INSERT INTO territory_weather(map_id,instance_id,region_id,weather,native_payload) VALUES(527,0,99,'LIGHT',$1)",&[&vec![0_u8;37]]).await?;
    let catalog = Catalog::new(f.pool.clone(), "a".repeat(64), None);
    let weather = r
        .query(
            &json!({"kind":"weather","map_id":527,"instance_id":0,"region_id":99}),
            &catalog,
        )
        .await?;
    assert_eq!(weather["authoritative"], true);
    assert!(weather["revision"].as_i64().unwrap() > 0);
    assert!(weather["observed_at"].as_str().is_some());
    assert_eq!(weather["data"]["regions"][0]["weather"], "LIGHT");
    let population = r
        .query(
            &json!({"kind":"population","map_id":527,"instance_id":0}),
            &catalog,
        )
        .await?;
    assert_eq!(population["data"]["complete"], true);
    assert_eq!(population["data"]["regions"], json!({}));
    f.cleanup().await
}

#[tokio::test]
#[ignore = "Requires dedicated WAKFU_POSTGRES_TEST_URL"]
async fn completed_retention_is_capped_and_pending_rows_are_never_deleted() -> Result<()> {
    let f = Fixture::create().await?;
    let r = f.repository(3)?;
    let row = proposal("plants", json!({"uid":1}), "boot")?;
    r.save(&[row.clone()], &[]).await?;
    f.pool.get().await?.execute("INSERT INTO ecology_service_proposals(id,domain,payload,world_epoch,delivered_at) SELECT 'archived-'||n,'plants','{}'::jsonb,'boot',CURRENT_TIMESTAMP FROM generate_series(1,4098) n",&[]).await?;
    r.acknowledge(&[]).await?;
    let total: i64 = f
        .pool
        .get()
        .await?
        .query_one(
            "SELECT count(*) FROM ecology_service_proposals WHERE delivered_at IS NOT NULL",
            &[],
        )
        .await?
        .get(0);
    assert_eq!(total, 4096);
    assert_eq!(r.pending().await?, vec![row]);
    f.cleanup().await
}

#[test]
fn proposal_identity_is_stable_across_epoch_and_dictionary_order() -> Result<()> {
    let first = proposal("plants", json!({"revision":1,"uid":7}), "old")?;
    let second = proposal("plants", json!({"uid":7,"revision":1}), "new")?;
    assert_eq!(first["id"], second["id"]);
    assert_ne!(first["world_epoch"], second["world_epoch"]);
    assert_ne!(
        first["id"],
        proposal("plants", json!({"uid":7,"revision":2}), "new")?["id"]
    );
    Ok(())
}

#[test]
fn duplicate_unknown_domain_and_over_budget_proposals_are_rejected() -> Result<()> {
    let row = proposal("plants", json!({}), "boot")?;
    for rows in [
        vec![row.clone(), row.clone()],
        vec![{
            let mut value = row.clone();
            value["domain"] = json!("chat");
            value
        }],
        vec![row; 17],
    ] {
        assert!(
            protocol::validate_proposals(&json!({"schema_version":1,"proposals":rows})).is_err()
        );
    }
    Ok(())
}

#[test]
fn json_bounds_nonfinite_values_and_snapshot_capacity_are_enforced() -> Result<()> {
    assert!(
        protocol::json_bytes(&json!({"data":"x".repeat(MAX_BODY_BYTES)}), MAX_BODY_BYTES).is_err()
    );
    for invalid in [b"NaN".as_slice(), b"Infinity", b"{\"bad\":NaN}"] {
        assert!(protocol::bounded_json(invalid, MAX_BODY_BYTES).is_err());
    }
    assert!(protocol::validate_snapshot(
        &json!({"schema_version":1,"world_epoch":"boot","scopes":vec![json!({});65]})
    )
    .is_err());
    Ok(())
}

#[test]
fn partial_foreign_unknown_and_duplicate_acknowledgements_are_rejected() -> Result<()> {
    let row = proposal("mobs", json!({}), "boot")?;
    for results in [
        json!([]),
        json!([{"id":"other","status":"applied"}]),
        json!([{"id":row["id"],"status":"unknown"}]),
    ] {
        assert!(protocol::validate_results(&[row.clone()], &json!({"results":results})).is_err());
    }
    let other = proposal("mobs", json!({"revision":1}), "boot")?;
    assert!(protocol::validate_results(&[row.clone(),other],&json!({"results":[{"id":row["id"],"status":"applied"},{"id":row["id"],"status":"applied"}]})).is_err());
    Ok(())
}

#[test]
fn population_identity_coalesces_scope_but_preserves_authoritative_version() -> Result<()> {
    let payload = json!({"kind":"initial_population","plan":{"map_id":527,"instance_id":0,"region_id":1},"scope_digest":"a","policy":{},"catalog_revision":7});
    let first = identity::proposal_identity(&proposal("population", payload.clone(), "boot")?)?;
    let mut randomized = payload.clone();
    randomized["plan"]["draw"] = json!(0.9);
    assert_eq!(
        first,
        identity::proposal_identity(&proposal("population", randomized, "boot")?)?
    );
    let mut changed = payload;
    changed["scope_digest"] = json!("b");
    let changed = identity::proposal_identity(&proposal("population", changed, "boot")?)?;
    assert_eq!(first.0, changed.0);
    assert_ne!(first.1, changed.1);
    let first = identity::proposal_identity(&proposal(
        "population",
        json!({"kind":"corpse_expiry","actor_id":-1,"revision":1}),
        "boot",
    )?)?;
    let second = identity::proposal_identity(&proposal(
        "population",
        json!({"kind":"corpse_expiry","actor_id":-1,"revision":2}),
        "boot",
    )?)?;
    assert_eq!(first.0, second.0);
    assert_ne!(first.1, second.1);
    Ok(())
}

#[test]
fn query_fields_and_retry_configuration_remain_bounded() -> Result<()> {
    let valid = json!({"kind":"weather","map_id":527,"instance_id":0});
    for (field, value) in [
        ("command", json!("give")),
        ("map_id", json!(true)),
        ("instance_id", json!(-1)),
        ("region_id", json!(0)),
        ("kind", json!("combat")),
    ] {
        let mut invalid = valid.clone();
        invalid[field] = value;
        assert!(protocol::validate_query(&invalid).is_err());
    }
    let config: Config = "host=127.0.0.1 dbname=unreachable_test".parse()?;
    let pool = Pool::builder(deadpool_postgres::Manager::new(config, NoTls)).build()?;
    assert!(Repository::new(pool.clone(), 0).is_err());
    assert!(Repository::new(pool, 101).is_err());
    Ok(())
}

async fn serve(app: Router) -> Result<(String, oneshot::Sender<()>)> {
    let listener = tokio::net::TcpListener::bind("127.0.0.1:0").await?;
    let address = listener.local_addr()?;
    let (stop, wait) = oneshot::channel();
    tokio::spawn(async move {
        let _ = axum::serve(listener, app)
            .with_graceful_shutdown(async move {
                let _ = wait.await;
            })
            .await;
    });
    Ok((format!("http://{address}"), stop))
}

#[tokio::test]
async fn client_caps_reads_and_passes_credentials_with_a_real_deadline() -> Result<()> {
    let (send, mut seen) = mpsc::channel(1);
    let app = Router::new().route(
        "/internal/ecology/snapshot",
        get(move |headers: axum::http::HeaderMap| {
            let send = send.clone();
            async move {
                send.send(
                    headers
                        .get(header::AUTHORIZATION)
                        .map(|v| v.to_str().unwrap().to_owned()),
                )
                .await
                .unwrap();
                axum::Json(json!({"schema_version":1,"world_epoch":"boot-1","scopes":[]}))
            }
        }),
    );
    let (url, stop) = serve(app).await?;
    let client = WorldClient::new(&url, "private-token".into())?;
    assert_eq!(client.snapshot().await?["world_epoch"], "boot-1");
    assert_eq!(
        seen.recv().await.flatten().as_deref(),
        Some("Bearer private-token")
    );
    let _ = stop.send(());
    let app = Router::new().route(
        "/internal/ecology/snapshot",
        get(|| async { Body::from(vec![b'x'; MAX_RESPONSE_BYTES + 1]).into_response() }),
    );
    let (url, stop) = serve(app).await?;
    assert!(WorldClient::new(&url, "token".into())?
        .snapshot()
        .await
        .is_err());
    let _ = stop.send(());
    let app = Router::new().route(
        "/internal/ecology/snapshot",
        get(|| async {
            tokio::time::sleep(Duration::from_secs(4)).await;
            axum::Json(json!({}))
        }),
    );
    let (url, stop) = serve(app).await?;
    let started = Instant::now();
    assert!(WorldClient::new(&url, "token".into())?
        .snapshot()
        .await
        .is_err());
    assert!(
        started.elapsed() >= Duration::from_millis(1800)
            && started.elapsed() < Duration::from_secs(3)
    );
    let _ = stop.send(());
    Ok(())
}

#[tokio::test]
async fn client_apply_uses_post_and_rejects_partial_response() -> Result<()> {
    let (send, mut seen) = mpsc::channel(1);
    let app = Router::new().route(
        "/internal/ecology/apply",
        post(move |axum::Json(body): axum::Json<Value>| {
            let send = send.clone();
            async move {
                send.send(body).await.unwrap();
                axum::Json(json!({"results":[]}))
            }
        }),
    );
    let (url, stop) = serve(app).await?;
    let row = proposal("plants", json!({"uid":7}), "boot")?;
    let client = WorldClient::new(&url, "token".into())?;
    assert!(client.apply(&[row.clone()]).await.is_err());
    assert_eq!(
        seen.recv().await,
        Some(json!({"schema_version":1,"proposals":[row]}))
    );
    let _ = stop.send(());
    Ok(())
}

#[tokio::test]
#[ignore = "Requires dedicated WAKFU_POSTGRES_TEST_URL"]
async fn health_status_metrics_and_query_require_the_dedicated_credential() -> Result<()> {
    let f = Fixture::create().await?;
    let context = f.context();
    let worker = Arc::new(Worker::new(
        context,
        f.repository(3)?,
        WorldClient::new("http://127.0.0.1:1", "secret".into())?,
        Duration::from_secs(1),
    )?);
    let app = http::router(worker, "secret".into());
    for endpoint in ["/health", "/status", "/metrics", "/query"] {
        let response = app
            .clone()
            .oneshot(
                Request::builder()
                    .uri(endpoint)
                    .header(header::AUTHORIZATION, "Bearer wrong")
                    .body(Body::empty())?,
            )
            .await?;
        assert_eq!(response.status(), StatusCode::UNAUTHORIZED);
        assert_eq!(
            response.into_body().collect().await?.to_bytes(),
            "{\"error\":\"Unauthorized\"}"
        );
    }
    drop(app);
    f.cleanup().await
}

#[tokio::test]
#[ignore = "Requires dedicated WAKFU_POSTGRES_TEST_URL"]
async fn pause_persists_rejects_oversize_and_query_uses_authoritative_post() -> Result<()> {
    let f = Fixture::create().await?;
    let context = f.context();
    let worker = Arc::new(Worker::new(
        context,
        f.repository(3)?,
        WorldClient::new("http://127.0.0.1:1", "secret".into())?,
        Duration::from_secs(1),
    )?);
    let app = http::router(worker, "secret".into());
    let request = |path: &str, body: &str| {
        Request::builder()
            .uri(path)
            .method("POST")
            .header(header::AUTHORIZATION, "Bearer secret")
            .header(header::CONTENT_LENGTH, body.len())
            .body(Body::from(body.to_owned()))
    };
    let response = app.clone().oneshot(request("/pause", "{}")?).await?;
    assert_eq!(response.status(), StatusCode::OK);
    assert!(!f.repository(3)?.enabled().await?);
    let response = app.clone().oneshot(request("/resume", "{}")?).await?;
    assert_eq!(response.status(), StatusCode::OK);
    assert!(f.repository(3)?.enabled().await?);
    let response = app
        .clone()
        .oneshot(request("/pause", &"x".repeat(MAX_BODY_BYTES + 1))?)
        .await?;
    assert_eq!(response.status(), StatusCode::BAD_REQUEST);
    let response = app
        .clone()
        .oneshot(request(
            "/query",
            "{\"kind\":\"weather\",\"map_id\":527,\"instance_id\":0}",
        )?)
        .await?;
    assert_eq!(response.status(), StatusCode::OK);
    let body = protocol::bounded_json(
        &response.into_body().collect().await?.to_bytes(),
        MAX_RESPONSE_BYTES,
    )?;
    assert_eq!(body["authoritative"], true);
    let response = app
        .clone()
        .oneshot(
            Request::builder()
                .uri("/query")
                .header(header::AUTHORIZATION, "Bearer secret")
                .body(Body::empty())?,
        )
        .await?;
    let body = protocol::bounded_json(
        &response.into_body().collect().await?.to_bytes(),
        MAX_RESPONSE_BYTES,
    )?;
    assert_eq!(body["authoritative"], false);
    drop(app);
    f.cleanup().await
}

fn lifecycle_entry(x: i32, y: i32, draw: f64) -> Value {
    json!({
        "kind":"maturation","world_epoch":"boot","scope":[527,0],
        "configuration":{"interval_ms":300000,"stage_decay":0.5,"base_probability":0.1,"boss_probability":0.00001},
        "expected_members":[{"id":-8818,"ref":88,"team":1,"x":x,"y":y,"z":60,"ap":7,"hp":153,"max_hp":153,"mp":3,"wp":0,"breed":88,"level":22,"map_id":527,"instance_id":0,"sprite_id":101500088,"initiative":16,"effective_level":22}],
        "draw":draw,"plan":{"draw":draw,"cycle":18},
        "grown":{"id":-8818,"x":-1,"y":-168,"z":60,"ref":87},
        "ticket":{"map_id":527,"instance_id":0,"monster_id":-8818,"group_id":881,"reference":88,"cycle":18,"plan_incarnation":"fixture-native-incarnation","decision":{"draw":0.1337787157356456,"cycle":18,"attempts":1,"group_draw":0.9225139524098953,"variant_seed":"1152527292a2b3f5cba5b55f50e82597b6ca949460e152ab91e6137e2ad4f3c7","destination_draw":0.025525398700429247}}
    })
}

#[tokio::test]
#[ignore = "Requires dedicated SQL DB plus explicitly read-only native catalog reference"]
async fn stale_maturation_rebuilds_grown_from_fresh_parent_and_first_decision() -> Result<()> {
    let f = Fixture::create().await?;
    let (context, native_pool) = native_catalog_context(&f).await?;
    let repository = Repository::with_context(context.clone(), 3)?;
    let original = lifecycle_entry(-1, -168, 0.1337787157356456);
    let fresh = lifecycle_entry(-2, -170, 0.97);
    let bulk = |entry: Value| {
        proposal(
            "mobs",
            json!({"kind":"lifecycle_bulk","scope":[527,0],"world_epoch":"boot","operations":[entry]}),
            "boot",
        )
    };
    repository.save(&[bulk(original.clone())?], &[]).await?;
    repository.save(&[bulk(fresh.clone())?], &[]).await?;
    let pending = repository.pending().await?;
    assert_eq!(pending.len(), 1);
    let entry = &pending[0]["payload"]["operations"][0];
    assert_eq!(entry["expected_members"], fresh["expected_members"]);
    assert_eq!(entry["draw"], original["draw"]);
    assert_eq!(entry["plan"], original["plan"]);
    assert_eq!(entry["ticket"]["cycle"], 18);
    assert_eq!(entry["ticket"]["decision"], original["ticket"]["decision"]);
    assert_eq!(entry["grown"]["ref"], 87);
    assert_eq!(entry["grown"]["id"], original["ticket"]["monster_id"]);
    assert_eq!(
        (
            entry["grown"]["x"].as_i64(),
            entry["grown"]["y"].as_i64(),
            entry["grown"]["z"].as_i64()
        ),
        (Some(-2), Some(-170), Some(60))
    );
    let unchanged = wakemu_ecology::planners::native_monster::refresh_stale_decision(
        &context, &original, &original,
    )
    .await?;
    assert_eq!(unchanged["grown"]["x"], -1);
    assert_eq!(unchanged["grown"]["ref"], 87);
    drop(repository);
    drop(context);
    native_pool.close();
    f.cleanup().await
}

async fn native_catalog_context(f: &Fixture) -> Result<(Arc<Context>, Pool)> {
    let mut native_config: Config = std::env::var("WAKFU_ECOLOGY_NATIVE_TEST_URL")
        .context("Set WAKFU_ECOLOGY_NATIVE_TEST_URL for read-only catalog fixtures")?
        .parse()?;
    // This separate pool can only read catalog authority. All queue mutations
    // still use f.pool in the private test schema, never the reference database.
    native_config.options("-c default_transaction_read_only=on");
    native_config.application_name("wakemu-ecology-legacy-catalog-readonly");
    if let Ok(path) = std::env::var("WAKFU_DATABASE_PASSWORD_FILE") {
        native_config.password(std::fs::read_to_string(path)?.trim());
    }
    let native_pool = Pool::builder(deadpool_postgres::Manager::new(native_config, NoTls))
        .max_size(8)
        .build()?;
    let revision =
        std::env::var("WAKFU_CATALOG_REVISION").context("Pinned native test revision required")?;
    let generation = std::env::var("WAKFU_COMPILED_CATALOG_GENERATION")
        .context("Pinned native test compiled generation required")?;
    let context = Arc::new(Context {
        db: f.pool.clone(),
        catalog: Catalog::new(native_pool.clone(), revision, Some(generation)),
    });
    context.catalog.verify().await?;
    Ok((context, native_pool))
}

fn retry_birth_batch(uids: &[i64], epoch: &str, incarnation: i64) -> Result<Value> {
    proposal(
        "plants",
        json!({"kind":"resource_growth_bulk","world_epoch":epoch,"resources":uids.iter().map(|uid|json!({"kind":"resource_growth","world_epoch":epoch,"expected":{"resource_uid":uid,"stage":1,"map_id":527,"instance_id":0,"resource_reference":10,"creation_time":incarnation},"member":{"id":-uid}})).collect::<Vec<_>>()}),
        epoch,
    )
}

async fn make_all_due(f: &Fixture) -> Result<()> {
    f.pool
        .get()
        .await?
        .execute(
            "UPDATE ecology_service_proposals SET next_attempt_at=CURRENT_TIMESTAMP",
            &[],
        )
        .await?;
    Ok(())
}

#[tokio::test]
#[ignore = "Requires dedicated WAKFU_POSTGRES_TEST_URL"]
async fn three_occupied_executions_stop_across_batches_and_restart() -> Result<()> {
    let f = Fixture::create().await?;
    let mut r = f.repository(3)?;
    for cycle in 0..3 {
        let epoch = format!("boot-{cycle}");
        r.save(&[retry_birth_batch(&[1, cycle + 2], &epoch, 100)?], &[])
            .await?;
        let row = r
            .pending()
            .await?
            .into_iter()
            .find(|row| row["world_epoch"] == epoch)
            .unwrap();
        r.acknowledge(&[json!({"id":row["id"],"status":"applied","resource_failures":[1]})])
            .await?;
        r = f.repository(3)?;
    }
    r.save(&[retry_birth_batch(&[1, 9], "boot-final", 100)?], &[])
        .await?;
    let row = r
        .pending()
        .await?
        .into_iter()
        .find(|row| row["world_epoch"] == "boot-final")
        .unwrap();
    assert_eq!(
        row["payload"]["resources"]
            .as_array()
            .unwrap()
            .iter()
            .map(|entry| entry["expected"]["resource_uid"].as_i64().unwrap())
            .collect::<Vec<_>>(),
        vec![9]
    );
    ack(&r, id(&row), "applied").await?;
    r.save(&[retry_birth_batch(&[1], "boot-final", 100)?], &[])
        .await?;
    assert_eq!(r.pending_count().await?, 0);
    r.save(&[retry_birth_batch(&[1], "boot-final", 101)?], &[])
        .await?;
    assert_eq!(r.pending_count().await?, 1);
    f.cleanup().await
}

#[tokio::test]
#[ignore = "Requires dedicated WAKFU_POSTGRES_TEST_URL"]
async fn timer_wait_does_not_consume_resource_failure_budget() -> Result<()> {
    let f = Fixture::create().await?;
    let r = f.repository(3)?;
    for _ in 0..5 {
        r.save(&[retry_birth_batch(&[1], "boot", 100)?], &[])
            .await?;
        let row = r.pending().await?.remove(0);
        ack(&r, id(&row), "deferred").await?;
        make_all_due(&f).await?;
    }
    let guards:i64=f.pool.get().await?.query_one("SELECT count(*) FROM ecology_service_proposals WHERE payload->>'kind'='bulk_failure_guard'",&[]).await?.get(0);
    assert_eq!(guards, 0);
    r.save(&[retry_birth_batch(&[1], "boot", 100)?], &[])
        .await?;
    assert_eq!(r.pending_count().await?, 1);
    f.cleanup().await
}

#[tokio::test]
#[ignore = "Requires dedicated WAKFU_POSTGRES_TEST_URL"]
async fn occupied_single_resource_does_not_keep_a_delivery_slot_forever() -> Result<()> {
    let f = Fixture::create().await?;
    let r = f.repository(3)?;
    let payload = retry_birth_batch(&[1], "boot", 100)?["payload"]["resources"][0].clone();
    for _ in 0..3 {
        r.save(&[proposal("plants", payload.clone(), "boot")?], &[])
            .await?;
        let row = r.pending().await?.remove(0);
        r.acknowledge(&[json!({"id":row["id"],"status":"deferred","resource_failures":[1]})])
            .await?;
        make_all_due(&f).await?;
    }
    r.save(&[], &[]).await?;
    assert_eq!(r.pending_count().await?, 0);
    f.cleanup().await
}

#[tokio::test]
#[ignore = "Requires dedicated WAKFU_POSTGRES_TEST_URL"]
async fn full_background_lane_preserves_interactive_capacity() -> Result<()> {
    let f = Fixture::create().await?;
    let r = f.repository(3)?;
    // Exercise the actual production limits rather than patching constants down
    // to 5: 4048 ambient slots, 16 monster births, then 32 player intents.
    f.pool.get().await?.execute("INSERT INTO ecology_service_proposals(id,domain,payload,world_epoch) SELECT 'background-'||i,'weather',jsonb_build_object('revision',i),'boot' FROM generate_series(1,4048) i",&[]).await?;
    let background = (0..20)
        .map(|revision| proposal("weather", json!({"revision":revision}), "boot"))
        .collect::<Result<Vec<_>>>()?;
    let stats = r.save(&background, &[]).await?;
    assert_eq!(r.pending_count().await?, 4048);
    assert_eq!(stats["capacity_deferred"], 20);
    let births = (1..=16)
        .map(|uid| proposal("plants", growth(uid, 10), "boot"))
        .collect::<Result<Vec<_>>>()?;
    r.save(&births, &[]).await?;
    assert_eq!(r.pending_count().await?, 4064);
    let interactive = (1..=32)
        .map(|intent_id| {
            proposal(
                "plants",
                json!({"kind":"planting_begin","intent_id":intent_id}),
                "boot",
            )
        })
        .collect::<Result<Vec<_>>>()?;
    r.save(&interactive, &[]).await?;
    assert_eq!(r.pending_count().await?, 4096);
    let stats = r.save(&background, &[]).await?;
    assert_eq!(r.pending_count().await?, 4096);
    assert!(stats["capacity_deferred"].as_i64().unwrap() > 0);
    f.cleanup().await
}

fn bulk_births(ids: impl IntoIterator<Item = i64>, variant: i64) -> Result<Value> {
    proposal(
        "plants",
        json!({"kind":"resource_growth_bulk","world_epoch":"boot","resources":ids.into_iter().map(|uid|json!({"kind":"resource_growth","world_epoch":"boot","expected":{"resource_uid":uid,"stage":1,"map_id":1134,"instance_id":0},"member":{"ref":variant},"draw":variant as f64/100.0})).collect::<Vec<_>>()}),
        "boot",
    )
}

#[tokio::test]
#[ignore = "Requires dedicated WAKFU_POSTGRES_TEST_URL"]
async fn merge_keeps_first_draw_bounded_pending_and_late_ack_safe() -> Result<()> {
    let f = Fixture::create().await?;
    let r = f.repository(3)?;
    r.save(&[bulk_births(1..33, 10)?], &[]).await?;
    let old = r.pending().await?.remove(0);
    ack(&r, id(&old), "retry").await?;
    r.save(&[bulk_births(1..101, 11)?], &[]).await?;
    let saved:Value=f.pool.get().await?.query_one("SELECT jsonb_build_object('id',id,'payload',payload,'attempts',attempts) FROM ecology_service_proposals WHERE delivered_at IS NULL",&[]).await?.get(0);
    assert_ne!(saved["id"], old["id"]);
    assert_eq!(saved["attempts"], 1);
    let entries = saved["payload"]["resources"].as_array().unwrap();
    assert_eq!(entries.len(), 64);
    assert_eq!(
        entries
            .iter()
            .map(|entry| entry["expected"]["resource_uid"].as_i64().unwrap())
            .collect::<Vec<_>>(),
        (1..65).collect::<Vec<_>>()
    );
    assert!(entries[..32]
        .iter()
        .all(|entry| entry["member"]["ref"] == 10));
    ack(&r, id(&old), "applied").await?;
    assert_eq!(r.pending_count().await?, 1);
    let reopened = f.repository(3)?;
    reopened.save(&[bulk_births(1..101, 12)?], &[]).await?;
    assert_eq!(reopened.pending_count().await?, 1);
    let after = f.document(id(&saved)).await?;
    assert_eq!(after["payload"], saved["payload"]);
    assert_eq!(after["attempts"], 1);
    f.cleanup().await
}

#[tokio::test]
#[ignore = "Requires dedicated WAKFU_POSTGRES_TEST_URL"]
async fn identical_entry_set_cannot_reroll_after_three_failed_attempts() -> Result<()> {
    let f = Fixture::create().await?;
    let r = f.repository(3)?;
    r.save(&[bulk_births(1..65, 10)?], &[]).await?;
    let durable = id(&r.pending().await?[0]).to_owned();
    for _ in 0..3 {
        ack(&r, &durable, "retry").await?;
    }
    r.save(&[bulk_births(1..65, 11)?], &[]).await?;
    assert_eq!(r.pending_count().await?, 0);
    let saved = f.document(&durable).await?;
    assert_eq!(saved["attempts"], 3);
    assert_eq!(saved["last_error_code"], "retry_exhausted");
    assert_eq!(saved["payload"]["resources"][0]["member"]["ref"], 10);
    f.cleanup().await
}

#[tokio::test]
#[ignore = "Requires dedicated WAKFU_POSTGRES_TEST_URL"]
async fn lifecycle_metadata_does_not_duplicate_event_but_incarnation_does() -> Result<()> {
    let f = Fixture::create().await?;
    let r = f.repository(3)?;
    let ticket = json!({"map_id":1134,"instance_id":0,"group_id":1,"monster_id":-1,"reference":60,"cycle":7,"plan_incarnation":"a"});
    let original = json!({"kind":"maturation","ticket":ticket,"plan":{"draw":0.1}});
    let row = proposal(
        "mobs",
        json!({"kind":"lifecycle_bulk","scope":[1134,0],"operations":[original.clone()]}),
        "boot",
    )?;
    r.save(&[row.clone()], &[]).await?;
    let mut changed = original.clone();
    changed["ticket"]["decision"] = json!({"attempts":4});
    changed["ticket"]["plan_policy"] = json!({"probability":0.9});
    changed["plan"] = json!({"draw":0.9});
    let mut payload = row["payload"].clone();
    payload["operations"] = json!([changed.clone()]);
    r.save(&[proposal("mobs", payload.clone(), "boot")?], &[])
        .await?;
    assert_eq!(
        r.pending().await?[0]["payload"]["operations"],
        json!([original.clone()])
    );
    let mut reincarnated = changed;
    reincarnated["ticket"] = ticket;
    reincarnated["ticket"]["plan_incarnation"] = json!("b");
    payload["operations"] = json!([reincarnated.clone()]);
    r.save(&[proposal("mobs", payload, "boot")?], &[]).await?;
    assert_eq!(r.pending_count().await?, 1);
    assert_eq!(
        r.pending().await?[0]["payload"]["operations"],
        json!([original, reincarnated])
    );
    f.cleanup().await
}

#[tokio::test]
#[ignore = "Requires dedicated WAKFU_POSTGRES_TEST_URL"]
async fn exhausted_entry_is_filtered_when_bulk_membership_changes() -> Result<()> {
    let f = Fixture::create().await?;
    let r = f.repository(3)?;
    let batch = |ids: Vec<i64>, reference: i64| -> Result<Value> {
        let mut row = bulk_births(ids, 10)?;
        for entry in row["payload"]["resources"].as_array_mut().unwrap() {
            entry["expected"]["resource_reference"] = json!(reference);
        }
        Ok(row)
    };
    r.save(&[batch(vec![1], 60)?], &[]).await?;
    let old = r.pending().await?.remove(0);
    for _ in 0..3 {
        ack(&r, id(&old), "retry").await?;
    }
    r.save(&[batch(vec![1, 2], 60)?], &[]).await?;
    let row = r.pending().await?.remove(0);
    assert_eq!(
        row["payload"]["resources"]
            .as_array()
            .unwrap()
            .iter()
            .map(|v| v["expected"]["resource_uid"].as_i64().unwrap())
            .collect::<Vec<_>>(),
        vec![2]
    );
    ack(&r, id(&row), "deferred").await?;
    ack(&r, id(&row), "retry").await?;
    r.save(&[batch(vec![1, 2, 3], 60)?], &[]).await?;
    let row = r.pending().await?.remove(0);
    assert_eq!(
        row["payload"]["resources"]
            .as_array()
            .unwrap()
            .iter()
            .map(|v| v["expected"]["resource_uid"].as_i64().unwrap())
            .collect::<Vec<_>>(),
        vec![2, 3]
    );
    r.save(&[batch(vec![1], 61)?], &[]).await?;
    let row = r.pending().await?.remove(0);
    assert!(row["payload"]["resources"]
        .as_array()
        .unwrap()
        .iter()
        .any(|v| v["expected"]["resource_uid"] == 1 && v["expected"]["resource_reference"] == 61));
    f.cleanup().await
}

#[tokio::test]
#[ignore = "Requires dedicated WAKFU_POSTGRES_TEST_URL"]
async fn normal_wait_releases_scope_and_rearms_same_decision_only_after_due() -> Result<()> {
    let f = Fixture::create().await?;
    let r = f.repository(3)?;
    r.save(&[bulk_births([1], 10)?], &[]).await?;
    let a = r.pending().await?.remove(0);
    ack(&r, id(&a), "deferred").await?;
    assert_eq!(r.pending_count().await?, 0);
    r.save(&[bulk_births([2], 10)?], &[]).await?;
    let b = r.pending().await?.remove(0);
    assert_eq!(b["payload"]["resources"][0]["expected"]["resource_uid"], 2);
    ack(&r, id(&b), "applied").await?;
    r.save(&[bulk_births([1], 11)?], &[]).await?;
    assert_eq!(r.pending_count().await?, 0);
    let saved = f.document(id(&a)).await?;
    assert_eq!(saved["attempts"], 0);
    assert_eq!(saved["last_error_code"], "normal_wait");
    make_all_due(&f).await?;
    let reopened = f.repository(3)?;
    reopened.save(&[bulk_births([1], 11)?], &[]).await?;
    let ready = reopened.pending().await?.remove(0);
    assert_eq!(ready["id"], a["id"]);
    assert_eq!(ready["payload"]["resources"], a["payload"]["resources"]);
    ack(&reopened, id(&ready), "applied").await?;
    assert_eq!(f.document(id(&a)).await?["attempts"], 0);
    f.cleanup().await
}

#[tokio::test]
#[ignore = "Requires dedicated SQL DB plus explicitly read-only native catalog reference"]
async fn completed_lifecycle_pass_rearms_due_same_cas_and_refreshes_new_roster() -> Result<()> {
    let f = Fixture::create().await?;
    let (context, native_pool) = native_catalog_context(&f).await?;
    let r = Repository::with_context(context.clone(), 3)?;
    let mut original = lifecycle_entry(-1, -168, 0.1337787157356456);
    let mut peer = original["expected_members"][0].clone();
    peer["id"] = json!(-8817);
    peer["ref"] = json!(87);
    peer["breed"] = json!(87);
    peer["sprite_id"] = json!(101500087);
    peer["x"] = json!(-2);
    peer["y"] = json!(-171);
    original["expected_members"]
        .as_array_mut()
        .unwrap()
        .insert(0, peer);
    original["ticket"]["plan_incarnation"] = json!("83b01e9724394c346f22fa4f2df19e15");
    let bulk = |op: Value| {
        proposal(
            "mobs",
            json!({"kind":"lifecycle_bulk","scope":[527,0],"operations":[op]}),
            "boot",
        )
    };
    let row = bulk(original.clone())?;
    r.save(&[row.clone()], &[]).await?;
    let old = r.pending().await?.remove(0);
    ack(&r, id(&old), "applied").await?;
    r.save(&[row], &[]).await?;
    assert_eq!(r.pending().await?[0]["id"], old["id"]);
    let mut fresh = original.clone();
    fresh["expected_members"][1]["x"] = json!(-2);
    fresh["expected_members"][1]["y"] = json!(-170);
    r.save(&[bulk(fresh.clone())?], &[]).await?;
    let current = r.pending().await?.remove(0);
    assert_ne!(current["id"], old["id"]);
    let entry = &current["payload"]["operations"][0];
    assert_eq!(entry["expected_members"], fresh["expected_members"]);
    assert_eq!(entry["draw"], original["draw"]);
    assert_eq!(entry["ticket"]["cycle"], 18);
    assert_eq!(entry["ticket"]["decision"], original["ticket"]["decision"]);
    assert_eq!(entry["grown"]["x"], -2);
    assert_eq!(entry["grown"]["y"], -170);
    assert_eq!(entry["grown"]["z"], 60);
    assert_eq!(entry["grown"]["ref"], 87);
    ack(&r, id(&old), "applied").await?;
    assert_eq!(r.pending_count().await?, 1);
    assert_eq!(f.document(id(&current)).await?["attempts"], 0);
    drop(r);
    drop(context);
    native_pool.close();
    f.cleanup().await
}
