//! Durable ecology admission, semantic coalescing, delivery attempts and queries.
//!
//! The owner connection remains checked out for the entire advisory-lock lease.
//! Ordinary transactions use separate, bounded pool clients. A lost owner is
//! discarded rather than transparently reconnected or returned with a live lock.
use std::collections::{HashMap, HashSet};
use std::sync::Arc;
use std::time::Duration;

use anyhow::{anyhow, bail, ensure, Context as _, Result};
use deadpool_postgres::{Object, Pool};
use serde_json::{json, Value};
use tokio::sync::Mutex;
use tokio_postgres::{IsolationLevel, Transaction};

use crate::catalog::Catalog;
use crate::identity::{
    bulk_entry_key, bulk_failure_identity, filter_failed_bulk, merge_bulk_payload,
    proposal_identity, refresh_stale_decision, split_bulk_proposals,
};
use crate::protocol::{json_bytes, proposal, validate_query, MAX_BODY_BYTES, SCHEMA_VERSION};

pub const OWNER_LOCK: i64 = 5_790_545_566;
pub const MAX_PENDING: usize = 4096;
pub const RESERVED_INTERACTIVE: usize = 32;
pub const RESERVED_GROWTH: usize = 16;
pub const MAX_PROPOSALS: usize = 16;
pub const MAX_SCOPES: usize = 64;

pub struct Repository {
    pool: Pool,
    owner: Mutex<Option<Object>>,
    max_attempts: i32,
    context: Option<Arc<crate::Context>>,
}

impl Repository {
    pub fn new(pool: Pool, max_attempts: u32) -> Result<Self> {
        ensure!(
            (1..=100).contains(&max_attempts),
            "Invalid ecology maximum attempts"
        );
        Ok(Self {
            pool,
            owner: Mutex::new(None),
            max_attempts: max_attempts as i32,
            context: None,
        })
    }

    pub fn with_context(context: Arc<crate::Context>, max_attempts: u32) -> Result<Self> {
        let mut repository = Self::new(context.db.clone(), max_attempts)?;
        repository.context = Some(context);
        Ok(repository)
    }

    pub fn max_attempts(&self) -> u32 {
        self.max_attempts as u32
    }

    pub async fn owns_database(&self) -> bool {
        self.owner.lock().await.is_some()
    }

    async fn client(&self) -> Result<Object> {
        tokio::time::timeout(Duration::from_millis(500), self.pool.get())
            .await
            .context("Ecology database pool acquisition timed out")?
            .context("Ecology database pool unavailable")
    }

    pub async fn acquire(&self) -> Result<()> {
        let mut owner = self.owner.lock().await;
        if owner.is_some() {
            bail!("Ecology already owns an advisory session");
        }
        let connection = tokio::time::timeout(Duration::from_secs(2), self.pool.get())
            .await
            .context("Ecology ownership connection timed out")??;
        let result = async {
            connection
                .batch_execute("SET statement_timeout='1s'")
                .await?;
            let row = connection
                .query_one("SELECT pg_try_advisory_lock($1) AS owned", &[&OWNER_LOCK])
                .await?;
            Ok::<_, anyhow::Error>(row.get::<_, bool>("owned"))
        }
        .await;
        match result {
            Ok(true) => {
                *owner = Some(connection);
                Ok(())
            }
            Ok(false) => {
                // Detaching closes the session; it never leaves advisory locks
                // or altered session settings on a pooled idle connection.
                drop(Object::take(connection));
                bail!("Another ecology worker owns the database")
            }
            Err(error) => {
                drop(Object::take(connection));
                Err(error.context("Ecology ownership acquisition failed"))
            }
        }
    }

    pub async fn assert_owner(&self) -> Result<()> {
        let mut owner = self.owner.lock().await;
        let connection = owner
            .as_ref()
            .ok_or_else(|| anyhow!("Ecology worker does not own the database"))?;
        if connection.simple_query("SELECT 1").await.is_err() {
            if let Some(connection) = owner.take() {
                drop(Object::take(connection));
            }
            bail!("Ecology ownership session was lost");
        }
        Ok(())
    }

    pub async fn close(&self) -> Result<()> {
        if let Some(connection) = self.owner.lock().await.take() {
            // Closing the actual session is the release boundary, even if an
            // explicit unlock fails because PostgreSQL is unavailable.
            let _ = connection
                .query_one("SELECT pg_advisory_unlock($1)", &[&OWNER_LOCK])
                .await;
            drop(Object::take(connection));
        }
        Ok(())
    }

    pub async fn expire_exhausted(&self) -> Result<u64> {
        let mut connection = self.client().await?;
        let tx = connection.transaction().await?;
        configure(&tx).await?;
        let count = tx.execute(
            "UPDATE ecology_service_proposals SET delivered_at=CURRENT_TIMESTAMP, \
             last_error_code='retry_exhausted' WHERE id IN (SELECT id FROM ecology_service_proposals \
             WHERE delivered_at IS NULL AND attempts>=$1 ORDER BY created_at,id LIMIT 256)",
            &[&self.max_attempts],
        ).await?;
        tx.commit().await?;
        Ok(count)
    }

    pub async fn retry_stats(&self) -> Result<Value> {
        let mut connection = self.client().await?;
        let tx = connection.transaction().await?;
        configure(&tx).await?;
        let row = tx
            .query_one(
                "SELECT COALESCE(sum(attempts),0)::bigint AS attempts, \
             count(*) FILTER (WHERE last_error_code='retry_exhausted') AS exhausted \
             FROM ecology_service_proposals",
                &[],
            )
            .await?;
        let result = json!({"attempts": row.get::<_, i64>("attempts"), "exhausted": row.get::<_, i64>("exhausted")});
        tx.commit().await?;
        Ok(result)
    }

    pub async fn enabled(&self) -> Result<bool> {
        let mut connection = self.client().await?;
        let tx = connection.transaction().await?;
        configure(&tx).await?;
        let row = tx
            .query_opt(
                "SELECT value FROM settings WHERE name='ecology_service_enabled'",
                &[],
            )
            .await?;
        let enabled = row
            .map(|row| row.get::<_, Value>("value") == Value::Bool(true))
            .unwrap_or(true);
        tx.commit().await?;
        Ok(enabled)
    }

    pub async fn set_enabled(&self, enabled: bool) -> Result<()> {
        let mut connection = self.client().await?;
        let tx = connection.transaction().await?;
        configure(&tx).await?;
        tx.execute(
            "INSERT INTO settings(name,value) VALUES('ecology_service_enabled',$1) \
             ON CONFLICT(name) DO UPDATE SET value=EXCLUDED.value",
            &[&json!(enabled)],
        )
        .await?;
        tx.commit().await?;
        Ok(())
    }

    pub async fn dirty(&self) -> Result<Vec<Value>> {
        let mut connection = self.client().await?;
        let tx = connection.transaction().await?;
        configure(&tx).await?;
        let rows = tx.query(
            "SELECT jsonb_build_object('map_id',map_id,'instance_id',instance_id,'revision',revision) AS document \
             FROM ecology_dirty_scopes WHERE revision>processed_revision \
             ORDER BY updated_at,map_id,instance_id LIMIT $1", &[&(MAX_SCOPES as i64)],
        ).await?;
        let result = rows.iter().map(|r| r.get("document")).collect();
        tx.commit().await?;
        Ok(result)
    }

    pub async fn save(&self, proposals: &[Value], dirty: &[Value]) -> Result<Value> {
        let mut proposals = split_bulk_proposals(proposals)?;
        let mut statistics = AdmissionStats {
            incoming: proposals.len(),
            ..Default::default()
        };
        let mut connection = self.client().await?;
        let tx = connection.transaction().await?;
        configure(&tx).await?;
        let rows = tx.query(
            "SELECT jsonb_build_object('id',id,'domain',domain,'payload',payload,\
             'world_epoch',world_epoch,'attempts',attempts) AS document FROM ecology_service_proposals \
             WHERE delivered_at IS NULL ORDER BY created_at,id FOR UPDATE", &[],
        ).await?;
        let pending: Vec<Value> = rows.iter().map(|r| r.get("document")).collect();
        let mut guard_ids = HashSet::new();
        for row in pending.iter().chain(proposals.iter()) {
            let payload = &row["payload"];
            let entries = if let Some(field) = bulk_field(payload) {
                payload[field]
                    .as_array()
                    .context("Invalid ecology bulk entries")?
                    .clone()
            } else if payload["kind"] == "resource_growth" {
                vec![payload.clone()]
            } else {
                vec![]
            };
            for entry in entries {
                guard_ids.insert(bulk_failure_identity(
                    string(row, "domain")?,
                    string(row, "world_epoch")?,
                    &entry,
                )?);
            }
        }
        let mut exhausted = HashSet::new();
        if !guard_ids.is_empty() {
            let guard_ids: Vec<String> = guard_ids.into_iter().collect();
            for row in tx
                .query(
                    "SELECT id FROM ecology_service_proposals WHERE id=ANY($1) AND attempts>=$2",
                    &[&guard_ids, &self.max_attempts],
                )
                .await?
            {
                exhausted.insert(row.get::<_, String>("id"));
            }
        }
        let mut superseded: Vec<String> = vec![];
        let mut retained = vec![];
        for existing in pending {
            match filter_failed_bulk(&existing, &exhausted)? {
                Some(filtered) if filtered["id"] == existing["id"] => retained.push(filtered),
                filtered => {
                    superseded.push(string(&existing, "id")?.to_owned());
                    if let Some(mut filtered) = filtered {
                        filtered["attempts"] =
                            existing.get("attempts").cloned().unwrap_or(json!(0));
                        proposals.insert(0, filtered);
                    }
                }
            }
        }
        let pending: Vec<Arc<Value>> = retained.into_iter().map(Arc::new).collect();
        let mut filtered_proposals = vec![];
        for row in proposals {
            if let Some(filtered) = filter_failed_bulk(&row, &exhausted)? {
                filtered_proposals.push(filtered);
            }
        }
        let mut proposals: Vec<Arc<Value>> = pending
            .iter()
            .filter(|row| bulk_field(&row["payload"]).is_some())
            .cloned()
            .collect();
        proposals.extend(filtered_proposals.into_iter().map(Arc::new));
        let mut slots: HashMap<String, (Arc<Value>, String)> = HashMap::new();
        for existing in pending {
            let (slot, version, _) = proposal_identity(&existing)?;
            if let Some(previous) = slots.get(&slot) {
                if previous.1 == version {
                    superseded.push(string(&existing, "id")?.to_owned());
                    statistics.deduplicated += 1;
                    continue;
                }
                superseded.push(string(&previous.0, "id")?.to_owned());
            }
            slots.insert(slot, (existing, version));
        }
        for supplied in proposals {
            let mut row = Arc::try_unwrap(supplied).unwrap_or_else(|shared| (*shared).clone());
            let (mut slot, mut version, mut decision_id) = proposal_identity(&row)?;
            let previous = slots.get(&slot).cloned();
            let mut inherited_attempts = attempts(&row)?;
            if let Some((previous_row, _)) = &previous {
                if bulk_field(&row["payload"]).is_some() {
                    let merged = self
                        .merge_payload(&previous_row["payload"], &row["payload"])
                        .await?;
                    row = proposal(
                        string(&row, "domain")?,
                        merged,
                        string(&row, "world_epoch")?,
                    )?;
                    (slot, version, decision_id) = proposal_identity(&row)?;
                    inherited_attempts = attempts(previous_row)?;
                }
            }
            if let Some((previous_row, previous_version)) = &previous {
                if previous_version == &version {
                    statistics.deduplicated += 1;
                    continue;
                }
                if row["domain"] == "bonuses"
                    && row["payload"]["revision"].as_i64().unwrap_or(0)
                        < previous_row["payload"]["revision"].as_i64().unwrap_or(0)
                {
                    statistics.deduplicated += 1;
                    continue;
                }
                superseded.push(string(previous_row, "id")?.to_owned());
            } else if slots.len() >= admission_capacity(&row["payload"]) {
                statistics.capacity_deferred += 1;
                continue;
            }
            if let Some(decision_id) = decision_id {
                row["id"] = json!(decision_id);
                let history = tx.query_opt(
                    "SELECT payload,attempts,last_error_code,delivered_at IS NOT NULL AS delivered, \
                     next_attempt_at<=CURRENT_TIMESTAMP AS due FROM ecology_service_proposals \
                     WHERE id=$1 AND world_epoch=$2 FOR UPDATE", &[&string(&row, "id")?, &string(&row, "world_epoch")?],
                ).await?;
                if let Some(history) = history {
                    let history_payload: Value = history.get("payload");
                    let history_attempts: i32 = history.get("attempts");
                    let last_error: Option<String> = history.get("last_error_code");
                    let delivered: bool = history.get("delivered");
                    let due: bool = history.get("due");
                    let bulk_kind = bulk_field(&row["payload"]).is_some();
                    let pass_complete =
                        last_error.is_none() || last_error.as_deref() == Some("bulk_pass_complete");
                    let normal_wait_due = last_error.as_deref() == Some("normal_wait") && due;
                    if bulk_kind
                        && delivered
                        && history_attempts < self.max_attempts
                        && (pass_complete || normal_wait_due)
                    {
                        row["payload"] = self
                            .merge_payload(&history_payload, &row["payload"])
                            .await?;
                        tx.execute(
                            "UPDATE ecology_service_proposals SET payload=$1,delivered_at=NULL, \
                             last_error_code=NULL,next_attempt_at=CURRENT_TIMESTAMP,created_at=CURRENT_TIMESTAMP WHERE id=$2",
                            &[&row["payload"], &string(&row, "id")?],
                        ).await?;
                        row["attempts"] = json!(history_attempts);
                        slots.insert(slot, (Arc::new(row), version));
                        statistics.refreshed += 1;
                        continue;
                    }
                    let changed = history_payload.get("expected_members")
                        != row["payload"].get("expected_members");
                    if last_error.as_deref() == Some("stale")
                        && history_attempts < self.max_attempts
                        && (changed || due)
                    {
                        row["payload"] = self
                            .refresh_decision(&history_payload, &row["payload"])
                            .await?;
                        tx.execute(
                            "UPDATE ecology_service_proposals SET payload=$1,delivered_at=NULL, \
                             last_error_code=NULL,next_attempt_at=CURRENT_TIMESTAMP WHERE id=$2",
                            &[&row["payload"], &string(&row, "id")?],
                        )
                        .await?;
                        slots.insert(slot, (Arc::new(row), version));
                        statistics.refreshed += 1;
                    } else {
                        statistics.deduplicated += 1;
                    }
                    continue;
                }
            }
            let inserted = tx.execute(
                "INSERT INTO ecology_service_proposals(id,domain,payload,world_epoch,attempts) \
                 VALUES($1,$2,$3,$4,$5) ON CONFLICT(id) DO UPDATE SET \
                 world_epoch=EXCLUDED.world_epoch,delivered_at=NULL,attempts=0,last_error_code=NULL,next_attempt_at=CURRENT_TIMESTAMP \
                 WHERE ecology_service_proposals.world_epoch<>EXCLUDED.world_epoch",
                &[&string(&row, "id")?, &string(&row, "domain")?, &row["payload"], &string(&row, "world_epoch")?, &inherited_attempts],
            ).await?;
            row["attempts"] = json!(inherited_attempts);
            statistics.inserted += inserted as usize;
            slots.insert(slot, (Arc::new(row), version));
        }
        let active_ids: HashSet<String> = slots
            .values()
            .map(|(row, _)| string(row, "id").map(str::to_owned))
            .collect::<Result<_>>()?;
        let superseded: HashSet<String> = superseded
            .into_iter()
            .filter(|identifier| !active_ids.contains(identifier))
            .collect();
        if !superseded.is_empty() {
            statistics.superseded = superseded.len();
            let superseded: Vec<String> = superseded.into_iter().collect();
            tx.execute("UPDATE ecology_service_proposals SET delivered_at=CURRENT_TIMESTAMP, last_error_code='superseded' WHERE id=ANY($1) AND delivered_at IS NULL", &[&superseded]).await?;
        }
        if !dirty.is_empty() && statistics.capacity_deferred == 0 {
            let maps: Vec<i64> = dirty
                .iter()
                .map(|row| integer(row, "map_id"))
                .collect::<Result<_>>()?;
            let instances: Vec<i64> = dirty
                .iter()
                .map(|row| integer(row, "instance_id"))
                .collect::<Result<_>>()?;
            let revisions: Vec<i64> = dirty
                .iter()
                .map(|row| integer(row, "revision"))
                .collect::<Result<_>>()?;
            tx.execute(
                "UPDATE ecology_dirty_scopes d SET processed_revision=GREATEST(d.processed_revision,x.revision) \
                 FROM unnest($1::bigint[],$2::bigint[],$3::bigint[]) AS x(map_id,instance_id,revision) \
                 WHERE d.map_id=x.map_id AND d.instance_id=x.instance_id", &[&maps, &instances, &revisions],
            ).await?;
        }
        tx.commit().await?;
        let result = statistics.value();
        if statistics.incoming > 0 || statistics.superseded > 0 || statistics.capacity_deferred > 0
        {
            let mut event = result.clone();
            event["event"] = json!("ecology_queue_admission");
            println!("{}", event);
        }
        Ok(result)
    }

    async fn refresh_decision(&self, original: &Value, fresh: &Value) -> Result<Value> {
        if fresh["kind"] == "maturation" && fresh.get("configuration").is_some() {
            let context = self.context.as_deref().context(
                "Maturation decision refresh requires the pinned native catalog context",
            )?;
            return crate::planners::native_monster::refresh_stale_decision(
                context, original, fresh,
            )
            .await;
        }
        refresh_stale_decision(original, fresh)
    }

    async fn merge_payload(&self, original: &Value, fresh: &Value) -> Result<Value> {
        if fresh["kind"] != "lifecycle_bulk" {
            return merge_bulk_payload(original, fresh);
        }
        let mut merged = fresh.clone();
        let mut entries: Vec<Value> = vec![];
        let mut indices: HashMap<Vec<u8>, usize> = HashMap::new();
        let old = original["operations"]
            .as_array()
            .context("Invalid original lifecycle bulk operations")?;
        let new = fresh["operations"]
            .as_array()
            .context("Invalid fresh lifecycle bulk operations")?;
        for entry in old.iter().chain(new) {
            let key = json_bytes(&bulk_entry_key(entry)?, MAX_BODY_BYTES)?;
            if let Some(index) = indices.get(&key).copied() {
                let previous = &entries[index];
                let mut updated = self.refresh_decision(previous, entry).await?;
                if updated.get("plan").is_some_and(Value::is_object)
                    && previous.get("plan").is_some_and(Value::is_object)
                {
                    for name in ["draw", "group_draw", "destination_draw", "variant_order"] {
                        if let Some(value) = previous["plan"].get(name) {
                            updated["plan"][name] = value.clone();
                        }
                    }
                }
                entries[index] = updated;
            } else {
                if entries.len() >= 16 {
                    continue;
                }
                let mut candidate = merged.clone();
                let mut candidates = entries.clone();
                candidates.push(entry.clone());
                candidate["operations"] = Value::Array(candidates);
                // Python's bound serializer raises beyond 256 KiB and admits
                // at most 224 KiB into a retained bulk. Preserve both fences.
                if json_bytes(&candidate, MAX_BODY_BYTES)?.len() > 224 * 1024 {
                    continue;
                }
                indices.insert(key, entries.len());
                entries.push(entry.clone());
            }
        }
        merged["operations"] = Value::Array(entries);
        Ok(merged)
    }

    pub async fn pending_count(&self) -> Result<usize> {
        self.count(
            "SELECT count(*) AS count FROM ecology_service_proposals WHERE delivered_at IS NULL",
        )
        .await
    }

    pub async fn growth_pending_count(&self) -> Result<usize> {
        self.count(
            "SELECT count(*) AS count FROM ecology_service_proposals WHERE delivered_at IS NULL \
             AND domain='plants' AND ((payload->>'kind'='resource_growth' \
             AND jsonb_typeof(payload->'member')='object') OR payload->>'kind'='resource_growth_bulk')"
        ).await
    }

    async fn count(&self, query: &str) -> Result<usize> {
        let mut connection = self.client().await?;
        let tx = connection.transaction().await?;
        configure(&tx).await?;
        let count: i64 = tx.query_one(query, &[]).await?.get("count");
        tx.commit().await?;
        Ok(usize::try_from(count)?)
    }

    pub async fn queue_summary(&self) -> Result<Vec<Value>> {
        let mut connection = self.client().await?;
        let tx = connection.transaction().await?;
        configure(&tx).await?;
        let rows = tx.query(
            "SELECT jsonb_build_object('domain',domain,'kind',COALESCE(payload->>'kind','context'),\
             'pending',count(*),'oldest_age_seconds',round(extract(epoch FROM CURRENT_TIMESTAMP-min(created_at)))::bigint,\
             'min_attempts',min(attempts),'max_attempts',max(attempts)) AS document \
             FROM ecology_service_proposals WHERE delivered_at IS NULL \
             GROUP BY domain,payload->>'kind' ORDER BY min(created_at)", &[],
        ).await?;
        let result = rows.iter().map(|r| r.get("document")).collect();
        tx.commit().await?;
        Ok(result)
    }

    pub async fn pending(&self) -> Result<Vec<Value>> {
        let mut connection = self.client().await?;
        let tx = connection.transaction().await?;
        configure(&tx).await?;
        let rows = tx.query(
            "SELECT jsonb_build_object('id',id,'domain',domain,'payload',payload,'world_epoch',world_epoch) AS document \
             FROM ecology_service_proposals WHERE delivered_at IS NULL AND next_attempt_at<=CURRENT_TIMESTAMP \
             ORDER BY CASE WHEN domain='plants' AND payload->>'kind' IN ('planting_begin','planting_rejected') THEN 0 \
             WHEN domain='plants' AND ((payload->>'kind'='resource_growth' AND jsonb_typeof(payload->'member')='object') \
             OR payload->>'kind'='resource_growth_bulk') THEN 1 ELSE 2 END, attempts,created_at,id LIMIT $1",
            &[&(MAX_PROPOSALS as i64)],
        ).await?;
        let mut batch = vec![];
        for row in rows {
            let candidate: Value = row.get("document");
            batch.push(candidate);
            if json_bytes(
                &json!({"schema_version":SCHEMA_VERSION,"proposals":batch}),
                MAX_BODY_BYTES,
            )
            .is_err()
            {
                batch.pop();
                break;
            }
        }
        tx.commit().await?;
        Ok(batch)
    }

    pub async fn acknowledge(&self, results: &[Value]) -> Result<()> {
        let mut connection = self.client().await?;
        let tx = connection.transaction().await?;
        configure(&tx).await?;
        for result in results {
            let id = string(result, "id")?;
            let status = string(result, "status")?;
            let failures = match result.get("resource_failures") {
                None => &[][..],
                Some(value) => value
                    .as_array()
                    .context("Invalid failed ecology resources")?
                    .as_slice(),
            };
            if !failures.is_empty() {
                if let Some(source) = proposal_for_update(&tx, id).await? {
                    let entries = match source["payload"].get("resources") {
                        Some(value) => value
                            .as_array()
                            .context("Invalid failed ecology resource entries")?
                            .clone(),
                        None => vec![source["payload"].clone()],
                    };
                    let by_uid: HashMap<i64, &Value> = entries
                        .iter()
                        .filter(|e| e["kind"] == "resource_growth")
                        .map(|e| Ok((integer(&e["expected"], "resource_uid")?, e)))
                        .collect::<Result<_>>()?;
                    let failures: HashSet<i64> = failures
                        .iter()
                        .map(|v| {
                            v.as_i64()
                                .ok_or_else(|| anyhow!("Invalid failed ecology resource"))
                        })
                        .collect::<Result<_>>()?;
                    for uid in failures {
                        let entry = by_uid
                            .get(&uid)
                            .context("Unknown failed ecology resource")?;
                        self.record_failure_guard(&tx, &source, entry).await?;
                    }
                }
            }
            if matches!(status, "deferred" | "applied" | "duplicate" | "stale") {
                let outcome = tx.query_opt("SELECT payload->>'kind' AS kind FROM ecology_service_proposals WHERE id=$1 AND delivered_at IS NULL FOR UPDATE", &[&id]).await?;
                let kind = outcome.and_then(|row| row.get::<_, Option<String>>("kind"));
                if matches!(
                    kind.as_deref(),
                    Some("resource_growth_bulk" | "lifecycle_bulk")
                ) && (status != "deferred" || kind.as_deref() == Some("resource_growth_bulk"))
                {
                    let normal_wait =
                        kind.as_deref() == Some("resource_growth_bulk") && status == "deferred";
                    let error = if normal_wait {
                        "normal_wait"
                    } else {
                        "bulk_pass_complete"
                    };
                    let delay: i32 = if normal_wait { 5 } else { 0 };
                    tx.execute(
                        "UPDATE ecology_service_proposals SET delivered_at=CURRENT_TIMESTAMP, \
                         last_error_code=$1,next_attempt_at=CURRENT_TIMESTAMP+$2::integer*interval '1 second' \
                         WHERE id=$3 AND delivered_at IS NULL", &[&error,&delay,&id],
                    ).await?;
                    continue;
                }
            }
            if status == "deferred" {
                tx.execute("UPDATE ecology_service_proposals SET next_attempt_at=CURRENT_TIMESTAMP+interval '1 second' WHERE id=$1 AND delivered_at IS NULL", &[&id]).await?;
                continue;
            }
            let failed_bulk = if status == "retry" {
                proposal_for_update(&tx, id).await?
            } else {
                None
            };
            let terminal = matches!(status, "applied" | "duplicate" | "stale");
            let acknowledged = tx.execute(
                "UPDATE ecology_service_proposals SET attempts=attempts+1,last_error_code=\
                 CASE WHEN $1 THEN NULL WHEN attempts+1>=$2 THEN 'retry_exhausted' ELSE 'retry' END, \
                 delivered_at=CASE WHEN $1 OR attempts+1>=$2 THEN CURRENT_TIMESTAMP ELSE delivered_at END, \
                 next_attempt_at=CASE WHEN $1 THEN next_attempt_at ELSE CURRENT_TIMESTAMP+ \
                 LEAST(30,power(2,LEAST(attempts,5))::integer)*interval '1 second' END \
                 WHERE id=$3 AND delivered_at IS NULL", &[&terminal,&self.max_attempts,&id],
            ).await?;
            if acknowledged > 0 {
                if let Some(source) = failed_bulk {
                    if let Some(field) = bulk_field(&source["payload"]) {
                        for entry in source["payload"][field]
                            .as_array()
                            .context("Invalid failed ecology bulk entries")?
                        {
                            self.record_failure_guard(&tx, &source, entry).await?;
                        }
                    }
                }
            }
            if status == "stale" && acknowledged > 0 {
                tx.execute(
                    "UPDATE ecology_service_proposals SET last_error_code=\
                     CASE WHEN attempts>=$1 THEN 'retry_exhausted' ELSE 'stale' END, \
                     next_attempt_at=CURRENT_TIMESTAMP+interval '1 second' WHERE id=$2 AND delivered_at IS NOT NULL",
                    &[&self.max_attempts,&id],
                ).await?;
            }
        }
        tx.execute(
            "DELETE FROM ecology_service_proposals WHERE id IN (SELECT id FROM (\
             (SELECT id FROM ecology_service_proposals WHERE delivered_at<CURRENT_TIMESTAMP-interval '7 days' \
             AND COALESCE(payload->>'kind','') NOT IN ('maturation','reproduction','resource_growth','planting_begin','planting_rejected','mineral_refill','fishing_refill','bulk_failure_guard') \
             ORDER BY delivered_at,id LIMIT 256) UNION \
             (SELECT id FROM ecology_service_proposals WHERE delivered_at IS NOT NULL \
             AND COALESCE(payload->>'kind','') NOT IN ('maturation','reproduction','resource_growth','planting_begin','planting_rejected','mineral_refill','fishing_refill','bulk_failure_guard') \
             ORDER BY delivered_at DESC,id OFFSET 4096 LIMIT 256)) obsolete LIMIT 256)", &[],
        ).await?;
        tx.commit().await?;
        Ok(())
    }

    async fn record_failure_guard(
        &self,
        tx: &Transaction<'_>,
        source: &Value,
        entry: &Value,
    ) -> Result<()> {
        let domain = string(source, "domain")?;
        let epoch = string(source, "world_epoch")?;
        let guard_id = bulk_failure_identity(domain, epoch, entry)?;
        let payload = json!({"kind":"bulk_failure_guard","entry_key":bulk_entry_key(entry)?});
        tx.execute(
            "INSERT INTO ecology_service_proposals(id,domain,payload,world_epoch,attempts,delivered_at,last_error_code) \
             VALUES($1,$2,$3,$4,1,CURRENT_TIMESTAMP,'bulk_entry_retry') \
             ON CONFLICT(id) DO UPDATE SET attempts=LEAST($5,ecology_service_proposals.attempts+1), \
             delivered_at=CURRENT_TIMESTAMP,last_error_code='bulk_entry_retry'",
            &[&guard_id,&domain,&payload,&epoch,&self.max_attempts],
        ).await?;
        Ok(())
    }

    pub async fn query(&self, request: &Value, catalog: &Catalog) -> Result<Value> {
        validate_query(request)?;
        let map_id = i32::try_from(integer(request, "map_id")?)?;
        let instance_id = integer(request, "instance_id")?;
        let region = request
            .get("region_id")
            .map(|v| {
                v.as_i64()
                    .ok_or_else(|| anyhow!("Invalid ecology query region"))
            })
            .transpose()?
            .map(i32::try_from)
            .transpose()?;
        let mut connection = self.client().await?;
        let tx = connection
            .build_transaction()
            .isolation_level(IsolationLevel::RepeatableRead)
            .read_only(true)
            .start()
            .await?;
        configure(&tx).await?;
        let dirty_map_id = i64::from(map_id);
        let metadata=tx.query_one(
            "SELECT clock_timestamp() AS observed_at, COALESCE((SELECT revision FROM ecology_dirty_scopes WHERE map_id=$1 AND instance_id=$2),0) AS revision",
            &[&dirty_map_id,&instance_id],
        ).await?;
        let observed_at: chrono::DateTime<chrono::Utc> = metadata.get("observed_at");
        let revision: i64 = metadata.get("revision");
        let data = if request["kind"] == "weather" {
            let query="SELECT region_id,weather,revision,updated_at FROM territory_weather WHERE map_id=$1 AND instance_id=$2";
            let rows = if let Some(region) = region {
                tx.query(
                    &(query.to_owned() + " AND region_id=$3 ORDER BY region_id LIMIT 65"),
                    &[&map_id, &instance_id, &region],
                )
                .await?
            } else {
                tx.query(
                    &(query.to_owned() + " ORDER BY region_id LIMIT 65"),
                    &[&map_id, &instance_id],
                )
                .await?
            };
            ensure!(
                rows.len() <= 64,
                "Ecology weather query exceeds region budget"
            );
            let mut regions = vec![];
            for row in rows {
                let updated: chrono::DateTime<chrono::Utc> = row.get("updated_at");
                regions.push(json!({"region_id":row.get::<_,i32>("region_id"),"weather":row.get::<_,String>("weather"),"revision":row.get::<_,i64>("revision"),"updated_at":isoformat(updated)}));
            }
            json!({"regions":regions})
        } else {
            let count:i64=tx.query_one(
                "SELECT (SELECT count(*) FROM planted_resources WHERE map_id=$1 AND instance_id=$2) + \
                 COALESCE((SELECT sum(jsonb_array_length(members)) FROM combat_groups WHERE map_id=$1 AND instance_id=$2 AND status<>'defeated'),0)::bigint AS count",
                &[&map_id,&instance_id],
            ).await?.get("count");
            ensure!(
                count <= 4096,
                "Ecology population query exceeds entity budget"
            );
            let mut result = catalog
                .population_snapshot(&tx, map_id, instance_id)
                .await?;
            if let Some(region) = region {
                let key = region.to_string();
                let values = result["regions"]
                    .get(&key)
                    .cloned()
                    .unwrap_or_else(|| json!({}));
                let mut regions = serde_json::Map::new();
                regions.insert(key, values);
                result["regions"] = Value::Object(regions);
            }
            result
        };
        tx.commit().await?;
        let response = json!({"authoritative":true,"kind":request["kind"],"map_id":map_id,"instance_id":instance_id,"revision":revision,"observed_at":isoformat(observed_at),"data":data});
        json_bytes(&response, MAX_BODY_BYTES)?;
        Ok(response)
    }
}

async fn configure(tx: &Transaction<'_>) -> Result<()> {
    tx.batch_execute("SET LOCAL statement_timeout='1s'; SET LOCAL lock_timeout='250ms'")
        .await?;
    Ok(())
}

async fn proposal_for_update(tx: &Transaction<'_>, id: &str) -> Result<Option<Value>> {
    Ok(tx.query_opt(
        "SELECT jsonb_build_object('domain',domain,'payload',payload,'world_epoch',world_epoch) AS document \
         FROM ecology_service_proposals WHERE id=$1 AND delivered_at IS NULL FOR UPDATE", &[&id],
    ).await?.map(|row|row.get("document")))
}

impl Drop for Repository {
    fn drop(&mut self) {
        // A dropped repository must close its lock-owning backend, rather than
        // return that backend to a shared pool with a session lock still held.
        if let Some(connection) = self.owner.get_mut().take() {
            drop(Object::take(connection));
        }
    }
}

fn bulk_field(payload: &Value) -> Option<&'static str> {
    match payload["kind"].as_str() {
        Some("resource_growth_bulk") => Some("resources"),
        Some("lifecycle_bulk") => Some("operations"),
        _ => None,
    }
}

fn admission_capacity(payload: &Value) -> usize {
    match payload["kind"].as_str() {
        Some("planting_begin" | "planting_rejected") => MAX_PENDING,
        Some("resource_growth_bulk") => MAX_PENDING - RESERVED_INTERACTIVE,
        Some("resource_growth") if payload.get("member").is_some_and(python_truthy) => {
            MAX_PENDING - RESERVED_INTERACTIVE
        }
        _ => MAX_PENDING - RESERVED_INTERACTIVE - RESERVED_GROWTH,
    }
}

fn python_truthy(value: &Value) -> bool {
    match value {
        Value::Null => false,
        Value::Bool(value) => *value,
        Value::Number(value) => value.as_f64().is_some_and(|number| number != 0.0),
        Value::String(value) => !value.is_empty(),
        Value::Array(value) => !value.is_empty(),
        Value::Object(value) => !value.is_empty(),
    }
}

fn string<'a>(row: &'a Value, key: &str) -> Result<&'a str> {
    row.get(key)
        .and_then(Value::as_str)
        .with_context(|| format!("Missing ecology {key}"))
}
fn integer(row: &Value, key: &str) -> Result<i64> {
    row.get(key)
        .and_then(Value::as_i64)
        .with_context(|| format!("Invalid ecology {key}"))
}
fn attempts(row: &Value) -> Result<i32> {
    i32::try_from(row.get("attempts").and_then(Value::as_i64).unwrap_or(0))
        .context("Invalid ecology attempt count")
}

fn isoformat(value: chrono::DateTime<chrono::Utc>) -> String {
    // Python datetime.isoformat uses no fractional part at zero and six digits
    // otherwise; preserve its +00:00 spelling rather than RFC3339's Z suffix.
    let precision = if value.timestamp_subsec_micros() == 0 {
        chrono::SecondsFormat::Secs
    } else {
        chrono::SecondsFormat::Micros
    };
    value.to_rfc3339_opts(precision, false)
}

#[derive(Default)]
struct AdmissionStats {
    incoming: usize,
    inserted: usize,
    deduplicated: usize,
    superseded: usize,
    capacity_deferred: usize,
    refreshed: usize,
}
impl AdmissionStats {
    fn value(&self) -> Value {
        json!({"incoming":self.incoming,"inserted":self.inserted,"deduplicated":self.deduplicated,"superseded":self.superseded,"capacity_deferred":self.capacity_deferred,"refreshed":self.refreshed})
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn reserved_lanes_preserve_interactive_and_monster_growth_admission() {
        assert_eq!(admission_capacity(&json!({"kind":"planting_begin"})), 4096);
        assert_eq!(
            admission_capacity(&json!({"kind":"planting_rejected"})),
            4096
        );
        assert_eq!(
            admission_capacity(&json!({"kind":"resource_growth_bulk"})),
            4064
        );
        assert_eq!(
            admission_capacity(&json!({"kind":"resource_growth","member":{"id":-1}})),
            4064
        );
        assert_eq!(
            admission_capacity(&json!({"kind":"resource_growth","member":null})),
            4048
        );
        assert_eq!(
            admission_capacity(&json!({"kind":"resource_growth","member":{}})),
            4048
        );
        assert_eq!(admission_capacity(&json!({"kind":"lifecycle_bulk"})), 4048);
    }
    #[test]
    fn publication_dates_match_python_utc_isoformat() {
        let whole = chrono::DateTime::parse_from_rfc3339("2026-11-14T00:00:00Z")
            .unwrap()
            .with_timezone(&chrono::Utc);
        let fraction = chrono::DateTime::parse_from_rfc3339("2026-11-14T00:00:00.001234Z")
            .unwrap()
            .with_timezone(&chrono::Utc);
        assert_eq!(isoformat(whole), "2026-11-14T00:00:00+00:00");
        assert_eq!(isoformat(fraction), "2026-11-14T00:00:00.001234+00:00");
    }
}

#[cfg(test)]
#[path = "repository_tests.rs"]
mod sql_tests;
