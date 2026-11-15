//! Durable decision and pending-slot identities, compatible with Python ecology.
use anyhow::{bail, ensure, Context as _, Result};
use serde_json::{json, Value};
use sha2::{Digest, Sha256};
use std::collections::{HashMap, HashSet};

pub use crate::protocol::{canonical_bytes, proposal};
pub fn canonical_json_bytes(value: &Value) -> Result<Vec<u8>> {
    canonical_bytes(value)
}
pub fn digest(value: &Value) -> Result<String> {
    Ok(hex::encode(Sha256::digest(canonical_bytes(value)?)))
}
fn kind(value: &Value) -> &str {
    value
        .get("kind")
        .or_else(|| value.get("operation"))
        .and_then(Value::as_str)
        .unwrap_or("")
}
fn specification(value: &Value) -> Option<(&'static str, usize)> {
    match kind(value) {
        "resource_growth_bulk" => Some(("resources", 64)),
        "lifecycle_bulk" => Some(("operations", 16)),
        _ => None,
    }
}
fn required<'a>(value: &'a Value, key: &str) -> Result<&'a Value> {
    value
        .get(key)
        .with_context(|| format!("Missing ecology identity field {key}"))
}
fn select(value: &Value, fields: &[&str], required_fields: bool) -> Result<Value> {
    let mut out = serde_json::Map::new();
    for field in fields {
        out.insert(
            (*field).into(),
            if required_fields {
                required(value, field)?.clone()
            } else {
                value[*field].clone()
            },
        );
    }
    Ok(Value::Object(out))
}
fn scope(entry: &Value) -> Value {
    entry.get("scope").cloned().unwrap_or_else(|| {
        let source = entry
            .get("expected")
            .or_else(|| entry.get("ticket"))
            .unwrap_or(&Value::Null);
        json!([source["map_id"], source["instance_id"]])
    })
}

pub fn bulk_entry_key(entry: &Value) -> Result<Value> {
    if kind(entry) == "resource_growth" {
        return Ok(json!([
            entry["expected"]["resource_uid"],
            entry["expected"]["stage"],
            entry["expected"].get("resource_reference")
        ]));
    }
    if let Some(ticket) = entry.get("ticket").filter(|x| !x.is_null()) {
        return Ok(json!([
            entry["kind"],
            select(
                ticket,
                &[
                    "map_id",
                    "instance_id",
                    "group_id",
                    "monster_id",
                    "reference",
                    "cycle",
                    "plan_incarnation"
                ],
                false
            )?
        ]));
    }
    Ok(entry.clone())
}

pub fn bulk_failure_identity(domain: &str, epoch: &str, entry: &Value) -> Result<String> {
    let value = if kind(entry) == "resource_growth" {
        json!([
            domain,
            "resource_growth",
            select(
                &entry["expected"],
                &[
                    "resource_uid",
                    "map_id",
                    "instance_id",
                    "resource_reference",
                    "creation_time",
                    "stage"
                ],
                false
            )?
        ])
    } else {
        json!([epoch, domain, bulk_entry_key(entry)?])
    };
    let mut hasher = Sha256::new();
    hasher.update(b"bulk_failure_guard:");
    hasher.update(canonical_bytes(&value)?);
    Ok(hex::encode(hasher.finalize()))
}

pub fn filter_failed_bulk(row: &Value, exhausted: &HashSet<String>) -> Result<Option<Value>> {
    let domain = row["domain"].as_str().context("Missing ecology domain")?;
    let epoch = row["world_epoch"]
        .as_str()
        .context("Missing ecology epoch")?;
    if let Some((field, _)) = specification(&row["payload"]) {
        let entries = row["payload"][field]
            .as_array()
            .context("Missing ecology bulk entries")?;
        let retained = entries
            .iter()
            .filter_map(|entry| match bulk_failure_identity(domain, epoch, entry) {
                Ok(id) if exhausted.contains(&id) => None,
                Ok(_) => Some(Ok(entry.clone())),
                Err(e) => Some(Err(e)),
            })
            .collect::<Result<Vec<_>>>()?;
        if retained.is_empty() {
            return Ok(None);
        }
        if retained.len() == entries.len() {
            return Ok(Some(row.clone()));
        }
        let mut payload = row["payload"].clone();
        payload[field] = json!(retained);
        return Ok(Some(proposal(domain, payload, epoch)?));
    }
    if kind(&row["payload"]) == "resource_growth"
        && exhausted.contains(&bulk_failure_identity(domain, epoch, &row["payload"])?)
    {
        return Ok(None);
    }
    Ok(Some(row.clone()))
}

pub fn split_bulk_proposals(rows: &[Value]) -> Result<Vec<Value>> {
    let mut output = Vec::new();
    for row in rows {
        let Some((field, _)) = specification(&row["payload"]) else {
            output.push(row.clone());
            continue;
        };
        let entries = row["payload"][field]
            .as_array()
            .context("Invalid ecology bulk entries")?;
        let mut scopes: Vec<(Value, Vec<Value>)> = Vec::new();
        for entry in entries {
            let scope = scope(entry);
            if let Some((_, group)) = scopes.iter_mut().find(|(s, _)| s == &scope) {
                group.push(entry.clone());
            } else {
                scopes.push((scope, vec![entry.clone()]));
            }
        }
        for (scope, entries) in scopes {
            let mut payload = row["payload"].clone();
            payload[field] = json!(entries);
            payload["scope"] = scope;
            output.push(proposal(
                row["domain"].as_str().context("Missing ecology domain")?,
                payload,
                row["world_epoch"]
                    .as_str()
                    .context("Missing ecology epoch")?,
            )?);
        }
    }
    Ok(output)
}

fn semantic_identity(row: &Value) -> Result<(String, String, Option<String>)> {
    let p = required(row, "payload")?;
    let domain = required(row, "domain")?
        .as_str()
        .context("Invalid ecology domain")?;
    let epoch = required(row, "world_epoch")?;
    let name = kind(p);
    let base = json!([epoch, domain, p.get("kind").or_else(|| p.get("operation"))]);
    let decision = match (domain, name) {
        ("mobs", "maturation" | "reproduction") => Some(json!([
            epoch,
            domain,
            name,
            select(
                required(p, "ticket")?,
                &[
                    "map_id",
                    "instance_id",
                    "group_id",
                    "monster_id",
                    "reference",
                    "cycle"
                ],
                true
            )?
        ])),
        ("plants", "affinity_reconcile") => {
            let operations = p["original_operations"]
                .as_array()
                .context("Invalid affinity reconciliation identity batch")?;
            ensure!(
                (1..=16).contains(&operations.len()),
                "Invalid affinity reconciliation identity batch"
            );
            for field in ["account_id", "character_id"] {
                ensure!(
                    p[field].as_i64().is_some_and(|v| v > 0),
                    "Invalid affinity reconciliation owner identity"
                );
            }
            let mut pairs = Vec::new();
            let mut seen = HashSet::new();
            for operation in operations {
                let name = operation["operation"]
                    .as_str()
                    .context("Invalid affinity reconciliation receipt identity")?;
                let hash = operation["receipt_sha256"]
                    .as_str()
                    .context("Invalid affinity reconciliation receipt identity")?;
                ensure!(
                    (1..=128).contains(&name.chars().count())
                        && hash.len() == 64
                        && hash
                            .bytes()
                            .all(|c| c.is_ascii_digit() || (b'a'..=b'f').contains(&c))
                        && seen.insert(name),
                    "Invalid affinity reconciliation receipt identity"
                );
                pairs.push((name.to_owned(), hash.to_owned()));
            }
            pairs.sort();
            Some(json!([
                epoch,
                domain,
                name,
                p["account_id"],
                p["character_id"],
                pairs
            ]))
        }
        ("plants", "resource_growth") => Some(json!([
            epoch,
            domain,
            name,
            required(&p["expected"], "resource_uid")?,
            required(&p["expected"], "stage")?
        ])),
        ("plants", "planting_begin" | "planting_rejected") => Some(json!([
            epoch,
            domain,
            "planting_intent",
            required(p, "intent_id")?
        ])),
        ("plants", "growth_publish" | "mineral_refill" | "fishing_refill") => Some(json!([
            epoch,
            domain,
            name,
            required(p, "resource_uid")?,
            p.get("available_at")
        ])),
        _ => None,
    };
    if let Some(decision) = decision {
        let key = digest(&decision)?;
        return Ok((key.clone(), key.clone(), Some(key)));
    }
    if domain == "bonuses" && name == "regional_snapshot" {
        return Ok((
            digest(&json!([
                epoch,
                domain,
                name,
                required(p, "map_id")?,
                required(p, "instance_id")?
            ]))?,
            digest(&json!([required(p, "revision")?, required(p, "regions")?]))?,
            None,
        ));
    }
    if domain == "mobs" && name == "wander_bulk" {
        let mut groups = p["moves"]
            .as_array()
            .context("Missing wander moves")?
            .iter()
            .map(|r| {
                Ok((
                    required(r, "group_id")?
                        .as_i64()
                        .context("Invalid wander group")?,
                    r["expected_members"].clone(),
                ))
            })
            .collect::<Result<Vec<_>>>()?;
        groups.sort_by_key(|g| g.0);
        return Ok((
            digest(&json!([epoch, domain, name, required(p, "scope")?]))?,
            digest(&json!([required(p, "configuration")?, groups]))?,
            None,
        ));
    }
    if domain == "mobs"
        && matches!(
            name,
            "wander" | "publish_maturation" | "publish_reproduction"
        )
    {
        return Ok((
            digest(&json!([
                epoch,
                domain,
                name,
                required(p, "scope")?,
                required(p, "group_id")?
            ]))?,
            digest(required(p, "expected_members")?)?,
            None,
        ));
    }
    let _ = base;
    let id = required(row, "id")?
        .as_str()
        .context("Invalid ecology identity")?
        .to_owned();
    Ok((id.clone(), id, None))
}

/// Legacy malformed rows retain their exact ID and reach their domain validator.
pub fn proposal_identity(row: &Value) -> Result<(String, String, Option<String>)> {
    let try_identity = || -> Result<(String, String, Option<String>)> {
        let p = required(row, "payload")?;
        if let Some((field, _)) = specification(p) {
            let entries = p[field]
                .as_array()
                .context("Invalid ecology bulk entries")?;
            let scope = p
                .get("scope")
                .cloned()
                .unwrap_or_else(|| entries.first().map(scope).unwrap_or(Value::Null));
            ensure!(!scope.is_null(), "Missing bulk scope");
            let slot = String::from_utf8(canonical_bytes(&json!([
                row["world_epoch"],
                row["domain"],
                p["kind"],
                scope
            ]))?)?;
            let version = entries
                .iter()
                .map(|e| {
                    Ok(json!([
                        bulk_entry_key(e)?,
                        e.get("expected_members"),
                        e.get("configuration"),
                        e.get("expected")
                    ]))
                })
                .collect::<Result<Vec<_>>>()?;
            let version = String::from_utf8(canonical_bytes(&json!(version))?)?;
            let id = hex::encode(Sha256::digest(format!("{slot}{version}").as_bytes()));
            return Ok((slot, version, Some(id)));
        }
        if row["domain"] == "population" && kind(p) == "initial_population" {
            return Ok((
                String::from_utf8(canonical_bytes(&json!([
                    row["world_epoch"],
                    "initial_population",
                    required(&p["plan"], "map_id")?,
                    required(&p["plan"], "instance_id")?,
                    required(&p["plan"], "region_id")?
                ]))?)?,
                String::from_utf8(canonical_bytes(&json!([
                    required(p, "scope_digest")?,
                    required(p, "policy")?,
                    required(p, "catalog_revision")?
                ]))?)?,
                None,
            ));
        }
        if row["domain"] == "population" && kind(p) == "corpse_expiry" {
            return Ok((
                String::from_utf8(canonical_bytes(&json!([
                    row["world_epoch"],
                    "corpse_expiry",
                    required(p, "actor_id")?
                ]))?)?,
                row["id"].as_str().context("Invalid ecology ID")?.into(),
                None,
            ));
        }
        semantic_identity(row)
    };
    match try_identity() {
        Ok(value) => Ok(value),
        Err(_) => {
            let id = row["id"].as_str().context("Invalid ecology ID")?.to_owned();
            Ok((id.clone(), id, None))
        }
    }
}

pub fn refresh_stale_decision(original: &Value, fresh: &Value) -> Result<Value> {
    if kind(fresh) == "maturation" && fresh.get("configuration").is_some() {
        bail!("Maturation refresh requires the native catalog-aware decision adapter");
    }
    let mut refreshed = fresh.clone();
    for key in ["draw", "group_draw", "child", "member", "grown"] {
        if let Some(value) = original.get(key) {
            refreshed[key] = value.clone();
        }
    }
    if refreshed.get("child").is_some_and(|v| !v.is_null()) {
        if let Some(destination) = fresh.get("destination").and_then(Value::as_array) {
            ensure!(destination.len() == 3, "Invalid child destination");
            for (key, value) in ["x", "y", "z"].into_iter().zip(destination) {
                refreshed["child"][key] = value.clone();
            }
        }
    }
    if refreshed.get("member").is_some_and(|v| !v.is_null()) {
        if let Some(expected) = fresh.get("expected") {
            for key in ["x", "y", "z"] {
                refreshed["member"][key] = required(expected, key)?.clone();
            }
        }
    }
    Ok(refreshed)
}

pub fn merge_bulk_payload(original: &Value, fresh: &Value) -> Result<Value> {
    let (field, limit) = specification(fresh).context("Invalid ecology bulk payload")?;
    let mut merged = fresh.clone();
    let mut entries: Vec<Value> = Vec::new();
    let mut indexes = HashMap::new();
    for entry in original[field]
        .as_array()
        .context("Invalid original ecology bulk")?
        .iter()
        .chain(
            fresh[field]
                .as_array()
                .context("Invalid fresh ecology bulk")?,
        )
    {
        let key = canonical_bytes(&bulk_entry_key(entry)?)?;
        if let Some(&index) = indexes.get(&key) {
            let old: &Value = &entries[index];
            let mut updated = if kind(fresh) == "lifecycle_bulk" {
                refresh_stale_decision(old, entry)?
            } else {
                let mut updated = entry.clone();
                for outcome in ["draw", "group_draw", "child", "member", "grown"] {
                    if let Some(v) = old.get(outcome) {
                        updated[outcome] = v.clone();
                    }
                }
                updated
            };
            if updated["plan"].is_object() && old["plan"].is_object() {
                for outcome in ["draw", "group_draw", "destination_draw", "variant_order"] {
                    if let Some(v) = old["plan"].get(outcome) {
                        updated["plan"][outcome] = v.clone();
                    }
                }
            }
            entries[index] = updated;
        } else {
            let mut candidate = merged.clone();
            let mut values = entries.clone();
            values.push(entry.clone());
            candidate[field] = json!(values);
            if entries.len() >= limit || canonical_bytes(&candidate)?.len() > 224 * 1024 {
                continue;
            }
            indexes.insert(key, entries.len());
            entries.push(entry.clone());
        }
    }
    merged[field] = json!(entries);
    Ok(merged)
}
