//! Native ffC/ffx monster creation and ordinary world appearance qualification.
//!
//! These are the existing native curves and constructor bounds, not ecological
//! species recommendations or a replacement for authoritative World admission.
use anyhow::{anyhow, ensure, Context as _, Result};
use serde_json::{json, Value};
use std::collections::{BTreeMap, HashMap, HashSet, VecDeque};
use std::sync::{Mutex, OnceLock};

use crate::Context;

fn integer(value: &Value, name: &str) -> Result<i64> {
    value
        .as_i64()
        .ok_or_else(|| anyhow!("Invalid native {name}"))
}
fn number(value: &Value, name: &str) -> Result<f64> {
    let result = value
        .as_f64()
        .ok_or_else(|| anyhow!("Invalid native {name}"))?;
    ensure!(result.is_finite(), "Invalid native {name}");
    Ok(result)
}
fn native_float(value: &Value, name: &str) -> Result<f64> {
    let result = number(value, name)? as f32;
    ensure!(
        result.is_finite(),
        "Native float curve exceeds IEEE754 binary32"
    );
    Ok(f64::from(result))
}

/// Native Java d2i saturates, then the following integer addition wraps.
fn native_increment(base: i64, growth: f64) -> Result<i32> {
    let base = i32::try_from(base).context("Invalid native curve base")?;
    Ok(base.wrapping_add(growth as i32))
}

pub fn statistics(monster: &Value, level: i32) -> Result<BTreeMap<String, i32>> {
    ensure!((1..32768).contains(&level), "Invalid monster level");
    let base_level = integer(&monster["min_level"], "monster base level")?;
    let curves = monster["statistics"]
        .as_object()
        .context("Missing native monster curves")?;
    curves
        .iter()
        .map(|(name, curve)| {
            let per_level = native_float(&curve["per_level"], "monster growth")?;
            let result = native_increment(
                integer(&curve["base"], "monster curve base")?,
                (i64::from(level) - base_level) as f64 * per_level,
            )?;
            Ok((name.clone(), result))
        })
        .collect()
}

/// Return the fresh native characteristic maps, preserving all definition keys.
pub fn npc_creation_values(profile: &Value, definitions: &Value, level: i32) -> Result<Value> {
    ensure!(
        (0..32768).contains(&level),
        "Missing native NPC profile or level"
    );
    let definitions = definitions
        .as_object()
        .context("Missing native characteristic catalog")?;
    let mut characteristic_ids = HashSet::new();
    for key in definitions.keys() {
        ensure!(
            characteristic_ids.insert(
                key.parse::<i32>()
                    .context("Invalid native characteristic identity")?
            ),
            "Duplicate native characteristic identity"
        );
    }
    for key in ["1", "2", "3", "4", "9", "32", "35", "92", "97", "100"] {
        ensure!(
            definitions.contains_key(key),
            "Incomplete native characteristic catalog"
        );
    }
    let mut values = profile["at_base_level"]
        .as_object()
        .context("Missing native NPC base values")?
        .clone();
    ensure!(
        values.len() == definitions.len() && values.keys().all(|key| definitions.contains_key(key)),
        "Incomplete native lazy NPC characteristic fixture"
    );
    let base_level = integer(&profile["base_level"], "NPC base level")?;
    let curves = profile["curves"]
        .as_object()
        .context("Missing native NPC curves")?;
    for (key, row) in definitions {
        let Some(curve) = curves.get(key) else {
            continue;
        };
        let curve = curve
            .as_array()
            .context("Invalid native characteristic curve")?;
        ensure!(curve.len() == 2, "Invalid native characteristic curve");
        let growth = native_float(&curve[1], "NPC growth")?;
        let native = i64::from(native_increment(
            integer(&curve[0], "NPC curve base")?,
            (i64::from(level) - base_level) as f64 * growth,
        )?);
        let value = values
            .get_mut(key)
            .unwrap()
            .as_object_mut()
            .context("Invalid native NPC value")?;
        let hard_minimum = integer(&row["hard_minimum"], "hard minimum")?;
        let hard_maximum = integer(&row["hard_maximum"], "hard maximum")?;
        ensure!(hard_minimum <= hard_maximum, "Invalid native hard bounds");
        if row["expandable"]
            .as_bool()
            .context("Missing native expandable policy")?
        {
            value.insert(
                "maximum".into(),
                json!(native.clamp(hard_minimum, hard_maximum)),
            );
        }
        let minimum = integer(value.get("minimum").unwrap_or(&Value::Null), "minimum")?;
        let maximum = integer(value.get("maximum").unwrap_or(&Value::Null), "maximum")?;
        ensure!(minimum <= maximum, "Invalid native characteristic bounds");
        value.insert("current".into(), json!(native.clamp(minimum, maximum)));
    }
    Ok(Value::Object(values))
}

#[allow(clippy::too_many_arguments)]
pub async fn owned_instance(
    ctx: &Context,
    reference: i64,
    level: i32,
    id: i64,
    map_id: i32,
    x: i32,
    y: i32,
    z: i16,
) -> Result<Value> {
    owned_instance_in(ctx, reference, level, id, map_id, 0, 1, x, y, z).await
}

#[allow(clippy::too_many_arguments)]
pub async fn owned_instance_in(
    ctx: &Context,
    reference: i64,
    level: i32,
    id: i64,
    map_id: i32,
    instance_id: i64,
    team: i32,
    x: i32,
    y: i32,
    z: i16,
) -> Result<Value> {
    ensure!(id != 0, "Invalid owned actor ID");
    ensure!(
        map_id > 0 && instance_id >= 0 && (team == 0 || team == 1),
        "Invalid local monster map or team"
    );
    let monster = ctx.catalog.monster_definition(reference).await?;
    let stats = statistics(&monster, level)?;
    ensure!(
        *stats.get("HP").context("Missing native HP curve")? > 0
            && ["AP", "MP", "WP"]
                .iter()
                .all(|name| stats.get(*name).is_some_and(|v| *v >= 0)),
        "Reference cannot initialize a living local fighter"
    );
    let definitions = ctx.catalog.characteristic_definitions().await?;
    let profile = ctx
        .catalog
        .document_record(
            "native-actor-characteristics.json",
            "npc_profiles",
            &json!(reference.to_string()),
        )
        .await?;
    let values = npc_creation_values(&profile, &definitions, level)?;
    Ok(json!({
        "id": id, "ref": reference, "breed": reference,
        "level": level, "effective_level": level,
        "map_id": map_id, "instance_id": instance_id,
        "x": x, "y": y, "z": z, "team": team,
        "hp": values["1"]["current"], "max_hp": values["1"]["maximum"],
        "ap": values["2"]["current"], "mp": values["3"]["current"],
        "wp": values["4"]["current"],
        "initiative": stats.get("INIT").context("Missing native initiative curve")?,
        "sprite_id": monster.get("sprite_id").context("Missing native sprite identity")?,
    }))
}

/// Same explicit ordinary-summon inventory as monster_minigame_policy.py.
/// Other reversible minigame/admin policies are not silently added here.
pub fn ordinary_summon_only(reference: i64) -> bool {
    matches!(
        reference,
        182 | 1236
            | 1380
            | 1381
            | 1382
            | 1383
            | 1384
            | 1620
            | 1775
            | 3251
            | 3745
            | 3746
            | 3747
            | 3748
            | 3749
            | 3750
            | 3751
            | 4189
            | 4194
            | 4195
            | 4196
            | 4539
            | 4559
            | 5034
            | 5403
            | 5404
            | 5528
            | 5533
    )
}

type ViabilityKey = (String, String, i64, i32);
#[derive(Default)]
struct ViabilityCache {
    values: HashMap<ViabilityKey, bool>,
    order: VecDeque<ViabilityKey>,
}
static VIABILITY: OnceLock<Mutex<ViabilityCache>> = OnceLock::new();
const MAX_VIABILITY_PROOFS: usize = 4096;

fn cache_viability(key: ViabilityKey, viable: bool) {
    let mut cache = VIABILITY
        .get_or_init(Default::default)
        .lock()
        .unwrap_or_else(|e| e.into_inner());
    if !cache.values.contains_key(&key) {
        if cache.values.len() >= MAX_VIABILITY_PROOFS {
            if let Some(old) = cache.order.pop_front() {
                cache.values.remove(&old);
            }
        }
        cache.order.push_back(key.clone());
    }
    cache.values.insert(key, viable);
}

fn push_i16(bytes: &mut Vec<u8>, value: &Value) -> Result<()> {
    bytes.extend_from_slice(&i16::try_from(integer(value, "signed short")?)?.to_be_bytes());
    Ok(())
}

pub(crate) use wakemu_world_spatial::geometry::placement_direction;

fn native_member_fields(member: &Value) -> Result<Value> {
    let mut native = member
        .as_object()
        .context("Invalid native monster member")?
        .clone();
    if native.contains_key("fixed_actor_placement") {
        placement_direction(member)?;
        native.remove("fixed_actor_placement");
    }
    if let Some(resistance) = native.get("rii_practice_resistance") {
        let resistance = integer(resistance, "dojo resistance")?;
        ensure!(
            (0..=90).contains(&resistance)
                && resistance % 10 == 0
                && member["ref"] == 2335
                && member["map_id"] == 1388
                && member["instance_id"] == 0
                && member["id"].as_i64().is_some_and(|id| id < 0),
            "Invalid owned dojo resistance"
        );
        native.remove("rii_practice_resistance");
    }
    if let Some(marker) = native.get("environmental_world_action_only") {
        ensure!(
            marker == &Value::Bool(true),
            "Invalid world-action-only NPC marker"
        );
        native.remove("environmental_world_action_only");
    }
    Ok(Value::Object(native))
}

fn world_blob(monster: &Value, members: &[Value], group_id: i64, name: &str) -> Result<Vec<u8>> {
    ensure!(
        !name.is_empty() && name.len() <= usize::from(u16::MAX),
        "Invalid NPC name"
    );
    ensure!(
        group_id > 0 && !members.is_empty() && members.len() <= 127,
        "Invalid own monster group membership"
    );
    let id = integer(&monster["id"], "actor ID")?;
    ensure!(id < 0, "Expected verified own negative NPC instance");
    let mut out = vec![11];
    out.extend_from_slice(&id.to_be_bytes());
    out.push(1);
    out.extend_from_slice(&(-1_i64).to_be_bytes());
    out.extend_from_slice(&(name.len() as u16).to_be_bytes());
    out.extend_from_slice(name.as_bytes());
    push_i16(&mut out, &monster["ref"])?;
    out.extend_from_slice(&i32::try_from(integer(&monster["x"], "x")?)?.to_be_bytes());
    out.extend_from_slice(&i32::try_from(integer(&monster["y"], "y")?)?.to_be_bytes());
    push_i16(&mut out, &monster["z"])?;
    out.extend_from_slice(&integer(&monster["map_id"], "map identity")?.to_be_bytes());
    out.extend_from_slice(&[placement_direction(monster)?, 0, 1]);
    push_i16(&mut out, &monster["level"])?;
    out.extend_from_slice(&0_u16.to_be_bytes());
    out.push(0);
    out.extend_from_slice(&(-1_i32).to_be_bytes());
    out.extend_from_slice(&[0, 0, 0, 0, 255, 0]);
    if monster["environmental_world_action_only"] == true {
        out.extend_from_slice(&[1, 0, 1, 13, 1]);
    } else {
        out.push(0);
    }
    out.extend_from_slice(&group_id.to_be_bytes());
    out.extend_from_slice(&(members.len() as u16).to_be_bytes());
    for member in members {
        push_i16(&mut out, &member["ref"])?;
        push_i16(&mut out, &member["level"])?;
    }
    out.extend_from_slice(&(-1_i16).to_be_bytes());
    out.extend_from_slice(&(-1_i16).to_be_bytes());
    out.extend_from_slice(&0_u16.to_be_bytes());
    out.extend_from_slice(&[0, 0]);
    out.extend_from_slice(&[0; 16]);
    out.extend_from_slice(&[0, 0, 0]);
    ensure!(
        out.len() <= usize::from(u16::MAX),
        "NPC appearance too large"
    );
    Ok(out)
}

/// Validate and encode exactly the ordinary fresh group constructor used by planners.
pub async fn spawn_group(ctx: &Context, members: &[Value], group_id: i64) -> Result<Vec<u8>> {
    ensure!(
        !members.is_empty() && members.len() <= 127,
        "Invalid owned group size"
    );
    let mut seen = HashSet::new();
    let mut names = Vec::new();
    for member in members {
        let id = integer(&member["id"], "actor ID")?;
        ensure!(
            seen.insert(id) && id < 0,
            "Invalid own monster group membership"
        );
        let actual = owned_instance_in(
            ctx,
            integer(&member["ref"], "reference")?,
            i32::try_from(integer(&member["level"], "level")?)?,
            id,
            i32::try_from(integer(&member["map_id"], "map")?)?,
            integer(&member["instance_id"], "instance")?,
            i32::try_from(integer(&member["team"], "team")?)?,
            i32::try_from(integer(&member["x"], "x")?)?,
            i32::try_from(integer(&member["y"], "y")?)?,
            i16::try_from(integer(&member["z"], "z")?)?,
        )
        .await?;
        ensure!(
            actual == native_member_fields(member)?
                && member["map_id"] == members[0]["map_id"]
                && member["instance_id"] == members[0]["instance_id"],
            "Group member is not a verified own NPC on this map"
        );
        let definition = ctx
            .catalog
            .monster_definition(integer(&member["ref"], "reference")?)
            .await?;
        names.push(
            definition["name"]
                .as_str()
                .context("Invalid NPC name")?
                .to_owned(),
        );
        world_blob(member, members, group_id, names.last().unwrap())?;
    }
    let eligible = members
        .iter()
        .enumerate()
        .filter(|(_, member)| {
            member["instance_id"].as_i64() != Some(0)
                || !ordinary_summon_only(member["ref"].as_i64().unwrap_or_default())
        })
        .collect::<Vec<_>>();
    let visible = eligible
        .iter()
        .map(|(_, m)| (*m).clone())
        .collect::<Vec<_>>();
    let mut out = (eligible.len() as u16).to_be_bytes().to_vec();
    for (index, member) in eligible {
        let blob = world_blob(member, &visible, group_id, &names[index])?;
        out.push(1);
        out.extend_from_slice(&integer(&member["id"], "actor ID")?.to_be_bytes());
        out.extend_from_slice(&(blob.len() as u16).to_be_bytes());
        out.extend_from_slice(&blob);
    }
    Ok(out)
}

pub async fn publication_viable(ctx: &Context, reference: i64, min_level: i32) -> Result<bool> {
    if ordinary_summon_only(reference) {
        return Ok(false);
    }
    // Only an explicit sealed publication may reuse a constructor proof. The
    // cache holds booleans and bounded identities, never actor/catalog graphs.
    let key = ctx.catalog.compiled_generation().map(|generation| {
        (
            ctx.catalog.revision().to_owned(),
            generation.to_owned(),
            reference,
            min_level,
        )
    });
    if let Some(ref key) = key {
        if let Some(viable) = VIABILITY
            .get_or_init(Default::default)
            .lock()
            .unwrap_or_else(|e| e.into_inner())
            .values
            .get(key)
            .copied()
        {
            return Ok(viable);
        }
    }
    let result = async {
        let member = owned_instance(ctx, reference, min_level, -1, 1, 0, 0, 0).await?;
        spawn_group(ctx, &[member], 1).await?;
        Result::<()>::Ok(())
    }
    .await;
    let viable = match result {
        Ok(()) => true,
        Err(error)
            if error.downcast_ref::<tokio_postgres::Error>().is_some()
                || error
                    .downcast_ref::<deadpool_postgres::PoolError>()
                    .is_some() =>
        {
            return Err(error);
        }
        Err(_) => false,
    };
    if let Some(key) = key {
        cache_viability(key, viable);
    }
    Ok(viable)
}

/// Retain the first durable random outcome while rebuilding live CAS inputs.
pub async fn refresh_stale_decision(
    ctx: &Context,
    original: &Value,
    fresh: &Value,
) -> Result<Value> {
    let mut refreshed = fresh.clone();
    ensure!(refreshed.is_object(), "Invalid refreshed ecology decision");
    for key in ["draw", "group_draw", "child", "member"] {
        if let Some(value) = original.get(key) {
            refreshed[key] = value.clone();
        }
    }
    if fresh["kind"] == "maturation" && fresh.get("configuration").is_some() {
        let members = fresh["expected_members"]
            .as_array()
            .context("Missing refreshed maturation roster")?;
        let id = integer(&fresh["ticket"]["monster_id"], "maturation actor")?;
        let parent = members
            .iter()
            .find(|member| member["id"].as_i64() == Some(id))
            .context("Maturation parent missing fresh roster")?;
        let scope = fresh["scope"]
            .as_array()
            .context("Missing refreshed maturation scope")?;
        ensure!(scope.len() == 2, "Invalid refreshed maturation scope");
        let candidate = super::mobs::choose_next(
            ctx,
            integer(&parent["ref"], "reference")?,
            &fresh["configuration"],
            number(&refreshed["draw"], "maturation draw")?,
            fresh["ticket"].get("decision").unwrap_or(&Value::Null),
            members,
            i32::try_from(integer(&parent["level"], "level")?)?,
        )
        .await?;
        refreshed["grown"] = match candidate {
            None => Value::Null,
            Some(candidate) => {
                owned_instance_in(
                    ctx,
                    integer(&candidate["reference"], "reference")?,
                    i32::try_from(integer(&candidate["min_level"], "level")?)?,
                    id,
                    i32::try_from(integer(&scope[0], "map")?)?,
                    integer(&scope[1], "instance")?,
                    i32::try_from(integer(&parent["team"], "team")?)?,
                    i32::try_from(integer(&parent["x"], "x")?)?,
                    i32::try_from(integer(&parent["y"], "y")?)?,
                    i16::try_from(integer(&parent["z"], "z")?)?,
                )
                .await?
            }
        };
    } else if let Some(value) = original.get("grown") {
        refreshed["grown"] = value.clone();
    }
    if !refreshed["child"].is_null() {
        if let Some(destination) = fresh.get("destination") {
            let destination = destination
                .as_array()
                .context("Invalid refreshed birth destination")?;
            ensure!(
                destination.len() == 3,
                "Invalid refreshed birth destination"
            );
            for (index, key) in ["x", "y", "z"].iter().enumerate() {
                refreshed["child"][*key] = destination[index].clone();
            }
        }
    }
    if !refreshed["member"].is_null() {
        if let Some(expected) = fresh.get("expected") {
            for key in ["x", "y", "z"] {
                refreshed["member"][key] = expected[key].clone();
            }
        }
    }
    Ok(refreshed)
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn native_float_growth_truncates_saturates_and_wraps() {
        let monster = json!({"min_level":1,"statistics":{
            "HP":{"base":100,"per_level":0.7},
            "INIT":{"base":2147483647_i64,"per_level":1.0}}});
        let stats = statistics(&monster, 4).unwrap();
        assert_eq!(stats["HP"], 102);
        assert_eq!(stats["INIT"], -2147483646);
        assert_eq!(native_increment(5, f64::INFINITY).unwrap(), i32::MIN + 4);
        assert_eq!(
            native_increment(5, f64::NEG_INFINITY).unwrap(),
            i32::MIN + 5
        );
        assert_eq!(native_increment(5, f64::NAN).unwrap(), 5);
    }
    #[test]
    fn native_resource_constructor_clamps_expandable_values() {
        let keys = ["1", "2", "3", "4", "9", "32", "35", "92", "97", "100"];
        let defs = Value::Object(
            keys.iter()
                .map(|key| {
                    (
                        (*key).into(),
                        json!({"expandable":true,"hard_minimum":0,"hard_maximum":20}),
                    )
                })
                .collect(),
        );
        let values = Value::Object(
            keys.iter()
                .map(|key| ((*key).into(), json!({"minimum":0,"maximum":20,"current":0})))
                .collect(),
        );
        let profile =
            json!({"base_level":1,"at_base_level":values,"curves":{"4":[25,0.0],"1":[-5,1.0]}});
        let result = npc_creation_values(&profile, &defs, 1).unwrap();
        assert_eq!(result["4"]["current"], 20);
        assert_eq!(result["1"]["current"], 0);
        assert_eq!(result["1"]["maximum"], 0);
    }
    #[test]
    fn name_budget_counts_utf8_bytes_and_native_signed_short_fields() {
        let member = json!({"id":-1,"ref":6,"level":1,"map_id":1,"x":0,"y":0,"z":0});
        let bytes = world_blob(&member, &[member.clone()], 1, "Tofu").unwrap();
        assert_eq!(bytes[0], 11);
        assert!(world_blob(&member, &[member.clone()], 1, &"é".repeat(32768)).is_err());
        let mut invalid = member.clone();
        invalid["ref"] = json!(32768);
        assert!(world_blob(&invalid, &[invalid.clone()], 1, "Tofu").is_err());
    }

    #[test]
    fn world_blob_matches_existing_python_native_encoder() {
        // Generated from combat_monster_world.world_actor with the actual codec
        // body and a fixed verified native factory/name boundary, no database.
        let member = json!({"id":-1,"ref":6,"level":1,"map_id":1,"x":0,"y":0,"z":0});
        let encoded = world_blob(&member, &[member.clone()], 1, "Tofu é").unwrap();
        assert_eq!(encoded.len(), 107);
        assert_eq!(hex::encode(encoded), "0bffffffffffffffff01ffffffffffffffff0007546f667520c3a900060000000000000000000000000000000000010300010001000000ffffffff00000000ff00000000000000000001000100060001ffffffff0000000000000000000000000000000000000000000000");
    }
}
