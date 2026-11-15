//! Versioned JSON contract shared with the authoritative Python World.
use anyhow::{bail, ensure, Context as _, Result};
use serde_json::{json, Value};
use sha2::{Digest, Sha256};

pub const SCHEMA_VERSION: u64 = 1;
pub const MAX_BODY_BYTES: usize = 256 * 1024;
pub const MAX_RESPONSE_BYTES: usize = 1024 * 1024;
pub const MAX_PROPOSALS: usize = 16;
pub const MAX_SCOPES: usize = 64;
pub const DOMAINS: [&str; 5] = ["plants", "mobs", "weather", "population", "bonuses"];

/// World advertises its actual startup pin; never guess the newest SQL release.
pub fn catalog_publication(
    snapshot: &Value,
    revision: &str,
    configured: Option<&str>,
) -> Result<String> {
    ensure!(
        snapshot["mode"] == "external",
        "World does not authorize external ecology ownership"
    );
    ensure!(
        snapshot["catalog_revision"].as_str() == Some(revision),
        "World ecology catalog revision differs"
    );
    let generation = snapshot["compiled_catalog_generation"]
        .as_str()
        .context("World did not advertise a compiled catalog generation")?;
    ensure!(
        generation.len() == 64
            && generation
                .bytes()
                .all(|c| c.is_ascii_digit() || (b'a'..=b'f').contains(&c)),
        "Invalid World compiled catalog generation"
    );
    if let Some(configured) = configured {
        ensure!(configured == generation, "World compiled catalog generation changed; restart ecology with the current publication");
    }
    Ok(generation.to_owned())
}

/// Python's JSON encoder escapes non-ASCII scalars, including surrogate pairs.
fn string_bytes(value: &str, out: &mut Vec<u8>) {
    out.push(b'"');
    for c in value.chars() {
        match c {
            '"' => out.extend_from_slice(b"\\\""),
            '\\' => out.extend_from_slice(b"\\\\"),
            '\n' => out.extend_from_slice(b"\\n"),
            '\r' => out.extend_from_slice(b"\\r"),
            '\t' => out.extend_from_slice(b"\\t"),
            '\u{08}' => out.extend_from_slice(b"\\b"),
            '\u{0c}' => out.extend_from_slice(b"\\f"),
            c if c < '\u{20}' || !c.is_ascii() => {
                let mut units = [0u16; 2];
                for unit in c.encode_utf16(&mut units) {
                    out.extend_from_slice(format!("\\u{unit:04x}").as_bytes());
                }
            }
            c => out.push(c as u8),
        }
    }
    out.push(b'"');
}

/// Normalize shortest round-trip digits to CPython's repr exponent conventions.
fn float_text(number: &serde_json::Number) -> Result<String> {
    let value = number.as_f64().context("Invalid JSON float")?;
    ensure!(value.is_finite(), "Non-finite JSON number");
    if value == 0.0 {
        return Ok(if value.is_sign_negative() {
            "-0.0"
        } else {
            "0.0"
        }
        .into());
    }
    let raw = number.to_string();
    let negative = raw.starts_with('-');
    let raw = raw.trim_start_matches('-');
    let (mantissa, power) = match raw.split_once(['e', 'E']) {
        Some((m, e)) => (m, e.parse::<i32>()?),
        None => (raw, 0),
    };
    let point = mantissa.find('.').unwrap_or(mantissa.len()) as i32;
    let all = mantissa.replace('.', "");
    let leading = all.len() - all.trim_start_matches('0').len();
    let exponent = power + point - leading as i32 - 1;
    let digits = all[leading..].trim_end_matches('0');
    let sign = if negative { "-" } else { "" };
    if !(-4..16).contains(&exponent) {
        let fractional = if digits.len() > 1 {
            format!(".{}", &digits[1..])
        } else {
            String::new()
        };
        Ok(format!(
            "{sign}{}{fractional}e{}{:02}",
            &digits[..1],
            if exponent < 0 { '-' } else { '+' },
            exponent.abs()
        ))
    } else if exponent < 0 {
        Ok(format!(
            "{sign}0.{}{digits}",
            "0".repeat((-exponent - 1) as usize)
        ))
    } else {
        let point = (exponent + 1) as usize;
        if digits.len() > point {
            Ok(format!("{sign}{}.{}", &digits[..point], &digits[point..]))
        } else {
            Ok(format!(
                "{sign}{digits}{}.0",
                "0".repeat(point - digits.len())
            ))
        }
    }
}

fn encode(value: &Value, out: &mut Vec<u8>) -> Result<()> {
    match value {
        Value::Null => out.extend_from_slice(b"null"),
        Value::Bool(v) => out.extend_from_slice(if *v { b"true" } else { b"false" }),
        Value::Number(v) => {
            if v.is_i64() || v.is_u64() {
                out.extend_from_slice(v.to_string().as_bytes());
            } else {
                out.extend_from_slice(float_text(v)?.as_bytes());
            }
        }
        Value::String(v) => string_bytes(v, out),
        Value::Array(values) => {
            out.push(b'[');
            for (index, value) in values.iter().enumerate() {
                if index > 0 {
                    out.push(b',');
                }
                encode(value, out)?;
            }
            out.push(b']');
        }
        Value::Object(values) => {
            out.push(b'{');
            let mut fields: Vec<_> = values.iter().collect();
            fields.sort_unstable_by(|a, b| a.0.cmp(b.0));
            for (index, (key, value)) in fields.into_iter().enumerate() {
                if index > 0 {
                    out.push(b',');
                }
                string_bytes(key, out);
                out.push(b':');
                encode(value, out)?;
            }
            out.push(b'}');
        }
    }
    Ok(())
}

pub fn canonical_bytes(value: &Value) -> Result<Vec<u8>> {
    let mut out = Vec::new();
    encode(value, &mut out)?;
    Ok(out)
}

pub fn json_bytes(value: &Value, limit: usize) -> Result<Vec<u8>> {
    let bytes = canonical_bytes(value)?;
    ensure!(bytes.len() <= limit, "Ecology JSON exceeds byte limit");
    Ok(bytes)
}

pub fn bounded_json(bytes: &[u8], limit: usize) -> Result<Value> {
    ensure!(bytes.len() <= limit, "Ecology JSON exceeds byte limit");
    Ok(serde_json::from_slice(bytes)?)
}

pub fn proposal(domain: &str, payload: Value, epoch: &str) -> Result<Value> {
    ensure!(
        DOMAINS.contains(&domain) && payload.is_object(),
        "Invalid ecology proposal"
    );
    let mut body = json!({"domain":domain,"payload":payload});
    let id = hex::encode(Sha256::digest(json_bytes(&body, MAX_BODY_BYTES)?));
    let fields = body.as_object_mut().expect("Proposal body is an object");
    fields.insert("id".into(), Value::String(id));
    fields.insert("world_epoch".into(), Value::String(epoch.to_owned()));
    Ok(body)
}

pub fn validate_snapshot(value: &Value) -> Result<()> {
    ensure!(
        value.is_object() && value["schema_version"].as_u64() == Some(SCHEMA_VERSION),
        "Unsupported ecology snapshot schema"
    );
    let epoch = value
        .get("world_epoch")
        .or_else(|| value.get("epoch"))
        .and_then(Value::as_str)
        .context("Invalid ecology snapshot epoch")?;
    ensure!(
        (1..=128).contains(&epoch.chars().count()),
        "Invalid ecology snapshot epoch"
    );
    ensure!(
        value["scopes"]
            .as_array()
            .is_some_and(|v| v.len() <= MAX_SCOPES),
        "Invalid ecology scope count"
    );
    json_bytes(value, MAX_RESPONSE_BYTES)?;
    Ok(())
}

pub fn validate_query(value: &Value) -> Result<()> {
    let object = value.as_object().context("Invalid ecology query fields")?;
    ensure!(
        object
            .keys()
            .all(|key| ["kind", "map_id", "instance_id", "region_id"].contains(&key.as_str())),
        "Invalid ecology query fields"
    );
    ensure!(
        matches!(value["kind"].as_str(), Some("population" | "weather")),
        "Invalid ecology query kind"
    );
    ensure!(
        value["map_id"]
            .as_i64()
            .is_some_and(|v| v > 0 && v < (1i64 << 31)),
        "Invalid ecology query map"
    );
    ensure!(
        value["instance_id"].as_i64().is_some_and(|v| v >= 0),
        "Invalid ecology query instance"
    );
    if let Some(region) = value.get("region_id") {
        ensure!(
            region.as_i64().is_some_and(|v| v > 0 && v < (1i64 << 31)),
            "Invalid ecology query region"
        );
    }
    Ok(())
}

pub fn validate_proposals(value: &Value) -> Result<()> {
    let envelope = value
        .as_object()
        .context("Invalid ecology proposal envelope")?;
    ensure!(
        envelope.len() == 2
            && envelope.contains_key("schema_version")
            && envelope.contains_key("proposals"),
        "Invalid ecology proposal envelope"
    );
    ensure!(
        value["schema_version"].as_u64() == Some(SCHEMA_VERSION),
        "Unsupported ecology proposal schema"
    );
    let rows = value["proposals"]
        .as_array()
        .context("Invalid ecology proposal count")?;
    ensure!(
        rows.len() <= MAX_PROPOSALS,
        "Invalid ecology proposal count"
    );
    let mut ids = std::collections::HashSet::new();
    for row in rows {
        let row = row.as_object().context("Invalid ecology proposal fields")?;
        ensure!(
            row.len() == 4
                && ["id", "domain", "payload", "world_epoch"]
                    .iter()
                    .all(|field| row.contains_key(*field)),
            "Invalid ecology proposal fields"
        );
        let id = row["id"]
            .as_str()
            .context("Invalid ecology proposal identity")?;
        let epoch = row["world_epoch"]
            .as_str()
            .context("Invalid ecology proposal identity")?;
        ensure!(
            (1..=128).contains(&id.chars().count())
                && (1..=128).contains(&epoch.chars().count())
                && ids.insert(id)
                && row["domain"]
                    .as_str()
                    .is_some_and(|domain| DOMAINS.contains(&domain))
                && row["payload"].is_object(),
            "Invalid ecology proposal identity"
        );
    }
    json_bytes(value, MAX_BODY_BYTES)?;
    Ok(())
}

pub fn validate_results(rows: &[Value], results: &Value) -> Result<Vec<Value>> {
    let results = results["results"]
        .as_array()
        .context("Incomplete ecology acknowledgement")?;
    ensure!(
        results.len() == rows.len(),
        "Incomplete ecology acknowledgement"
    );
    let mut expected: std::collections::HashSet<&str> = rows
        .iter()
        .map(|r| r["id"].as_str().unwrap_or(""))
        .collect();
    for result in results {
        let id = result["id"]
            .as_str()
            .context("Invalid ecology acknowledgement")?;
        ensure!(expected.remove(id), "Invalid ecology acknowledgement");
        ensure!(
            matches!(
                result["status"].as_str(),
                Some("applied" | "duplicate" | "stale" | "retry" | "deferred")
            ),
            "Invalid ecology acknowledgement"
        );
        if let Some(failures) = result.get("resource_failures") {
            let failures = failures
                .as_array()
                .context("Invalid ecology resource failure acknowledgement")?;
            ensure!(
                failures.len() <= 64,
                "Invalid ecology resource failure acknowledgement"
            );
            let source = rows.iter().find(|r| r["id"].as_str() == Some(id)).unwrap();
            let entries = source["payload"]["resources"]
                .as_array()
                .map(Vec::as_slice)
                .unwrap_or_else(|| std::slice::from_ref(&source["payload"]));
            let mut seen = std::collections::HashSet::new();
            for uid in failures {
                let uid = uid
                    .as_i64()
                    .context("Invalid ecology resource failure acknowledgement")?;
                ensure!(
                    uid > 0 && seen.insert(uid),
                    "Invalid ecology resource failure acknowledgement"
                );
                ensure!(
                    entries
                        .iter()
                        .any(|entry| entry["kind"] == "resource_growth"
                            && entry["expected"]["resource_uid"].as_i64() == Some(uid)),
                    "Unknown ecology resource failure acknowledgement"
                );
            }
        }
    }
    if !expected.is_empty() {
        bail!("Incomplete ecology acknowledgement");
    }
    Ok(results.clone())
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn python_ascii_float_and_large_integer_contract() {
        let data = json!({"é":"🦀\n","float":1.0,"small":0.000001,"large":1e20,"id":4611967493404098561i64});
        assert_eq!(String::from_utf8(canonical_bytes(&data).unwrap()).unwrap(),"{\"float\":1.0,\"id\":4611967493404098561,\"large\":1e+20,\"small\":1e-06,\"\\u00e9\":\"\\ud83e\\udd80\\n\"}");
    }
    #[test]
    fn query_rejects_bools_overflow_and_unknown_fields() {
        assert!(validate_query(&json!({"kind":"weather","map_id":true,"instance_id":0})).is_err());
        assert!(validate_query(
            &json!({"kind":"weather","map_id":1,"instance_id":9223372036854775808u64})
        )
        .is_err());
        assert!(validate_query(
            &json!({"kind":"weather","map_id":1,"instance_id":0,"command":"x"})
        )
        .is_err());
    }
}
