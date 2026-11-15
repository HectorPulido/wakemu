//! Durable corpse/publication work and read-only native habitat preparation.
//!
//! World remains the sole allocator/registrar of initial population actors.
use std::collections::{HashMap, HashSet};

use anyhow::{anyhow, ensure, Context as _, Result};
use chrono::{DateTime, SecondsFormat, Utc};
use serde::Deserialize;
use serde_json::{json, Value};
use tokio_postgres::Transaction;

use crate::{identity, Context};

use super::native_monster;

type Habitat = (i32, i64, i32);
type Point = (i32, i32, i16);

#[derive(Clone, Debug)]
struct Member {
    reference: i64,
    level: i32,
    point: Point,
}

#[derive(Clone, Debug)]
struct Plan {
    habitat: Habitat,
    members: Vec<Member>,
    value: Value,
}

fn integer(value: &Value, name: &str) -> Result<i64> {
    value
        .get(name)
        .and_then(Value::as_i64)
        .ok_or_else(|| anyhow!("Missing or invalid initial population {name}"))
}

fn exact_keys(value: &Value, names: &[&str]) -> bool {
    value.as_object().is_some_and(|object| {
        object.len() == names.len() && names.iter().all(|name| object.contains_key(*name))
    })
}

fn point(value: &Value) -> Result<Point> {
    Ok((
        i32::try_from(integer(value, "x")?).context("Invalid monster x coordinate")?,
        i32::try_from(integer(value, "y")?).context("Invalid monster y coordinate")?,
        i16::try_from(integer(value, "z")?).context("Invalid monster z coordinate")?,
    ))
}

#[derive(Deserialize)]
struct NativeWalkingGeometry {
    map_id: i32,
    cells: Vec<Point>,
    edges: Vec<(Point, Point)>,
}

fn parse_plans(catalog: &Value) -> Result<Vec<Plan>> {
    ensure!(
        exact_keys(catalog, &["version", "scope", "plans"])
            && catalog["version"].as_i64() == Some(1)
            && catalog["scope"].is_string(),
        "Invalid initial monster habitat catalog"
    );
    let rows = catalog["plans"]
        .as_array()
        .ok_or_else(|| anyhow!("Invalid initial monster habitat plans"))?;
    let mut plans = Vec::with_capacity(rows.len());
    let mut seen = HashSet::new();
    for row in rows {
        ensure!(
            exact_keys(row, &["map_id", "instance_id", "region_id", "members"]),
            "Invalid configured initial monster habitat"
        );
        let map = i32::try_from(integer(row, "map_id")?)?;
        let instance = integer(row, "instance_id")?;
        let region = i32::try_from(integer(row, "region_id")?)?;
        let habitat = (map, instance, region);
        ensure!(
            map > 0 && instance == 0 && region > 0 && seen.insert(habitat),
            "Invalid or repeated initial monster habitat identity"
        );
        let rows = row["members"]
            .as_array()
            .filter(|members| members.len() == 2)
            .ok_or_else(|| anyhow!("Initial pilot requires two adjacent monsters"))?;
        let mut members = Vec::with_capacity(2);
        for row in rows {
            ensure!(
                exact_keys(row, &["reference", "level", "x", "y", "z"]),
                "Invalid configured initial monster"
            );
            let level = i32::try_from(integer(row, "level")?)?;
            ensure!((1..32768).contains(&level), "Invalid initial monster level");
            members.push(Member {
                reference: integer(row, "reference")?,
                level,
                point: point(row)?,
            });
        }
        plans.push(Plan {
            habitat,
            members,
            value: row.clone(),
        });
    }
    Ok(plans)
}

async fn validate_configured(
    ctx: &Context,
    plans: &[Plan],
    completed: &HashSet<Habitat>,
) -> Result<()> {
    // Keep only the currently inspected native geometry. Source catalog caching
    // is bounded independently; no second map-sized cell/edge index is retained.
    let mut current_geometry: Option<(i32, NativeWalkingGeometry)> = None;
    for plan in plans {
        let (map, _, region) = plan.habitat;
        for member in &plan.members {
            // Native constructor validity depends only on reference/level and
            // the immutable publication. Position fields are copied verbatim;
            // parse_plans already bounds them and this call uses valid map/ID.
            let proof = format!(
                "initial-population:constructor:{}:{}",
                member.reference, member.level
            );
            if !ctx.catalog.immutable_validation_cached(&proof).await? {
                let (x, y, z) = member.point;
                native_monster::owned_instance(
                    ctx,
                    member.reference,
                    member.level,
                    -1,
                    map,
                    x,
                    y,
                    z,
                )
                .await?;
                ctx.catalog.remember_immutable_validation(&proof);
            }
        }
        if completed.contains(&plan.habitat) {
            // A permanent durable marker forbids reseeding, even after defeat.
            // Preserve the old shape/stat validation without loading geometry.
            continue;
        }
        let geometry_proof = format!(
            "initial-population:geometry:{}",
            identity::digest(&plan.value)?
        );
        if ctx
            .catalog
            .immutable_validation_cached(&geometry_proof)
            .await?
        {
            continue;
        }
        if current_geometry.as_ref().map(|entry| entry.0) != Some(map) {
            let raw = ctx
                .catalog
                .document_bytes(&format!("combat-maps/{map}.json"))
                .await?;
            let geometry: NativeWalkingGeometry = serde_json::from_slice(&raw)?;
            ensure!(
                geometry.map_id == map,
                "Combat map export identity mismatch"
            );
            current_geometry = Some((map, geometry));
        }
        let geometry = &current_geometry.as_ref().expect("geometry loaded").1;
        for member in &plan.members {
            let walkable = geometry.cells.contains(&member.point);
            let (x, y, z) = member.point;
            ensure!(
                walkable && ctx.catalog.surface_region(map, x, y, z).await? == region,
                "Initial pilot cell is outside walkable native habitat"
            );
        }
        let first = plan.members[0].point;
        let second = plan.members[1].point;
        let mut forward = false;
        let mut backward = false;
        for &(start, end) in &geometry.edges {
            forward |= start == first && end == second;
            backward |= start == second && end == first;
            if forward && backward {
                break;
            }
        }
        ensure!(
            forward && backward,
            "Initial pilot members lack a bidirectional native walking edge"
        );
        ctx.catalog.remember_immutable_validation(&geometry_proof);
    }
    Ok(())
}

async fn native_regions(ctx: &Context) -> Result<HashMap<(i32, i32), Value>> {
    let catalog = ctx.catalog.document("ecology-regions.json").await?;
    let worlds = catalog
        .as_array()
        .ok_or_else(|| anyhow!("Invalid native ecology regions"))?;
    let mut regions = HashMap::new();
    for world in worlds {
        let map = i32::try_from(integer(world, "map_id")?)?;
        for region in world["regions"]
            .as_array()
            .ok_or_else(|| anyhow!("Invalid native ecology region list"))?
        {
            regions.insert(
                (map, i32::try_from(integer(region, "region_id")?)?),
                region.clone(),
            );
        }
    }
    Ok(regions)
}

fn population_count(population: &Value, region: i32) -> Result<i64> {
    ensure!(
        population["complete"].as_bool() == Some(true),
        "Initial monster population has unresolved native regions"
    );
    let Some(counts) = population["regions"]
        .get(region.to_string())
        .and_then(|value| value.get("monster"))
    else {
        return Ok(0);
    };
    let mut count = 0_i64;
    for value in counts
        .as_object()
        .ok_or_else(|| anyhow!("Invalid region monster counts"))?
        .values()
    {
        count = count
            .checked_add(
                value
                    .as_i64()
                    .filter(|n| *n >= 0)
                    .ok_or_else(|| anyhow!("Invalid monster count"))?,
            )
            .ok_or_else(|| anyhow!("Monster population count overflow"))?;
    }
    Ok(count)
}

async fn scope_state(tx: &Transaction<'_>, map: i32, instance: i64) -> Result<Value> {
    let groups = tx
        .query(
            "SELECT group_id,status,members FROM combat_groups WHERE map_id=$1 \
             AND instance_id=$2 ORDER BY group_id",
            &[&map, &instance],
        )
        .await?
        .into_iter()
        .map(|row| {
            json!({
                "group_id": row.get::<_, i64>("group_id"),
                "status": row.get::<_, String>("status"),
                "members": row.get::<_, Value>("members"),
            })
        })
        .collect::<Vec<_>>();
    let plants = tx
        .query(
            "SELECT resource_uid,resource_reference,stage,x,y,z FROM planted_resources \
             WHERE map_id=$1 AND instance_id=$2 ORDER BY resource_uid",
            &[&map, &instance],
        )
        .await?
        .into_iter()
        .map(|row| {
            json!({
                "resource_uid": row.get::<_, i64>("resource_uid"),
                "resource_reference": row.get::<_, i32>("resource_reference"),
                "stage": row.get::<_, i16>("stage"),
                "x": row.get::<_, i32>("x"),
                "y": row.get::<_, i32>("y"),
                "z": row.get::<_, i16>("z"),
            })
        })
        .collect::<Vec<_>>();
    Ok(json!([groups, plants]))
}

fn validate_policy(policy: &Value, member_count: usize) -> Result<bool> {
    let enabled = policy.get("enabled").and_then(Value::as_bool);
    let version = policy.get("version").and_then(Value::as_i64);
    let members = policy.get("members_per_zone").and_then(Value::as_i64);
    ensure!(
        policy.is_object()
            && enabled.is_some()
            && version.is_some_and(|v| v > 0)
            && members.is_some_and(|v| (1..=8).contains(&v)),
        "Invalid initial monster population policy"
    );
    if enabled == Some(false) {
        return Ok(false);
    }
    ensure!(
        members == Some(member_count as i64),
        "Initial monster plan violates population policy"
    );
    Ok(true)
}

async fn prepare_zone(ctx: &Context, plan: &Plan, region: &Value) -> Result<Option<Value>> {
    let (map, instance, region_id) = plan.habitat;
    let mut client = ctx.db.get().await?;
    let tx = client
        .build_transaction()
        .isolation_level(tokio_postgres::IsolationLevel::RepeatableRead)
        .read_only(true)
        .start()
        .await?;
    let completed = tx
        .query_opt(
            "SELECT 1 FROM monster_initial_population \
             WHERE map_id=$1 AND instance_id=$2 AND region_id=$3",
            &[&map, &instance, &region_id],
        )
        .await?
        .is_some();
    if completed {
        tx.commit().await?;
        return Ok(None);
    }
    let policy = tx
        .query_opt(
            "SELECT value FROM settings WHERE name='monster_initial_population'",
            &[],
        )
        .await?
        .map(|row| row.get::<_, Value>("value"))
        .unwrap_or(Value::Null);
    if !validate_policy(&policy, plan.members.len())? {
        tx.commit().await?;
        return Ok(None);
    }
    // Exactly the strict planting-height locator used by Python prepare_zone:
    // exclude explicit -1 regions, but retain unknown/invalid region failures.
    let population = ctx
        .catalog
        .population_snapshot_with_policy(&tx, map, instance, &["monster"], false, true)
        .await?;
    let count = population_count(&population, region_id)?;
    let capacity = integer(region, "monster_capacity")?;
    ensure!(
        count
            .checked_add(plan.members.len() as i64)
            .is_some_and(|value| value <= capacity),
        "Initial monster plan exceeds regional capacity"
    );
    let allowed = region["monster_families"]
        .as_array()
        .ok_or_else(|| anyhow!("Missing native habitat families"))?
        .iter()
        .map(|family| integer(family, "family_id"))
        .collect::<Result<HashSet<_>>>()?;
    let mut families = HashSet::new();
    for member in &plan.members {
        let definition = ctx.catalog.monster_definition(member.reference).await?;
        families.insert(integer(&definition, "family_id")?);
    }
    ensure!(
        families.len() == 1 && families.is_subset(&allowed),
        "Initial monster plan has a foreign family"
    );
    let state = scope_state(&tx, map, instance).await?;
    let mut occupied = HashSet::new();
    for group in state[0].as_array().expect("scope groups array") {
        if group["status"] == "defeated" {
            continue;
        }
        for member in group["members"]
            .as_array()
            .ok_or_else(|| anyhow!("Invalid durable monster roster"))?
        {
            occupied.insert(point(member)?);
        }
    }
    for resource in state[1].as_array().expect("scope plants array") {
        occupied.insert(point(resource)?);
    }
    let positions = plan
        .members
        .iter()
        .map(|member| member.point)
        .collect::<HashSet<_>>();
    ensure!(
        positions.len() == plan.members.len() && positions.is_disjoint(&occupied),
        "Initial monster cells are occupied"
    );
    let digest = identity::digest(&state)?;
    let prepared = json!({
        "plan": plan.value,
        "policy": policy,
        "scope_digest": digest,
        "catalog_revision": ctx.catalog.revision(),
    });
    tx.commit().await?;
    Ok(Some(prepared))
}

fn timestamp(value: DateTime<Utc>) -> String {
    // Python datetime.isoformat emits six fractional digits when microseconds
    // are nonzero, and no fraction when zero. Use +00:00 rather than Z.
    value.to_rfc3339_opts(
        if value.timestamp_subsec_micros() == 0 {
            SecondsFormat::Secs
        } else {
            SecondsFormat::Micros
        },
        false,
    )
}

pub async fn prepare(ctx: &Context, snapshot: &Value, limit: usize) -> Result<Vec<Value>> {
    ensure!(
        (1..=256).contains(&limit),
        "Invalid ecology population preparation limit"
    );
    let epoch = snapshot
        .get("world_epoch")
        .and_then(Value::as_str)
        .filter(|epoch| !epoch.is_empty())
        .ok_or_else(|| anyhow!("Missing world epoch"))?;
    let mut client = ctx.db.get().await?;
    let tx = client.transaction().await?;
    let mut proposals = Vec::with_capacity(limit);
    for row in tx
        .query(
            "SELECT actor_id,map_id,instance_id,expires_at,consumed_at FROM monster_corpses \
             WHERE NOT expiry_published AND \
             (expires_at<=CURRENT_TIMESTAMP OR consumed_at IS NOT NULL) \
             ORDER BY expires_at,actor_id LIMIT $1",
            &[&(limit as i64)],
        )
        .await?
    {
        proposals.push(json!({
            "kind": "corpse_expiry", "world_epoch": epoch,
            "actor_id": row.get::<_,i64>("actor_id"),
            "map_id": row.get::<_,i64>("map_id"),
            "instance_id": row.get::<_,i64>("instance_id"),
            "expires_at": timestamp(row.get::<_,DateTime<Utc>>("expires_at")),
            "consumed_at": row.get::<_,Option<DateTime<Utc>>>("consumed_at").map(timestamp),
        }));
    }
    if proposals.len() < limit {
        for row in tx
            .query(
                "SELECT map_id,instance_id,region_id,group_id FROM monster_initial_population_publication \
                 WHERE published_at IS NULL ORDER BY map_id,instance_id,region_id LIMIT $1",
                &[&((limit - proposals.len()) as i64)],
            )
            .await?
        {
            proposals.push(json!({
                "kind":"initial_publish", "world_epoch": epoch,
                "map_id":row.get::<_,i32>("map_id"),
                "instance_id":row.get::<_,i64>("instance_id"),
                "region_id":row.get::<_,i32>("region_id"),
                "group_id":row.get::<_,i64>("group_id"),
            }));
        }
    }
    let completed = tx
        .query(
            "SELECT map_id,instance_id,region_id FROM monster_initial_population",
            &[],
        )
        .await?
        .into_iter()
        .map(|row| {
            (
                row.get::<_, i32>("map_id"),
                row.get::<_, i64>("instance_id"),
                row.get::<_, i32>("region_id"),
            )
        })
        .collect::<HashSet<_>>();
    tx.commit().await?;
    drop(client);
    if proposals.len() == limit {
        return Ok(proposals);
    }
    let plans = parse_plans(
        &ctx.catalog
            .document("initial-monster-population.json")
            .await?,
    )?;
    validate_configured(ctx, &plans, &completed).await?;
    let regions = native_regions(ctx).await?;
    for plan in plans {
        if completed.contains(&plan.habitat) {
            continue;
        }
        let region = regions
            .get(&(plan.habitat.0, plan.habitat.2))
            .ok_or_else(|| anyhow!("Unknown native initial monster habitat"))?;
        if let Some(mut payload) = prepare_zone(ctx, &plan, region).await? {
            let object = payload.as_object_mut().expect("prepared population object");
            object.insert("kind".into(), json!("initial_population"));
            object.insert("world_epoch".into(), json!(epoch));
            proposals.push(payload);
        }
        if proposals.len() == limit {
            break;
        }
    }
    Ok(proposals)
}

#[cfg(test)]
mod tests {
    use super::*;
    use chrono::TimeZone;

    fn catalog() -> Value {
        json!({"version":1,"scope":"native pilot","plans":[{
            "map_id":1134,"instance_id":0,"region_id":12,
            "members":[
                {"reference":5525,"level":1,"x":-1,"y":2,"z":-1},
                {"reference":5525,"level":1,"x":0,"y":2,"z":-1}
            ]
        }]})
    }

    #[test]
    fn configured_plans_preserve_negative_coordinates_and_validate_shape() {
        let value = catalog();
        let plans = parse_plans(&value).unwrap();
        assert_eq!(plans[0].members[0].point, (-1, 2, -1));
        assert_eq!(plans[0].value, value["plans"][0]);
        let mut repeated = value.clone();
        repeated["plans"]
            .as_array_mut()
            .unwrap()
            .push(value["plans"][0].clone());
        assert!(parse_plans(&repeated).is_err());
        let mut private = value.clone();
        private["plans"][0]["instance_id"] = json!(1_i64 << 62);
        assert!(parse_plans(&private).is_err());
        let mut boolean = value;
        boolean["plans"][0]["members"][0]["x"] = json!(true);
        assert!(parse_plans(&boolean).is_err());
    }

    #[test]
    fn incomplete_population_never_becomes_zero_capacity() {
        assert!(population_count(&json!({"complete":false,"regions":{}}), 12).is_err());
        assert_eq!(
            population_count(&json!({"complete":true,"regions":{}}), 12).unwrap(),
            0
        );
        assert_eq!(
            population_count(
                &json!({"complete":true,"regions":{"12":{"monster":{"1":2,"2":3}}}}),
                12
            )
            .unwrap(),
            5
        );
    }

    #[test]
    fn paused_policy_stays_explicit_and_malformed_policies_fail() {
        assert!(!validate_policy(
            &json!({"enabled":false,"version":1,"members_per_zone":2}),
            2
        )
        .unwrap());
        assert!(
            validate_policy(&json!({"enabled":true,"version":1,"members_per_zone":2}), 2).unwrap()
        );
        assert!(
            validate_policy(&json!({"enabled":true,"version":1,"members_per_zone":2}), 1).is_err()
        );
        assert!(validate_policy(
            &json!({"enabled":true,"version":true,"members_per_zone":2}),
            2
        )
        .is_err());
    }

    #[test]
    fn postgres_timestamp_matches_python_isoformat_precision() {
        let seconds = Utc.with_ymd_and_hms(2026, 11, 14, 5, 0, 0).unwrap();
        assert_eq!(timestamp(seconds), "2026-11-14T05:00:00+00:00");
        assert_eq!(
            timestamp(seconds + chrono::Duration::microseconds(123000)),
            "2026-11-14T05:00:00.123000+00:00"
        );
    }
}

#[cfg(test)]
#[path = "legacy_population_contract.rs"]
mod legacy_population_contract;
