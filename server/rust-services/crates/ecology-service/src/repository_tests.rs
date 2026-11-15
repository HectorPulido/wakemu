//! Real SQL queue contracts. Run explicitly against a non-runtime test database.
use super::*;
use tokio_postgres::{Client, Config, NoTls};

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
        let schema = format!("rust_ecology_{}_{}", std::process::id(), nanos);
        admin
            .batch_execute(&format!("CREATE SCHEMA {schema}"))
            .await?;
        config.options(format!("-c search_path={schema}"));
        let manager = deadpool_postgres::Manager::new(config, NoTls);
        let pool = Pool::builder(manager)
            .max_size(6)
            .runtime(deadpool_postgres::Runtime::Tokio1)
            .build()?;
        let connection = pool.get().await?;
        connection.batch_execute(
            "CREATE TABLE settings(name text PRIMARY KEY,value jsonb NOT NULL); \
             CREATE TABLE ecology_dirty_scopes(map_id bigint NOT NULL,instance_id bigint NOT NULL,revision bigint NOT NULL,processed_revision bigint NOT NULL DEFAULT 0,updated_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,PRIMARY KEY(map_id,instance_id)); \
             CREATE TABLE ecology_service_proposals(id text PRIMARY KEY,domain text NOT NULL,payload jsonb NOT NULL,world_epoch text NOT NULL,created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,delivered_at timestamptz,attempts integer NOT NULL DEFAULT 0,last_error_code text,next_attempt_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP)"
        ).await?;
        drop(connection);
        Ok(Self {
            admin,
            schema,
            pool,
        })
    }

    async fn cleanup(self) -> Result<()> {
        self.pool.close();
        self.admin
            .batch_execute(&format!("DROP SCHEMA {} CASCADE", self.schema))
            .await?;
        Ok(())
    }

    async fn row(&self, id: &str) -> Result<Value> {
        let connection = self.pool.get().await?;
        Ok(connection.query_one("SELECT jsonb_build_object('attempts',attempts,'error',last_error_code,'delivered',delivered_at IS NOT NULL,'payload',payload) AS document FROM ecology_service_proposals WHERE id=$1", &[&id]).await?.get("document"))
    }

    async fn due(&self, id: &str) -> Result<()> {
        self.pool.get().await?.execute("UPDATE ecology_service_proposals SET next_attempt_at=CURRENT_TIMESTAMP WHERE id=$1", &[&id]).await?;
        Ok(())
    }
}

#[tokio::test]
#[ignore = "Requires WAKFU_POSTGRES_TEST_URL dedicated database"]
async fn sql_owner_exclusion_and_explicit_close_release_the_exact_session_lock() -> Result<()> {
    let fixture = Fixture::create().await?;
    {
        let first = Repository::new(fixture.pool.clone(), 3)?;
        let second = Repository::new(fixture.pool.clone(), 3)?;
        first.acquire().await?;
        first.assert_owner().await?;
        assert!(second.acquire().await.is_err());
        assert!(!second.owns_database().await);
        first.close().await?;
        assert!(!first.owns_database().await);
        second.acquire().await?;
        second.assert_owner().await?;
        second.close().await?;
    }
    fixture.cleanup().await
}

#[tokio::test]
#[ignore = "Requires WAKFU_POSTGRES_TEST_URL dedicated database"]
async fn sql_deferred_is_not_an_attempt_and_stale_refresh_keeps_attempt_history() -> Result<()> {
    let fixture = Fixture::create().await?;
    {
        let repository = Repository::new(fixture.pool.clone(), 3)?;
        repository.acquire().await?;
        let supplied = proposal(
            "plants",
            json!({"kind":"mineral_refill","resource_uid":71,"available_at":"2026-11-14T00:00:00+00:00"}),
            "epoch",
        )?;
        repository.save(&[supplied.clone()], &[]).await?;
        let pending = repository.pending().await?;
        let id = string(&pending[0], "id")?.to_owned();
        repository
            .acknowledge(&[json!({"id":id,"status":"deferred"})])
            .await?;
        let deferred = fixture.row(&id).await?;
        assert_eq!(deferred["attempts"], 0);
        assert_eq!(deferred["delivered"], false);
        assert!(repository.pending().await?.is_empty());
        fixture.due(&id).await?;
        repository
            .acknowledge(&[json!({"id":id,"status":"stale"})])
            .await?;
        let stale = fixture.row(&id).await?;
        assert_eq!(stale["attempts"], 1);
        assert_eq!(stale["error"], "stale");
        assert_eq!(stale["delivered"], true);
        fixture.due(&id).await?;
        let admitted = repository.save(&[supplied], &[]).await?;
        assert_eq!(admitted["refreshed"], 1);
        let refreshed = fixture.row(&id).await?;
        assert_eq!(refreshed["attempts"], 1);
        assert_eq!(refreshed["delivered"], false);
        repository
            .acknowledge(&[json!({"id":id,"status":"retry"})])
            .await?;
        fixture.due(&id).await?;
        repository
            .acknowledge(&[json!({"id":id,"status":"retry"})])
            .await?;
        let exhausted = fixture.row(&id).await?;
        assert_eq!(exhausted["attempts"], 3);
        assert_eq!(exhausted["error"], "retry_exhausted");
        assert_eq!(exhausted["delivered"], true);
        assert_eq!(repository.retry_stats().await?["exhausted"], 1);
        repository.close().await?;
    }
    fixture.cleanup().await
}

fn growth(uid: i64) -> Value {
    json!({"kind":"resource_growth","world_epoch":"epoch","expected":{"resource_uid":uid,"map_id":1134,"instance_id":0,"x":2,"y":3,"z":0,"resource_reference":100,"stage":1,"creation_time":1000},"transition":null,"member":{"id":-uid,"ref":44}})
}

#[tokio::test]
#[ignore = "Requires WAKFU_POSTGRES_TEST_URL dedicated database"]
async fn sql_bulk_failure_guards_do_not_consume_pass_attempts_or_restart_failed_entries(
) -> Result<()> {
    let fixture = Fixture::create().await?;
    {
        let repository = Repository::new(fixture.pool.clone(), 1)?;
        repository.acquire().await?;
        let supplied = proposal(
            "plants",
            json!({"kind":"resource_growth_bulk","world_epoch":"epoch","resources":[growth(11),growth(12)]}),
            "epoch",
        )?;
        repository.save(&[supplied.clone()], &[]).await?;
        let pending = repository.pending().await?;
        assert_eq!(pending.len(), 1);
        let id = string(&pending[0], "id")?.to_owned();
        repository
            .acknowledge(&[json!({"id":id,"status":"deferred","resource_failures":[11]})])
            .await?;
        let waited = fixture.row(&id).await?;
        assert_eq!(waited["attempts"], 0);
        assert_eq!(waited["error"], "normal_wait");
        assert_eq!(waited["delivered"], true);
        fixture.due(&id).await?;
        repository.save(&[supplied], &[]).await?;
        let pending = repository.pending().await?;
        assert_eq!(pending.len(), 1);
        let resources = pending[0]["payload"]["resources"].as_array().unwrap();
        assert_eq!(resources.len(), 1);
        assert_eq!(resources[0]["expected"]["resource_uid"], 12);
        let guard = bulk_failure_identity("plants", "epoch", &growth(11))?;
        let failure = fixture.row(&guard).await?;
        assert_eq!(failure["attempts"], 1);
        assert_eq!(failure["payload"]["kind"], "bulk_failure_guard");

        let dirty = json!({"map_id":1134,"instance_id":0,"revision":9});
        fixture
            .pool
            .get()
            .await?
            .execute(
                "INSERT INTO ecology_dirty_scopes(map_id,instance_id,revision) VALUES(1134,0,9)",
                &[],
            )
            .await?;
        let regional = |revision| {
            proposal(
                "bonuses",
                json!({"kind":"regional_snapshot","map_id":1134,"instance_id":0,"revision":revision,"regions":[]}),
                "epoch",
            )
        };
        repository.save(&[regional(2)?], &[dirty]).await?;
        let pending = repository.pending().await?;
        let previous = pending
            .iter()
            .find(|row| row["domain"] == "bonuses")
            .unwrap();
        let previous_id = string(previous, "id")?.to_owned();
        repository.save(&[regional(1)?], &[]).await?;
        assert_eq!(fixture.row(&previous_id).await?["delivered"], false);
        repository.save(&[regional(3)?], &[]).await?;
        assert_eq!(fixture.row(&previous_id).await?["error"], "superseded");
        repository
            .acknowledge(&[json!({"id":previous_id,"status":"applied"})])
            .await?;
        let pending = repository.pending().await?;
        let current = pending
            .iter()
            .find(|row| row["domain"] == "bonuses")
            .unwrap();
        assert_eq!(current["payload"]["revision"], 3);
        assert_ne!(string(current, "id")?, previous_id);
        let processed: i64 = fixture.pool.get().await?.query_one(
            "SELECT processed_revision FROM ecology_dirty_scopes WHERE map_id=1134 AND instance_id=0",
            &[],
        ).await?.get("processed_revision");
        assert_eq!(processed, 9);
        repository.close().await?;
    }
    fixture.cleanup().await
}
