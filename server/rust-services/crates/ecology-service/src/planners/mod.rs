//! Bounded policy planning. Final world mutations remain behind World fences.
use crate::Context;
use anyhow::{bail, Result};
use serde_json::Value;

pub mod bonuses;
pub mod mob_geometry;
pub mod mob_idle;
pub mod mob_lifecycle;
pub mod mobs;
pub mod native_monster;
pub mod planting_intents;
pub mod planting_policy;
pub mod plants;
pub mod population;
pub mod weather;

pub async fn prepare(
    ctx: &Context,
    domain: &str,
    snapshot: &Value,
    limit: usize,
) -> Result<Vec<Value>> {
    match domain {
        "plants" => plants::prepare(ctx, snapshot, limit).await,
        "mobs" => mobs::prepare(ctx, snapshot, limit).await,
        "weather" => weather::prepare(ctx, snapshot, limit).await,
        "population" => population::prepare(ctx, snapshot, limit).await,
        "bonuses" => bonuses::prepare(ctx, snapshot, limit).await,
        _ => bail!("Invalid ecology domain"),
    }
}

pub async fn prepare_interactive(
    ctx: &Context,
    snapshot: &Value,
    limit: usize,
) -> Result<Vec<Value>> {
    planting_intents::prepare(ctx, snapshot, limit).await
}
pub async fn wander_interval(ctx: &Context) -> Result<f64> {
    mobs::wander_interval(ctx).await
}
pub async fn validate_proposal(ctx: &Context, row: &Value) -> Result<bool> {
    mobs::validate_proposal(ctx, row).await
}
