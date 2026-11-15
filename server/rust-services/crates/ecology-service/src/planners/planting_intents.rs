//! Read-only native planting preparation over exact session and location authority.
use anyhow::{anyhow, ensure, Context as _, Result};
use serde_json::{json, Map, Value};
use tokio_postgres::Transaction;

use super::{planting_policy, weather};
use crate::Context;

const LOCATION_KEYS: [&str; 5] = ["map_id", "instance_id", "x", "y", "z"];

fn integer(value: &Value, key: &str) -> Result<i64> {
    value
        .get(key)
        .and_then(Value::as_i64)
        .ok_or_else(|| anyhow!("Invalid native integer: {key}"))
}
fn location(value: &Value) -> Result<[i64; 5]> {
    let values = [
        integer(value, "map_id")?,
        integer(value, "instance_id")?,
        integer(value, "x")?,
        integer(value, "y")?,
        integer(value, "z")?,
    ];
    ensure!(
        (1..=i32::MAX as i64).contains(&values[0])
            && values[1] >= 0
            && (i32::MIN as i64..=i32::MAX as i64).contains(&values[2])
            && (i32::MIN as i64..=i32::MAX as i64).contains(&values[3])
            && (i16::MIN as i64..=i16::MAX as i64).contains(&values[4]),
        "Invalid authoritative planting location"
    );
    Ok(values)
}
fn decode(body: &[u8]) -> Result<Value> {
    ensure!(body.len() == 20, "Invalid native seed request size");
    let action = i32::from_be_bytes(body[0..4].try_into()?);
    let uid = i64::from_be_bytes(body[4..12].try_into()?);
    let x = i32::from_be_bytes(body[12..16].try_into()?);
    let y = i32::from_be_bytes(body[16..20].try_into()?);
    ensure!(uid > 0 && action > 0, "Invalid seed action identity");
    Ok(json!({"action_id":action,"item_uid":uid,"x":x,"y":y}))
}
fn profession_level(xp: i64) -> Result<i64> {
    ensure!(
        (0..=3_000_000).contains(&xp),
        "Invalid cumulative profession XP"
    );
    // This bounded integer range is exactly representable; retain integer sqrt.
    let value = xp / 75;
    let mut result = 0i64;
    while (result + 1) * (result + 1) <= value {
        result += 1;
    }
    Ok(result)
}
fn fixed_kind(resource: &Value, profession: i64) -> bool {
    resource.get("monster_resource").and_then(Value::as_bool) == Some(false)
        && resource
            .get("stage_definitions")
            .and_then(Value::as_array)
            .into_iter()
            .flatten()
            .flat_map(|stage| {
                stage
                    .get("actions")
                    .and_then(Value::as_array)
                    .into_iter()
                    .flatten()
            })
            .any(|action| action.get("profession_id").and_then(Value::as_i64) == Some(profession))
}
fn validate_achievement_projection(state: &Value, full: bool) -> Result<()> {
    let object = state
        .as_object()
        .ok_or_else(|| anyhow!("Missing or malformed achievement authority"))?;
    let required: &[&str] = if full {
        &[
            "variables",
            "objectives",
            "running",
            "completed",
            "tracking",
            "recent",
            "completion_dates",
        ]
    } else {
        &["running", "completed", "objectives"]
    };
    ensure!(
        object.len() == required.len() && required.iter().all(|key| object.contains_key(*key)),
        "Missing or malformed achievement authority"
    );
    let mut projections = std::collections::HashMap::new();
    for key in ["running", "completed", "objectives"] {
        let values = state
            .get(key)
            .and_then(Value::as_array)
            .ok_or_else(|| anyhow!("Malformed achievement authority identifiers"))?;
        let mut seen = std::collections::HashSet::new();
        for value in values {
            let value = value
                .as_u64()
                .filter(|value| *value > 0)
                .ok_or_else(|| anyhow!("Malformed achievement authority identifiers"))?;
            ensure!(
                !full || value < (1u64 << 31),
                "Achievement identifiers exceed native signed32"
            );
            seen.insert(value);
        }
        projections.insert(key, seen);
    }
    ensure!(
        projections["running"].is_disjoint(&projections["completed"]),
        "Achievement cannot be running and completed"
    );
    if !full {
        return Ok(());
    }
    let string_identifier = |key: &str| {
        !key.is_empty()
            && key.bytes().all(|byte| byte.is_ascii_digit())
            && key
                .parse::<u64>()
                .is_ok_and(|value| value > 0 && value < (1u64 << 31))
    };
    for key in ["variables", "completion_dates"] {
        let values = state[key]
            .as_object()
            .ok_or_else(|| anyhow!("Invalid achievement {key}"))?;
        ensure!(
            values.iter().all(|(name, value)| string_identifier(name)
                && value.as_i64().is_some_and(|value| value >= 0)),
            "Invalid achievement {key}"
        );
    }
    let tracking = state["tracking"]
        .as_array()
        .ok_or_else(|| anyhow!("Invalid tracked achievements"))?;
    ensure!(
        tracking.len() <= 255
            && tracking.iter().all(|value| value
                .as_i64()
                .is_some_and(|value| value > 0 && value < (1i64 << 31))),
        "Invalid tracked achievements"
    );
    let recent = state["recent"]
        .as_array()
        .ok_or_else(|| anyhow!("Invalid recent achievements"))?;
    ensure!(
        recent.len() <= 255
            && recent.iter().all(
                |value| value.as_object().is_some_and(|object| object.len() == 2
                    && object.contains_key("id")
                    && object.contains_key("date_ms"))
                    && value["id"]
                        .as_i64()
                        .is_some_and(|id| id > 0 && id < (1i64 << 31))
                    && value["date_ms"].as_i64().is_some_and(|value| value >= 0)
            ),
        "Invalid recent achievements"
    );
    Ok(())
}
async fn authorize_tutorial(
    tx: &Transaction<'_>,
    actor: &Value,
    seed: &Value,
    resource: &Value,
) -> Result<bool> {
    if integer(actor, "map_id")? != 1361 {
        return Ok(false);
    }
    let id = integer(actor, "id")?;
    let scope = (1i64 << 62)
        .checked_add(id)
        .ok_or_else(|| anyhow!("Invalid introductory scene owner"))?;
    ensure!(
        id > 0
            && id < (1i64 << 48)
            && integer(actor, "instance_id")? == scope
            && seed["item_reference"].as_i64() == Some(30938)
            && seed["action_id"].as_i64() == Some(13435)
            && seed["resource_reference"].as_i64() == Some(824)
            && resource["resource_reference"].as_i64() == Some(824),
        "Incarnam planting exercise is not available"
    );
    ensure!(
        tx.query_opt("SELECT id FROM characters WHERE id=$1 FOR UPDATE", &[&id])
            .await?
            .is_some(),
        "Missing achievement character"
    );
    let (state, full) = if let Some(row) = tx
        .query_opt(
            "SELECT state FROM character_achievement_progress WHERE character_id=$1",
            &[&id],
        )
        .await?
    {
        (row.get::<_, Value>("state"), true)
    } else {
        (tx.query_opt(
            "SELECT snapshot FROM character_achievement_authority WHERE character_id=$1 FOR UPDATE",
            &[&id],
        )
        .await?
        .ok_or_else(|| anyhow!("Missing initialized achievement authority"))?
        .get::<_, Value>("snapshot"), false)
    };
    validate_achievement_projection(&state, full)?;
    ensure!(
        state["running"]
            .as_array()
            .is_some_and(|running| running.iter().any(|quest| quest.as_i64() == Some(5136))),
        "Incarnam planting exercise is not available"
    );
    Ok(true)
}

async fn active_actor(
    ctx: &Context,
    stored: &Value,
    players: &[Value],
    expected: &Value,
) -> Result<Value> {
    let id = integer(stored, "id")?;
    let account = integer(stored, "account_id")?;
    ensure!(id > 0 && account > 0, "Invalid planting actor identity");
    let matches: Vec<_> = players
        .iter()
        .filter(|player| player.get("id").and_then(Value::as_i64) == Some(id))
        .collect();
    ensure!(
        matches.len() == 1,
        "Planting requires one active actor location"
    );
    let live = matches[0];
    ensure!(
        live.get("account_id").and_then(Value::as_i64) == Some(account),
        "Planting actor account does not match its active session"
    );
    ensure!(
        live.get("_ecology_active").unwrap_or(&Value::Bool(true)) == &Value::Bool(true),
        "Planting actor is not active outside combat"
    );
    let at = location(live)?;
    ensure!(
        at == location(expected)?,
        "Planting origin changed during preparation"
    );
    let mut actor = stored
        .as_object()
        .cloned()
        .ok_or_else(|| anyhow!("Invalid planting actor identity"))?;
    for key in LOCATION_KEYS {
        actor.insert(key.to_owned(), live[key].clone());
    }
    if matches!(at[0], 9 | 1440) && at[1] > 0 {
        let owner = at[1];
        let db = ctx.db.get().await?;
        let config = if at[0] == 1440 {
            let row=db.query_opt("SELECT h.character_id AS owner_id,h.appearance_id,h.layout AS rooms,h.locked,h.furniture,h.access FROM account_haven_bags a JOIN haven_bags h ON h.character_id=a.character_id JOIN characters c ON c.id=h.character_id WHERE a.character_id=$1 AND c.deleted_at IS NULL",&[&owner]).await?.ok_or_else(||anyhow!("Ranch requires an authoritative Haven Bag"))?;
            let config = json!({"owner_id":row.get::<_,i64>("owner_id"),"appearance_id":row.get::<_,i32>("appearance_id"),"rooms":row.get::<_,Value>("rooms"),"locked":row.get::<_,bool>("locked"),"furniture":row.get::<_,Value>("furniture"),"access":row.get::<_,Value>("access")});
            if let Some(live_config) = live.get("haven_bag").filter(|config| !config.is_null()) {
                ensure!(
                    *live_config == config,
                    "Ranch Haven Bag configuration is stale"
                );
            }
            ensure!(
                live.get("haven_bag_visitor")
                    .map(Value::is_boolean)
                    .unwrap_or(true),
                "Invalid Ranch visitor authority"
            );
            actor.insert("haven_ranch_session".to_owned(), Value::Bool(true));
            config
        } else if let Some(config) = live
            .get("haven_bag")
            .filter(|config| config.as_object().is_some_and(|map| !map.is_empty()))
        {
            config.clone()
        } else {
            let row=db.query_opt("SELECT h.character_id AS owner_id,h.appearance_id,h.layout AS rooms,h.locked,h.furniture,h.access FROM account_haven_bags a JOIN characters c ON c.account_id=a.account_id JOIN haven_bags h ON h.character_id=a.character_id WHERE c.id=$1",&[&owner]).await?.ok_or_else(||anyhow!("Missing account haven bag"))?;
            json!({"owner_id":row.get::<_,i64>("owner_id"),"appearance_id":row.get::<_,i32>("appearance_id"),"rooms":row.get::<_,Value>("rooms"),"locked":row.get::<_,bool>("locked"),"furniture":row.get::<_,Value>("furniture"),"access":row.get::<_,Value>("access")})
        };
        ensure!(
            config.get("owner_id").and_then(Value::as_i64) == Some(owner),
            "Garden requires an authoritative active Haven Bag"
        );
        actor.insert("haven_bag".to_owned(), config);
        actor.insert(
            "haven_bag_visitor".to_owned(),
            live.get("haven_bag_visitor")
                .cloned()
                .unwrap_or(Value::Bool(false)),
        );
    }
    Ok(Value::Object(actor))
}

/// Exact f32 intermediate arithmetic of the native eGj.PS profession bonus.
pub fn probability(
    ground_percent: i64,
    climate_compatible: bool,
    profession_bonus_percent: f64,
) -> Result<f64> {
    ensure!(
        (0..=100).contains(&ground_percent),
        "Invalid native planting ground threshold"
    );
    ensure!(
        profession_bonus_percent.is_finite()
            && profession_bonus_percent >= i32::MIN as f64
            && profession_bonus_percent < (i32::MAX as f64 + 1.0),
        "Invalid authoritative planting profession bonus"
    );
    let bonus = profession_bonus_percent as f32;
    // Python widens the first f32 to f64 for division, then narrows once more.
    let bonus = ((bonus as f64) / 100.0) as f32;
    Ok(((ground_percent as f64 / 100.0)
        * if climate_compatible { 1.0 } else { 0.8 }
        * (1.0 + bonus as f64))
        .clamp(0.0, 1.0))
}
/// Apply exact native ground precedence to one catalog resource.
fn ground_threshold(ground: &Value, resource: &Value) -> Result<i64> {
    let reference = integer(resource, "resource_reference")?.to_string();
    let family = integer(resource, "family_id")?.to_string();
    let threshold = ground
        .get("resources")
        .and_then(|rows| rows.get(&reference))
        .filter(|value| !value.is_null())
        .or_else(|| ground.get("families").and_then(|rows| rows.get(&family)))
        .cloned()
        .unwrap_or(json!(0));
    threshold
        .as_i64()
        .ok_or_else(|| anyhow!("Invalid native planting ground threshold"))
}

/// Resolve a probability only for one unambiguous exact-height native surface.
pub fn native_cell_probability(
    resource: &Value,
    weather: &str,
    bonus: f64,
    surfaces: &[Value],
    z: i16,
    grounds: &Value,
    climates: &Value,
) -> Result<f64> {
    ensure!(
        matches!(weather, "ABSENT" | "LIGHT" | "HEAVY" | "STORM"),
        "Unknown authoritative planting weather"
    );
    let matching: Vec<_> = surfaces
        .iter()
        .filter(|row| row.get("z").and_then(Value::as_i64) == Some(i64::from(z)))
        .collect();
    ensure!(
        matching.len() == 1,
        "Unknown or ambiguous planting probability surface"
    );
    let climate = climates
        .as_array()
        .ok_or_else(|| anyhow!("Invalid resource climate catalog"))?
        .iter()
        .find(|row| row.get("resource_reference") == resource.get("resource_reference"))
        .ok_or_else(|| anyhow!("Unknown native planting probability context"))?;
    let ground = grounds
        .as_array()
        .ok_or_else(|| anyhow!("Invalid native planting grounds"))?
        .iter()
        .find(|row| row.get("ground_id") == matching[0].get("ground_id"))
        .ok_or_else(|| anyhow!("Unknown native planting probability context"))?;
    let compatible = weather == "ABSENT"
        || climate["climate"] == "NONE"
        || climate["allowed_weather"]
            .as_array()
            .is_some_and(|rows| rows.contains(&json!(weather)));
    probability(ground_threshold(ground, resource)?, compatible, bonus)
}

/// Fixed resource admission belongs to the same native preparation path.
pub fn validate_seed_resource(resource: &Value) -> Result<()> {
    ensure!(
        !fixed_kind(resource, 73),
        "Mining resources cannot be planted"
    );
    ensure!(
        !fixed_kind(resource, 75),
        "Fishing resources cannot be planted"
    );
    Ok(())
}

#[derive(Debug)]
struct EquipmentProjectionUnavailable;
impl std::fmt::Display for EquipmentProjectionUnavailable {
    fn fmt(&self, output: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        output.write_str("Missing or invalid authoritative planting equipment projection")
    }
}
impl std::error::Error for EquipmentProjectionUnavailable {}

fn equipment_projection(
    snapshot: &Value,
    intent: &Value,
    profession: i64,
    body: &[u8],
) -> Result<f64> {
    let unavailable = || anyhow::Error::new(EquipmentProjectionUnavailable);
    let entries = snapshot
        .get("planting_equipment")
        .and_then(Value::as_array)
        .ok_or_else(unavailable)?;
    if entries.len() > 4 {
        return Err(unavailable());
    }
    let matching: Vec<_> = entries
        .iter()
        .filter(|entry| entry.get("intent_id") == intent.get("id"))
        .collect();
    if matching.len() != 1 {
        return Err(unavailable());
    }
    let projection = matching[0];
    for field in [
        "intent_version",
        "world_epoch",
        "account_id",
        "generation",
        "character_id",
    ] {
        if projection.get(field) != intent.get(field) || projection.get(field).is_none() {
            return Err(unavailable());
        }
    }
    if projection.get("profession_id").and_then(Value::as_i64) != Some(profession)
        || projection.get("body_hex").and_then(Value::as_str) != Some(hex::encode(body).as_str())
    {
        return Err(unavailable());
    }
    match (projection.get("plant_probability"), projection.get("error")) {
        (Some(value), None) => value
            .as_i64()
            .map(|value| value as f64)
            .ok_or_else(unavailable),
        (None, Some(Value::String(message))) => Err(anyhow!(message.clone())),
        _ => Err(unavailable()),
    }
}

pub async fn probability_for(
    ctx: &Context,
    snapshot: &Value,
    intent: &Value,
    body: &[u8],
    actor: &Value,
    request: &Value,
    seed: &Value,
    resource: &Value,
    z: i16,
    open_policy: bool,
) -> Result<f64> {
    let map = i32::try_from(integer(actor, "map_id")?)?;
    if map == 1361 {
        let mut db = ctx.db.get().await?;
        let tx = db.transaction().await?;
        authorize_tutorial(&tx, actor, seed, resource).await?;
        tx.commit().await?;
        return Ok(1.0);
    }
    let x = i32::try_from(integer(request, "x")?)?;
    let y = i32::try_from(integer(request, "y")?)?;
    if map == 9 {
        let bonus = equipment_projection(snapshot, intent, integer(seed, "profession_id")?, body)?;
        ensure!(
            !resource["monster_resource"]
                .as_bool()
                .ok_or_else(|| anyhow!("Invalid native resource type"))?,
            "Monster reproduction is unavailable inside private gardens"
        );
        let grounds = ctx.catalog.document("planting-grounds.json").await?;
        let ground = grounds
            .as_array()
            .ok_or_else(|| anyhow!("Invalid native planting grounds"))?
            .iter()
            .find(|row| row.get("ground_id").and_then(Value::as_i64) == Some(28))
            .ok_or_else(|| anyhow!("Native Haven Bag garden ground is unavailable"))?;
        let threshold = ground_threshold(ground, resource)?;
        let chance = probability(threshold, true, bonus)?;
        ensure!(
            chance > 0.0,
            "This resource cannot grow on native garden ground"
        );
        return Ok(chance);
    }
    if open_policy {
        let db = ctx.db.get().await?;
        let row = db
            .query_opt(
                "SELECT value FROM settings WHERE name='open_planting_probability'",
                &[],
            )
            .await?;
        let value = row
            .and_then(|row| row.get::<_, Value>("value").as_f64())
            .ok_or_else(|| anyhow!("Invalid authoritative planting roll"))?;
        ensure!(
            value.is_finite() && (0.0..=1.0).contains(&value),
            "Invalid authoritative planting roll"
        );
        return Ok(value);
    }
    let region = ctx.catalog.territory_region(map, x, y).await?;
    let weather =
        weather::context_weather(ctx, map, integer(actor, "instance_id")?, region).await?;
    let bonus = equipment_projection(snapshot, intent, integer(seed, "profession_id")?, body)?;
    let surfaces = ctx.catalog.surfaces_at(map, x, y).await?;
    let climates = ctx.catalog.document("resource-climates.json").await?;
    let grounds = ctx.catalog.document("planting-grounds.json").await?;
    native_cell_probability(resource, &weather, bonus, &surfaces, z, &grounds, &climates)
}

async fn prepare_one(
    ctx: &Context,
    snapshot: &Value,
    intent: &Value,
    body: &[u8],
) -> Result<Value> {
    let request = decode(body)?;
    let account = integer(intent, "account_id")?;
    let character = integer(intent, "character_id")?;
    let generation = intent["generation"]
        .as_str()
        .ok_or_else(|| anyhow!("Invalid inventory session"))?;
    let mut db = ctx.db.get().await?;
    let tx = db.transaction().await?;
    ensure!(tx.query_opt("SELECT 1 FROM sessions s JOIN characters c ON c.id=s.character_id AND c.account_id=s.account_id WHERE s.account_id=$1 AND s.generation=$2 AND s.character_id=$3 AND s.expires_at>CURRENT_TIMESTAMP AND c.deleted_at IS NULL",&[&account,&generation,&character]).await?.is_some(),"Invalid inventory session");
    let stored=tx.query_opt("SELECT to_jsonb(c) AS row FROM characters c WHERE c.account_id=$1 AND c.id=$2 AND c.deleted_at IS NULL",&[&account,&character]).await?.ok_or_else(||anyhow!("Personaje no encontrado."))?.get::<_,Value>("row");
    let actor = active_actor(
        ctx,
        &stored,
        snapshot
            .get("players")
            .and_then(Value::as_array)
            .map(Vec::as_slice)
            .unwrap_or(&[]),
        &intent["actor_location"],
    )
    .await?;
    let uid = integer(&request, "item_uid")?;
    let item = tx
        .query_opt(
            "SELECT to_jsonb(i) AS row FROM inventory_items i WHERE uid=$1 AND character_id=$2",
            &[&uid, &character],
        )
        .await?
        .ok_or_else(|| anyhow!("Seed unavailable or foreign"))?
        .get::<_, Value>("row");
    let seeds = ctx.catalog.document("seed-actions.json").await?;
    let seed = seeds
        .as_array()
        .ok_or_else(|| anyhow!("Invalid native seed actions"))?
        .iter()
        .find(|seed| seed.get("item_reference") == item.get("reference"))
        .ok_or_else(|| anyhow!("Unknown, mismatched or conditional seed action"))?;
    let open_policy = snapshot
        .get("open_planting")
        .and_then(Value::as_bool)
        .unwrap_or(true);
    ensure!(
        seed.get("action_id") == request.get("action_id")
            && !(seed
                .get("has_item_criteria")
                .and_then(Value::as_bool)
                .unwrap_or(false)
                && !open_policy),
        "Unknown, mismatched or conditional seed action"
    );
    let resource = ctx
        .catalog
        .resource_definition(integer(seed, "resource_reference")?)
        .await
        .context("Unknown native resource reference")?;
    validate_seed_resource(&resource)?;
    authorize_tutorial(&tx, &actor, seed, &resource).await?;
    let profession = i32::try_from(integer(seed, "profession_id")?)?;
    let learned = tx
        .query_opt(
            "SELECT xp FROM account_professions WHERE account_id=$1 AND profession_id=$2",
            &[&account, &profession],
        )
        .await?
        .map(|row| row.get::<_, i64>("xp"))
        .map(profession_level)
        .transpose()?;
    ensure!(
        learned.is_some_and(
            |level| open_policy || level >= seed["minimum_level"].as_i64().unwrap_or(i64::MAX)
        ),
        "Profession unlearned or below seed requirement"
    );
    tx.commit().await?;
    drop(db);
    let z = planting_policy::authorize_cell(ctx, &actor, &request, seed, &resource, open_policy)
        .await?;
    let chance = probability_for(
        ctx,
        snapshot,
        intent,
        body,
        &actor,
        &request,
        seed,
        &resource,
        z,
        open_policy,
    )
    .await?;
    let db = ctx.db.get().await?;
    let duration = db
        .query_opt(
            "SELECT value FROM settings WHERE name='planting_duration_ms'",
            &[],
        )
        .await?
        .and_then(|row| row.get::<_, Value>("value").as_i64())
        .filter(|value| (1..=300000).contains(value))
        .ok_or_else(|| anyhow!("Invalid PostgreSQL planting duration"))?;
    let mut character_out = Map::new();
    for key in ["id", "account_id", "map_id", "instance_id", "x", "y", "z"] {
        character_out.insert(key.to_owned(), actor[key].clone());
    }
    Ok(
        json!({"character":character_out,"request":request,"seed":seed,"definition":resource,"z":z,"probability":chance,"duration_ms":duration}),
    )
}

fn infrastructure_failure(error: &anyhow::Error) -> bool {
    error.chain().any(|cause| {
        cause.is::<tokio_postgres::Error>()
            || cause.is::<deadpool_postgres::PoolError>()
            || cause.is::<EquipmentProjectionUnavailable>()
    })
}

/// Resolve at most four reserved player intents without claiming World ownership.
pub async fn prepare(ctx: &Context, snapshot: &Value, limit: usize) -> Result<Vec<Value>> {
    ensure!((1..=64).contains(&limit), "Invalid planting intent batch");
    let start = snapshot
        .get("started_at_ms")
        .and_then(Value::as_i64)
        .filter(|value| *value > 0 && *value < (1i64 << 53))
        .ok_or_else(|| anyhow!("Missing or invalid planting snapshot start time"))?;
    let epoch = snapshot
        .get("world_epoch")
        .and_then(Value::as_str)
        .ok_or_else(|| anyhow!("Missing ecology world epoch"))?;
    ensure!(
        snapshot
            .get("open_planting")
            .map(Value::is_boolean)
            .unwrap_or(true),
        "Invalid open planting probability policy"
    );
    let db = ctx.db.get().await?;
    let limit = i64::try_from(limit)?;
    let rows=db.query("SELECT to_jsonb(i)-'body' AS intent,i.body FROM ecology_planting_intents i WHERE world_epoch=$1 AND status='pending' AND created_at<to_timestamp($2::bigint/1000.0) ORDER BY intent_version LIMIT $3",&[&epoch,&start,&limit]).await?;
    drop(db);
    let mut plans = Vec::new();
    for row in rows {
        let intent: Value = row.get("intent");
        let body: Vec<u8> = row.get("body");
        let mut envelope = Map::new();
        for key in [
            "world_epoch",
            "intent_id",
            "intent_version",
            "account_id",
            "generation",
            "character_id",
        ] {
            let source = if key == "intent_id" { "id" } else { key };
            envelope.insert(
                key.to_owned(),
                intent
                    .get(source)
                    .cloned()
                    .ok_or_else(|| anyhow!("Incomplete planting intent identity"))?,
            );
        }
        envelope.insert("body_hex".to_owned(), json!(hex::encode(&body)));
        match prepare_one(ctx, snapshot, &intent, &body).await {
            Ok(prepared) => {
                envelope.insert("kind".to_owned(), json!("planting_begin"));
                envelope.insert("prepared".to_owned(), prepared);
            }
            Err(error) => {
                if infrastructure_failure(&error) {
                    return Err(error);
                }
                envelope.insert("kind".to_owned(), json!("planting_rejected"));
                envelope.insert("error".to_owned(), json!(error.to_string()));
            }
        }
        plans.push(Value::Object(envelope));
    }
    Ok(plans)
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn native_request_has_exact_signed_big_endian_shape() {
        let mut body = Vec::new();
        body.extend(13435i32.to_be_bytes());
        body.extend(1234567890123i64.to_be_bytes());
        body.extend((-12i32).to_be_bytes());
        body.extend(27i32.to_be_bytes());
        assert_eq!(
            decode(&body).unwrap(),
            json!({"action_id":13435,"item_uid":1234567890123i64,"x":-12,"y":27})
        );
        assert!(decode(&body[..19]).is_err());
        body[0..4].copy_from_slice(&(-1i32).to_be_bytes());
        assert!(decode(&body).is_err());
    }
    #[test]
    fn native_probability_preserves_f32_bonus_and_clamp() {
        assert_eq!(
            probability(50, true, 12.0).unwrap(),
            0.5 * (1.0 + (12f32 as f64 / 100.0) as f32 as f64)
        );
        assert_eq!(probability(100, true, 100.0).unwrap(), 1.0);
        assert_eq!(probability(10, false, -100.0).unwrap(), 0.0);
        assert!(probability(101, true, 0.0).is_err());
        assert!(probability(20, true, f64::NAN).is_err());
    }
    #[test]
    fn profession_level_uses_cumulative_integer_sqrt() {
        assert_eq!(profession_level(0).unwrap(), 0);
        assert_eq!(profession_level(299).unwrap(), 1);
        assert_eq!(profession_level(300).unwrap(), 2);
        assert_eq!(profession_level(3_000_000).unwrap(), 200);
        assert!(profession_level(-1).is_err());
    }
    #[test]
    fn achievement_authority_preserves_duplicate_lists_but_rejects_overlap() {
        let state = json!({"running":[5136,5136],"completed":[],"objectives":[]});
        assert!(validate_achievement_projection(&state, false).is_ok());
        assert!(validate_achievement_projection(
            &json!({"running":[5136],"completed":[5136],"objectives":[]}),
            false
        )
        .is_err());
        assert!(validate_achievement_projection(&state, true).is_err());
    }
    fn projected_intent() -> (Value, Value, Vec<u8>) {
        let body = vec![1u8; 20];
        let intent = json!({"id":"intent-a","intent_version":7,"world_epoch":"world-a","account_id":9,"generation":"lease-a","character_id":11});
        let projection = json!({"intent_id":"intent-a","intent_version":7,"world_epoch":"world-a","account_id":9,"generation":"lease-a","character_id":11,"profession_id":71,"body_hex":hex::encode(&body),"plant_probability":12});
        (intent, projection, body)
    }
    #[test]
    fn equipment_projection_is_fenced_by_request_owner_and_version() {
        let (intent, projection, body) = projected_intent();
        assert_eq!(
            equipment_projection(
                &json!({"planting_equipment":[projection.clone()]}),
                &intent,
                71,
                &body
            )
            .unwrap(),
            12.0
        );
        for field in [
            "intent_id",
            "intent_version",
            "world_epoch",
            "account_id",
            "generation",
            "character_id",
            "profession_id",
            "body_hex",
        ] {
            let mut stale = projection.clone();
            stale[field] = Value::Null;
            let error =
                equipment_projection(&json!({"planting_equipment":[stale]}), &intent, 71, &body)
                    .unwrap_err();
            assert!(
                infrastructure_failure(&error),
                "{field} must remain retryable"
            );
        }
        assert!(equipment_projection(
            &json!({"planting_equipment":[projection.clone(),projection]}),
            &intent,
            71,
            &body
        )
        .is_err());
    }
    #[test]
    fn missing_projection_retries_but_owned_policy_rejection_is_preserved() {
        let (intent, mut projection, body) = projected_intent();
        let missing = equipment_projection(&json!({}), &intent, 71, &body).unwrap_err();
        assert!(infrastructure_failure(&missing));
        projection
            .as_object_mut()
            .unwrap()
            .remove("plant_probability");
        projection["error"] = json!("Invalid equipment profession sheet");
        let error = equipment_projection(
            &json!({"planting_equipment":[projection]}),
            &intent,
            71,
            &body,
        )
        .unwrap_err();
        assert_eq!(error.to_string(), "Invalid equipment profession sheet");
        assert!(!infrastructure_failure(&error));
    }
    #[test]
    fn location_accepts_large_private_instance_without_float_round_trip() {
        let actor = json!({"map_id":1361,"instance_id":(1i64<<62)+42,"x":-12,"y":0,"z":-13});
        assert_eq!(location(&actor).unwrap()[1], (1i64 << 62) + 42);
    }
}
