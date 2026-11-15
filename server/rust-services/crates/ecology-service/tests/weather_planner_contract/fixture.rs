#![allow(dead_code)]
//! Native weather SQL contracts; every mutation is confined to a private test schema.
use anyhow::{ensure, Context as _, Result};
use deadpool_postgres::Pool;
use serde_json::{json, Value};
use sha2::{Digest, Sha256};
use tokio_postgres::{Client, Config, NoTls};
use wakemu_ecology::{catalog::Catalog, planners::weather, Context};

pub struct Fixture {
    admin: Client,
    pub pool: Pool,
    schema: String,
    revision: String,
    generation: String,
}
impl Fixture {
    pub async fn create() -> Result<Self> {
        let mut config: Config = std::env::var("WAKFU_POSTGRES_TEST_URL")
            .context("Dedicated WAKFU_POSTGRES_TEST_URL required")?
            .parse()?;
        let name = config.get_dbname().context("Explicit database required")?;
        ensure!(
            name.contains("test") && !matches!(name, "wakemu" | "wakemu_runtime"),
            "Refusing runtime database"
        );
        if let Ok(path) = std::env::var("WAKFU_DATABASE_PASSWORD_FILE") {
            config.password(std::fs::read_to_string(path)?.trim());
        }
        let (admin, connection) = config.connect(NoTls).await?;
        tokio::spawn(async move {
            let _ = connection.await;
        });
        let stamp = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)?
            .as_nanos();
        let schema = format!("rust_weather_contract_{}_{stamp}", std::process::id());
        admin
            .batch_execute(&format!("CREATE SCHEMA {schema}"))
            .await?;
        config.options(format!("-c search_path={schema},pg_catalog"));
        let pool = Pool::builder(deadpool_postgres::Manager::new(config, NoTls))
            .max_size(8)
            .build()?;
        let db = pool.get().await?;
        db.batch_execute("CREATE TABLE fixture_clock(now timestamptz NOT NULL); INSERT INTO fixture_clock VALUES('2026-01-11 01:00:00+00'); CREATE FUNCTION clock_timestamp() RETURNS timestamptz LANGUAGE sql STABLE AS 'SELECT now FROM fixture_clock'; CREATE TABLE settings(name text PRIMARY KEY,value jsonb NOT NULL);").await?;
        for migration in [
            include_str!(concat!(
                env!("CARGO_MANIFEST_DIR"),
                "/../../../migrations/020_territory_weather.sql"
            )),
            include_str!(concat!(
                env!("CARGO_MANIFEST_DIR"),
                "/../../../migrations/055_territory_weather_transitions.sql"
            )),
            include_str!(concat!(
                env!("CARGO_MANIFEST_DIR"),
                "/../../../migrations/056_territory_weather_local_policy.sql"
            )),
            include_str!(concat!(
                env!("CARGO_MANIFEST_DIR"),
                "/../../../migrations/058_territory_weather_forecast_policy.sql"
            )),
            include_str!(concat!(
                env!("CARGO_MANIFEST_DIR"),
                "/../../../migrations/118_regional_weather_simulation.sql"
            )),
        ] {
            db.batch_execute(migration).await?;
        }
        db.batch_execute("DELETE FROM territory_weather; CREATE TABLE native_catalog_releases(revision text PRIMARY KEY,complete boolean NOT NULL); CREATE TABLE native_catalog_active(id integer PRIMARY KEY,revision text); CREATE TABLE native_catalog_documents(revision text,path text,raw bytea,sha256 text,source_bytes bigint,PRIMARY KEY(revision,path)); CREATE TABLE native_compiled_catalog_releases(generation text PRIMARY KEY,policy text,source_revision text,source_inventory_sha256 text,compiler_contract_sha256 text,config_sha256 text,manifest_raw bytea,manifest jsonb,complete boolean);").await?;
        let revision = hex::encode(Sha256::digest(schema.as_bytes()));
        db.execute(
            "INSERT INTO native_catalog_releases VALUES($1,true)",
            &[&revision],
        )
        .await?;
        db.execute(
            "INSERT INTO native_catalog_active VALUES(1,$1)",
            &[&revision],
        )
        .await?;
        let manifest = json!({"policy":"wakemu.compiled-combat-catalog.v1","source_revision":revision,"source_inventory_sha256":"b".repeat(64),"compiler_contract_sha256":"c".repeat(64),"config_sha256":"d".repeat(64),"collections":{},"raw_documents":{},"documents":{}});
        let raw = serde_json::to_vec(&manifest)?;
        let generation = hex::encode(Sha256::digest(&raw));
        db.execute(
            "INSERT INTO native_compiled_catalog_releases VALUES($1,$2,$3,$4,$5,$6,$7,$8,true)",
            &[
                &generation,
                &"wakemu.compiled-combat-catalog.v1",
                &revision,
                &"b".repeat(64),
                &"c".repeat(64),
                &"d".repeat(64),
                &raw,
                &manifest,
            ],
        )
        .await?;
        let raw = serde_json::to_vec(
            &json!({"schema_version":1,"grid_size":18,"maps":[{"map_id":1134,"regions":[{"region_id":79201,"cells":[[0,0]]}]}]}),
        )?;
        let digest = hex::encode(Sha256::digest(&raw));
        db.execute(
            "INSERT INTO native_catalog_documents VALUES($1,'territory-map-cells.json',$2,$3,$4)",
            &[&revision, &raw, &digest, &(raw.len() as i64)],
        )
        .await?;
        drop(db);
        Ok(Self {
            admin,
            pool,
            schema,
            revision,
            generation,
        })
    }
    pub async fn document(&self, name: &str, value: &Value) -> Result<()> {
        let raw = serde_json::to_vec(value)?;
        let digest = hex::encode(Sha256::digest(&raw));
        self.pool.get().await?.execute("INSERT INTO native_catalog_documents VALUES($1,$2,$3,$4,$5) ON CONFLICT(revision,path) DO UPDATE SET raw=EXCLUDED.raw,sha256=EXCLUDED.sha256,source_bytes=EXCLUDED.source_bytes", &[&self.revision,&name,&raw,&digest,&(raw.len() as i64)]).await?;
        Ok(())
    }
    pub fn context(&self) -> Context {
        Context {
            db: self.pool.clone(),
            catalog: Catalog::new(
                self.pool.clone(),
                self.revision.clone(),
                Some(self.generation.clone()),
            ),
        }
    }
    pub async fn prepare(&self) -> Result<Vec<Value>> {
        weather::prepare(
            &self.context(),
            &json!({"world_epoch":"weather-contract"}),
            100,
        )
        .await
    }
    pub async fn sql(&self, sql: &str) -> Result<()> {
        self.pool.get().await?.batch_execute(sql).await?;
        Ok(())
    }
    pub async fn number(&self, sql: &str) -> Result<i64> {
        Ok(self.pool.get().await?.query_one(sql, &[]).await?.get(0))
    }
    pub async fn state(&self) -> Result<Value> {
        Ok(self.pool.get().await?.query_one("SELECT jsonb_build_object('weather',w.weather,'payload',encode(w.native_payload,'hex'),'revision',w.revision,'day',s.simulated_day,'version',f.policy_version,'hash',s.configuration_hash) FROM territory_weather w LEFT JOIN territory_weather_simulation s USING(map_id,instance_id,region_id) LEFT JOIN territory_weather_forecast_policy f USING(map_id,instance_id,region_id) WHERE w.instance_id=17",&[]).await?.get(0))
    }
    pub async fn local(&self) -> Result<()> {
        self.sql("INSERT INTO territory_weather_local_policy VALUES(1134,79201,'LOCAL_POLICY',1,'LIGHT',-7,0.1,0.2,0.3,0.4,0.5,0.6,clock_timestamp())").await?;
        self.instance(17).await
    }
    pub async fn instance(&self, instance: i64) -> Result<()> {
        let mut payload = 123456789i64.to_be_bytes().to_vec();
        payload.push((-7i8) as u8);
        for value in [0.1f32, 0.2, 0.3, 0.4, 0.5, 0.6] {
            payload.extend_from_slice(&value.to_be_bytes());
        }
        payload.extend_from_slice(&1i32.to_be_bytes());
        self.pool.get().await?.execute("INSERT INTO territory_weather(map_id,instance_id,region_id,weather,native_payload) VALUES(1134,$1,79201,'LIGHT',$2)", &[&instance,&payload]).await?;
        Ok(())
    }
    pub async fn close(self) -> Result<()> {
        self.pool.close();
        self.admin
            .batch_execute(&format!("DROP SCHEMA {} CASCADE", self.schema))
            .await?;
        Ok(())
    }
}
