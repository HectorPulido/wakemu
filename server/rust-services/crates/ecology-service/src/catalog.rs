//! Pinned catalog authority with a shared, bounded cache of immutable bytes and
//! compact surface indexes. Decoded gameplay records are private to callers.
use anyhow::{anyhow, bail, ensure, Context as _, Result};
use deadpool_postgres::{ClientWrapper, Object, Pool};
use serde::Deserialize;
use serde_json::{json, value::RawValue, Map, Value};
use sha2::{Digest, Sha256};
use std::collections::{HashMap, VecDeque};
use std::fmt;
use std::mem::size_of;
use std::sync::{Arc, Mutex};
use tokio::sync::Mutex as AsyncMutex;
use tokio_postgres::Transaction;

const CACHE_BYTES: usize = 8 * 1024 * 1024;
const CACHE_ENTRIES: usize = 2048;
const MONSTER_INDEX_BYTES: usize = 8 * 1024 * 1024;
const DOCUMENT_BYTES: usize = 64 * 1024 * 1024;
const MANIFEST_BYTES: usize = 8 * 1024 * 1024;
const RECORD_BYTES: usize = 16 * 1024 * 1024;
const POPULATION_ENTITIES: usize = 4096;
const POLICY: &str = "wakemu.compiled-combat-catalog.v1";

#[derive(Clone)]
pub struct Catalog {
    inner: Arc<Inner>,
}

struct Inner {
    pool: Pool,
    revision: String,
    generation: Option<String>,
    // A checked-out connection holds the same lifetime advisory pins as Python.
    pins: AsyncMutex<Option<ClientWrapper>>,
    cache: Mutex<Cache>,
    monsters: AsyncMutex<Option<Arc<MonsterIndex>>>,
}

#[derive(Clone)]
enum Cached {
    Validated,
    Bytes(Arc<[u8]>),
    Surfaces(Arc<Vec<Surface>>),
    Territories(Arc<Vec<Territory>>),
}

struct Cache {
    entries: HashMap<String, (Cached, usize)>,
    order: VecDeque<String>,
    bytes: usize,
}

impl Cache {
    fn new() -> Self {
        Self {
            entries: HashMap::new(),
            order: VecDeque::new(),
            bytes: 0,
        }
    }

    fn get(&mut self, key: &str) -> Option<Cached> {
        let value = self.entries.get(key)?.0.clone();
        self.order.retain(|old| old != key);
        self.order.push_back(key.to_owned());
        Some(value)
    }

    fn put(&mut self, key: String, value: Cached, payload_bytes: usize) {
        // Charge key copies and conservative fixed map/deque allocation overhead.
        let cost = payload_bytes
            .saturating_add(key.capacity() * 2)
            .saturating_add(192);
        if cost > CACHE_BYTES {
            return;
        }
        if let Some((_, old)) = self.entries.remove(&key) {
            self.bytes -= old;
        }
        self.order.retain(|old| old != &key);
        self.bytes += cost;
        self.order.push_back(key.clone());
        self.entries.insert(key, (value, cost));
        while self.bytes > CACHE_BYTES || self.entries.len() > CACHE_ENTRIES {
            // Small immutable validation proofs must survive large byte-only
            // churn. Entry pressure still evicts the oldest entry of any kind.
            let victim = if self.entries.len() > CACHE_ENTRIES {
                self.order.front().cloned()
            } else {
                self.order
                    .iter()
                    .find(|key| !matches!(self.entries.get(*key), Some((Cached::Validated, _))))
                    .or_else(|| self.order.front())
                    .cloned()
            };
            if let Some(oldest) = victim {
                self.order.retain(|key| key != &oldest);
                if let Some((_, cost)) = self.entries.remove(&oldest) {
                    self.bytes -= cost;
                }
            } else {
                break;
            }
        }
    }
}

#[derive(Clone, Copy, Debug)]
struct MonsterRange {
    reference: i64,
    start: usize,
    length: usize,
    ordinal: usize,
}

struct MonsterIndex {
    raw: Arc<[u8]>,
    rows: Vec<MonsterRange>,
    last_invalid: Option<(usize, String)>,
}

impl MonsterIndex {
    fn new(raw: Arc<[u8]>) -> Result<Self> {
        let document: RawMonsterDocument<'_> = serde_json::from_slice(&raw)?;
        let mut rows = Vec::with_capacity(document.monsters.len());
        let mut last_invalid = None;
        for (ordinal, row) in document.monsters.into_iter().enumerate() {
            match serde_json::from_str::<MonsterReference>(row.get()) {
                Ok(header) => rows.push(MonsterRange {
                    reference: header.reference,
                    start: (row.get().as_ptr() as usize)
                        .checked_sub(raw.as_ptr() as usize)
                        .ok_or_else(|| anyhow!("Native monster row lies outside source bytes"))?,
                    length: row.get().len(),
                    ordinal,
                }),
                Err(error) => last_invalid = Some((ordinal, error.to_string())),
            }
        }
        // Python's reference dict and the former reverse scan both select the
        // last source row for a repeated reference.
        rows.sort_unstable_by_key(|row| (row.reference, std::cmp::Reverse(row.ordinal)));
        rows.dedup_by_key(|row| row.reference);
        rows.shrink_to_fit();
        Ok(Self {
            raw,
            rows,
            last_invalid,
        })
    }

    fn cost(&self) -> usize {
        self.raw.len()
            + self.rows.capacity() * size_of::<MonsterRange>()
            + self
                .last_invalid
                .as_ref()
                .map_or(0, |(_, message)| message.capacity())
            + size_of::<Self>()
            + 64
    }

    fn record(&self, reference: i64) -> Result<Value> {
        let row = self
            .rows
            .binary_search_by_key(&reference, |row| row.reference)
            .ok()
            .map(|index| self.rows[index]);
        if let Some((ordinal, message)) = &self.last_invalid {
            ensure!(
                row.is_some_and(|row| row.ordinal > *ordinal),
                "Invalid native monster reference: {message}"
            );
        }
        let row = row.ok_or_else(|| anyhow!("Unknown monster reference"))?;
        Ok(serde_json::from_slice(
            &self.raw[row.start..row.start + row.length],
        )?)
    }
}

#[derive(Clone, Copy, Debug)]
struct Surface {
    x: i32,
    y: i32,
    z: i16,
    ground: i32,
    region: i32,
    ordinal: u32,
}

#[derive(Clone, Copy, Debug)]
struct Territory {
    map: i32,
    x: i32,
    y: i32,
    region: i32,
}

#[derive(Deserialize)]
struct RawMonsterDocument<'a> {
    #[serde(borrow)]
    monsters: Vec<&'a RawValue>,
}

#[derive(Deserialize)]
struct MonsterReference {
    #[serde(rename = "ref")]
    reference: i64,
}

#[derive(Deserialize)]
struct ResourceReference {
    resource_reference: i64,
}

impl Catalog {
    pub fn new(pool: Pool, revision: String, compiled_generation: Option<String>) -> Self {
        Self {
            inner: Arc::new(Inner {
                pool,
                revision,
                generation: compiled_generation,
                pins: AsyncMutex::new(None),
                cache: Mutex::new(Cache::new()),
                monsters: AsyncMutex::new(None),
            }),
        }
    }

    pub fn revision(&self) -> &str {
        &self.inner.revision
    }

    pub fn compiled_generation(&self) -> Option<&str> {
        self.inner.generation.as_deref()
    }

    pub async fn verify(&self) -> Result<()> {
        self.pin().await?;
        if self.inner.generation.is_some() {
            self.manifest().await?;
        }
        Ok(())
    }

    pub(crate) async fn ensure_authority(&self) -> Result<()> {
        self.pin().await
    }

    async fn pin(&self) -> Result<()> {
        let mut pins = self.inner.pins.lock().await;
        if let Some(owner) = pins.as_ref() {
            ensure!(
                !owner.is_closed(),
                "Catalog lifetime pin connection was lost"
            );
            return Ok(());
        }
        validate_digest(&self.inner.revision)?;
        if let Some(generation) = &self.inner.generation {
            validate_digest(generation)?;
        }
        // Detach the lifetime session: dropping it must close the socket, not
        // return advisory locks to an otherwise reusable pool connection.
        let client = Object::take(self.inner.pool.get().await?);
        let active = client.query_opt(
            "SELECT a.revision FROM native_catalog_active a JOIN native_catalog_releases r USING(revision) WHERE a.id=1 AND r.complete", &[]
        ).await?.ok_or_else(|| anyhow!("No published native catalog release"))?;
        ensure!(
            active.get::<_, String>(0) == self.inner.revision,
            "Published native catalog release differs from configured revision"
        );
        client.execute("SELECT pg_advisory_lock_shared(hashtextextended(current_database()||':'||current_schema()||':native_revision:'||$1,0))", &[&self.inner.revision]).await?;
        let exists = client
            .query_opt(
                "SELECT 1 FROM native_catalog_releases WHERE revision=$1 AND complete",
                &[&self.inner.revision],
            )
            .await?;
        ensure!(
            exists.is_some(),
            "Pinned native catalog release disappeared"
        );
        if let Some(generation) = &self.inner.generation {
            client.execute("SELECT pg_advisory_lock_shared(hashtextextended(current_database()||':'||current_schema()||':compiled_generation:'||$1,0))", &[generation]).await?;
            let exists = client.query_opt("SELECT 1 FROM native_compiled_catalog_releases WHERE generation=$1 AND source_revision=$2 AND complete", &[generation, &self.inner.revision]).await?;
            ensure!(
                exists.is_some(),
                "Pinned compiled catalog generation is absent or belongs to another source"
            );
        }
        *pins = Some(client);
        Ok(())
    }

    fn cached(&self, key: &str) -> Option<Cached> {
        self.inner
            .cache
            .lock()
            .expect("catalog cache mutex poisoned")
            .get(key)
    }

    fn cache(&self, key: String, value: Cached, bytes: usize) {
        self.inner
            .cache
            .lock()
            .expect("catalog cache mutex poisoned")
            .put(key, value, bytes)
    }

    /// Borrow hash-checked immutable bytes without expanding a JSON graph.
    pub async fn document_bytes(&self, name: &str) -> Result<Arc<[u8]>> {
        self.raw_document(name).await
    }

    /// Proofs belong to this exact pinned authority, sharing its byte budget.
    /// Unsealed source-only contexts always perform validation again.
    pub(crate) async fn immutable_validation_cached(&self, key: &str) -> Result<bool> {
        ensure!(key.len() <= 256, "Immutable validation key exceeds budget");
        self.pin().await?;
        Ok(self.inner.generation.is_some()
            && matches!(
                self.cached(&format!("validation:{key}")),
                Some(Cached::Validated)
            ))
    }

    pub(crate) fn remember_immutable_validation(&self, key: &str) {
        if self.inner.generation.is_some() && key.len() <= 256 {
            self.cache(format!("validation:{key}"), Cached::Validated, 0);
        }
    }

    pub fn cache_status(&self) -> Value {
        let cache = self
            .inner
            .cache
            .lock()
            .expect("catalog cache mutex poisoned");
        json!({"bytes":cache.bytes,"entries":cache.entries.len(),"max_bytes":CACHE_BYTES,"max_entries":CACHE_ENTRIES,"monster_index_max_bytes":MONSTER_INDEX_BYTES,"total_max_bytes":CACHE_BYTES+MONSTER_INDEX_BYTES})
    }

    async fn raw_document(&self, name: &str) -> Result<Arc<[u8]>> {
        validate_name(name)?;
        self.pin().await?;
        let key = format!("native:{}:{name}", self.inner.revision);
        if let Some(Cached::Bytes(bytes)) = self.cached(&key) {
            return Ok(bytes);
        }
        let client = self.inner.pool.get().await?;
        let row = client.query_opt(
            "SELECT raw,sha256,source_bytes FROM native_catalog_documents WHERE revision=$1 AND path=$2 AND source_bytes<=$3 AND octet_length(raw)<=$3",
            &[&self.inner.revision, &name, &(DOCUMENT_BYTES as i64)],
        ).await?.ok_or_else(|| anyhow!("Missing or oversized pinned native document: {name}"))?;
        let raw: Vec<u8> = row.get(0);
        let digest: String = row.get(1);
        let declared: i64 = row.get(2);
        ensure!(
            declared >= 0 && raw.len() == declared as usize,
            "Native document byte count differs"
        );
        verify_sha(&raw, &digest)?;
        let raw: Arc<[u8]> = raw.into();
        self.cache(key, Cached::Bytes(raw.clone()), raw.len());
        Ok(raw)
    }

    pub async fn document_exists(&self, name: &str) -> Result<bool> {
        validate_name(name)?;
        self.pin().await?;
        let client = self.inner.pool.get().await?;
        Ok(client
            .query_opt(
                "SELECT 1 FROM native_catalog_documents WHERE revision=$1 AND path=$2",
                &[&self.inner.revision, &name],
            )
            .await?
            .is_some())
    }

    pub async fn document(&self, name: &str) -> Result<Value> {
        let raw = self.raw_document(name).await?;
        serde_json::from_slice(&raw)
            .with_context(|| format!("Invalid native JSON document: {name}"))
    }

    async fn manifest(&self) -> Result<Value> {
        self.pin().await?;
        let generation = self
            .inner
            .generation
            .as_ref()
            .ok_or_else(|| anyhow!("A pinned compiled catalog generation is required"))?;
        let key = format!("manifest:{generation}");
        if let Some(Cached::Bytes(raw)) = self.cached(&key) {
            return Ok(serde_json::from_slice(&raw)?);
        }
        let client = self.inner.pool.get().await?;
        let row = client.query_opt(
            "SELECT manifest_raw,manifest,policy,source_revision,source_inventory_sha256,compiler_contract_sha256,config_sha256 FROM native_compiled_catalog_releases WHERE generation=$1 AND complete AND octet_length(manifest_raw)<=$2",
            &[generation, &(MANIFEST_BYTES as i32)],
        ).await?.ok_or_else(|| anyhow!("No complete bounded compiled catalog publication"))?;
        let raw: Vec<u8> = row.get(0);
        verify_sha(&raw, generation)?;
        let manifest: Value = serde_json::from_slice(&raw)?;
        ensure!(
            manifest == row.get::<_, Value>(1),
            "Compiled manifest differs from authoritative JSON"
        );
        for (index, field) in [
            (2, "policy"),
            (3, "source_revision"),
            (4, "source_inventory_sha256"),
            (5, "compiler_contract_sha256"),
            (6, "config_sha256"),
        ] {
            ensure!(
                manifest.get(field).and_then(Value::as_str)
                    == Some(row.get::<_, String>(index).as_str()),
                "Compiled manifest authority differs: {field}"
            );
        }
        ensure!(
            manifest["policy"] == POLICY && manifest["source_revision"] == self.inner.revision,
            "Compiled publication source or policy differs"
        );
        for field in [
            "source_revision",
            "source_inventory_sha256",
            "compiler_contract_sha256",
            "config_sha256",
        ] {
            validate_digest(
                manifest[field]
                    .as_str()
                    .ok_or_else(|| anyhow!("Missing compiled publication pin"))?,
            )?;
        }
        ensure!(
            manifest["collections"].is_object(),
            "Missing compiled collection inventory"
        );
        let raw: Arc<[u8]> = raw.into();
        self.cache(key, Cached::Bytes(raw.clone()), raw.len());
        Ok(manifest)
    }

    async fn collection_metadata(&self, collection: &str) -> Result<Value> {
        self.pin().await?;
        let generation = self
            .inner
            .generation
            .as_ref()
            .ok_or_else(|| anyhow!("A pinned compiled catalog generation is required"))?;
        let key = format!("collection-meta:{generation}:{collection}");
        if let Some(Cached::Bytes(raw)) = self.cached(&key) {
            return Ok(serde_json::from_slice(&raw)?);
        }
        let manifest = self.manifest().await?;
        let value = manifest["collections"]
            .get(collection)
            .cloned()
            .ok_or_else(|| anyhow!("Collection absent from pinned publication"))?;
        let raw: Arc<[u8]> = serde_json::to_vec(&value)?.into();
        self.cache(key, Cached::Bytes(raw.clone()), raw.len());
        Ok(value)
    }

    async fn document_metadata(&self, document: &str) -> Result<Value> {
        validate_name(document)?;
        self.pin().await?;
        let generation = self
            .inner
            .generation
            .as_ref()
            .ok_or_else(|| anyhow!("A pinned compiled catalog generation is required"))?;
        let key = format!("document-meta:{generation}:{document}");
        if let Some(Cached::Bytes(raw)) = self.cached(&key) {
            return Ok(serde_json::from_slice(&raw)?);
        }
        let manifest = self.manifest().await?;
        let value = Self::published_document(&manifest, document)?.clone();
        let raw: Arc<[u8]> = serde_json::to_vec(&value)?.into();
        self.cache(key, Cached::Bytes(raw.clone()), raw.len());
        Ok(value)
    }

    pub async fn record(&self, collection: &str, record_key: &Value) -> Result<Value> {
        validate_name(collection)?;
        let encoded = encoded_key(record_key)?;
        let meta = self.collection_metadata(collection).await?;
        ensure!(
            meta["representation"] == "native_json",
            "Collection does not contain native JSON records"
        );
        ensure!(
            meta["collection"] == collection
                && matches!(meta["kind"].as_str(), Some("dict" | "list")),
            "Invalid compiled collection metadata"
        );
        let count = meta["count"]
            .as_u64()
            .ok_or_else(|| anyhow!("Invalid compiled collection count"))?;
        let generation = self
            .inner
            .generation
            .as_ref()
            .expect("manifest requires generation");
        let cache_key = format!("compiled:{generation}:{collection}:{encoded}");
        if let Some(Cached::Bytes(raw)) = self.cached(&cache_key) {
            return Ok(serde_json::from_slice(&raw)?);
        }
        let client = self.inner.pool.get().await?;
        let row = client.query_opt(
            "SELECT r.raw,r.sha256,r.ordinal,c.kind,c.record_count,c.ordered_keys_sha256 FROM native_compiled_catalog_records r JOIN native_compiled_catalog_collections c USING(generation,collection) WHERE r.generation=$1 AND r.collection=$2 AND r.record_key=$3 AND octet_length(r.raw)<=$4",
            &[generation,&collection,&encoded,&(RECORD_BYTES as i32)],
        ).await?.ok_or_else(|| anyhow!("Missing or oversized compiled catalog record"))?;
        let raw: Vec<u8> = row.get(0);
        verify_sha(&raw, &row.get::<_, String>(1))?;
        let ordinal: i32 = row.get(2);
        ensure!(
            ordinal >= 0 && (ordinal as u64) < count,
            "Compiled record ordinal is outside sealed collection"
        );
        ensure!(
            meta["kind"] == row.get::<_, String>(3)
                && count == row.get::<_, i32>(4) as u64
                && meta["ordered_keys_sha256"] == row.get::<_, String>(5),
            "Compiled collection differs from sealed manifest"
        );
        let value = serde_json::from_slice(&raw)?;
        let raw: Arc<[u8]> = raw.into();
        self.cache(cache_key, Cached::Bytes(raw.clone()), raw.len());
        Ok(value)
    }

    fn published_document<'a>(manifest: &'a Value, name: &str) -> Result<&'a Value> {
        let transformed = manifest["documents"].get(name);
        let original = manifest["raw_documents"].get(name);
        ensure!(
            transformed.is_some() != original.is_some(),
            "Missing or ambiguous published document: {name}"
        );
        let entry = transformed.or(original).expect("one document was found");
        if original.is_some() {
            ensure!(
                manifest["source_documents"]
                    .get(name)
                    .and_then(Value::as_str)
                    .is_some()
                    && entry["source_sha256"] == manifest["source_documents"][name],
                "Published raw document differs from original source"
            );
        }
        Ok(entry)
    }

    pub async fn document_record(
        &self,
        document: &str,
        collection: &str,
        key: &Value,
    ) -> Result<Value> {
        validate_name(document)?;
        let entry = self.document_metadata(document).await?;
        if entry["root_kind"] == "record_mapping" {
            ensure!(
                collection == "$",
                "Record-mapping document requires root collection"
            );
            return self
                .record(
                    entry["root_collection"]
                        .as_str()
                        .ok_or_else(|| anyhow!("Missing root collection"))?,
                    key,
                )
                .await;
        }
        ensure!(
            entry["root_kind"] == "dict",
            "Unsupported published document root"
        );
        if let Some(meta) = entry["collections"].get(collection) {
            let name = meta["collection"]
                .as_str()
                .ok_or_else(|| anyhow!("Missing document collection"))?;
            let sealed = self.collection_metadata(name).await?;
            ensure!(
                meta["count"] == sealed["count"]
                    && meta["ordered_keys_sha256"] == sealed["ordered_keys_sha256"],
                "Document collection differs from sealed inventory"
            );
            return self.record(name, key).await;
        }
        let key = key
            .as_str()
            .map(str::to_owned)
            .or_else(|| key.as_i64().map(|x| x.to_string()))
            .ok_or_else(|| anyhow!("Invalid document metadata key"))?;
        entry["header"][collection]
            .get(&key)
            .cloned()
            .ok_or_else(|| anyhow!("Missing document metadata record"))
    }

    pub async fn document_collection(
        &self,
        document: &str,
        collection: &str,
        max_bytes: usize,
        max_records: usize,
    ) -> Result<Value> {
        ensure!(
            max_bytes > 0 && max_bytes <= RECORD_BYTES && max_records > 0 && max_records <= 4096,
            "Invalid small collection read budget"
        );
        self.pin().await?;
        let generation = self
            .inner
            .generation
            .as_ref()
            .ok_or_else(|| anyhow!("A pinned compiled catalog generation is required"))?;
        let cache_key = format!(
            "small-collection:{generation}:{document}:{collection}:{max_bytes}:{max_records}"
        );
        if let Some(Cached::Bytes(raw)) = self.cached(&cache_key) {
            return Ok(serde_json::from_slice(&raw)?);
        }
        let entry = self.document_metadata(document).await?;
        if let Some(header) = entry["header"].get(collection) {
            ensure!(
                header.is_object() && header.as_object().map_or(0, Map::len) <= max_records,
                "Small document metadata collection exceeds count budget"
            );
            ensure!(
                serde_json::to_vec(header)?.len() <= max_bytes,
                "Small document metadata collection exceeds byte budget"
            );
            return Ok(header.clone());
        }
        let meta = &entry["collections"][collection];
        let name = meta["collection"]
            .as_str()
            .ok_or_else(|| anyhow!("Missing published document collection"))?;
        let sealed = self.collection_metadata(name).await?;
        let count = meta["count"]
            .as_u64()
            .ok_or_else(|| anyhow!("Invalid small collection count"))? as usize;
        ensure!(
            count <= max_records
                && meta["count"] == sealed["count"]
                && meta["ordered_keys_sha256"] == sealed["ordered_keys_sha256"]
                && sealed["representation"] == "native_json",
            "Small collection differs from sealed inventory"
        );
        let generation = self
            .inner
            .generation
            .as_ref()
            .expect("manifest requires generation");
        let client = self.inner.pool.get().await?;
        let budget = client.query_one("SELECT count(*)::bigint,COALESCE(sum(octet_length(raw)),0)::bigint FROM native_compiled_catalog_records WHERE generation=$1 AND collection=$2", &[generation,&name]).await?;
        ensure!(
            budget.get::<_, i64>(0) == count as i64
                && budget.get::<_, i64>(1) >= 0
                && budget.get::<_, i64>(1) <= max_bytes as i64,
            "Small collection actual bytes/count exceed budget"
        );
        let rows = client.query("SELECT record_key,raw,sha256,ordinal FROM native_compiled_catalog_records WHERE generation=$1 AND collection=$2 ORDER BY ordinal", &[generation,&name]).await?;
        let mut result = Map::new();
        let mut bytes = 0usize;
        for (ordinal, row) in rows.into_iter().enumerate() {
            let key: String = row.get(0);
            let key: Value = serde_json::from_str(&key)?;
            let key = key
                .as_str()
                .map(str::to_owned)
                .or_else(|| key.as_i64().map(|x| x.to_string()))
                .ok_or_else(|| anyhow!("Unsupported small collection key"))?;
            let raw: Vec<u8> = row.get(1);
            bytes = bytes
                .checked_add(raw.len())
                .ok_or_else(|| anyhow!("Collection byte count overflow"))?;
            ensure!(
                bytes <= max_bytes && row.get::<_, i32>(3) == ordinal as i32,
                "Small collection bytes/order differ"
            );
            verify_sha(&raw, &row.get::<_, String>(2))?;
            ensure!(
                result.insert(key, serde_json::from_slice(&raw)?).is_none(),
                "Duplicate small collection record key"
            );
        }
        ensure!(
            result.len() == count,
            "Small collection record count differs"
        );
        let value = Value::Object(result);
        let raw: Arc<[u8]> = serde_json::to_vec(&value)?.into();
        self.cache(cache_key, Cached::Bytes(raw.clone()), raw.len());
        Ok(value)
    }

    pub async fn characteristic_definitions(&self) -> Result<Value> {
        self.document_collection(
            "native-actor-characteristics.json",
            "characteristics",
            256 * 1024,
            128,
        )
        .await
    }

    pub async fn resource_definition(&self, reference: i64) -> Result<Value> {
        self.pin().await?;
        let key = format!("resource:{}:{reference}", self.inner.revision);
        if let Some(Cached::Bytes(raw)) = self.cached(&key) {
            return Ok(serde_json::from_slice(&raw)?);
        }
        let raw = self.raw_document("plant-resources.json").await?;
        let rows: Vec<&RawValue> = serde_json::from_slice(&raw)?;
        for row in rows.into_iter().rev() {
            if serde_json::from_str::<ResourceReference>(row.get())?.resource_reference == reference
            {
                let value = serde_json::from_str(row.get())?;
                let raw: Arc<[u8]> = row.get().as_bytes().into();
                self.cache(key, Cached::Bytes(raw.clone()), raw.len());
                return Ok(value);
            }
        }
        bail!("Unknown native resource reference")
    }

    pub async fn monster_definition(&self, reference: i64) -> Result<Value> {
        self.pin().await?;
        let mut cached = self.inner.monsters.lock().await;
        let index = match cached.as_ref() {
            Some(index) => index.clone(),
            None => {
                let index = Arc::new(MonsterIndex::new(
                    self.raw_document("monsters.json").await?,
                )?);
                if index.cost() <= MONSTER_INDEX_BYTES {
                    *cached = Some(index.clone());
                }
                index
            }
        };
        drop(cached);
        index.record(reference)
    }

    async fn surfaces(&self, map_id: i32) -> Result<Arc<Vec<Surface>>> {
        self.pin().await?;
        ensure!(map_id > 0, "Invalid native planting map");
        let cache_key = format!("surfaces:{}:{map_id}", self.inner.revision);
        if let Some(Cached::Surfaces(rows)) = self.cached(&cache_key) {
            return Ok(rows);
        }
        let name = format!("planting-maps/{map_id}.json");
        if !self.document_exists(&name).await? {
            return Err(MissingLocation::Surface.into());
        }
        let raw = self.raw_document(&name).await?;
        #[derive(Deserialize)]
        struct Data {
            cells: Vec<[i64; 6]>,
        }
        let data: Data = serde_json::from_slice(&raw)?;
        let mut cells = Vec::with_capacity(data.cells.len());
        for (ordinal, row) in data.cells.into_iter().enumerate() {
            cells.push(Surface {
                x: i32::try_from(row[0])?,
                y: i32::try_from(row[1])?,
                z: i16::try_from(row[2])?,
                ground: i32::try_from(row[4])?,
                region: i32::try_from(row[5])?,
                ordinal: u32::try_from(ordinal)?,
            });
        }
        cells.sort_unstable_by_key(|r| (r.x, r.y, r.z, r.ordinal));
        cells.shrink_to_fit();
        let cost = cells.capacity() * size_of::<Surface>();
        let cells = Arc::new(cells);
        self.cache(cache_key, Cached::Surfaces(cells.clone()), cost);
        Ok(cells)
    }

    pub async fn surface(&self, map_id: i32, x: i32, y: i32, z: i16) -> Result<Value> {
        let rows = self.surfaces(map_id).await?;
        let ordinal = rows.partition_point(|row| (row.x, row.y, row.z) < (x, y, z));
        let row = rows
            .get(ordinal)
            .filter(|row| (row.x, row.y, row.z) == (x, y, z))
            .ok_or(MissingLocation::Surface)?;
        Ok(json!({"z":row.z,"ground_id":row.ground,"region_id":row.region}))
    }

    pub async fn surface_region(&self, map_id: i32, x: i32, y: i32, z: i16) -> Result<i32> {
        Ok(self.surface(map_id, x, y, z).await?["region_id"]
            .as_i64()
            .expect("typed surface region") as i32)
    }

    pub async fn surfaces_at(&self, map_id: i32, x: i32, y: i32) -> Result<Vec<Value>> {
        let rows = self.surfaces(map_id).await?;
        Ok(surface_rows_at(&rows, x, y))
    }

    async fn territories(&self) -> Result<Arc<Vec<Territory>>> {
        self.pin().await?;
        let cache_key = format!("territories:{}", self.inner.revision);
        if let Some(Cached::Territories(rows)) = self.cached(&cache_key) {
            return Ok(rows);
        }
        let data = self.document("territory-map-cells.json").await?;
        ensure!(
            data["schema_version"] == 1 && data["grid_size"] == 18,
            "Unsupported native territory cell catalog"
        );
        let mut rows = Vec::new();
        let mut maps = std::collections::HashSet::new();
        for map in data["maps"]
            .as_array()
            .ok_or_else(|| anyhow!("Missing native territory maps"))?
        {
            let map_id = integer_i32(&map["map_id"])?;
            ensure!(maps.insert(map_id), "Duplicate native territory map");
            for region in map["regions"]
                .as_array()
                .ok_or_else(|| anyhow!("Missing native territory regions"))?
            {
                let region_id = integer_i32(&region["region_id"])?;
                ensure!(region_id > 0, "Invalid native territory identifier");
                for point in region["cells"]
                    .as_array()
                    .ok_or_else(|| anyhow!("Missing native territory cells"))?
                {
                    let point = point
                        .as_array()
                        .filter(|p| p.len() == 2)
                        .ok_or_else(|| anyhow!("Invalid native territory grid cell"))?;
                    rows.push(Territory {
                        map: map_id,
                        x: integer_i32(&point[0])?,
                        y: integer_i32(&point[1])?,
                        region: region_id,
                    });
                }
            }
        }
        rows.sort_unstable_by_key(|r| (r.map, r.x, r.y));
        ensure!(
            !rows
                .windows(2)
                .any(|w| (w[0].map, w[0].x, w[0].y) == (w[1].map, w[1].x, w[1].y)),
            "Overlapping native territory grid cells"
        );
        rows.shrink_to_fit();
        let cost = rows.capacity() * size_of::<Territory>();
        let rows = Arc::new(rows);
        self.cache(cache_key, Cached::Territories(rows.clone()), cost);
        Ok(rows)
    }

    pub async fn territory_region(&self, map_id: i32, x: i32, y: i32) -> Result<i32> {
        let rows = self.territories().await?;
        let key = (map_id, x.div_euclid(18), y.div_euclid(18));
        let index = rows
            .binary_search_by_key(&key, |row| (row.map, row.x, row.y))
            .map_err(|_| MissingLocation::Territory)?;
        Ok(rows[index].region)
    }

    pub async fn known_territories(&self) -> Result<std::collections::BTreeSet<(i32, i32)>> {
        Ok(self
            .territories()
            .await?
            .iter()
            .map(|row| (row.map, row.region))
            .collect())
    }

    pub async fn map_geometry(&self, map_id: i32) -> Result<Value> {
        ensure!(map_id > 0, "Invalid native map geometry identity");
        if map_id == 2_000_000_000 {
            ensure!(
                !self.document_exists("combat-maps/2000000000.json").await?,
                "Internal Haven World geometry namespace collides with native map"
            );
            return haven_world_geometry();
        }
        let value = self.document(&format!("combat-maps/{map_id}.json")).await?;
        ensure!(
            value["map_id"] == map_id,
            "Combat map export identity differs"
        );
        Ok(value)
    }

    pub async fn population_snapshot(
        &self,
        db: &Transaction<'_>,
        map_id: i32,
        instance_id: i64,
    ) -> Result<Value> {
        self.population_snapshot_with_policy(
            db,
            map_id,
            instance_id,
            &["plant", "monster"],
            false,
            false,
        )
        .await
    }

    pub async fn population_snapshot_regional(
        &self,
        db: &Transaction<'_>,
        map_id: i32,
        instance_id: i64,
    ) -> Result<Value> {
        self.population_snapshot_with_policy(
            db,
            map_id,
            instance_id,
            &["plant", "monster"],
            true,
            true,
        )
        .await
    }

    pub async fn population_snapshot_with_policy(
        &self,
        db: &Transaction<'_>,
        map_id: i32,
        instance_id: i64,
        kinds: &[&str],
        regional: bool,
        exclude_unassigned: bool,
    ) -> Result<Value> {
        ensure!(
            map_id > 0 && instance_id >= 0,
            "Invalid ecology population scope"
        );
        ensure!(
            !kinds.is_empty()
                && kinds.len() <= 2
                && kinds
                    .iter()
                    .all(|kind| matches!(*kind, "plant" | "monster"))
                && (kinds.len() != 2 || kinds[0] != kinds[1]),
            "Invalid ecology population kinds"
        );
        let mut entries = Vec::new();
        if kinds.contains(&"plant") {
            let plants=db.query("SELECT resource_uid,resource_reference,x,y,z FROM planted_resources WHERE map_id=$1 AND instance_id=$2 AND stage NOT IN (0,16) LIMIT $3",&[&map_id,&instance_id,&((POPULATION_ENTITIES+1) as i64)]).await?;
            ensure!(
                plants.len() <= POPULATION_ENTITIES,
                "Ecology population exceeds entity budget"
            );
            for row in plants {
                let reference: i32 = row.get("resource_reference");
                let definition = self.resource_definition(reference as i64).await?;
                let monster = definition["monster_resource"]
                    .as_bool()
                    .ok_or_else(|| anyhow!("Missing resource species kind"))?;
                let fixed = definition
                    .get("stage_definitions")
                    .and_then(Value::as_array)
                    .into_iter()
                    .flatten()
                    .any(|stage| {
                        stage
                            .get("actions")
                            .and_then(Value::as_array)
                            .into_iter()
                            .flatten()
                            .any(|action| matches!(action["profession_id"].as_i64(), Some(73 | 75)))
                    });
                if !monster && !fixed {
                    entries.push(PopulationEntry {
                        kind: "plant",
                        identity: row.get::<_, i64>("resource_uid"),
                        family: integer_i64(&definition["family_id"])?,
                        x: row.get("x"),
                        y: row.get("y"),
                        z: row.get("z"),
                    });
                }
            }
        }
        if kinds.contains(&"monster") {
            let groups=db.query(
                "SELECT members FROM combat_groups WHERE map_id=$1 AND instance_id=$2 AND status!='defeated' AND NOT EXISTS(SELECT 1 FROM environmental_owned_groups environmental_owned WHERE (environmental_owned.map_id,environmental_owned.world_instance_id,environmental_owned.group_id)=(combat_groups.map_id,combat_groups.instance_id,combat_groups.group_id) AND environmental_owned.retired_at_ms IS NULL) AND NOT EXISTS(SELECT 1 FROM objectives_public_hunts h WHERE h.map_id=combat_groups.map_id AND combat_groups.instance_id=0 AND h.group_id=combat_groups.group_id) AND NOT EXISTS(SELECT 1 FROM developer_item_test_groups t WHERE (t.map_id,t.instance_id,t.group_id)=(combat_groups.map_id,combat_groups.instance_id,combat_groups.group_id)) LIMIT $3",
                &[&map_id,&instance_id,&((POPULATION_ENTITIES+1) as i64)],
            ).await?;
            ensure!(
                groups.len() <= POPULATION_ENTITIES,
                "Ecology population exceeds group budget"
            );
            for group in groups {
                let members: Value = group.get(0);
                for member in members
                    .as_array()
                    .ok_or_else(|| anyhow!("Invalid native group members"))?
                {
                    ensure!(
                        entries.len() < POPULATION_ENTITIES,
                        "Ecology population exceeds entity budget"
                    );
                    let reference = integer_i64(&member["ref"])?;
                    let definition = self.monster_definition(reference).await?;
                    entries.push(PopulationEntry {
                        kind: "monster",
                        identity: integer_i64(&member["id"])?,
                        family: integer_i64(&definition["family_id"])?,
                        x: integer_i32(&member["x"])?,
                        y: integer_i32(&member["y"])?,
                        z: i16::try_from(integer_i64(&member["z"])?)?,
                    });
                }
            }
        }
        let mut regions = Map::new();
        let mut unresolved = Vec::new();
        for entry in entries {
            let region = if regional {
                match self.territory_region(map_id, entry.x, entry.y).await {
                    Ok(region) => Ok(region),
                    Err(error) if error.is::<MissingLocation>() => {
                        match self.surface_region(map_id, entry.x, entry.y, entry.z).await {
                            Ok(-1) => Ok(-1),
                            Ok(_) => Err(MissingLocation::Surface.into()),
                            Err(error) => Err(error),
                        }
                    }
                    Err(error) => return Err(error),
                }
            } else {
                self.surface_region(map_id, entry.x, entry.y, entry.z).await
            };
            match region {
                Ok(-1) if exclude_unassigned => continue,
                Ok(region) if region > 0 => {
                    let counts = regions
                        .entry(region.to_string())
                        .or_insert_with(|| json!({"plant":{},"monster":{}}));
                    let family = entry.family.to_string();
                    let previous = counts[entry.kind]
                        .get(&family)
                        .and_then(Value::as_u64)
                        .unwrap_or(0);
                    counts[entry.kind][&family] = json!(previous + 1);
                }
                Ok(_) => unresolved.push(json!([entry.kind, entry.identity])),
                Err(error) if error.is::<MissingLocation>() => {
                    unresolved.push(json!([entry.kind, entry.identity]))
                }
                Err(error) => return Err(error),
            }
        }
        Ok(json!({"regions":regions,"complete":unresolved.is_empty(),"unresolved":unresolved}))
    }
}

#[derive(Debug)]
enum MissingLocation {
    Surface,
    Territory,
}
impl fmt::Display for MissingLocation {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        formatter.write_str(match self {
            Self::Surface => "Unknown native planting height",
            Self::Territory => "Unknown native map territory at position",
        })
    }
}
impl std::error::Error for MissingLocation {}

fn surface_rows_at(rows: &[Surface], x: i32, y: i32) -> Vec<Value> {
    let begin = rows.partition_point(|row| (row.x, row.y) < (x, y));
    let mut column: Vec<_> = rows[begin..]
        .iter()
        .take_while(|row| (row.x, row.y) == (x, y))
        .collect();
    // Source order, rather than height order, is observable for first-fit native
    // planting authorization. The compact search index retains that ordinal.
    column.sort_unstable_by_key(|row| row.ordinal);
    column
        .into_iter()
        .map(|row| json!({"z":row.z,"ground_id":row.ground,"region_id":row.region}))
        .collect()
}

fn haven_world_geometry() -> Result<Value> {
    const RAW: &[u8] =
        include_bytes!("../../../../wakfu_server/maps/interior-base-partition-geometry.json");
    verify_sha(
        RAW,
        "cf13fa55f2478702ed4403381d9637b13299cd18396a4d824c205dcfd229d0f2",
    )?;
    let data: Value = serde_json::from_slice(RAW)?;
    let rows = data["cells"]
        .as_array()
        .ok_or_else(|| anyhow!("Missing native Haven World geometry cells"))?;
    let mut cells = std::collections::BTreeSet::new();
    for row in rows {
        let row = row
            .as_array()
            .filter(|r| r.len() >= 4)
            .ok_or_else(|| anyhow!("Invalid Haven World geometry row"))?;
        if row[3].as_bool() == Some(false) {
            cells.insert((
                integer_i32(&row[0])?,
                integer_i32(&row[1])?,
                i16::try_from(integer_i64(&row[2])?)?,
            ));
        }
    }
    ensure!(
        rows.len() == 324 && cells.contains(&(4, -86, 0)),
        "Incomplete native Haven World base partition"
    );
    let mut edges = Vec::new();
    for &(x, y, z) in &cells {
        for (dx, dy) in [(1, 0), (-1, 0), (0, 1), (0, -1)] {
            if cells.contains(&(x + dx, y + dy, z)) {
                edges.push(json!([[x, y, z as i32], [x + dx, y + dy, z as i32]]));
            }
        }
    }
    Ok(
        json!({"map_id":2_000_000_000i32,"cells":cells.iter().map(|&(x,y,z)|json!([x,y,z as i32])).collect::<Vec<_>>(),"edges":edges,"source":"original cen.af partition(0,-5), patch0; explicit Wakemu namespace"}),
    )
}

struct PopulationEntry {
    kind: &'static str,
    identity: i64,
    family: i64,
    x: i32,
    y: i32,
    z: i16,
}

fn integer_i64(value: &Value) -> Result<i64> {
    value
        .as_i64()
        .ok_or_else(|| anyhow!("Expected signed native integer"))
}
fn integer_i32(value: &Value) -> Result<i32> {
    Ok(i32::try_from(integer_i64(value)?)?)
}

fn validate_name(name: &str) -> Result<()> {
    ensure!(
        !name.is_empty()
            && !name.contains(['\\', '\0'])
            && name.split('/').all(|part| !matches!(part, "" | "." | "..")),
        "Invalid published native catalog name"
    );
    Ok(())
}

fn validate_digest(value: &str) -> Result<()> {
    ensure!(
        value.len() == 64
            && value
                .bytes()
                .all(|byte| byte.is_ascii_digit() || (b'a'..=b'f').contains(&byte)),
        "Invalid catalog SHA256 identity"
    );
    Ok(())
}

fn verify_sha(raw: &[u8], expected: &str) -> Result<()> {
    validate_digest(expected)?;
    ensure!(
        format!("{:x}", Sha256::digest(raw)) == expected,
        "Native catalog checksum differs"
    );
    Ok(())
}

fn encoded_key(value: &Value) -> Result<String> {
    match value {
        Value::String(text) => {
            // Match Python json.dumps(..., ensure_ascii=True) for record keys.
            let utf8 = serde_json::to_string(text)?;
            let mut ascii = String::with_capacity(utf8.len());
            for ch in utf8.chars() {
                if ch <= '\u{007e}' {
                    ascii.push(ch);
                } else {
                    let mut units = [0u16; 2];
                    for unit in ch.encode_utf16(&mut units) {
                        ascii.push_str(&format!("\\u{unit:04x}"));
                    }
                }
            }
            Ok(ascii)
        }
        Value::Number(number) if number.is_i64() || number.is_u64() => Ok(number.to_string()),
        _ => bail!("Compiled record keys must be strings or integers"),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn validation_proofs_survive_byte_churn_but_entry_count_is_bounded() {
        let mut cache = Cache::new();
        cache.put("proof".into(), Cached::Validated, 0);
        cache.put(
            "large".into(),
            Cached::Bytes(vec![0; CACHE_BYTES - 4096].into()),
            CACHE_BYTES - 4096,
        );
        cache.put("other".into(), Cached::Bytes(vec![0; 8192].into()), 8192);
        assert!(matches!(cache.get("proof"), Some(Cached::Validated)));
        assert!(cache.bytes <= CACHE_BYTES);
        for index in 0..CACHE_ENTRIES + 1 {
            cache.put(format!("proof:{index}"), Cached::Validated, 0);
        }
        assert_eq!(cache.entries.len(), CACHE_ENTRIES);
        assert!(cache.get("proof").is_none());
        assert!(cache.get("proof:0").is_none());
        assert!(cache.bytes <= CACHE_BYTES);
    }

    #[test]
    fn monster_offset_index_preserves_last_source_row_and_integer_identity() {
        let raw: Arc<[u8]> = br#"{"monsters":[{"ref":2,"name":"first"},{"ref":9223372036854775807,"name":"wide"},{"ref":2,"name":"last"}]}"#.as_slice().into();
        let index = MonsterIndex::new(raw.clone()).unwrap();
        assert_eq!(index.rows.len(), 2);
        assert_eq!(index.record(2).unwrap()["name"], "last");
        assert_eq!(index.record(i64::MAX).unwrap()["name"], "wide");
        assert!(index.record(3).is_err());
        assert!(index.cost() >= raw.len());
        assert!(index.cost() <= MONSTER_INDEX_BYTES);
    }

    #[test]
    fn monster_offset_index_preserves_reverse_scan_malformed_header_failures() {
        let raw: Arc<[u8]> =
            br#"{"monsters":[{"ref":1},{"ref":true},{"ref":2}]}"#.as_slice().into();
        let index = MonsterIndex::new(raw).unwrap();
        assert_eq!(index.record(2).unwrap()["ref"], 2);
        assert!(index
            .record(1)
            .unwrap_err()
            .to_string()
            .contains("Invalid native monster reference"));
        assert!(index
            .record(3)
            .unwrap_err()
            .to_string()
            .contains("Invalid native monster reference"));
        assert!(MonsterIndex::new(br#"{"monsters":[{"ref":1},]}"#.as_slice().into()).is_err());
    }

    #[test]
    fn cache_budget_and_replacement_are_bounded() {
        let mut cache = Cache::new();
        for i in 0..8 {
            cache.put(
                format!("entry-{i}"),
                Cached::Bytes(vec![0; 2 * 1024 * 1024].into()),
                2 * 1024 * 1024,
            );
        }
        assert!(cache.bytes <= CACHE_BYTES);
        assert!(cache.entries.len() < 8);
        cache.put(
            "oversized".into(),
            Cached::Bytes(vec![0; CACHE_BYTES + 1].into()),
            CACHE_BYTES + 1,
        );
        assert!(!cache.entries.contains_key("oversized"));
        cache.put("small".into(), Cached::Bytes(Arc::from([1u8, 2, 3])), 3);
        cache.put("small".into(), Cached::Bytes(Arc::from([4u8])), 1);
        if let Some(Cached::Bytes(bytes)) = cache.get("small") {
            assert_eq!(&*bytes, &[4]);
        } else {
            panic!("missing cache entry");
        }
        assert!(cache.bytes <= CACHE_BYTES);
    }

    #[test]
    fn native_record_keys_keep_exact_i64_and_python_unicode_encoding() {
        assert_eq!(
            encoded_key(&json!(-9223372036854775808i64)).unwrap(),
            "-9223372036854775808"
        );
        assert_eq!(
            encoded_key(&json!("é😀")).unwrap(),
            "\"\\u00e9\\ud83d\\ude00\""
        );
        assert_eq!(encoded_key(&json!("\u{007f}")).unwrap(), "\"\\u007f\"");
        assert!(encoded_key(&json!(1.5)).is_err());
        assert!(encoded_key(&json!(true)).is_err());
    }

    #[test]
    fn territory_floor_division_matches_negative_native_coordinates() {
        assert_eq!((-1i32).div_euclid(18), -1);
        assert_eq!((-18i32).div_euclid(18), -1);
        assert_eq!((-19i32).div_euclid(18), -2);
    }

    #[test]
    fn surface_columns_preserve_native_order_instead_of_sorted_height() {
        let rows = [
            Surface {
                x: 1,
                y: 2,
                z: -1,
                ground: 5,
                region: 8,
                ordinal: 2,
            },
            Surface {
                x: 1,
                y: 2,
                z: 0,
                ground: 6,
                region: 9,
                ordinal: 1,
            },
            Surface {
                x: 1,
                y: 2,
                z: 4,
                ground: 7,
                region: 10,
                ordinal: 0,
            },
            Surface {
                x: 3,
                y: 4,
                z: 0,
                ground: 8,
                region: 11,
                ordinal: 3,
            },
        ];
        let column = surface_rows_at(&rows, 1, 2);
        assert_eq!(
            column
                .iter()
                .map(|row| row["z"].as_i64().unwrap())
                .collect::<Vec<_>>(),
            vec![4, 0, -1]
        );
        assert!(surface_rows_at(&rows, 0, 0).is_empty());
        assert!(surface_rows_at(&rows, 5, 5).is_empty());
    }

    #[test]
    fn haven_world_geometry_uses_the_verified_original_partition() {
        let geometry = haven_world_geometry().unwrap();
        assert_eq!(geometry["map_id"], 2_000_000_000i32);
        assert!(geometry["cells"]
            .as_array()
            .unwrap()
            .contains(&json!([4, -86, 0])));
        assert!(!geometry["edges"].as_array().unwrap().is_empty());
    }

    #[test]
    fn catalog_identity_and_paths_fail_closed() {
        assert!(validate_name("planting-maps/1134.json").is_ok());
        for bad in ["../secret", "/absolute", "a//b", "a\\b", ""] {
            assert!(validate_name(bad).is_err());
        }
        assert!(verify_sha(b"different", &format!("{:x}", Sha256::digest(b"original"))).is_err());
        assert!(validate_digest(&"G".repeat(64)).is_err());
    }
}
