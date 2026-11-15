//! Bounded external monster planning. World remains the mutation authority.
use anyhow::{anyhow, ensure, Context as _, Result};
use serde_json::{json, Value};
use std::collections::{BTreeMap, BTreeSet, HashSet, VecDeque};
use std::sync::{Arc, Mutex, OnceLock};

use super::{mob_geometry, mob_idle, mob_lifecycle, native_monster, plants};
use crate::Context;

fn integer(value: &Value, key: &str) -> Result<i64> {
    value[key]
        .as_i64()
        .ok_or_else(|| anyhow!("Invalid ecology monster {key}"))
}
fn number(value: &Value, key: &str) -> Result<f64> {
    let n = value[key]
        .as_f64()
        .ok_or_else(|| anyhow!("Invalid ecology monster {key}"))?;
    ensure!(n.is_finite(), "Invalid ecology monster {key}");
    Ok(n)
}
fn special(candidate: &Value) -> bool {
    matches!(
        candidate["boss_classification"].as_str(),
        Some("boss" | "ultimate_boss" | "raid_boss" | "archmonster" | "arch")
    )
}
fn scripted_intro(scope: [i64; 2]) -> bool {
    scope[0] == 1361 && (1_i64 << 62) < scope[1] && scope[1] < (1_i64 << 62) + (1_i64 << 48)
}

pub async fn wander_policy(ctx: &Context) -> Result<Value> {
    let db = ctx.db.get().await?;
    let row = db
        .query_opt(
            "SELECT value FROM settings WHERE name='monster_wander'",
            &[],
        )
        .await?
        .context("Missing monster wander policy")?;
    let value: Value = row.get(0);
    let expected = [
        "interval_seconds",
        "move_probability",
        "min_steps",
        "max_steps",
        "radius",
    ];
    let object = value.as_object().context("Invalid monster wander policy")?;
    ensure!(
        object.len() == expected.len() && expected.iter().all(|k| object.contains_key(*k)),
        "Invalid monster wander policy"
    );
    let interval = number(&value, "interval_seconds")?;
    let probability = number(&value, "move_probability")?;
    ensure!(
        interval > 0.0 && interval <= 3600.0 && (0.0..=1.0).contains(&probability),
        "Invalid monster wander timing or probability"
    );
    let minimum = integer(&value, "min_steps")?;
    let maximum = integer(&value, "max_steps")?;
    ensure!(
        1 <= minimum
            && minimum <= maximum
            && maximum <= 255
            && (1..=1000).contains(&integer(&value, "radius")?),
        "Invalid monster wander distance"
    );
    Ok(value)
}
pub async fn wander_interval(ctx: &Context) -> Result<f64> {
    number(&wander_policy(ctx).await?, "interval_seconds")
}
pub async fn validate_proposal(ctx: &Context, row: &Value) -> Result<bool> {
    if row["domain"] == "mobs" && row["payload"]["kind"] == "idle_distribution" {
        return mob_idle::validate_idle_proposal(ctx, &row["payload"]).await;
    }
    mob_geometry::validate_proposal(ctx, row).await
}

fn stage<'a>(catalog: &'a Value, reference: i64) -> Result<Option<(&'a Value, usize, &'a Value)>> {
    for family in catalog["families"]
        .as_array()
        .context("Invalid native growth families")?
    {
        for (rank, tier) in family["tiers"]
            .as_array()
            .context("Invalid native growth tiers")?
            .iter()
            .enumerate()
        {
            for candidate in tier["candidates"]
                .as_array()
                .context("Invalid native growth candidates")?
            {
                if candidate["reference"].as_i64() == Some(reference) {
                    return Ok(Some((family, rank, candidate)));
                }
            }
        }
    }
    Ok(None)
}
#[derive(Default)]
struct GrowthCatalogs {
    entries: VecDeque<((String, String), Arc<Value>, usize)>,
    bytes: usize,
}
static GROWTH_CATALOGS: OnceLock<Mutex<GrowthCatalogs>> = OnceLock::new();
const MAX_GROWTH_BYTES: usize = 4 * 1024 * 1024;

async fn growth_catalog(ctx: &Context) -> Result<Arc<Value>> {
    let key = ctx
        .catalog
        .compiled_generation()
        .map(|generation| (ctx.catalog.revision().to_owned(), generation.to_owned()));
    if let Some(ref key) = key {
        let cache = GROWTH_CATALOGS
            .get_or_init(Default::default)
            .lock()
            .unwrap_or_else(|e| e.into_inner());
        if let Some((_, value, _)) = cache
            .entries
            .iter()
            .find(|(candidate, _, _)| candidate == key)
        {
            return Ok(Arc::clone(value));
        }
    }
    let value = Arc::new(plants::normalize_growth_catalog(
        ctx.catalog.document("monster-growth-catalog.json").await?,
    )?);
    if let Some(key) = key {
        let size = serde_json::to_vec(value.as_ref())?.len();
        if size <= MAX_GROWTH_BYTES {
            let mut cache = GROWTH_CATALOGS
                .get_or_init(Default::default)
                .lock()
                .unwrap_or_else(|e| e.into_inner());
            // A second publisher may have completed the same immutable read.
            if let Some((_, value, _)) = cache
                .entries
                .iter()
                .find(|(candidate, _, _)| candidate == &key)
            {
                return Ok(Arc::clone(value));
            }
            while cache.entries.len() >= 2 || cache.bytes + size > MAX_GROWTH_BYTES {
                if let Some((_, _, old_size)) = cache.entries.pop_front() {
                    cache.bytes -= old_size;
                } else {
                    break;
                }
            }
            cache.bytes += size;
            cache.entries.push_back((key, Arc::clone(&value), size));
        }
    }
    Ok(value)
}
fn choose(candidates: &[Value], decision: &Value) -> Result<Value> {
    ensure!(!candidates.is_empty(), "Empty maturation candidate pool");
    if decision.get("variant_seed").is_some() {
        mob_lifecycle::choose(candidates, decision)
    } else {
        Ok(candidates[rand::random_range(0..candidates.len())].clone())
    }
}

/// Same roster-aware ordinary stage mass and neighboring-stage policy as Python.
async fn choose_transition(
    ctx: &Context,
    catalog: &Value,
    reference: i64,
    configuration: &Value,
    draw: f64,
    decision: &Value,
    members: &[Value],
    source_level: i32,
) -> Result<Option<Value>> {
    ensure!(
        draw.is_finite() && (0.0..1.0).contains(&draw) && source_level >= 0,
        "Invalid monster maturation draw or source level"
    );
    let Some((family, rank, current)) = stage(catalog, reference)? else {
        return Ok(None);
    };
    if special(current) {
        return Ok(None);
    }
    let tiers = family["tiers"].as_array().context("Invalid growth tiers")?;
    let mut ordinary = Vec::new();
    for tier in tiers {
        let mut candidates = Vec::new();
        for candidate in tier["candidates"]
            .as_array()
            .context("Invalid growth candidates")?
        {
            if !special(candidate)
                && native_monster::publication_viable(
                    ctx,
                    integer(candidate, "reference")?,
                    i32::try_from(integer(candidate, "min_level")?)?,
                )
                .await?
            {
                candidates.push(candidate.clone());
            }
        }
        ordinary.push(candidates);
    }
    let birth_pool = plants::initial_candidates(ctx, integer(family, "family_id")?, None).await?;
    if !birth_pool.is_empty() && !ordinary.is_empty() {
        let initial: HashSet<i64> = birth_pool
            .iter()
            .map(|c| integer(c, "reference"))
            .collect::<Result<_>>()?;
        ordinary[0].retain(|c| {
            c["reference"]
                .as_i64()
                .is_some_and(|r| initial.contains(&r))
        });
    }
    let minimum_level = integer(current, "min_level")?.max(i64::from(source_level));
    let mut bosses = Vec::new();
    if let Some(next_tier) = tiers.get(rank + 1) {
        for candidate in next_tier["candidates"]
            .as_array()
            .context("Invalid growth candidates")?
        {
            if matches!(
                candidate["boss_classification"].as_str(),
                Some("boss" | "ultimate_boss" | "raid_boss")
            ) && integer(candidate, "min_level")? >= minimum_level
                && native_monster::publication_viable(
                    ctx,
                    integer(candidate, "reference")?,
                    i32::try_from(integer(candidate, "min_level")?)?,
                )
                .await?
            {
                bosses.push(candidate.clone());
            }
        }
    }
    choose_prepared(
        catalog,
        reference,
        configuration,
        draw,
        decision,
        members,
        source_level,
        ordinary,
        bosses,
    )
}

/// Pure selection kernel over already qualified native candidate populations.
#[allow(clippy::too_many_arguments)]
fn choose_prepared(
    catalog: &Value,
    reference: i64,
    configuration: &Value,
    draw: f64,
    decision: &Value,
    members: &[Value],
    source_level: i32,
    ordinary: Vec<Vec<Value>>,
    bosses: Vec<Value>,
) -> Result<Option<Value>> {
    ensure!(
        draw.is_finite() && (0.0..1.0).contains(&draw) && source_level >= 0,
        "Invalid monster maturation draw or source level"
    );
    let Some((family, rank, current)) = stage(catalog, reference)? else {
        return Ok(None);
    };
    if special(current) {
        return Ok(None);
    }
    let minimum_level = integer(current, "min_level")?.max(i64::from(source_level));
    let mut counts = BTreeMap::<usize, usize>::new();
    for member in members {
        if let Some((member_family, member_rank, _)) = stage(catalog, integer(member, "ref")?)? {
            if member_family["family_id"] == family["family_id"] {
                *counts.entry(member_rank).or_default() += 1;
            }
        }
    }
    let count = counts.entry(rank).or_default();
    *count = count.saturating_sub(1);
    let boss_mass = if bosses.is_empty() {
        0.0
    } else {
        number(configuration, "boss_probability")?
    };
    if draw < boss_mass {
        return Ok(Some(choose(&bosses, decision)?));
    }
    let size = members.len();
    let speed = if size < 4 {
        1.8
    } else if size == 4 {
        1.0
    } else {
        0.45
    };
    let probability = (number(configuration, "base_probability")? * speed).min(1.0 - boss_mass);
    if draw >= boss_mass + probability || probability <= 0.0 {
        return Ok(None);
    }
    let active: Vec<usize> = ordinary
        .iter()
        .enumerate()
        .filter_map(|(i, c)| (!c.is_empty()).then_some(i))
        .collect();
    if active.is_empty() {
        return Ok(None);
    }
    let decay = (0.20 + size as f64 * 0.035).min(0.48);
    let base = decay * number(configuration, "stage_decay")?.max(0.001);
    let raw: BTreeMap<usize, f64> = active
        .iter()
        .enumerate()
        .map(|(i, target)| (*target, base.powi(i as i32)))
        .collect();
    let total: f64 = raw.values().sum();
    let mut options = Vec::new();
    for target in &active {
        let neighboring = if let Some(position) = active.iter().position(|r| *r == rank) {
            position.abs_diff(active.iter().position(|r| r == target).unwrap()) <= 1
        } else {
            active.iter().filter(|r| **r < rank).max() == Some(target)
                || active.iter().filter(|r| **r > rank).min() == Some(target)
        };
        if *target < rank || !neighboring {
            continue;
        }
        let candidates: Vec<Value> = ordinary[*target]
            .iter()
            .filter(|c| c["min_level"].as_i64().is_some_and(|n| n >= minimum_level))
            .cloned()
            .collect();
        if candidates.is_empty() {
            continue;
        }
        let expected = size as f64 * raw[target] / total;
        let crowding = (-(counts.get(target).copied().unwrap_or(0) as f64 / expected.max(0.20))
            .min(50.0))
        .exp();
        options.push((candidates, raw[target] * crowding));
    }
    if options.is_empty() {
        return Ok(None);
    }
    let mut point = (draw - boss_mass) / probability * options.iter().map(|(_, w)| w).sum::<f64>();
    for (candidates, weight) in &options {
        if point < *weight {
            let selected = choose(candidates, decision)?;
            return Ok((selected["reference"].as_i64() != Some(reference)).then_some(selected));
        }
        point -= *weight;
    }
    let selected = choose(&options.last().unwrap().0, decision)?;
    Ok((selected["reference"].as_i64() != Some(reference)).then_some(selected))
}

pub async fn choose_next(
    ctx: &Context,
    reference: i64,
    configuration: &Value,
    draw: f64,
    decision: &Value,
    members: &[Value],
    source_level: i32,
) -> Result<Option<Value>> {
    let catalog = growth_catalog(ctx).await?;
    choose_transition(
        ctx,
        &catalog,
        reference,
        configuration,
        draw,
        decision,
        members,
        source_level,
    )
    .await
}

fn proposal_slots(proposals: &[Value]) -> Result<usize> {
    let mut counts = BTreeMap::<[i64; 2], usize>::new();
    let mut other = 0;
    for p in proposals {
        if p["noop"] == true {
            continue;
        }
        if matches!(p["kind"].as_str(), Some("maturation" | "reproduction")) {
            let scope = scope(&p["scope"])?;
            *counts.entry(scope).or_default() += 1;
        } else {
            other += 1;
        }
    }
    Ok(other
        + counts
            .values()
            .map(|count| (count + 15) / 16)
            .sum::<usize>())
}
fn scope(value: &Value) -> Result<[i64; 2]> {
    let a = value.as_array().context("Invalid ecology scope")?;
    ensure!(a.len() == 2, "Invalid ecology scope");
    let map = a[0].as_i64().context("Invalid ecology map")?;
    let instance = a[1].as_i64().context("Invalid ecology instance")?;
    ensure!(
        map > 0 && map < i64::from(i32::MAX) + 1 && instance >= 0,
        "Invalid ecology scope"
    );
    Ok([map, instance])
}
fn pack_lifecycle(proposals: Vec<Value>) -> Result<Vec<Value>> {
    let mut result: Vec<Value> = Vec::new();
    for p in proposals {
        if !matches!(p["kind"].as_str(), Some("maturation" | "reproduction")) {
            result.push(p);
            continue;
        }
        let needs_batch = result.last().is_none_or(|last| {
            last["kind"] != "lifecycle_bulk"
                || last["scope"] != p["scope"]
                || last["operations"].as_array().is_none_or(|o| o.len() >= 16)
        });
        if needs_batch {
            result.push(json!({"kind":"lifecycle_bulk","scope":p["scope"],"world_epoch":p["world_epoch"],"operations":[]}));
        }
        let mut candidate = result.last().unwrap().clone();
        candidate["operations"]
            .as_array_mut()
            .unwrap()
            .push(p.clone());
        if crate::identity::canonical_json_bytes(&candidate)?.len() > 224 * 1024 {
            result.push(json!({"kind":"lifecycle_bulk","scope":p["scope"],"world_epoch":p["world_epoch"],"operations":[]}));
        }
        result.last_mut().unwrap()["operations"]
            .as_array_mut()
            .unwrap()
            .push(p);
    }
    Ok(result)
}

fn active_locations(snapshot: &Value, players: &[Value]) -> Result<BTreeSet<[i64; 2]>> {
    let occupied: BTreeSet<[i64; 2]> = players
        .iter()
        .filter(|p| {
            p.get("_ecology_active")
                .and_then(Value::as_bool)
                .unwrap_or(true)
        })
        .map(|p| {
            Ok([
                integer(p, "map_id")?,
                p.get("instance_id").and_then(Value::as_i64).unwrap_or(0),
            ])
        })
        .collect::<Result<_>>()?;
    let mut locations: BTreeSet<[i64; 2]> = snapshot["locations"]
        .as_array()
        .context("Invalid ecology locations")?
        .iter()
        .map(scope)
        .collect::<Result<_>>()?;
    locations.retain(|scope| occupied.contains(scope) && !scripted_intro(*scope));
    Ok(locations)
}

fn rotated_scopes(locations: &BTreeSet<[i64; 2]>, tick: u64) -> Vec<[i64; 2]> {
    let mut scopes: Vec<_> = locations.iter().copied().collect();
    if !scopes.is_empty() {
        let offset = tick as usize % scopes.len();
        scopes.rotate_left(offset);
    }
    scopes
}

fn background_capacity(limit: usize, active_scope: bool) -> usize {
    limit - usize::from(active_scope)
}

fn lifecycle_order(tick: u64) -> [&'static str; 2] {
    if tick % 2 == 0 {
        ["maturation", "reproduction"]
    } else {
        ["reproduction", "maturation"]
    }
}

fn departure_clocks<'a>(
    previous: &'a BTreeSet<[i64; 2]>,
    current: &'a BTreeSet<[i64; 2]>,
) -> impl Iterator<Item = ([i64; 2], &'static str)> + 'a {
    previous.difference(current).flat_map(|scope| {
        let scope = *scope;
        ["maturation", "reproduction"]
            .into_iter()
            .map(move |kind| (scope, kind))
    })
}

fn observation_generation(epoch: &str, player: &Value) -> Result<String> {
    match player.get("presence_generation").filter(|v| !v.is_null()) {
        Some(value) => Ok(format!(
            "{epoch}:presence:{}",
            value.as_i64().context("Invalid presence generation")?
        )),
        None => Ok(epoch.to_owned()),
    }
}

fn reproduction_has_capacity(
    zone_members: usize,
    groups: usize,
    members: usize,
    policy: &Value,
) -> Result<bool> {
    Ok(
        zone_members < usize::try_from(integer(policy, "max_zone_members")?)?
            && (groups < usize::try_from(integer(policy, "max_zone_groups")?)?
                || members < usize::try_from(integer(policy, "max_members")?)?),
    )
}

pub async fn prepare(ctx: &Context, snapshot: &Value, limit: usize) -> Result<Vec<Value>> {
    ensure!((1..=256).contains(&limit), "Invalid ecology proposal limit");
    let epoch = snapshot["world_epoch"]
        .as_str()
        .filter(|s| !s.is_empty())
        .context("Missing ecology world epoch")?;
    let now = integer(snapshot, "now_ms")?;
    ensure!(now >= 0, "Invalid ecology clock");
    let players: Vec<Value> = snapshot["players"]
        .as_array()
        .context("Invalid ecology players")?
        .iter()
        .filter(|p| {
            p.get("_ecology_active")
                .and_then(Value::as_bool)
                .unwrap_or(true)
        })
        .cloned()
        .collect();
    let excluded: HashSet<i64> = snapshot["excluded_ids"]
        .as_array()
        .context("Invalid ecology excluded identities")?
        .iter()
        .map(|n| n.as_i64().context("Invalid ecology excluded identity"))
        .collect::<Result<_>>()?;
    let locations = active_locations(snapshot, &players)?;
    let tick = snapshot
        .get("domain_planning_tick")
        .and_then(Value::as_u64)
        .unwrap_or(0);
    let scopes = rotated_scopes(&locations, tick);
    let background_limit = background_capacity(limit, !scopes.is_empty());
    let mut proposals = Vec::new();
    let mut noops = Vec::new();
    if background_limit > 0 {
        proposals.extend(mob_idle::prepare(ctx, snapshot, background_limit).await?);
        let remaining = background_limit.saturating_sub(proposal_slots(&proposals)?);
        if remaining > 0 {
            proposals.extend(mob_idle::prepare_cleanup(ctx, snapshot, remaining).await?);
        }
    }
    let maturation = mob_lifecycle::policy(ctx, "maturation").await?;
    let reproduction = mob_lifecycle::policy(ctx, "reproduction").await?;
    let wander = wander_policy(ctx).await?;
    let catalog = growth_catalog(ctx).await?;
    let mut eligible = HashSet::new();
    for family in catalog["families"]
        .as_array()
        .context("Invalid growth families")?
    {
        for tier in family["tiers"].as_array().context("Invalid growth tiers")? {
            for c in tier["candidates"]
                .as_array()
                .context("Invalid growth candidates")?
            {
                if c["boss_classification"] == "regular" {
                    eligible.insert(i32::try_from(integer(c, "reference")?)?);
                }
            }
        }
    }
    let previous: BTreeSet<[i64; 2]> = snapshot
        .get("previous_locations")
        .and_then(Value::as_array)
        .map(|a| a.iter().map(scope).collect())
        .transpose()?
        .unwrap_or_default();
    for (old, kind) in departure_clocks(&previous, &locations) {
        mob_lifecycle::observe(
            ctx,
            i32::try_from(old[0])?,
            old[1],
            false,
            epoch,
            now,
            &excluded,
            kind,
            &eligible,
            &Value::Null,
        )
        .await?;
    }
    for current in scopes {
        if mob_lifecycle::dungeon_population(ctx, current[1]).await? {
            continue;
        }
        let scoped: Vec<Value> = players
            .iter()
            .filter(|p| {
                p["map_id"].as_i64() == Some(current[0])
                    && p.get("instance_id").and_then(Value::as_i64).unwrap_or(0) == current[1]
            })
            .cloned()
            .collect();
        let generation = observation_generation(epoch, &scoped[0])?;
        let groups: Vec<Value> = {
            let db = ctx.db.get().await?;
            db.query("SELECT to_jsonb(g) FROM combat_groups g WHERE map_id=$1 AND instance_id=$2 ORDER BY group_id",&[&i32::try_from(current[0])?,&current[1]]).await?.into_iter().map(|r|r.get(0)).collect()
        };
        let homes = mob_geometry::ensure_homes(
            ctx,
            current,
            &groups
                .iter()
                .filter(|g| g["status"] != "defeated")
                .cloned()
                .collect::<Vec<_>>(),
        )
        .await?;
        let living: Vec<&Value> = groups
            .iter()
            .filter(|g| g["status"] != "defeated")
            .collect();
        let zone_members = living
            .iter()
            .map(|g| g["members"].as_array().map_or(0, Vec::len))
            .sum::<usize>();
        let ordered = lifecycle_order(tick);
        if background_limit > 0 {
            for kind in ordered {
                if proposal_slots(&proposals)? >= background_limit {
                    break;
                }
                let mut seen = HashSet::new();
                for event in
                    mob_lifecycle::unpublished(ctx, i32::try_from(current[0])?, current[1], kind)
                        .await?
                {
                    if proposal_slots(&proposals)? >= background_limit {
                        break;
                    }
                    let group_id = integer(&event, "group_id")?;
                    if !seen.insert(group_id) {
                        continue;
                    }
                    if let Some(group) = groups.iter().find(|g| {
                        g["group_id"].as_i64() == Some(group_id) && g["status"] == "available"
                    }) {
                        proposals.push(json!({"kind":format!("publish_{kind}"),"world_epoch":epoch,"scope":current,"group_id":group_id,"expected_members":group["members"]}));
                    }
                }
            }
            for kind in ordered {
                if proposal_slots(&proposals)? >= background_limit {
                    break;
                }
                let config = if kind == "maturation" {
                    &maturation
                } else {
                    &reproduction
                };
                mob_lifecycle::observe(
                    ctx,
                    i32::try_from(current[0])?,
                    current[1],
                    true,
                    &generation,
                    now,
                    &excluded,
                    kind,
                    &eligible,
                    config,
                )
                .await?;
                let tickets =
                    mob_lifecycle::pending(ctx, i32::try_from(current[0])?, current[1], kind)
                        .await?;
                for ticket in mob_lifecycle::attach(
                    ctx,
                    i32::try_from(current[0])?,
                    current[1],
                    kind,
                    &tickets,
                    config,
                )
                .await?
                {
                    if proposal_slots(&proposals)? >= background_limit {
                        break;
                    }
                    let gid = integer(&ticket, "group_id")?;
                    let actor = integer(&ticket, "monster_id")?;
                    let Some(group) = groups.iter().find(|g| {
                        g["group_id"].as_i64() == Some(gid) && g["status"] == "available"
                    }) else {
                        continue;
                    };
                    if excluded.contains(&actor) {
                        continue;
                    }
                    let members = group["members"]
                        .as_array()
                        .context("Invalid monster roster")?;
                    if kind == "reproduction"
                        && !reproduction_has_capacity(
                            zone_members,
                            living.len(),
                            members.len(),
                            config,
                        )?
                    {
                        continue;
                    }
                    let Some(parent) = members.iter().find(|m| {
                        m["id"].as_i64() == Some(actor) && m["ref"] == ticket["reference"]
                    }) else {
                        continue;
                    };
                    let draw = number(&ticket["decision"], "draw")?;
                    let mut p = json!({"kind":kind,"world_epoch":epoch,"scope":current,"ticket":ticket,"configuration":ticket["plan_policy"],"expected_members":members,"draw":draw});
                    let Some((family, rank, parent_stage)) =
                        stage(&catalog, integer(parent, "ref")?)?
                    else {
                        continue;
                    };
                    let probability = if kind == "reproduction" {
                        mob_lifecycle::birth_probability(
                            rank as i64,
                            special(parent_stage),
                            &p["configuration"],
                            members.len(),
                        )?
                    } else {
                        0.0
                    };
                    if kind == "reproduction" && draw >= probability {
                        p["child"] = Value::Null;
                        p["group_draw"] = ticket["decision"]["group_draw"].clone();
                        p["noop"] = json!(true);
                        p["_noop_probability"] = json!(probability);
                        noops.push(p);
                        continue;
                    }
                    if kind == "maturation" {
                        let candidate = choose_transition(
                            ctx,
                            &catalog,
                            integer(parent, "ref")?,
                            &p["configuration"],
                            draw,
                            &ticket["decision"],
                            members,
                            i32::try_from(integer(parent, "level")?)?,
                        )
                        .await?;
                        p["grown"] = if let Some(c) = candidate {
                            native_monster::owned_instance_in(
                                ctx,
                                integer(&c, "reference")?,
                                i32::try_from(integer(&c, "min_level")?)?,
                                actor,
                                i32::try_from(current[0])?,
                                current[1],
                                i32::try_from(integer(parent, "team")?)?,
                                i32::try_from(integer(parent, "x")?)?,
                                i32::try_from(integer(parent, "y")?)?,
                                i16::try_from(integer(parent, "z")?)?,
                            )
                            .await?
                        } else {
                            Value::Null
                        };
                        if p["grown"].is_null() {
                            p["noop"] = json!(true);
                            noops.push(p);
                            continue;
                        }
                        let replaced: Vec<Value> = members
                            .iter()
                            .map(|m| {
                                if m["id"] == p["grown"]["id"] {
                                    p["grown"].clone()
                                } else {
                                    m.clone()
                                }
                            })
                            .collect();
                        native_monster::spawn_group(ctx, &replaced, gid).await?;
                    } else {
                        let pool =
                            plants::initial_candidates(ctx, integer(family, "family_id")?, None)
                                .await?;
                        if pool.is_empty() {
                            continue;
                        }
                        let c = mob_lifecycle::choose(&pool, &ticket["decision"])?;
                        let destinations = mob_geometry::birth_destinations(
                            ctx,
                            current,
                            parent,
                            &groups,
                            &scoped,
                            homes.get(&gid).copied(),
                            integer(&c, "reference")?,
                        )
                        .await?;
                        if destinations.is_empty() {
                            continue;
                        }
                        let destination =
                            mob_lifecycle::choose_destination(&destinations, &ticket["decision"])?;
                        p["destination"] = json!(destination);
                        p["group_draw"] = ticket["decision"]["group_draw"].clone();
                        p["child"] = Value::Null;
                        if draw < probability {
                            let id = mob_lifecycle::allocate_identity(ctx).await?;
                            let child = native_monster::owned_instance_in(
                                ctx,
                                integer(&c, "reference")?,
                                i32::try_from(integer(&c, "min_level")?)?,
                                id,
                                i32::try_from(current[0])?,
                                current[1],
                                i32::try_from(integer(parent, "team")?)?,
                                i32::try_from(destination[0])?,
                                i32::try_from(destination[1])?,
                                i16::try_from(destination[2])?,
                            )
                            .await?;
                            native_monster::spawn_group(
                                ctx,
                                &[child.clone()],
                                id.checked_neg().context("Invalid newborn ID")?,
                            )
                            .await?;
                            p["child"] = child;
                        }
                    }
                    proposals.push(p);
                }
            }
        }
        if proposal_slots(&proposals)? >= limit {
            continue;
        }
        if let Some(batch) =
            mob_geometry::prepare_scope_wander(ctx, snapshot, current, &groups, &wander, &homes)
                .await?
        {
            proposals.push(batch)
        }
    }
    proposals.extend(noops);
    pack_lifecycle(mob_lifecycle::resolve_noops(ctx, proposals).await?)
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn lifecycle_budget_counts_scope_envelopes_not_individual_operations() {
        let mut p = vec![json!({"kind":"idle_distribution"})];
        p.extend((0..16).map(|_| json!({"kind":"maturation","scope":[1,0]})));
        assert_eq!(proposal_slots(&p).unwrap(), 2);
        p.push(json!({"kind":"reproduction","scope":[1,0]}));
        assert_eq!(proposal_slots(&p).unwrap(), 3);
        p.push(json!({"kind":"maturation","scope":[1,0],"noop":true}));
        assert_eq!(proposal_slots(&p).unwrap(), 3);
    }
    #[test]
    fn lifecycle_packing_preserves_scope_order_and_sixteen_bound() {
        let p = (0..17)
            .map(|n| json!({"kind":"maturation","scope":[1,0],"world_epoch":"e","n":n}))
            .collect();
        let out = pack_lifecycle(p).unwrap();
        assert_eq!(out.len(), 2);
        assert_eq!(out[0]["operations"].as_array().unwrap().len(), 16);
        assert_eq!(out[1]["operations"][0]["n"], 16);
    }
    #[test]
    fn scripted_intro_namespace_is_strictly_excluded() {
        assert!(scripted_intro([1361, (1_i64 << 62) + 1]));
        assert!(!scripted_intro([1361, 1_i64 << 62]));
        assert!(!scripted_intro([1362, (1_i64 << 62) + 1]));
    }
    #[test]
    fn composition_maturation_matches_python_golden_draws() {
        // 240 outcomes generated by the existing monster_group_balance
        // choose_transition body with its native candidate-proof boundaries
        // fixed to this fixture and the real seeded variant preference.
        let vectors: Value = serde_json::from_str(r#"[[10,1,[99,99,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,20,20]],[10,3,[99,99,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null]],[10,4,[99,99,null,null,null,null,null,null,null,null,null,20,null,null,null,null,null,null,null,null]],[10,6,[99,99,null,null,null,null,20,null,null,null,null,null,null,null,null,null,null,null,null,null]],[20,1,[null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,30,30,null,null]],[20,3,[null,null,null,null,null,null,null,null,30,30,30,30,30,30,30,30,30,30,null,null]],[20,4,[null,null,null,null,null,null,30,30,30,30,null,null,null,null,null,null,null,null,null,null]],[20,6,[null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null]],[30,1,[null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null]],[30,3,[null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null]],[30,4,[null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null]],[30,6,[null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null]]]"#).unwrap();
        let c10 = json!({"reference":10,"min_level":10,"boss_classification":"regular"});
        let c11 = json!({"reference":11,"min_level":10,"boss_classification":"regular"});
        let c99 = json!({"reference":99,"min_level":15,"boss_classification":"boss"});
        let c20 = json!({"reference":20,"min_level":20,"boss_classification":"regular"});
        let c30 = json!({"reference":30,"min_level":30,"boss_classification":"regular"});
        let catalog = json!({"families":[{"family_id":1,"tiers":[
            {"candidates":[c10.clone(),c11.clone()]}, {"candidates":[c99.clone()]},
            {"candidates":[c20.clone()]}, {"candidates":[c30.clone()]}]}]});
        let configuration =
            json!({"base_probability":0.5,"boss_probability":0.1,"stage_decay":0.7});
        let decision = json!({"variant_seed":"ab".repeat(32)});
        for row in vectors.as_array().unwrap() {
            let parent = row[0].as_i64().unwrap();
            let size = row[1].as_u64().unwrap() as usize;
            let mut members = vec![json!({"ref":parent})];
            members.extend(
                [10, 20, 10, 30, 11, 20]
                    .iter()
                    .take(size - 1)
                    .map(|r| json!({"ref":r})),
            );
            for (index, expected) in row[2].as_array().unwrap().iter().enumerate() {
                let selected = choose_prepared(
                    &catalog,
                    parent,
                    &configuration,
                    index as f64 / 20.0,
                    &decision,
                    &members,
                    parent as i32,
                    vec![
                        vec![c10.clone(), c11.clone()],
                        vec![],
                        vec![c20.clone()],
                        vec![c30.clone()],
                    ],
                    if parent == 10 {
                        vec![c99.clone()]
                    } else {
                        vec![]
                    },
                )
                .unwrap();
                let actual = selected
                    .map(|c| c["reference"].clone())
                    .unwrap_or(Value::Null);
                assert_eq!(
                    &actual, expected,
                    "parent={parent} size={size} draw={index}/20"
                );
            }
        }
    }
    // Migrated from Python worker-only tests: World commit tests remain in
    // test_ecology_* and test_monster_empty_map_guards.py with fixed envelopes.
    #[test]
    fn cleanup_filling_background_capacity_cannot_starve_wander() {
        for limit in [1, 2, 8, 16] {
            let reserved = background_capacity(limit, true);
            let cleanup = vec![json!({"kind":"cleanup_unassigned"}); reserved];
            assert_eq!(proposal_slots(&cleanup).unwrap(), reserved);
            assert_eq!(limit - proposal_slots(&cleanup).unwrap(), 1);
        }
        assert_eq!(background_capacity(8, false), 8);
    }

    #[test]
    fn live_zone_cap_omits_blocked_birth_before_identity_allocation() {
        let policy = json!({"max_members":8,"max_zone_members":12,"max_zone_groups":100});
        assert!(!reproduction_has_capacity(12, 12, 1, &policy).unwrap());
        assert!(!reproduction_has_capacity(11, 100, 8, &policy).unwrap());
        assert!(reproduction_has_capacity(11, 100, 1, &policy).unwrap());
        assert!(reproduction_has_capacity(11, 99, 8, &policy).unwrap());
    }

    #[test]
    fn small_proposal_budget_rotates_maps_instead_of_starving_later_scope() {
        let snapshot = json!({"locations":[[1134,0],[1135,0]]});
        let players = vec![
            json!({"map_id":1134,"instance_id":0}),
            json!({"map_id":1135,"instance_id":0}),
        ];
        let scopes = active_locations(&snapshot, &players).unwrap();
        assert_eq!(rotated_scopes(&scopes, 0)[0], [1134, 0]);
        assert_eq!(rotated_scopes(&scopes, 1)[0], [1135, 0]);
        assert_eq!(rotated_scopes(&scopes, 2)[0], [1134, 0]);
        assert_eq!(background_capacity(1, true), 0);
    }

    #[test]
    fn lifecycle_categories_rotate_without_consuming_wander_reservation() {
        assert_eq!(lifecycle_order(0), ["maturation", "reproduction"]);
        assert_eq!(lifecycle_order(1), ["reproduction", "maturation"]);
        for tick in 0..16 {
            let publication = json!({"kind":format!("publish_{}",lifecycle_order(tick)[0])});
            assert_eq!(proposal_slots(&[publication]).unwrap(), 1);
            assert_eq!(background_capacity(2, true), 1);
        }
    }

    #[test]
    fn empty_occupancy_schedules_pause_for_both_lifecycle_clocks() {
        let snapshot = json!({"locations":[[1134,0]]});
        let previous = BTreeSet::from([[1134, 0]]);
        for players in [
            vec![],
            vec![json!({"map_id":1134,"instance_id":0,"_ecology_active":false})],
            vec![json!({"map_id":1134,"instance_id":99})],
            vec![json!({"map_id":1135,"instance_id":0})],
        ] {
            let active = active_locations(&snapshot, &players).unwrap();
            assert!(active.is_empty());
            assert_eq!(
                departure_clocks(&previous, &active).collect::<Vec<_>>(),
                vec![([1134, 0], "maturation"), ([1134, 0], "reproduction")]
            );
            assert!(rotated_scopes(&active, 0).is_empty());
        }
    }

    #[test]
    fn worker_clock_generation_tracks_each_occupancy_episode() {
        let generations = [1, 2].map(|episode| {
            observation_generation("boot-a", &json!({"presence_generation":episode})).unwrap()
        });
        assert_eq!(generations, ["boot-a:presence:1", "boot-a:presence:2"]);
        assert_eq!(
            observation_generation("boot-a", &json!({})).unwrap(),
            "boot-a"
        );
        assert_ne!(
            generations[0],
            observation_generation("boot-b", &json!({"presence_generation":1})).unwrap()
        );
    }
}

#[cfg(test)]
mod phase2_selection_contract {
    use super::*;

    #[test]
    fn fertile_maturation_pool_excludes_tutorial_and_allows_legacy_exit() -> Result<()> {
        // Synthetic qualified native candidates preserve the old reference
        // identities; unequal levels explicitly exercise the monotone contract.
        let low = json!({"reference":5455,"min_level":1,"boss_classification":"regular"});
        let high = json!({"reference":5456,"min_level":2,"boss_classification":"regular"});
        let tutorial = json!({"reference":5525,"min_level":1,"boss_classification":"regular"});
        let catalog = json!({"families":[{"family_id":11,"tiers":[{"rank":0,"candidates":[low.clone(),high.clone(),tutorial]}]}]});
        let configuration =
            json!({"base_probability":1.0,"boss_probability":0.0,"stage_decay":1.0});
        // The native fertility/publication qualification supplies this pool.
        // Tutorial identity remains in the catalogue for legacy recovery only.
        let ordinary = vec![vec![low, high]];
        let decision = (0u8..=255)
            .map(|byte| json!({"variant_seed":hex::encode([byte;32])}))
            .find(|d| choose(&ordinary[0], d).unwrap()["reference"] == 5456)
            .expect("Seeded preference for higher fertile form");
        let forward = choose_prepared(
            &catalog,
            5455,
            &configuration,
            0.5,
            &decision,
            &[json!({"ref":5455})],
            1,
            ordinary.clone(),
            vec![],
        )?
        .expect("Higher fertile alternative");
        assert_eq!(forward["reference"], 5456);
        assert_ne!(forward["reference"], 5525);
        // Returning the source means a no-op, never a downgrade to the lower
        // fertile alternative or an invented successful maturation receipt.
        assert!(choose_prepared(
            &catalog,
            5456,
            &configuration,
            0.5,
            &decision,
            &[json!({"ref":5456})],
            2,
            ordinary.clone(),
            vec![]
        )?
        .is_none());
        for byte in 0u8..=31 {
            let decision = json!({"variant_seed":hex::encode([byte;32])});
            let recovered = choose_prepared(
                &catalog,
                5525,
                &configuration,
                0.5,
                &decision,
                &[json!({"ref":5525})],
                1,
                ordinary.clone(),
                vec![],
            )?
            .expect("Legacy tutorial exits to qualified fertile pool");
            assert!(matches!(recovered["reference"].as_i64(), Some(5455 | 5456)));
            assert_ne!(recovered["reference"], 5525);
        }
        Ok(())
    }

    #[test]
    fn special_arch_is_excluded_and_boss_draw_stays_rare() -> Result<()> {
        let ordinary = json!({"reference":4085,"min_level":10,"boss_classification":"regular"});
        let boss = json!({"reference":44,"min_level":15,"boss_classification":"boss"});
        let arch = json!({"reference":4086,"min_level":20,"boss_classification":"archmonster"});
        assert!(special(&arch));
        let catalog = json!({"families":[{"family_id":68,"tiers":[{"rank":0,"candidates":[ordinary.clone()]},{"rank":1,"candidates":[boss.clone()]},{"rank":2,"candidates":[arch]}]}]});
        let configuration =
            json!({"base_probability":0.25,"boss_probability":0.00001,"stage_decay":0.5});
        let decision = json!({"variant_seed":"17".repeat(32)});
        let pool = vec![vec![ordinary], vec![], vec![]];
        let select = |reference, level, draw| {
            choose_prepared(
                &catalog,
                reference,
                &configuration,
                draw,
                &decision,
                &[json!({"ref":reference})],
                level,
                pool.clone(),
                vec![boss.clone()],
            )
        };
        assert_eq!(select(4085, 10, 0.000009)?.unwrap()["reference"], 44);
        // At the exact rare-boss boundary, the ordinary source is selected.
        // A self-selection is intentionally None, not a new actor/reference.
        assert!(select(4085, 10, 0.00001)?.is_none());
        assert!(select(4085, 10, 0.99)?.is_none());
        assert!(select(44, 15, 0.0)?.is_none());
        assert!(select(4086, 20, 0.0)?.is_none());
        for i in 0..1000 {
            if let Some(candidate) = select(4085, 10, i as f64 / 1000.0)? {
                assert_eq!(candidate["reference"], 44);
                assert_ne!(candidate["reference"], 4086);
            }
        }
        Ok(())
    }
}

#[cfg(test)]
mod monotone_contract {
    use super::*;

    #[test]
    fn all_qualified_topologies_rosters_and_draws_never_regress_stage_or_level() -> Result<()> {
        // The kernel is independent of species. Exhaust all seven-band hole
        // patterns, every remaining source, both same-band level alternatives,
        // old roster-size/draw boundaries and minimum/administrative levels.
        let configuration =
            json!({"base_probability":0.97,"stage_decay":0.5,"boss_probability":0.02});
        let mut successful = 0;
        for mask in 1u16..128 {
            let tiers: Vec<Value> = (0..7)
                .map(|rank| {
                    json!({"rank":rank,"candidates":[
                {"reference":rank*2+1,"min_level":rank*4+1,"boss_classification":"regular"},
                {"reference":rank*2+2,"min_level":rank*4+3,"boss_classification":"regular"}]})
                })
                .collect();
            let catalog = json!({"families":[{"family_id":68,"tiers":tiers}]});
            let pool: Vec<Vec<Value>> = tiers
                .iter()
                .enumerate()
                .map(|(rank, tier)| {
                    if mask & (1 << rank) != 0 {
                        tier["candidates"].as_array().unwrap().clone()
                    } else {
                        vec![]
                    }
                })
                .collect();
            for source_rank in 0..7usize {
                for source in tiers[source_rank]["candidates"].as_array().unwrap() {
                    let reference = integer(source, "reference")?;
                    for level in [integer(source, "min_level")? as i32, 40] {
                        for size in [1usize, 4, 8] {
                            let members = vec![json!({"ref":reference}); size];
                            for draw in [0.0, 0.019, 0.02, 0.2, 0.5, 0.9, 0.999999] {
                                for byte in [0u8, 17, 255] {
                                    let decision = json!({"variant_seed":hex::encode([byte;32])});
                                    if let Some(candidate) = choose_prepared(
                                        &catalog,
                                        reference,
                                        &configuration,
                                        draw,
                                        &decision,
                                        &members,
                                        level,
                                        pool.clone(),
                                        vec![],
                                    )? {
                                        let (family, target_rank, _) =
                                            stage(&catalog, integer(&candidate, "reference")?)?
                                                .unwrap();
                                        assert_eq!(family["family_id"], 68);
                                        assert!(target_rank >= source_rank);
                                        assert!(
                                            integer(&candidate, "min_level")? >= i64::from(level)
                                        );
                                        successful += 1;
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
        assert!(successful > 0);
        Ok(())
    }

    #[test]
    fn adult_gobball_never_returns_to_gobblies_or_reduces_same_band_level() -> Result<()> {
        let catalog = json!({"families":[{"family_id":68,"tiers":[
            {"rank":0,"candidates":[{"reference":2,"min_level":4},{"reference":39,"min_level":4}]},
            {"rank":1,"candidates":[{"reference":1,"min_level":8},{"reference":41,"min_level":10}]},
            {"rank":2,"candidates":[{"reference":3,"min_level":14}]}]}]});
        let ordinary: Vec<Vec<Value>> = catalog["families"][0]["tiers"]
            .as_array()
            .unwrap()
            .iter()
            .map(|tier| tier["candidates"].as_array().unwrap().clone())
            .collect();
        let configuration =
            json!({"base_probability":0.97,"stage_decay":0.5,"boss_probability":0.02});
        for level in [10, 20] {
            for size in [1usize, 4, 8] {
                for draw in [0.0, 0.02, 0.1, 0.2, 0.3, 0.5, 0.8, 0.9, 0.999] {
                    for byte in 0u8..32 {
                        let decision = json!({"variant_seed":hex::encode([byte;32])});
                        if let Some(candidate) = choose_prepared(
                            &catalog,
                            41,
                            &configuration,
                            draw,
                            &decision,
                            &vec![json!({"ref":41}); size],
                            level,
                            ordinary.clone(),
                            vec![],
                        )? {
                            assert!(![2, 39, 1].contains(&integer(&candidate, "reference")?));
                            assert!(integer(&candidate, "min_level")? >= i64::from(level));
                        }
                    }
                }
            }
        }
        Ok(())
    }
}

#[cfg(test)]
#[path = "legacy_balance_contract.rs"]
mod legacy_balance_contract;
