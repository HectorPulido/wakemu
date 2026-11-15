//! Read-only native constructor, surface and isolated growth-policy test probe.
//!
//! This executable never creates a worker, acquires ecology ownership, calls
//! World, or writes gameplay data. PostgreSQL enforces read-only transactions.
use std::io::{self, BufRead, BufReader, Read, Write};

use anyhow::{anyhow, bail, ensure, Context as _, Result};
use serde_json::{json, Value};
use wakemu_ecology::{catalog::Catalog, config::Config, planners::native_monster, Context};

const MAX_REQUEST_BYTES: u64 = 16 * 1024;
const MAX_RESPONSE_BYTES: usize = 1024 * 1024;

fn integer(request: &Value, key: &str) -> Result<i64> {
    request
        .get(key)
        .and_then(Value::as_i64)
        .ok_or_else(|| anyhow!("Missing or invalid native probe {key}"))
}

fn integer_or(request: &Value, key: &str, default: i64) -> Result<i64> {
    match request.get(key) {
        Some(value) => value
            .as_i64()
            .ok_or_else(|| anyhow!("Invalid native probe {key}")),
        None => Ok(default),
    }
}

fn i32_field(request: &Value, key: &str) -> Result<i32> {
    i32::try_from(integer(request, key)?)
        .with_context(|| format!("Native probe {key} exceeds i32 domain"))
}

fn height(request: &Value) -> Result<i16> {
    i16::try_from(integer(request, "z")?).context("Native probe z exceeds i16 domain")
}

async fn evaluate(context: &Context, request: &Value) -> Result<Value> {
    ensure!(
        request.is_object(),
        "Native probe request must be an object"
    );
    match request
        .get("operation")
        .or_else(|| request.get("op"))
        .and_then(Value::as_str)
        .unwrap_or("")
    {
        "prepare_growth" | "prepare_intents" => {
            let dsn = request["test_database_url"]
                .as_str()
                .context("Missing isolated fixture database")?;
            let mut config: tokio_postgres::Config = dsn.parse()?;
            let database = config
                .get_dbname()
                .context("Explicit fixture database required")?;
            ensure!(
                database.contains("test") && !matches!(database, "wakemu" | "wakemu_runtime"),
                "Growth fixture refuses runtime database"
            );
            let existing = config.get_options().unwrap_or("").to_owned();
            config.options(format!("{existing} -c default_transaction_read_only=on"));
            if let Ok(path) = std::env::var("WAKFU_DATABASE_PASSWORD_FILE") {
                config.password(std::fs::read_to_string(path)?.trim());
            }
            let pool = deadpool_postgres::Pool::builder(deadpool_postgres::Manager::new(
                config,
                tokio_postgres::NoTls,
            ))
            .max_size(2)
            .build()?;
            let fixture = Context {
                db: pool.clone(),
                catalog: context.catalog.clone(),
            };
            let limit = usize::try_from(integer_or(request, "limit", 64)?)?;
            let snapshot = request
                .get("snapshot")
                .context("Missing fixture growth snapshot")?;
            let result = if request["operation"] == "prepare_intents" {
                wakemu_ecology::planners::planting_intents::prepare(&fixture, snapshot, limit).await
            } else {
                wakemu_ecology::planners::plants::prepare(&fixture, snapshot, limit).await
            };
            pool.close();
            Ok(serde_json::to_value(result?)?)
        }
        "owned_instance" => {
            let reference = request
                .get("ref")
                .or_else(|| request.get("reference"))
                .and_then(Value::as_i64)
                .context("Missing or invalid native probe ref")?;
            native_monster::owned_instance_in(
                context,
                reference,
                i32_field(request, "level")?,
                integer(request, "id")?,
                i32_field(request, "map_id")?,
                integer_or(request, "instance_id", 0)?,
                i32::try_from(integer_or(request, "team", 1)?)
                    .context("Native probe team exceeds i32 domain")?,
                i32_field(request, "x")?,
                i32_field(request, "y")?,
                height(request)?,
            )
            .await
        }
        "surface" => {
            context
                .catalog
                .surface(
                    i32_field(request, "map_id")?,
                    i32_field(request, "x")?,
                    i32_field(request, "y")?,
                    height(request)?,
                )
                .await
        }
        "constructor_inputs" => {
            let reference = request
                .get("ref")
                .or_else(|| request.get("reference"))
                .and_then(Value::as_i64)
                .context("Missing or invalid native probe ref")?;
            Ok(json!({
                "monster": context.catalog.monster_definition(reference).await?,
                "npc_profile": context.catalog.document_record(
                    "native-actor-characteristics.json", "npc_profiles", &json!(reference.to_string())
                ).await?,
                "characteristic_definitions": context.catalog.characteristic_definitions().await?,
            }))
        }
        "catalog_record" => {
            let document = request["document"]
                .as_str()
                .context("Missing native probe document")?;
            let collection = request["collection"]
                .as_str()
                .context("Missing native probe collection")?;
            let key = request.get("key").context("Missing native probe key")?;
            context
                .catalog
                .document_record(document, collection, key)
                .await
        }
        "compiled_record" => {
            let collection = request["collection"]
                .as_str()
                .context("Missing native probe collection")?;
            let key = request.get("key").context("Missing native probe key")?;
            context.catalog.record(collection, key).await
        }
        _ => bail!("Unknown native ecology probe operation"),
    }
}

async fn run() -> Result<()> {
    let mut config = Config::from_environment()?;
    let existing = config.database.get_options().unwrap_or("").to_owned();
    config
        .database
        .options(format!("{existing} -c default_transaction_read_only=on"));
    config
        .database
        .application_name("wakemu-ecology-native-probe");
    let pool = config.pool()?;
    {
        let connection = pool.get().await?;
        let readonly: String = connection
            .query_one("SELECT current_setting('transaction_read_only')", &[])
            .await?
            .get(0);
        ensure!(readonly == "on", "Native probe requires read-only SQL");
    }
    let catalog = Catalog::new(
        pool.clone(),
        config.revision.clone(),
        config.compiled_generation.clone(),
    );
    let context = Context { db: pool, catalog };
    let mut input = BufReader::new(io::stdin().lock());
    let mut output = io::BufWriter::new(io::stdout().lock());
    loop {
        let mut line = String::new();
        let read = (&mut input)
            .take(MAX_REQUEST_BYTES + 1)
            .read_line(&mut line)?;
        if read == 0 {
            break;
        }
        let result = if line.len() as u64 > MAX_REQUEST_BYTES {
            Err(anyhow!("Native probe request exceeds byte limit"))
        } else {
            match serde_json::from_str::<Value>(&line) {
                Ok(request) => evaluate(&context, &request).await,
                Err(error) => Err(error.into()),
            }
        };
        let response = match result {
            Ok(result) => json!({"result": result}),
            Err(error) => json!({"error": error.to_string()}),
        };
        let encoded = serde_json::to_vec(&response)?;
        if encoded.len() <= MAX_RESPONSE_BYTES {
            output.write_all(&encoded)?;
        } else {
            output.write_all(b"{\"error\":\"Native probe response exceeds byte limit\"}")?;
        }
        output.write_all(b"\n")?;
        output.flush()?;
        if line.len() as u64 > MAX_REQUEST_BYTES {
            break;
        }
    }
    Ok(())
}

#[tokio::main(worker_threads = 2)]
async fn main() {
    if let Err(error) = run().await {
        // Only the top-level diagnostic is shown: never print connection config,
        // token contents or credential-bearing error-chain Debug values.
        eprintln!("ecology-native-probe: {error}");
        std::process::exit(1);
    }
}
