//! Environment compatibility without exposing credentials in logs or Debug output.
use anyhow::{ensure, Context as _, Result};
use deadpool_postgres::{Manager, ManagerConfig, Pool, RecyclingMethod};
use std::{env, net::SocketAddr, path::Path, str::FromStr, time::Duration};
use tokio_postgres::NoTls;

pub struct Config {
    pub database: tokio_postgres::Config,
    pub token: String,
    pub world_url: String,
    pub revision: String,
    pub compiled_generation: Option<String>,
    pub listen: SocketAddr,
    pub interval: Duration,
    pub max_attempts: u32,
}

pub fn token_from_environment() -> Result<String> {
    let path = env::var("WAKFU_ECOLOGY_TOKEN_FILE").context("Ecology credential file required")?;
    let token = std::fs::read_to_string(Path::new(&path))
        .context("Cannot read ecology credential file")?
        .trim()
        .to_owned();
    ensure!(
        !token.is_empty() && token.len() <= 4096,
        "Invalid ecology credential"
    );
    Ok(token)
}

impl Config {
    pub fn from_environment() -> Result<Self> {
        let mut database = tokio_postgres::Config::from_str(
            &env::var("WAKFU_DATABASE_URL").context("PostgreSQL connection required")?,
        )
        .context("Invalid PostgreSQL connection configuration")?;
        if let Ok(path) = env::var("WAKFU_DATABASE_PASSWORD_FILE") {
            let password =
                std::fs::read_to_string(path).context("Cannot read PostgreSQL credential file")?;
            ensure!(
                !password.trim().is_empty(),
                "Empty PostgreSQL credential file"
            );
            database.password(password.trim());
        }
        database
            .application_name("wakemu-ecology-rust")
            .connect_timeout(Duration::from_secs(2));
        let revision = env::var("WAKFU_CATALOG_REVISION")
            .context("Pinned ecology catalog revision required")?;
        ensure!(
            revision.len() == 64
                && revision
                    .bytes()
                    .all(|c| c.is_ascii_digit() || (b'a'..=b'f').contains(&c)),
            "Invalid native catalog revision"
        );
        let seconds = env::var("WAKFU_ECOLOGY_POLL_SECONDS")
            .unwrap_or_else(|_| "1".into())
            .parse::<f64>()
            .context("Invalid ecology poll interval")?;
        ensure!(
            seconds.is_finite() && (0.1..=60.0).contains(&seconds),
            "Invalid ecology poll interval"
        );
        let max_attempts = env::var("WAKFU_ECOLOGY_MAX_ATTEMPTS")
            .unwrap_or_else(|_| "3".into())
            .parse::<u32>()?;
        ensure!(
            (1..=100).contains(&max_attempts),
            "Invalid ecology maximum attempts"
        );
        // Modules cannot be injected as executable code into the Rust worker.
        if let Ok(modules) = env::var("WAKFU_ECOLOGY_DOMAIN_MODULES") {
            let modules: serde_json::Value = serde_json::from_str(&modules)?;
            ensure!(
                modules.as_object().is_some_and(|m| m.is_empty()),
                "Custom Python ecology modules require an explicit native adapter"
            );
        }
        Ok(Self {
            database,
            token: token_from_environment()?,
            world_url: env::var("WAKFU_WORLD_URL").unwrap_or_else(|_| "http://world:18081".into()),
            revision,
            compiled_generation: env::var("WAKFU_COMPILED_CATALOG_GENERATION")
                .ok()
                .filter(|s| !s.is_empty()),
            listen: format!(
                "{}:{}",
                env::var("WAKFU_ECOLOGY_BIND").unwrap_or_else(|_| "0.0.0.0".into()),
                env::var("WAKFU_ECOLOGY_PORT").unwrap_or_else(|_| "8093".into())
            )
            .parse()
            .context("Invalid ecology bind address")?,
            interval: Duration::from_secs_f64(seconds),
            max_attempts,
        })
    }
    pub fn pool(&self) -> Result<Pool> {
        let manager = Manager::from_config(
            self.database.clone(),
            NoTls,
            ManagerConfig {
                recycling_method: RecyclingMethod::Fast,
            },
        );
        Ok(Pool::builder(manager).max_size(8).build()?)
    }
}
