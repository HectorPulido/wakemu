//! Bounded native flora planning. World remains the sole mutation/publication owner.
use anyhow::{anyhow, ensure, Context as _, Result};
use chrono::{DateTime, Utc};
use serde::Deserialize;
use serde_json::{json, Map, Value};
use sha2::{Digest, Sha256};
use std::collections::{HashMap, HashSet, VecDeque};
use std::sync::{Arc, Mutex, OnceLock};
use std::time::{Duration, Instant};
use tokio_postgres::types::ToSql;

use super::{native_monster, planting_intents};
use crate::Context;

const RESOURCE_KEYS: [&str; 9] = [
    "resource_uid",
    "map_id",
    "instance_id",
    "x",
    "y",
    "z",
    "resource_reference",
    "stage",
    "creation_time",
];
const MAX_BIRTH_BATCH: i64 = 64;
const MAX_BIRTH_BYTES: usize = 224 * 1024;

#[derive(Default)]
struct Cursors {
    epochs: VecDeque<(String, HashMap<String, i64>)>,
}
static CURSORS: OnceLock<Mutex<Cursors>> = OnceLock::new();
fn cursor(epoch: &str, category: &str) -> i64 {
    let mut state = CURSORS
        .get_or_init(Default::default)
        .lock()
        .unwrap_or_else(|e| e.into_inner());
    if !state.epochs.iter().any(|(key, _)| key == epoch) {
        if state.epochs.len() == 8 {
            state.epochs.pop_front();
        }
        state.epochs.push_back((epoch.to_owned(), HashMap::new()));
    }
    state
        .epochs
        .iter()
        .find(|(key, _)| key == epoch)
        .and_then(|(_, entries)| entries.get(category))
        .copied()
        .unwrap_or(0)
}
fn set_cursor(epoch: &str, category: &str, uid: i64) {
    let mut state = CURSORS
        .get_or_init(Default::default)
        .lock()
        .unwrap_or_else(|e| e.into_inner());
    if !state.epochs.iter().any(|(key, _)| key == epoch) {
        if state.epochs.len() == 8 {
            state.epochs.pop_front();
        }
        state.epochs.push_back((epoch.to_owned(), HashMap::new()));
    }
    state
        .epochs
        .iter_mut()
        .find(|(key, _)| key == epoch)
        .expect("registered epoch")
        .1
        .insert(category.to_owned(), uid);
}
fn integer(value: &Value, key: &str) -> Result<i64> {
    value
        .get(key)
        .and_then(Value::as_i64)
        .ok_or_else(|| anyhow!("Invalid native integer: {key}"))
}
fn array<'a>(value: &'a Value, key: &str) -> Result<&'a Vec<Value>> {
    value
        .get(key)
        .and_then(Value::as_array)
        .ok_or_else(|| anyhow!("Missing native collection: {key}"))
}
fn resource(row: &Value) -> Result<Value> {
    let mut output = Map::new();
    for key in RESOURCE_KEYS {
        output.insert(
            key.to_owned(),
            row.get(key)
                .cloned()
                .with_context(|| format!("Missing native resource field: {key}"))?,
        );
    }
    Ok(Value::Object(output))
}
fn resource_cell(row: &Value) -> Result<[i64; 5]> {
    Ok([
        integer(row, "map_id")?,
        integer(row, "instance_id")?,
        integer(row, "x")?,
        integer(row, "y")?,
        integer(row, "z")?,
    ])
}
fn fixed_resource(definition: &Value) -> bool {
    definition.get("monster_resource").and_then(Value::as_bool) == Some(false)
        && definition
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
            .any(|action| {
                matches!(
                    action.get("profession_id").and_then(Value::as_i64),
                    Some(73 | 75)
                )
            })
}
fn timestamp_python(value: &Value) -> Result<String> {
    let source = value
        .as_str()
        .ok_or_else(|| anyhow!("Invalid refill timestamp"))?;
    let value = DateTime::parse_from_rfc3339(source).context("Invalid refill timestamp")?;
    Ok(if value.timestamp_subsec_micros() == 0 {
        value.format("%Y-%m-%dT%H:%M:%S%:z").to_string()
    } else {
        value.format("%Y-%m-%dT%H:%M:%S%.6f%:z").to_string()
    })
}

#[derive(Default)]
struct SeedLog {
    entries: HashMap<i64, (String, Instant)>,
    order: VecDeque<i64>,
}
static SEED_LOG: OnceLock<Mutex<SeedLog>> = OnceLock::new();
fn seed_log(resource: &Value, state: &str, details: Value) {
    let Some(uid) = resource.get("resource_uid").and_then(Value::as_i64) else {
        return;
    };
    let now = Instant::now();
    let mut log = SEED_LOG
        .get_or_init(Default::default)
        .lock()
        .unwrap_or_else(|e| e.into_inner());
    if let Some((previous, at)) = log.entries.get(&uid) {
        if previous == state && now.duration_since(*at) < Duration::from_secs(30) {
            return;
        }
    }
    if !log.entries.contains_key(&uid) {
        if log.entries.len() >= 1024 {
            if let Some(old) = log.order.pop_front() {
                log.entries.remove(&old);
            }
        }
        log.order.push_back(uid);
    }
    log.entries.insert(uid, (state.to_owned(), now));
    let mut event = json!({"event":"ecology_seed_growth", "state":state, "resource_uid":uid,
        "map_id":resource["map_id"], "instance_id":resource["instance_id"],
        "position":[resource["x"],resource["y"],resource["z"]]});
    if let (Some(out), Some(extra)) = (event.as_object_mut(), details.as_object()) {
        out.extend(extra.iter().map(|(k, v)| (k.clone(), v.clone())));
    }
    println!("{event}");
}

/// Normalize native families using anchored bands, never transitive level chains.
pub fn normalize_growth_catalog(mut catalog: Value) -> Result<Value> {
    for family in catalog
        .get_mut("families")
        .and_then(Value::as_array_mut)
        .ok_or_else(|| anyhow!("Missing native growth families"))?
    {
        let mut candidates: Vec<Value> = array(family, "tiers")?
            .iter()
            .flat_map(|tier| {
                tier.get("candidates")
                    .and_then(Value::as_array)
                    .into_iter()
                    .flatten()
                    .cloned()
            })
            .collect();
        for candidate in &candidates {
            integer(candidate, "min_level")?;
            integer(candidate, "reference")?;
            ensure!(
                candidate["boss_classification"].is_string(),
                "Invalid native boss classification"
            );
        }
        candidates.sort_by_key(|row| {
            (
                row["min_level"].as_i64().unwrap(),
                row["reference"].as_i64().unwrap(),
            )
        });
        let mut tiers: Vec<Value> = Vec::new();
        let mut latest: HashMap<String, usize> = HashMap::new();
        for candidate in candidates {
            let level = integer(&candidate, "min_level")?;
            let classification = candidate["boss_classification"].as_str().unwrap();
            let kind = if classification != "regular" {
                classification.to_owned()
            } else if candidate
                .get("world_properties")
                .and_then(Value::as_array)
                .is_some_and(|properties| {
                    properties
                        .iter()
                        .any(|property| property.as_i64() == Some(115))
                })
            {
                "dominant".to_owned()
            } else {
                "regular".to_owned()
            };
            let previous = latest.get(&kind).copied();
            let index = match previous {
                Some(index)
                    if level - integer(&tiers[index], "min_level")?
                        <= 3.max(integer(&tiers[index], "min_level")? / 20) =>
                {
                    index
                }
                _ => {
                    let index = tiers.len();
                    tiers.push(json!({"min_level":level,"kind":kind,"candidates":[]}));
                    latest.insert(kind.clone(), index);
                    index
                }
            };
            tiers[index]["candidates"]
                .as_array_mut()
                .unwrap()
                .push(candidate);
        }
        tiers.sort_by_key(|tier| {
            (
                tier["min_level"].as_i64().unwrap(),
                tier["kind"].as_str() != Some("regular"),
                tier["candidates"][0]["reference"].as_i64().unwrap(),
            )
        });
        for (rank, tier) in tiers.iter_mut().enumerate() {
            let values = tier.as_object_mut().unwrap();
            values.remove("kind");
            values.insert("rank".to_owned(), json!(rank));
        }
        family["terminal"] = json!(tiers.len() <= 1);
        family["tiers"] = json!(tiers);
    }
    Ok(catalog)
}

#[derive(Clone, Copy, Deserialize)]
struct SeedBinding {
    item_reference: i64,
    resource_reference: i64,
}
#[derive(Deserialize)]
struct SourceMonster {
    #[serde(rename = "ref")]
    reference: i64,
    family_id: i64,
    min_level: i32,
    name: Option<String>,
}
#[derive(Deserialize)]
struct SourceMonsters {
    monsters: Vec<SourceMonster>,
}
#[derive(Clone, Copy)]
struct MonsterBinding {
    reference: i64,
    family_id: i64,
    min_level: i32,
    valid_name: bool,
}
#[derive(Deserialize)]
struct SourceAction {
    d: i64,
    #[serde(rename = "csP")]
    seed: i64,
    #[serde(rename = "clT")]
    criterion: Option<String>,
}
#[derive(Deserialize)]
struct SourceActions {
    #[serde(rename = "ref")]
    reference: i64,
    collect_actions: Vec<SourceAction>,
}
#[derive(Deserialize)]
struct SourceEncyclopedia {
    monsters: Vec<SourceActions>,
}
fn producer_index(source: SourceEncyclopedia) -> Vec<(i64, i64)> {
    let mut actions = HashMap::new();
    for monster in source.monsters {
        for action in monster.collect_actions {
            actions.insert(
                (monster.reference, action.d),
                (
                    action.seed,
                    action.criterion.is_some_and(|criterion| {
                        matches!(criterion.trim(), "" | "not IsDead(\"target\")")
                    }),
                ),
            );
        }
    }
    // The source dictionary resolves duplicate (monster, action) rows last-wins.
    let mut producers: Vec<_> = actions
        .into_iter()
        .filter_map(|((monster, _), (seed, allowed))| allowed.then_some((seed, monster)))
        .collect();
    producers.sort_unstable();
    producers.dedup();
    producers.shrink_to_fit();
    producers
}
struct GrowthFamily {
    family_id: i64,
    raw: Box<[u8]>,
}
struct PlantMetadata {
    seeds: Vec<SeedBinding>,
    monsters: Vec<MonsterBinding>,
    producers: Vec<(i64, i64)>,
    families: Vec<GrowthFamily>,
}
impl PlantMetadata {
    fn retained_bytes(&self) -> usize {
        self.seeds.capacity() * std::mem::size_of::<SeedBinding>()
            + self.monsters.capacity() * std::mem::size_of::<MonsterBinding>()
            + self.producers.capacity() * std::mem::size_of::<(i64, i64)>()
            + self.families.capacity() * std::mem::size_of::<GrowthFamily>()
            + self
                .families
                .iter()
                .map(|family| family.raw.len())
                .sum::<usize>()
            + 128
    }
    fn family(&self, id: i64) -> Result<Option<Value>> {
        match self
            .families
            .binary_search_by_key(&id, |family| family.family_id)
        {
            Ok(index) => Ok(Some(serde_json::from_slice(&self.families[index].raw)?)),
            Err(_) => Ok(None),
        }
    }
    fn monster(&self, reference: i64) -> Option<MonsterBinding> {
        self.monsters
            .binary_search_by_key(&reference, |monster| monster.reference)
            .ok()
            .map(|index| self.monsters[index])
    }
    fn fertile(&self, seeds: &HashSet<i64>) -> HashSet<i64> {
        let mut fertile = HashSet::new();
        for seed in seeds {
            let start = self.producers.partition_point(|(item, _)| item < seed);
            for (_, monster) in self.producers[start..]
                .iter()
                .take_while(|(item, _)| item == seed)
            {
                fertile.insert(*monster);
            }
        }
        fertile
    }
}
#[derive(Default)]
struct PlantMetadataCache {
    entries: HashMap<String, (Arc<PlantMetadata>, usize)>,
    order: VecDeque<String>,
    bytes: usize,
}
const PLANT_METADATA_BYTES: usize = 2 * 1024 * 1024;
static PLANT_METADATA: OnceLock<Mutex<PlantMetadataCache>> = OnceLock::new();
fn cached_plant_metadata(key: &str) -> Option<Arc<PlantMetadata>> {
    let mut cache = PLANT_METADATA
        .get_or_init(Default::default)
        .lock()
        .unwrap_or_else(|error| error.into_inner());
    let metadata = cache.entries.get(key)?.0.clone();
    cache.order.retain(|previous| previous != key);
    cache.order.push_back(key.to_owned());
    Some(metadata)
}
fn cache_plant_metadata(key: String, metadata: Arc<PlantMetadata>) {
    let cost = metadata
        .retained_bytes()
        .saturating_add(key.capacity() * 2)
        .saturating_add(192);
    if cost > PLANT_METADATA_BYTES {
        return;
    }
    let mut cache = PLANT_METADATA
        .get_or_init(Default::default)
        .lock()
        .unwrap_or_else(|error| error.into_inner());
    if let Some((_, previous)) = cache.entries.remove(&key) {
        cache.bytes -= previous;
    }
    cache.order.retain(|previous| previous != &key);
    cache.order.push_back(key.clone());
    cache.bytes += cost;
    cache.entries.insert(key, (metadata, cost));
    while cache.bytes > PLANT_METADATA_BYTES || cache.entries.len() > 8 {
        if let Some(previous) = cache.order.pop_front() {
            if let Some((_, cost)) = cache.entries.remove(&previous) {
                cache.bytes -= cost;
            }
        } else {
            break;
        }
    }
}
async fn plant_metadata(ctx: &Context) -> Result<Arc<PlantMetadata>> {
    let key = ctx
        .catalog
        .compiled_generation()
        .map(|generation| format!("{}:{generation}", ctx.catalog.revision()));
    if let Some(key) = key.as_deref() {
        if let Some(metadata) = cached_plant_metadata(key) {
            return Ok(metadata);
        }
    }
    // Deserialize only the numeric ownership/index columns. Large combat,
    // ability and encyclopedia graphs are skipped by serde, never retained.
    let mut seeds: HashMap<i64, SeedBinding> = HashMap::new();
    for seed in serde_json::from_slice::<Vec<SeedBinding>>(
        &ctx.catalog.document_bytes("seed-actions.json").await?,
    )? {
        seeds.insert(seed.item_reference, seed);
    }
    let mut seeds: Vec<_> = seeds.into_values().collect();
    seeds.sort_unstable_by_key(|seed| seed.item_reference);
    let mut monsters = HashMap::new();
    for monster in serde_json::from_slice::<SourceMonsters>(
        &ctx.catalog.document_bytes("monsters.json").await?,
    )?
    .monsters
    {
        let valid_name = monster
            .name
            .is_some_and(|name| !name.trim().is_empty() && name.len() <= 65535);
        monsters.insert(
            monster.reference,
            MonsterBinding {
                reference: monster.reference,
                family_id: monster.family_id,
                min_level: monster.min_level,
                valid_name,
            },
        );
    }
    let mut monsters: Vec<_> = monsters.into_values().collect();
    monsters.sort_unstable_by_key(|monster| monster.reference);
    let producers = producer_index(serde_json::from_slice::<SourceEncyclopedia>(
        &ctx.catalog
            .document_bytes("monster-encyclopedia.json")
            .await?,
    )?);
    let mut growth =
        normalize_growth_catalog(ctx.catalog.document("monster-growth-catalog.json").await?)?;
    let mut families = HashMap::new();
    for family in growth["families"]
        .as_array_mut()
        .ok_or_else(|| anyhow!("Missing native growth families"))?
        .drain(..)
    {
        let id = integer(&family, "family_id")?;
        families.insert(
            id,
            GrowthFamily {
                family_id: id,
                raw: serde_json::to_vec(&family)?.into_boxed_slice(),
            },
        );
    }
    let mut families: Vec<_> = families.into_values().collect();
    families.sort_unstable_by_key(|family| family.family_id);
    let metadata = Arc::new(PlantMetadata {
        seeds,
        monsters,
        producers,
        families,
    });
    if let Some(key) = key {
        cache_plant_metadata(key, metadata.clone());
    }
    Ok(metadata)
}

#[derive(Default)]
struct InitialPools {
    entries: HashMap<String, (Arc<[u8]>, usize)>,
    order: VecDeque<String>,
    bytes: usize,
}
static INITIAL_POOLS: OnceLock<Mutex<InitialPools>> = OnceLock::new();
const INITIAL_POOL_CACHE_BYTES: usize = 2 * 1024 * 1024;

fn initial_pool_key(
    ctx: &Context,
    family: i64,
    eligible: Option<&HashSet<i64>>,
) -> Result<Option<String>> {
    let Some(generation) = ctx.catalog.compiled_generation() else {
        return Ok(None);
    };
    let mut references = eligible.map(|rows| rows.iter().copied().collect::<Vec<_>>());
    if let Some(rows) = references.as_mut() {
        rows.sort_unstable();
    }
    let selection = Sha256::digest(serde_json::to_vec(&references)?);
    Ok(Some(format!(
        "{}:{generation}:{family}:{}",
        ctx.catalog.revision(),
        hex::encode(selection)
    )))
}
fn cached_initial_pool(key: &str) -> Result<Option<Vec<Value>>> {
    let bytes = {
        let mut cache = INITIAL_POOLS
            .get_or_init(Default::default)
            .lock()
            .unwrap_or_else(|error| error.into_inner());
        let Some((bytes, _)) = cache.entries.get(key) else {
            return Ok(None);
        };
        let bytes = bytes.clone();
        cache.order.retain(|previous| previous != key);
        cache.order.push_back(key.to_owned());
        bytes
    };
    Ok(Some(serde_json::from_slice(&bytes)?))
}
fn cache_initial_pool(key: String, values: &[Value]) -> Result<()> {
    let bytes: Arc<[u8]> = serde_json::to_vec(values)?.into();
    let cost = bytes
        .len()
        .saturating_add(key.capacity() * 2)
        .saturating_add(192);
    if cost > INITIAL_POOL_CACHE_BYTES {
        return Ok(());
    }
    let mut cache = INITIAL_POOLS
        .get_or_init(Default::default)
        .lock()
        .unwrap_or_else(|error| error.into_inner());
    if let Some((_, previous)) = cache.entries.remove(&key) {
        cache.bytes -= previous;
    }
    cache.order.retain(|previous| previous != &key);
    cache.order.push_back(key.clone());
    cache.bytes += cost;
    cache.entries.insert(key, (bytes, cost));
    while cache.bytes > INITIAL_POOL_CACHE_BYTES || cache.entries.len() > 256 {
        if let Some(previous) = cache.order.pop_front() {
            if let Some((_, cost)) = cache.entries.remove(&previous) {
                cache.bytes -= cost;
            }
        } else {
            break;
        }
    }
    Ok(())
}

/// Match immutable native initial pools without retaining actors or live views.
pub async fn initial_candidates(
    ctx: &Context,
    family_id: i64,
    eligible_refs: Option<&HashSet<i64>>,
) -> Result<Vec<Value>> {
    let key = initial_pool_key(ctx, family_id, eligible_refs)?;
    if let Some(key) = key.as_deref() {
        if let Some(candidates) = cached_initial_pool(key)? {
            return Ok(candidates);
        }
    }
    let candidates = initial_candidates_uncached(ctx, family_id, eligible_refs).await?;
    if let Some(key) = key {
        cache_initial_pool(key, &candidates)?;
    }
    Ok(candidates)
}

/// Match the native initial-band preference, including publishability proofs.
async fn initial_candidates_uncached(
    ctx: &Context,
    family_id: i64,
    eligible_refs: Option<&HashSet<i64>>,
) -> Result<Vec<Value>> {
    let metadata = plant_metadata(ctx).await?;
    let Some(family) = metadata.family(family_id)? else {
        return Ok(Vec::new());
    };
    if array(&family, "tiers")?.is_empty() {
        return Ok(Vec::new());
    }
    let resources: HashSet<i64> = family
        .get("resource_references")
        .and_then(Value::as_array)
        .into_iter()
        .flatten()
        .filter_map(Value::as_i64)
        .collect();
    let seed_refs = metadata
        .seeds
        .iter()
        .filter(|seed| resources.contains(&seed.resource_reference))
        .map(|seed| seed.item_reference)
        .collect();
    let fertile = metadata.fertile(&seed_refs);
    let mut fallback = Vec::new();
    let mut chosen = Vec::new();
    for tier in array(&family, "tiers")? {
        let mut candidates = Vec::new();
        for candidate in array(tier, "candidates")? {
            let reference = integer(candidate, "reference")?;
            if candidate["boss_classification"] != "regular"
                || eligible_refs.is_some_and(|refs| !refs.contains(&reference))
            {
                continue;
            }
            let Some(definition) = metadata.monster(reference) else {
                continue;
            };
            if !definition.valid_name {
                continue;
            }
            let level = i32::try_from(integer(candidate, "min_level")?)?;
            if !native_monster::publication_viable(ctx, reference, level).await? {
                continue;
            }
            candidates.push(candidate.clone());
        }
        if fallback.is_empty() {
            fallback = candidates.clone();
        }
        let preferred: Vec<_> = candidates
            .into_iter()
            .filter(|candidate| fertile.contains(&candidate["reference"].as_i64().unwrap()))
            .collect();
        if !preferred.is_empty() {
            chosen = preferred;
            break;
        }
    }
    if chosen.is_empty() {
        chosen = fallback;
    }
    let allowed: HashSet<_> = chosen
        .iter()
        .map(|candidate| candidate["reference"].as_i64().unwrap())
        .collect();
    Ok(array(&family, "tiers")?
        .iter()
        .flat_map(|tier| tier["candidates"].as_array().into_iter().flatten())
        .filter(|candidate| allowed.contains(&candidate["reference"].as_i64().unwrap_or(0)))
        .cloned()
        .collect())
}

#[derive(Default)]
struct BirthChoices {
    entries: HashMap<String, (Vec<(i64, i32)>, usize)>,
    order: VecDeque<String>,
    bytes: usize,
}
static BIRTH_CHOICES: OnceLock<Mutex<BirthChoices>> = OnceLock::new();
const BIRTH_CHOICE_CACHE_BYTES: usize = 1024 * 1024;

fn cached_birth_choices(key: &str) -> Option<Vec<(i64, i32)>> {
    let mut cache = BIRTH_CHOICES
        .get_or_init(Default::default)
        .lock()
        .unwrap_or_else(|error| error.into_inner());
    let choices = cache.entries.get(key)?.0.clone();
    cache.order.retain(|previous| previous != key);
    cache.order.push_back(key.to_owned());
    Some(choices)
}
fn cache_birth_choices(key: String, choices: Vec<(i64, i32)>) {
    let cost = choices
        .capacity()
        .saturating_mul(std::mem::size_of::<(i64, i32)>())
        .saturating_add(key.capacity() * 2)
        .saturating_add(192);
    if cost > BIRTH_CHOICE_CACHE_BYTES {
        return;
    }
    let mut cache = BIRTH_CHOICES
        .get_or_init(Default::default)
        .lock()
        .unwrap_or_else(|error| error.into_inner());
    if let Some((_, previous)) = cache.entries.remove(&key) {
        cache.bytes -= previous;
    }
    cache.order.retain(|previous| previous != &key);
    cache.bytes += cost;
    cache.order.push_back(key.clone());
    cache.entries.insert(key, (choices, cost));
    while cache.bytes > BIRTH_CHOICE_CACHE_BYTES || cache.entries.len() > 256 {
        if let Some(previous) = cache.order.pop_front() {
            if let Some((_, cost)) = cache.entries.remove(&previous) {
                cache.bytes -= cost;
            }
        } else {
            break;
        }
    }
}

async fn birth_choices(
    ctx: &Context,
    resource: &Value,
    definition: &Value,
) -> Result<Vec<(i64, i32)>> {
    // Only immutable eligibility is retained: no position, actor, identity or RNG.
    let reference = integer(definition, "resource_reference")?;
    let key = ctx
        .catalog
        .compiled_generation()
        .map(|generation| format!("{}:{generation}:{reference}", ctx.catalog.revision()));
    if let Some(key) = key.as_deref() {
        if let Some(choices) = cached_birth_choices(key) {
            return Ok(choices);
        }
    }
    let metadata = plant_metadata(ctx).await?;
    let resource_reference = integer(definition, "resource_reference")?;
    let seed_refs: HashSet<_> = metadata
        .seeds
        .iter()
        .filter(|seed| seed.resource_reference == resource_reference)
        .map(|seed| seed.item_reference)
        .collect();
    let fertile = metadata.fertile(&seed_refs);
    let families: HashSet<_> = array(definition, "monster_family_ids")?
        .iter()
        .map(|value| {
            value
                .as_i64()
                .ok_or_else(|| anyhow!("Invalid native monster family"))
        })
        .collect::<Result<_>>()?;
    let mut fallback = HashSet::new();
    let mut eligible = HashSet::new();
    for template in &metadata.monsters {
        if !families.contains(&template.family_id) {
            continue;
        }
        let reference = template.reference;
        let level = template.min_level;
        if let Err(error) = native_monster::owned_instance_in(
            ctx,
            reference,
            level,
            -1,
            i32::try_from(integer(resource, "map_id")?)?,
            0,
            1,
            i32::try_from(integer(resource, "x")?)?,
            i32::try_from(integer(resource, "y")?)?,
            i16::try_from(integer(resource, "z")?)?,
        )
        .await
        {
            if error.chain().any(|cause| {
                cause.is::<tokio_postgres::Error>() || cause.is::<deadpool_postgres::PoolError>()
            }) {
                return Err(error);
            }
            continue;
        }
        fallback.insert(reference);
        if fertile.contains(&reference) {
            eligible.insert(reference);
        }
    }
    let allowed = if eligible.is_empty() {
        fallback
    } else {
        eligible
    };
    let mut candidates = Vec::new();
    for family in array(definition, "monster_family_ids")? {
        candidates.extend(
            initial_candidates(
                ctx,
                family
                    .as_i64()
                    .ok_or_else(|| anyhow!("Invalid native monster family"))?,
                Some(&allowed),
            )
            .await?,
        );
    }

    let mut choices = Vec::with_capacity(candidates.len());
    for candidate in candidates {
        let reference = integer(&candidate, "reference")?;
        let template = metadata
            .monster(reference)
            .ok_or_else(|| anyhow!("Missing native initial monster reference"))?;
        choices.push((reference, template.min_level));
    }
    if let Some(key) = key {
        cache_birth_choices(key, choices.clone());
    }
    Ok(choices)
}

async fn growth_member(
    ctx: &Context,
    resource: &Value,
    definition: &Value,
    decision_seed: Option<&str>,
) -> Result<Option<Value>> {
    // Validate the public placement even on an immutable metadata cache hit.
    let map = i32::try_from(integer(resource, "map_id")?)?;
    ensure!(map > 0, "Invalid local monster map or team");
    let x = i32::try_from(integer(resource, "x")?)?;
    let y = i32::try_from(integer(resource, "y")?)?;
    let z = i16::try_from(integer(resource, "z")?)?;
    let instance = integer(resource, "instance_id")?;
    ensure!(instance >= 0, "Invalid local monster map or team");
    let candidates = birth_choices(ctx, resource, definition).await?;
    if candidates.is_empty() {
        seed_log(
            resource,
            "unavailable",
            json!({"reason":"Native seed family has no eligible initial monster form"}),
        );
        return Ok(None);
    }
    let ((reference, level), group_id) = if let Some(seed) = decision_seed {
        let rank = |label: &str| -> [u8; 32] {
            Sha256::digest(format!("{seed}:{label}").as_bytes()).into()
        };
        let candidate = candidates
            .iter()
            .min_by_key(|(reference, _)| rank(&format!("variant:{reference}")))
            .copied()
            .unwrap();
        let identity = rank("preview_identity");
        (
            candidate,
            u64::from_be_bytes(identity[..8].try_into().unwrap()) % ((1u64 << 62) - 1) + 1,
        )
    } else {
        (
            candidates[rand::random_range(0..candidates.len())],
            (rand::random::<u64>() & ((1u64 << 62) - 1)) + 1,
        )
    };
    Ok(Some(
        native_monster::owned_instance_in(
            ctx,
            reference,
            level,
            -i64::try_from(group_id)?,
            map,
            instance,
            1,
            x,
            y,
            z,
        )
        .await?,
    ))
}

async fn prepare_birth_batch(
    ctx: &Context,
    snapshot: &Value,
    refs: &[i64],
    delay: f64,
    occupied: &HashSet<[i64; 5]>,
) -> Result<Vec<Value>> {
    let epoch = snapshot["world_epoch"].as_str().unwrap();
    let after = cursor(epoch, "monster_bulk");
    let threshold = integer(snapshot, "now_ms")?
        .checked_sub((delay * 1000.0).trunc() as i64)
        .ok_or_else(|| anyhow!("Ecology growth clock overflow"))?;
    let db = ctx.db.get().await?;
    let rows=db.query("SELECT to_jsonb(p) AS row FROM planted_resources p WHERE stage=1 AND creation_time<=$1 AND resource_reference=ANY($2::bigint[]) ORDER BY (resource_uid<=$3),resource_uid LIMIT $4",&[&threshold,&refs,&after,&MAX_BIRTH_BATCH]).await?;
    drop(db);
    let mut resources = Vec::new();
    for row in rows {
        let resource = resource(&row.get::<_, Value>("row"))?;
        set_cursor(epoch, "monster_bulk", integer(&resource, "resource_uid")?);
        if occupied.contains(&resource_cell(&resource)?) {
            continue;
        }
        let definition = ctx
            .catalog
            .resource_definition(integer(&resource, "resource_reference")?)
            .await?;
        let seed = format!(
            "seed-birth:{}:{}:{}",
            integer(&resource, "resource_uid")?,
            integer(&resource, "resource_reference")?,
            integer(&resource, "stage")?
        );
        let Some(member) = growth_member(ctx, &resource, &definition, Some(&seed)).await? else {
            continue;
        };
        resources.push(json!({"kind":"resource_growth","world_epoch":epoch,"expected":resource,"transition":null,"member":member}));
        let bulk = json!({"kind":"resource_growth_bulk","world_epoch":epoch,"resources":resources});
        if crate::protocol::json_bytes(&bulk, MAX_BIRTH_BYTES).is_err() {
            resources.pop();
            break;
        }
    }
    Ok(if resources.is_empty() {
        vec![]
    } else {
        vec![json!({"kind":"resource_growth_bulk","world_epoch":epoch,"resources":resources})]
    })
}

/// Plan a fair bounded set; cursors are advisory, never authority or receipts.
pub async fn prepare(ctx: &Context, snapshot: &Value, limit: usize) -> Result<Vec<Value>> {
    ensure!((1..=64).contains(&limit), "Invalid ecology growth batch");
    let epoch = snapshot
        .get("world_epoch")
        .and_then(Value::as_str)
        .filter(|epoch| !epoch.is_empty())
        .ok_or_else(|| anyhow!("Invalid ecology world snapshot"))?;
    let now_ms = integer(snapshot, "now_ms")?;
    let tick = snapshot
        .get("planning_tick")
        .map(|value| {
            value
                .as_u64()
                .ok_or_else(|| anyhow!("Invalid ecology world snapshot"))
        })
        .transpose()?
        .unwrap_or(0);
    let delay = snapshot
        .get("growth_seconds")
        .map(|value| {
            value
                .as_f64()
                .ok_or_else(|| anyhow!("Invalid ecology seed growth delay"))
        })
        .transpose()?
        .unwrap_or(30.0);
    ensure!(
        delay.is_finite() && delay > 0.0 && delay * 1000.0 <= i64::MAX as f64,
        "Invalid ecology seed growth delay"
    );
    let definitions = ctx.catalog.document("plant-resources.json").await?;
    let definitions = definitions
        .as_array()
        .ok_or_else(|| anyhow!("Invalid native resource definitions"))?;
    let mut refs = Vec::new();
    let mut excluded = Vec::new();
    for definition in definitions {
        let reference = integer(definition, "resource_reference")?;
        if definition["monster_resource"] == true {
            refs.push(reference);
            excluded.push(reference);
        } else if fixed_resource(definition) {
            excluded.push(reference);
        }
    }
    let mut occupied = HashSet::new();
    for player in snapshot
        .get("players")
        .and_then(Value::as_array)
        .into_iter()
        .flatten()
    {
        occupied.insert([
            integer(player, "map_id")?,
            player
                .get("instance_id")
                .map(|value| {
                    value
                        .as_i64()
                        .ok_or_else(|| anyhow!("Invalid ecology player instance"))
                })
                .transpose()?
                .unwrap_or(0),
            integer(player, "x")?,
            integer(player, "y")?,
            integer(player, "z")?,
        ]);
    }
    if snapshot
        .get("reserve_monster_births")
        .and_then(Value::as_bool)
        .unwrap_or(false)
    {
        return prepare_birth_batch(ctx, snapshot, &refs, delay, &occupied).await;
    }
    let skip_birth = snapshot
        .get("skip_monster_births")
        .and_then(Value::as_bool)
        .unwrap_or(false);
    let mut categories = if skip_birth {
        vec!["flora", "mineral", "fishing", "publication"]
    } else {
        vec!["monster", "flora", "mineral", "fishing", "publication"]
    };
    let rotation = tick as usize % categories.len();
    categories.rotate_left(rotation);
    let mut plans = if snapshot
        .get("skip_interactive")
        .and_then(Value::as_bool)
        .unwrap_or(false)
    {
        vec![]
    } else {
        planting_intents::prepare(ctx, snapshot, 4.min(limit)).await?
    };
    if plans.len() < limit {
        plans.extend(prepare_reconciliation(ctx, snapshot, 1).await?);
    }
    let growth_limit = limit.saturating_sub(plans.len());
    let now = Utc::now();
    let mut db = ctx.db.get().await?;
    let tx = db.transaction().await?;
    for (index, category) in categories.iter().enumerate() {
        let quota =
            growth_limit / categories.len() + usize::from(index < growth_limit % categories.len());
        if quota == 0 {
            continue;
        }
        let after = cursor(epoch, category);
        let quota = i64::try_from(quota)?;
        let threshold = now_ms
            .checked_sub((delay * 1000.0).trunc() as i64)
            .ok_or_else(|| anyhow!("Ecology growth clock overflow"))?;
        let (base,mut params):(String,Vec<&(dyn ToSql+Sync)>)=match *category {
            "monster" => ("SELECT p.* FROM planted_resources p WHERE p.stage=1 AND p.creation_time<=$1 AND p.resource_reference=ANY($2::bigint[])".to_owned(),vec![&threshold,&refs]),
            "flora" => ("SELECT p.*,t.to_stage,t.delay_ms,t.probability FROM planted_resources p JOIN resource_growth_transitions t ON t.resource_reference=p.resource_reference AND t.from_stage=p.stage WHERE p.creation_time+t.delay_ms<=$1 AND NOT(p.resource_reference=ANY($2::bigint[])) AND NOT EXISTS(SELECT 1 FROM environmental_owned_resources e WHERE e.resource_uid=p.resource_uid AND e.retired_at_ms IS NULL) AND NOT EXISTS(SELECT 1 FROM resource_growth_decisions d WHERE d.resource_uid=p.resource_uid AND d.from_stage=p.stage)".to_owned(),vec![&now_ms,&excluded]),
            "mineral" => ("SELECT resource_uid,available_at FROM mining_vein_slots WHERE enabled AND NOT active AND available_at<=$1".to_owned(),vec![&now]),
            "fishing" => ("SELECT resource_uid,available_at FROM fishing_spot_slots WHERE enabled AND NOT active AND available_at<=$1".to_owned(),vec![&now]),
            "publication" => ("SELECT resource_uid FROM planting_growth_outbox WHERE NOT published".to_owned(),vec![]),
            _=>unreachable!(),
        };
        let after_index = params.len() + 1;
        params.push(&after);
        let limit_index = params.len() + 1;
        params.push(&quota);
        let query=format!("SELECT to_jsonb(q) AS row FROM ({base}) q WHERE q.resource_uid>${after_index} ORDER BY q.resource_uid LIMIT ${limit_index}");
        let mut rows = tx.query(&query, &params).await?;
        if rows.is_empty() && after != 0 {
            params.pop();
            params.pop();
            let limit_index = params.len() + 1;
            params.push(&quota);
            rows=tx.query(&format!("SELECT to_jsonb(q) AS row FROM ({base}) q ORDER BY q.resource_uid LIMIT ${limit_index}"),&params).await?;
        }
        if let Some(last) = rows.last() {
            set_cursor(
                epoch,
                category,
                integer(&last.get::<_, Value>("row"), "resource_uid")?,
            );
        }
        for row in rows {
            let row: Value = row.get("row");
            if matches!(*category, "mineral" | "fishing") {
                plans.push(json!({"kind":format!("{category}_refill"),"world_epoch":epoch,"resource_uid":row["resource_uid"],"available_at":timestamp_python(&row["available_at"])?}));
            } else if *category == "publication" {
                plans.push(json!({"kind":"growth_publish","world_epoch":epoch,"resource_uid":row["resource_uid"]}));
            } else {
                let resource = resource(&row)?;
                let definition = ctx
                    .catalog
                    .resource_definition(integer(&resource, "resource_reference")?)
                    .await?;
                let (transition, member) = if *category == "monster" {
                    if occupied.contains(&resource_cell(&resource)?) {
                        seed_log(
                            &resource,
                            "blocked",
                            json!({"reason":"player_occupied","age_ms":now_ms-integer(&resource,"creation_time")?}),
                        );
                        continue;
                    }
                    let Some(member) = growth_member(ctx, &resource, &definition, None).await?
                    else {
                        continue;
                    };
                    seed_log(
                        &resource,
                        "prepared",
                        json!({"age_ms":now_ms-integer(&resource,"creation_time")?,"offspring_reference":member["ref"]}),
                    );
                    (Value::Null, member)
                } else {
                    ensure!(
                        array(&definition, "stages")?.contains(&row["to_stage"]),
                        "Growth stage absent from native definition"
                    );
                    (
                        json!([row["to_stage"], row["delay_ms"], row["probability"]]),
                        Value::Null,
                    )
                };
                plans.push(json!({"kind":"resource_growth","world_epoch":epoch,"expected":resource,"transition":transition,"member":member}));
            }
        }
    }
    tx.commit().await?;
    Ok(plans)
}

fn native_limits(
    catalog: &Value,
    map_id: i64,
    region_id: i64,
    kind: &str,
    family_id: i64,
) -> Result<(Option<i64>, Option<i64>)> {
    ensure!(
        matches!(kind, "monster" | "plant"),
        "Invalid ecological population kind"
    );
    let territory = catalog
        .get("territories")
        .and_then(|territories| territories.get(region_id.to_string()));
    if let Some(territory) = territory {
        ensure!(
            integer(territory, "map_id")? == map_id,
            "Native chief belongs to a different map"
        );
    }
    let wishes = territory
        .and_then(|territory| territory.get(format!("{kind}_wishes")))
        .and_then(Value::as_array);
    let matching: Vec<_> = wishes
        .into_iter()
        .flatten()
        .filter(|wish| wish.get("family_id").and_then(Value::as_i64) == Some(family_id))
        .collect();
    ensure!(matching.len() <= 1, "Duplicate native chief family wish");
    if let Some(wish) = matching.first() {
        let low = integer(wish, "minimum")?;
        let high = integer(wish, "maximum")?;
        ensure!(
            0 <= low && low <= high && high < i32::MAX as i64 + 1,
            "Invalid native chief equilibrium range"
        );
        return Ok((Some(low), Some(high)));
    }
    Ok(if kind == "monster" {
        (Some(0), Some(10))
    } else {
        (None, None)
    })
}
fn evaluate_correction(catalog: &Value, receipt: &Value) -> Result<(i64, String)> {
    let evidence = receipt
        .get("evidence")
        .ok_or_else(|| anyhow!("Missing ecology evidence"))?;
    let policy = &evidence["policy"];
    ensure!(
        matches!(
            evidence["limit_source"].as_str(),
            Some("local_fallback" | "native" | "local")
        ) && policy["version"].as_i64() == Some(2)
            && policy["unit"] == "basis_points",
        "Unsupported historical ecology receipt"
    );
    let (low, high) = native_limits(
        catalog,
        integer(evidence, "map_id")?,
        integer(evidence, "region_id")?,
        evidence["kind"]
            .as_str()
            .ok_or_else(|| anyhow!("Invalid ecology kind"))?,
        integer(evidence, "family_id")?,
    )?;
    let before = integer(evidence, "before_population")?;
    let after = integer(evidence, "after_population")?;
    ensure!(
        before >= 0 && after >= 0,
        "Invalid historical population evidence"
    );
    let balance = integer(policy, "balance_delta")?;
    let imbalance = integer(policy, "imbalance_delta")?;
    ensure!(
        (1..=10000).contains(&balance) && (-10000..=-1).contains(&imbalance),
        "Invalid historical ecology policy"
    );
    let distance = |population: i64| {
        low.map(|low| (low - population).max(population - high.unwrap()).max(0))
            .unwrap_or(0)
    };
    let expected = if distance(after) < distance(before) {
        balance
    } else if distance(after) > distance(before) {
        imbalance
    } else {
        0
    };
    let before_value = integer(receipt, "before_value")?;
    let expected_applied = (before_value + expected).clamp(-10000, 10000) - before_value;
    let actual = integer(receipt, "after_value")? - before_value;
    Ok((expected_applied - actual, crate::identity::digest(receipt)?))
}
async fn prepare_reconciliation(
    ctx: &Context,
    snapshot: &Value,
    limit: usize,
) -> Result<Vec<Value>> {
    let epoch = snapshot["world_epoch"]
        .as_str()
        .filter(|epoch| !epoch.is_empty())
        .ok_or_else(|| anyhow!("Invalid affinity reconciliation snapshot"))?;
    ensure!(
        (1..=16).contains(&limit),
        "Invalid affinity reconciliation snapshot"
    );
    let mut catalog: Option<Value> = None;
    let mut proposals = Vec::new();
    for player in snapshot
        .get("players")
        .and_then(Value::as_array)
        .into_iter()
        .flatten()
    {
        let (Some(character), Some(account)) = (
            player.get("id").and_then(Value::as_i64),
            player.get("account_id").and_then(Value::as_i64),
        ) else {
            continue;
        };
        if character <= 0 || account <= 0 {
            continue;
        }
        let mut db = ctx.db.get().await?;
        let tx = db.transaction().await?;
        if tx
            .query_opt(
                "SELECT account_id FROM characters WHERE id=$1 AND deleted_at IS NULL",
                &[&character],
            )
            .await?
            .is_none_or(|row| row.get::<_, i64>("account_id") != account)
        {
            continue;
        }
        let rows=tx.query("SELECT to_jsonb(r) AS receipt FROM personal_ecology_receipts r WHERE character_id=$1 AND evidence->>'limit_source'=ANY($2::text[]) ORDER BY revision",&[&character,&vec!["local_fallback","native","local"]]).await?;
        let completed:HashSet<String>=tx.query("SELECT evidence->'original'->>'original_operation' AS original_operation FROM personal_ecology_receipts WHERE character_id=$1 AND operation LIKE 'native-chief-correction:%'",&[&character]).await?.iter().filter_map(|row|row.get::<_,Option<String>>("original_operation")).collect();
        let mut operations = Vec::new();
        for row in rows {
            let receipt: Value = row.get("receipt");
            let operation = receipt["operation"].as_str().unwrap_or("");
            if completed.contains(operation) {
                continue;
            }
            if !matches!(
                receipt["evidence"]["limit_source"].as_str(),
                Some("local_fallback" | "native" | "local")
            ) || receipt["evidence"]["policy"]["version"].as_i64() != Some(2)
                || receipt["evidence"]["policy"]["unit"] != "basis_points"
            {
                continue;
            }
            if catalog.is_none() {
                catalog = Some(
                    ctx.catalog
                        .document("territory-protector-bonuses.json")
                        .await?,
                );
            }
            if let Ok((delta, fingerprint)) =
                evaluate_correction(catalog.as_ref().unwrap(), &receipt)
            {
                if delta > 0 {
                    operations.push(json!({"operation":operation,"receipt_sha256":fingerprint}));
                    if operations.len() == 16 {
                        break;
                    }
                }
            }
        }
        tx.commit().await?;
        if !operations.is_empty() {
            proposals.push(json!({"kind":"affinity_reconcile","world_epoch":epoch,"character_id":character,"account_id":account,"original_operations":operations}));
            if proposals.len() == limit {
                break;
            }
        }
    }
    Ok(proposals)
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn compact_metadata_skips_combat_graphs_and_keeps_last_native_action() {
        let source = serde_json::from_value::<SourceEncyclopedia>(json!({"monsters":[
            {"ref":7,"collect_actions":[{"d":1,"csP":9,"clT":""},{"d":2,"csP":8,"clT":"IsDead(\"target\")"}]},
            {"ref":7,"collect_actions":[{"d":1,"csP":10,"clT":" not IsDead(\"target\") "}]},
            {"ref":8,"collect_actions":[{"d":1,"csP":10,"clT":""},{"d":2,"csP":10,"clT":""}]}
        ]})).unwrap();
        let metadata = PlantMetadata {
            seeds: vec![],
            monsters: vec![],
            families: vec![],
            producers: producer_index(source),
        };
        assert_eq!(metadata.producers, vec![(10, 7), (10, 8)]);
        assert_eq!(
            metadata.fertile(&HashSet::from([10])),
            HashSet::from([7, 8])
        );
        assert!(metadata.fertile(&HashSet::from([8, 9, 11])).is_empty());
        let monsters: SourceMonsters = serde_json::from_value(json!({"monsters":[{
            "ref":7,"family_id":3,"min_level":2,"name":"Native",
            "combat_graph":{"unknown":{"nested":[1,2,3]}},"statistics":null
        }]}))
        .unwrap();
        assert_eq!(monsters.monsters[0].reference, 7);
        assert!(metadata.retained_bytes() < PLANT_METADATA_BYTES);
    }
    #[test]
    fn anchored_bands_do_not_chain_and_special_forms_keep_their_kind() {
        let candidate = |reference, level, classification: &str, properties: Vec<i64>| json!({"reference":reference,"min_level":level,"boss_classification":classification,"world_properties":properties});
        let source = json!({"families":[{"family_id":1,"tiers":[{"candidates":[candidate(3,16,"regular",vec![]),candidate(1,10,"regular",vec![]),candidate(2,13,"regular",vec![]),candidate(4,10,"regular",vec![115])]}]}]});
        let normalized = normalize_growth_catalog(source).unwrap();
        let tiers = normalized["families"][0]["tiers"].as_array().unwrap();
        assert_eq!(tiers.len(), 3);
        assert_eq!(tiers[0]["candidates"].as_array().unwrap().len(), 2);
        assert_eq!(tiers[1]["candidates"][0]["reference"], 4);
        assert_eq!(tiers[2]["min_level"], 16);
    }
    #[test]
    fn historical_correction_only_restores_excess_old_charge() {
        let catalog = json!({"territories":{"7":{"map_id":1,"monster_wishes":[{"family_id":3,"minimum":10,"maximum":20}],"plant_wishes":[]}}});
        let receipt = json!({"character_id":1,"operation":"old","requested_delta":-100,"before_value":0,"after_value":-100,"revision":1,"evidence":{"limit_source":"native","map_id":1,"region_id":7,"kind":"monster","family_id":3,"before_population":10,"after_population":11,"policy":{"version":2,"unit":"basis_points","balance_delta":100,"imbalance_delta":-100}}});
        assert_eq!(evaluate_correction(&catalog, &receipt).unwrap().0, 100);
    }
    #[test]
    fn immutable_initial_pool_cache_returns_private_rows_and_rejects_oversize() {
        let key = "unit:private-initial-pool".to_owned();
        let values = vec![json!({"reference":42,"min_level":10,"metadata":{"native":true}})];
        cache_initial_pool(key.clone(), &values).unwrap();
        let mut copied = cached_initial_pool(&key).unwrap().unwrap();
        copied[0]["metadata"]["native"] = json!(false);
        assert_eq!(cached_initial_pool(&key).unwrap().unwrap(), values);
        let oversized = vec![json!({"metadata":"x".repeat(INITIAL_POOL_CACHE_BYTES)})];
        cache_initial_pool("unit:oversized-initial-pool".to_owned(), &oversized).unwrap();
        assert!(cached_initial_pool("unit:oversized-initial-pool")
            .unwrap()
            .is_none());
        let cache = INITIAL_POOLS.get().unwrap().lock().unwrap();
        assert!(cache.bytes <= INITIAL_POOL_CACHE_BYTES && cache.entries.len() <= 256);
    }
    #[test]
    fn refill_timestamp_matches_python_microsecond_isoformat() {
        assert_eq!(
            timestamp_python(&json!("2026-11-14T01:02:03+00:00")).unwrap(),
            "2026-11-14T01:02:03+00:00"
        );
        assert_eq!(
            timestamp_python(&json!("2026-11-14T01:02:03.123+00:00")).unwrap(),
            "2026-11-14T01:02:03.123000+00:00"
        );
    }
}
