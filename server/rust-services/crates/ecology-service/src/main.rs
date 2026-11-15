//! Native ecology executable. It never opens a game-client listener.
use anyhow::{ensure, Result};
use serde_json::json;
use std::{sync::Arc, time::Duration};
use wakemu_ecology::{
    catalog::Catalog,
    config::{token_from_environment, Config},
    http,
    repository::Repository,
    worker::Worker,
    world_client::WorldClient,
    Context,
};

#[tokio::main(worker_threads = 2)]
async fn main() -> Result<()> {
    if std::env::args().any(|argument| argument == "--health-check") {
        let port = std::env::var("WAKFU_ECOLOGY_PORT").unwrap_or_else(|_| "8093".into());
        let response = reqwest::Client::builder()
            .timeout(Duration::from_secs(3))
            .build()?
            .get(format!("http://127.0.0.1:{port}/health"))
            .bearer_auth(token_from_environment()?)
            .send()
            .await?;
        ensure!(response.status().is_success(), "Ecology is not healthy");
        return Ok(());
    }
    let config = Config::from_environment()?;
    let client = WorldClient::new(&config.world_url, config.token.clone())?;
    let snapshot = client.snapshot().await?;
    let generation = wakemu_ecology::protocol::catalog_publication(
        &snapshot,
        &config.revision,
        config.compiled_generation.as_deref(),
    )?;
    let pool = config.pool()?;
    let catalog = Catalog::new(pool.clone(), config.revision.clone(), Some(generation));
    catalog.verify().await?;
    let context = Arc::new(Context { db: pool, catalog });
    let repository = Repository::with_context(context.clone(), config.max_attempts)?;
    let worker = Arc::new(Worker::new(context, repository, client, config.interval)?);
    let listener = tokio::net::TcpListener::bind(config.listen).await?;
    println!(
        "{}",
        json!({"event":"ecology_listening","implementation":"rust","address":config.listen.to_string()})
    );
    let (shutdown, receiver) = tokio::sync::watch::channel(false);
    let task = tokio::spawn(worker.clone().run(receiver));
    let stop = async move {
        #[cfg(unix)]
        {
            let mut terminate =
                tokio::signal::unix::signal(tokio::signal::unix::SignalKind::terminate())
                    .expect("SIGTERM handler");
            tokio::select! {_=tokio::signal::ctrl_c()=>{},_=terminate.recv()=>{}}
        }
        #[cfg(not(unix))]
        {
            let _ = tokio::signal::ctrl_c().await;
        }
        let _ = shutdown.send(true);
    };
    axum::serve(listener, http::router(worker, config.token))
        .with_graceful_shutdown(stop)
        .await?;
    task.await?;
    Ok(())
}
