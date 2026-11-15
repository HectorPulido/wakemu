//! Compact authoritative position state and durable-I/O plans.
//!
//! The host performs SQL/Redis I/O under its account barrier. Native prepare
//! operations reserve immutable candidates; commit operations adopt those
//! candidates without callbacks, storage access or another lease decision.

use serde::Serialize;
use serde_json::{json, Value};
use std::collections::{BTreeMap, BTreeSet};

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct PositionError {
    pub kind: &'static str,
    pub message: String,
}

impl PositionError {
    fn new(kind: &'static str, message: &str) -> Self {
        Self {
            kind,
            message: message.to_owned(),
        }
    }
    fn value(message: &str) -> Self {
        Self::new("value", message)
    }
    fn journal(message: &str) -> Self {
        Self::new("journal", message)
    }
    fn busy() -> Self {
        Self::new("busy", "Position owner is busy; retry checkpoint")
    }
}

type Result<T> = std::result::Result<T, PositionError>;

#[derive(Clone, Debug, PartialEq, Eq, PartialOrd, Ord, Serialize)]
struct Key(i64, String, i64);

impl Key {
    fn parse(value: &Value) -> Result<Self> {
        let a = value
            .as_array()
            .filter(|a| a.len() == 3)
            .ok_or_else(|| PositionError::journal("Invalid journal owner identity"))?;
        let account = a[0].as_i64().filter(|n| *n > 0);
        let generation = a[1]
            .as_str()
            .filter(|s| !s.is_empty() && s.chars().count() <= 512);
        let character = a[2].as_i64().filter(|n| *n > 0);
        match (account, generation, character) {
            (Some(account), Some(generation), Some(character)) => {
                Ok(Self(account, generation.to_owned(), character))
            }
            _ => Err(PositionError::journal("Invalid journal owner identity")),
        }
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize)]
struct Position {
    map_id: i32,
    instance_id: i64,
    x: i32,
    y: i32,
    z: i16,
    direction: u8,
}

impl Position {
    fn parse(value: &Value) -> Result<Self> {
        const KEYS: [&str; 6] = ["map_id", "instance_id", "x", "y", "z", "direction"];
        let object = value
            .as_object()
            .filter(|o| o.len() == 6 && KEYS.iter().all(|k| o.contains_key(*k)))
            .ok_or_else(|| PositionError::journal("Invalid journal position fields"))?;
        let integer = |name: &str| {
            object[name]
                .as_i64()
                .ok_or_else(|| PositionError::journal("Invalid journal position range"))
        };
        let map_id = i32::try_from(integer("map_id")?)
            .map_err(|_| PositionError::journal("Invalid journal position range"))?;
        let instance_id = integer("instance_id")?;
        let x = i32::try_from(integer("x")?)
            .map_err(|_| PositionError::journal("Invalid journal position range"))?;
        let y = i32::try_from(integer("y")?)
            .map_err(|_| PositionError::journal("Invalid journal position range"))?;
        let z = i16::try_from(integer("z")?)
            .map_err(|_| PositionError::journal("Invalid journal position range"))?;
        let direction = object["direction"]
            .as_u64()
            .filter(|n| *n <= 7)
            .ok_or_else(|| PositionError::journal("Invalid journal direction"))?
            as u8;
        Ok(Self {
            map_id,
            instance_id,
            x,
            y,
            z,
            direction,
        })
    }

    fn moved(self, start: &Value, end: &Value) -> Result<Self> {
        if start["x"].as_i64() != Some(i64::from(self.x))
            || start["y"].as_i64() != Some(i64::from(self.y))
            || start["z"].as_i64() != Some(i64::from(self.z))
        {
            return Err(PositionError::value("Position origin is desynchronized"));
        }
        let error = || PositionError::value("Invalid buffered position coordinate");
        let x = i32::try_from(end["x"].as_i64().ok_or_else(error)?).map_err(|_| error())?;
        let y = i32::try_from(end["y"].as_i64().ok_or_else(error)?).map_err(|_| error())?;
        let z = i16::try_from(end["z"].as_i64().ok_or_else(error)?).map_err(|_| error())?;
        let direction = match end.get("direction") {
            None => self.direction,
            Some(value) => value
                .as_u64()
                .filter(|n| *n <= 7)
                .ok_or_else(|| PositionError::value("Invalid buffered position direction"))?
                as u8,
        };
        Ok(Self {
            x,
            y,
            z,
            direction,
            ..self
        })
    }

    fn same_scene(self, other: Self) -> bool {
        self.map_id == other.map_id && self.instance_id == other.instance_id
    }

    fn from_row(value: &Value) -> Result<Self> {
        let fields = ["map_id", "instance_id", "x", "y", "z", "direction"];
        Self::parse(&Value::Object(
            fields
                .iter()
                .map(|name| (name.to_string(), value[*name].clone()))
                .collect(),
        ))
    }
}

#[derive(Clone, Debug)]
struct Entry {
    current: Position,
    persisted: Position,
    revision: u64,
    dirty: bool,
}

impl Entry {
    fn dirty(&self) -> bool {
        self.dirty
    }
}

#[derive(Clone, Debug)]
enum Prepared {
    Move {
        key: Key,
        entry: Entry,
    },
    Stage {
        key: Key,
        entry: Entry,
        original_revision: u64,
    },
    Checkpoint {
        writes: Vec<(Key, Entry)>,
        stale: Vec<Key>,
    },
    Release {
        key: Key,
    },
}

impl Prepared {
    fn keys(&self) -> Vec<Key> {
        match self {
            Self::Move { key, .. } | Self::Stage { key, .. } | Self::Release { key } => {
                vec![key.clone()]
            }
            Self::Checkpoint { writes, stale } => writes
                .iter()
                .map(|(key, _)| key.clone())
                .chain(stale.iter().cloned())
                .collect(),
        }
    }
}

#[derive(Default)]
pub struct PositionEngine {
    entries: BTreeMap<Key, Entry>,
    mirrors: BTreeMap<Key, String>,
    pending_acks: BTreeMap<Key, String>,
    evictions: Vec<Key>,
    reserved: BTreeMap<Key, String>,
    prepared: BTreeMap<String, Prepared>,
    sequence: u64,
    cursor: Option<i64>,
}

fn scope_matches(key: &Key, args: &Value) -> bool {
    let scope = args.get("scope").unwrap_or(args);
    [
        ("account_id", json!(key.0)),
        ("generation", json!(key.1)),
        ("character_id", json!(key.2)),
    ]
    .iter()
    .all(|(name, expected)| {
        scope
            .get(*name)
            .is_none_or(|v| v.is_null() || v == expected)
    })
}

fn required_bool(args: &Value, name: &str) -> Result<bool> {
    args[name]
        .as_bool()
        .ok_or_else(|| PositionError::value("Invalid position ownership fact"))
}

fn token(args: &Value) -> Result<&str> {
    args["token"]
        .as_str()
        .ok_or_else(|| PositionError::value("Invalid native position token"))
}

fn ascii_json(value: &Value) -> String {
    fn string(value: &str) -> String {
        let encoded = serde_json::to_string(value).expect("JSON string serialization");
        let mut out = String::with_capacity(encoded.len());
        for c in encoded.chars() {
            if (c as u32) < 127 {
                out.push(c);
            } else {
                let mut units = [0_u16; 2];
                for n in c.encode_utf16(&mut units) {
                    out.push_str(&format!("\\u{n:04x}"));
                }
            }
        }
        out
    }
    match value {
        Value::Null => "null".to_owned(),
        Value::Bool(v) => v.to_string(),
        Value::Number(v) => v.to_string(),
        Value::String(v) => string(v),
        Value::Array(values) => format!(
            "[{}]",
            values.iter().map(ascii_json).collect::<Vec<_>>().join(",")
        ),
        Value::Object(values) => {
            let mut entries = values.iter().collect::<Vec<_>>();
            entries.sort_by(|a, b| a.0.cmp(b.0));
            format!(
                "{{{}}}",
                entries
                    .into_iter()
                    .map(|(k, v)| format!("{}:{}", string(k), ascii_json(v)))
                    .collect::<Vec<_>>()
                    .join(",")
            )
        }
    }
}

fn record_validate(field: &str, encoded: &str) -> Result<(Key, Value)> {
    let value: Value = serde_json::from_str(encoded)
        .map_err(|_| PositionError::journal("Invalid Redis position record"))?;
    let key = Key::parse(&value["owner"])?;
    if value["version"].as_i64() != Some(2)
        || field != ascii_json(&json!(key))
        || value["revision"]
            .as_str()
            .is_none_or(|s| s.chars().count() != 32)
    {
        return Err(PositionError::journal(
            "Invalid Redis position record identity",
        ));
    }
    let old = Position::parse(&value["baseline"])?;
    let new = Position::parse(&value["current"])?;
    if !old.same_scene(new) {
        return Err(PositionError::journal(
            "Invalid Redis position map transition",
        ));
    }
    Ok((key, value))
}

impl PositionEngine {
    pub fn new() -> Self {
        Self::default()
    }

    /// Scopes touched by a request, available before mutating a prepared token.
    pub fn request_scopes(&self, _op: &str, args: &Value) -> Vec<(i32, i64)> {
        let mut scopes = BTreeSet::new();
        for key in self.request_key_values(args) {
            if let Some(entry) = self.entries.get(&key) {
                scopes.insert((entry.current.map_id, entry.current.instance_id));
            }
        }
        for name in ["current", "persisted", "source", "destination", "saved"] {
            if let (Some(map), Some(instance)) = (
                args[name]["map_id"]
                    .as_i64()
                    .and_then(|v| i32::try_from(v).ok()),
                args[name]["instance_id"].as_i64(),
            ) {
                scopes.insert((map, instance));
            }
        }
        scopes.into_iter().collect()
    }

    pub fn request_keys(&self, _op: &str, args: &Value) -> Vec<(i64, String, i64)> {
        self.request_key_values(args)
            .into_iter()
            .map(|k| (k.0, k.1, k.2))
            .collect()
    }

    fn request_key_values(&self, args: &Value) -> Vec<Key> {
        if let Some(id) = args["token"].as_str() {
            if let Some(prepared) = self.prepared.get(id) {
                return prepared.keys();
            }
        }
        if let Ok(key) = Key::parse(&args["key"]) {
            return vec![key];
        }
        self.entries
            .keys()
            .filter(|key| scope_matches(key, args))
            .cloned()
            .collect()
    }

    fn dto(&self, key: &Key, entry: &Entry) -> Value {
        json!({"key":key,"current":entry.current,"persisted":entry.persisted,"dirty":entry.dirty(),"revision":entry.revision,
            "mirror":self.mirrors.get(key),"pending_ack":self.pending_acks.get(key)})
    }

    fn next_revision(entry: &Entry) -> Result<u64> {
        entry
            .revision
            .checked_add(1)
            .ok_or_else(|| PositionError::value("Position revision exhausted"))
    }

    fn available(&self, key: &Key) -> Result<()> {
        if self.reserved.contains_key(key) {
            Err(PositionError::busy())
        } else {
            Ok(())
        }
    }

    fn reserve(&mut self, prepared: Prepared) -> Result<String> {
        let keys = prepared.keys();
        for key in &keys {
            self.available(key)?;
        }
        self.sequence = self
            .sequence
            .checked_add(1)
            .ok_or_else(|| PositionError::value("Position token sequence exhausted"))?;
        let token = format!("position-{}", self.sequence);
        for key in keys {
            self.reserved.insert(key, token.clone());
        }
        self.prepared.insert(token.clone(), prepared);
        Ok(token)
    }

    fn take(&mut self, token: &str) -> Result<Prepared> {
        let prepared = self
            .prepared
            .remove(token)
            .ok_or_else(|| PositionError::value("Invalid or consumed native position token"))?;
        for key in prepared.keys() {
            self.reserved.remove(&key);
        }
        Ok(prepared)
    }

    fn accounts(&self, work_only: bool) -> Vec<i64> {
        let mut accounts = self
            .entries
            .iter()
            .filter(|(_, e)| !work_only || e.dirty())
            .map(|(k, _)| k.0)
            .collect::<BTreeSet<_>>();
        accounts.extend(
            self.mirrors
                .keys()
                .chain(self.pending_acks.keys())
                .map(|k| k.0),
        );
        accounts.into_iter().collect()
    }

    pub fn call(&mut self, op: &str, args: &Value) -> Result<Value> {
        let op = op.strip_prefix("positions.").unwrap_or(op);
        match op {
            "identity" => Ok(json!(ascii_json(&json!(Key::parse(&args["key"])?)))),
            "validate_position" => Ok(json!(Position::parse(&args["value"])?)),
            "encode_record" => {
                let key = Key::parse(&args["key"])?;
                let entry = &args["entry"];
                let old = Position::parse(&entry["persisted"])?;
                let new = Position::parse(&entry["current"])?;
                if !old.same_scene(new) {
                    return Err(PositionError::journal(
                        "Map transitions require a flushed position barrier",
                    ));
                }
                let revision = args["revision"]
                    .as_str()
                    .filter(|s| s.chars().count() == 32)
                    .ok_or_else(|| {
                        PositionError::journal("Invalid Redis position record identity")
                    })?;
                let value = json!({"version":2,"owner":key,"revision":revision,"baseline":old,"current":new});
                Ok(json!({"field":ascii_json(&json!(key)),"encoded":ascii_json(&value)}))
            }
            "validate_record" => {
                let field = args["field"].as_str().ok_or_else(|| {
                    PositionError::journal("Invalid Redis position record identity")
                })?;
                let encoded = args["encoded"]
                    .as_str()
                    .ok_or_else(|| PositionError::journal("Invalid Redis position record"))?;
                let (key, value) = record_validate(field, encoded)?;
                Ok(json!({"key":key,"value":value}))
            }
            "record_status" => {
                let key = Key::parse(&args["key"])?;
                let value = &args["value"];
                let current = Position::parse(&value["current"])?;
                let baseline = Position::parse(&value["baseline"])?;
                let saved = &args["saved"];
                let status =
                    if args["selected_character_id"].as_i64() != Some(key.2) || saved.is_null() {
                        "stale"
                    } else if Position::from_row(saved)? == current {
                        "already_committed"
                    } else if Position::from_row(saved)? == baseline {
                        "recoverable"
                    } else {
                        "conflict"
                    };
                Ok(json!(status))
            }
            "attach" => {
                let key = Key::parse(&args["key"])?;
                self.available(&key)?;
                if args["selected_character_id"].as_i64() != Some(key.2) {
                    if args["skip_stale_selection"].as_bool() == Some(true) {
                        return Ok(Value::Null);
                    }
                    return Err(PositionError::value("Invalid buffered position session"));
                }
                let persisted = Position::parse(&args["persisted"])?;
                let current = Position::parse(&args["current"])?;
                if current != persisted {
                    return Err(PositionError::new(
                        "baseline",
                        "Buffered position baseline does not match storage",
                    ));
                }
                if self.entries.get(&key).is_some_and(Entry::dirty) {
                    return Err(PositionError::value(
                        "Flush buffered position before attaching again",
                    ));
                }
                let revision = self
                    .entries
                    .get(&key)
                    .map(Self::next_revision)
                    .transpose()?
                    .unwrap_or(1);
                let entry = Entry {
                    current,
                    persisted,
                    revision,
                    dirty: false,
                };
                let dto = self.dto(&key, &entry);
                self.entries.insert(key, entry);
                Ok(dto)
            }
            "entry" | "merge" => {
                let key = Key::parse(&args["key"])?;
                if op == "merge"
                    && (!required_bool(args, "lease_active")? || !self.entries.contains_key(&key))
                {
                    return Err(PositionError::value("Stale buffered position session"));
                }
                Ok(self
                    .entries
                    .get(&key)
                    .map(|e| self.dto(&key, e))
                    .unwrap_or(Value::Null))
            }
            "entries" => Ok(json!(self
                .entries
                .iter()
                .filter(|(k, e)| scope_matches(k, args)
                    && (args["dirty_only"].as_bool() != Some(true) || e.dirty()))
                .map(|(k, e)| json!({"key":k,"entry":self.dto(k,e)}))
                .collect::<Vec<_>>())),
            "accounts" => {
                let scope = args.get("scope").unwrap_or(args);
                Ok(json!(self
                    .accounts(args["work_only"].as_bool() == Some(true))
                    .into_iter()
                    .filter(|account| scope
                        .get("account_id")
                        .is_none_or(|v| v.is_null() || v.as_i64() == Some(*account)))
                    .collect::<Vec<_>>()))
            }
            "has_dirty" => Ok(json!(self
                .entries
                .iter()
                .any(|(k, e)| e.dirty() && scope_matches(k, args)))),
            "prepare_move" | "stage_prepare" => {
                let key = Key::parse(&args["key"])?;
                self.available(&key)?;
                let entry = self
                    .entries
                    .get(&key)
                    .ok_or_else(|| PositionError::value("Stale buffered position session"))?
                    .clone();
                if !required_bool(args, "lease_active")? {
                    return Err(PositionError::value("Stale buffered position session"));
                }
                let moved = entry.current.moved(&args["start"], &args["end"])?;
                let revision = Self::next_revision(&entry)?;
                if op == "stage_prepare" {
                    if entry.dirty()
                        || self.mirrors.contains_key(&key)
                        || self.pending_acks.contains_key(&key)
                    {
                        return Err(PositionError::new(
                            "busy",
                            "Checkpoint movement before a durable choice",
                        ));
                    }
                    let next = Entry {
                        current: moved,
                        persisted: moved,
                        revision,
                        dirty: false,
                    };
                    let token = self.reserve(Prepared::Stage {
                        key,
                        entry: next,
                        original_revision: entry.revision,
                    })?;
                    Ok(
                        json!({"token":token,"current":entry.current,"persisted":entry.persisted,"result":moved,"dirty":false,"revision":entry.revision}),
                    )
                } else {
                    let next = Entry {
                        current: moved,
                        persisted: entry.persisted,
                        revision,
                        dirty: moved != entry.persisted,
                    };
                    let expected = self.mirrors.get(&key).cloned();
                    let dirty = next.dirty();
                    let token = self.reserve(Prepared::Move { key, entry: next })?;
                    Ok(
                        json!({"token":token,"current":moved,"persisted":entry.persisted,"dirty":dirty,"revision":revision,"expected":expected}),
                    )
                }
            }
            "commit_move" => {
                let id = token(args)?;
                if !matches!(self.prepared.get(id), Some(Prepared::Move { .. })) {
                    return Err(PositionError::value("Invalid native movement token"));
                }
                let encoded = match args.get("encoded") {
                    None | Some(Value::Null) => None,
                    Some(Value::String(s)) => Some(s.clone()),
                    _ => return Err(PositionError::journal("Invalid Redis position record")),
                };
                let Prepared::Move { key, entry } = self.take(id)? else {
                    unreachable!()
                };
                if let Some(encoded) = encoded {
                    self.mirrors.insert(key.clone(), encoded.clone());
                    self.pending_acks.remove(&key);
                    if !entry.dirty() {
                        self.pending_acks.insert(key.clone(), encoded);
                    }
                }
                let dto = self.dto(&key, &entry);
                self.entries.insert(key, entry);
                Ok(dto)
            }
            "stage_validate" => {
                let id = token(args)?;
                let Some(Prepared::Stage {
                    key,
                    original_revision,
                    ..
                }) = self.prepared.get(id)
                else {
                    return Err(PositionError::value("Invalid native staged movement token"));
                };
                if !required_bool(args, "lease_active")?
                    || self
                        .entries
                        .get(key)
                        .is_none_or(|e| e.revision != *original_revision || e.dirty())
                    || self.mirrors.contains_key(key)
                    || self.pending_acks.contains_key(key)
                {
                    return Err(if args["phase"].as_str() == Some("persist") {
                        PositionError::value("Buffered movement lease changed before persistence")
                    } else {
                        PositionError::new("busy", "Durable movement lost its clean owner")
                    });
                }
                Ok(json!(true))
            }
            "stage_commit" => {
                let id = token(args)?;
                if !matches!(self.prepared.get(id), Some(Prepared::Stage { .. })) {
                    return Err(PositionError::value("Invalid native staged movement token"));
                }
                let Prepared::Stage { key, entry, .. } = self.take(id)? else {
                    unreachable!()
                };
                let dto = self.dto(&key, &entry);
                self.entries.insert(key, entry);
                Ok(dto)
            }
            "abort" => {
                self.take(token(args)?)?;
                Ok(Value::Null)
            }
            "prepare_checkpoint" => {
                let selected = self
                    .entries
                    .iter()
                    .filter(|(k, e)| e.dirty() && scope_matches(k, args))
                    .map(|(k, e)| (k.clone(), e.clone()))
                    .collect::<Vec<_>>();
                let leases = args["leases"].as_array().ok_or_else(|| {
                    PositionError::value("Missing position checkpoint lease facts")
                })?;
                let mut writes = Vec::new();
                let mut stale = Vec::new();
                for (key, mut entry) in selected {
                    self.available(&key)?;
                    let fact = leases
                        .iter()
                        .find(|v| v.get("key") == Some(&json!(key)))
                        .ok_or_else(|| {
                            PositionError::value("Missing position checkpoint lease fact")
                        })?;
                    if fact.get("selected_character_id").is_none() {
                        return Err(PositionError::value(
                            "Missing position checkpoint selected-owner fact",
                        ));
                    }
                    if fact["selected_character_id"].as_i64() != Some(key.2) {
                        stale.push(key);
                        continue;
                    }
                    if !required_bool(fact, "lease_active")? {
                        return Err(PositionError::value(
                            "Live lease unavailable for buffered position",
                        ));
                    }
                    entry.revision = Self::next_revision(&entry)?;
                    writes.push((key, entry));
                }
                let dtos = writes
                    .iter()
                    .map(|(k, e)| self.dto(k, e))
                    .collect::<Vec<_>>();
                let stale_keys = json!(stale);
                let token = self.reserve(Prepared::Checkpoint { writes, stale })?;
                Ok(json!({"token":token,"writes":dtos,"stale_keys":stale_keys}))
            }
            "commit_checkpoint" => {
                let id = token(args)?;
                if !matches!(self.prepared.get(id), Some(Prepared::Checkpoint { .. })) {
                    return Err(PositionError::value("Invalid native checkpoint token"));
                }
                let Prepared::Checkpoint { writes, stale } = self.take(id)? else {
                    unreachable!()
                };
                let count = writes.len();
                for key in stale {
                    self.entries.remove(&key);
                    self.evictions.push(key);
                }
                for (key, mut entry) in writes {
                    entry.persisted = entry.current;
                    entry.dirty = false;
                    self.entries.insert(key, entry);
                }
                Ok(json!(count))
            }
            "pending_acks" => {
                let accounts = args["accounts"]
                    .as_array()
                    .ok_or_else(|| PositionError::value("Invalid position account set"))?
                    .iter()
                    .map(|v| {
                        v.as_i64()
                            .ok_or_else(|| PositionError::value("Invalid position account set"))
                    })
                    .collect::<Result<BTreeSet<_>>>()?;
                if args["mark_clean_mirrors"].as_bool() == Some(true) {
                    for (key, encoded) in &self.mirrors {
                        if accounts.contains(&key.0)
                            && self.entries.get(key).is_none_or(|e| !e.dirty())
                        {
                            self.pending_acks.insert(key.clone(), encoded.clone());
                        }
                    }
                }
                Ok(json!(self
                    .pending_acks
                    .iter()
                    .filter(|(k, _)| accounts.contains(&k.0))
                    .map(|(k, v)| json!({"key":k,"encoded":v}))
                    .collect::<Vec<_>>()))
            }
            "ack_complete" => {
                let key = Key::parse(&args["key"])?;
                let encoded = args["encoded"]
                    .as_str()
                    .ok_or_else(|| PositionError::journal("Invalid Redis position record"))?;
                if self.pending_acks.get(&key).is_some_and(|v| v == encoded) {
                    self.pending_acks.remove(&key);
                }
                if self.mirrors.get(&key).is_some_and(|v| v == encoded) {
                    self.mirrors.remove(&key);
                }
                Ok(Value::Null)
            }
            "journal_state" => Ok(json!({
                "mirrors":self.mirrors.iter().map(|(key,encoded)|json!({"key":key,"encoded":encoded})).collect::<Vec<_>>(),
                "pending_acks":self.pending_acks.iter().map(|(key,encoded)|json!({"key":key,"encoded":encoded})).collect::<Vec<_>>()
            })),
            "release_prepare" | "transition_prepare" => {
                let key = Key::parse(&args["key"])?;
                self.available(&key)?;
                if op == "transition_prepare" {
                    let destination = &args["destination"];
                    if args["saved"].is_null()
                        || ["map_id", "instance_id", "x", "y", "z"].iter().any(|k| {
                            args["saved"][*k] != destination[*k] || destination.get(*k).is_none()
                        })
                    {
                        return Err(PositionError::value(
                            "Buffered transition has no matching committed destination",
                        ));
                    }
                    if let Some(entry) = self.entries.get(&key) {
                        if entry.current != Position::parse(&args["source"])? {
                            return Err(PositionError::value(
                                "Buffered source changed after committed transition",
                            ));
                        }
                    }
                } else {
                    let discard = args["discard_stale"].as_bool() == Some(true);
                    if self.entries.get(&key).is_some_and(Entry::dirty) && !discard {
                        return Err(PositionError::value("Flush position before release"));
                    }
                    if discard && required_bool(args, "lease_active")? {
                        return Err(PositionError::value(
                            "Cannot discard a live authoritative position",
                        ));
                    }
                }
                let encoded = self.mirrors.get(&key).cloned();
                let token = self.reserve(Prepared::Release { key: key.clone() })?;
                if op == "transition_prepare" {
                    // Destination SQL is already durable. Failure to ACK Redis
                    // must never make the superseded source flushable again.
                    if let Some(entry) = self.entries.get_mut(&key) {
                        entry.dirty = false;
                    }
                    if let Some(raw) = &encoded {
                        self.pending_acks.insert(key.clone(), raw.clone());
                    }
                }
                Ok(json!({"token":token,"key":key,"encoded":encoded}))
            }
            "release_commit" => {
                let id = token(args)?;
                if !matches!(self.prepared.get(id), Some(Prepared::Release { .. })) {
                    return Err(PositionError::value("Invalid native release token"));
                }
                let Prepared::Release { key } = self.take(id)? else {
                    unreachable!()
                };
                self.entries.remove(&key);
                self.mirrors.remove(&key);
                self.pending_acks.remove(&key);
                Ok(Value::Null)
            }
            "evictions" => {
                if args["drain"].as_bool() == Some(false) {
                    Ok(json!(self.evictions))
                } else {
                    Ok(json!(std::mem::take(&mut self.evictions)))
                }
            }
            "cursor" => Ok(json!(self.cursor)),
            "background_accounts" => {
                let accounts = self.accounts(true);
                let ordered = match self.cursor {
                    None => accounts,
                    Some(cursor) => accounts
                        .iter()
                        .filter(|a| **a > cursor)
                        .chain(accounts.iter().filter(|a| **a <= cursor))
                        .copied()
                        .collect(),
                };
                Ok(json!(ordered))
            }
            "background_plan" => {
                let max_accounts = args["max_accounts"]
                    .as_u64()
                    .and_then(|n| usize::try_from(n).ok())
                    .filter(|n| *n > 0)
                    .ok_or_else(|| {
                        PositionError::value("Invalid background position checkpoint budget")
                    })?;
                let max_seconds = args["max_seconds"]
                    .as_f64()
                    .filter(|v| v.is_finite() && *v > 0.0)
                    .ok_or_else(|| {
                        PositionError::value("Invalid background position checkpoint budget")
                    })?;
                let accounts = self.accounts(true);
                let ordered = match self.cursor {
                    None => accounts,
                    Some(cursor) => accounts
                        .iter()
                        .filter(|a| **a > cursor)
                        .chain(accounts.iter().filter(|a| **a <= cursor))
                        .copied()
                        .collect(),
                };
                Ok(
                    json!({"accounts":ordered.into_iter().take(max_accounts).collect::<Vec<_>>(),"max_accounts":max_accounts,"max_seconds":max_seconds}),
                )
            }
            "cursor_advance" => {
                self.cursor =
                    Some(args["account_id"].as_i64().ok_or_else(|| {
                        PositionError::value("Invalid position checkpoint cursor")
                    })?);
                Ok(Value::Null)
            }
            _ => Err(PositionError::value("Unknown native positions operation")),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn pos(x: i64) -> Value {
        json!({"map_id":527,"instance_id":0,"x":x,"y":0,"z":0,"direction":0})
    }
    fn key() -> Value {
        json!([1, "lease", 10])
    }
    fn attached() -> PositionEngine {
        let mut engine = PositionEngine::new();
        engine.call("attach",&json!({"key":key(),"selected_character_id":10,"current":pos(0),"persisted":pos(0)})).unwrap();
        engine
    }
    fn prepare_move(engine: &mut PositionEngine, x: i64) -> Value {
        engine
            .call(
                "prepare_move",
                &json!({"key":key(),"start":pos(0),"end":pos(x),"lease_active":true}),
            )
            .unwrap()
    }

    #[test]
    fn redis_failure_aborts_without_publishing_candidate_and_preserves_old_revision() {
        let mut engine = attached();
        let before = engine.call("entry", &json!({"key":key()})).unwrap();
        let pending = prepare_move(&mut engine, 5);
        assert_eq!(engine.call("entry", &json!({"key":key()})).unwrap(), before);
        assert!(prepare_move_result(&mut engine, 7).is_err());
        engine.call("abort", &pending).unwrap();
        assert_eq!(engine.call("entry", &json!({"key":key()})).unwrap(), before);
    }
    fn prepare_move_result(engine: &mut PositionEngine, x: i64) -> Result<Value> {
        engine.call(
            "prepare_move",
            &json!({"key":key(),"start":pos(0),"end":pos(x),"lease_active":true}),
        )
    }

    #[test]
    fn invalid_coordinates_and_stale_lease_never_reserve_or_mutate() {
        let mut engine = attached();
        for end in [
            json!({"x":true,"y":0,"z":0}),
            json!({"x":2147483648_i64,"y":0,"z":0}),
            json!({"x":1,"y":0,"z":32768}),
            json!({"x":1,"y":0,"z":0,"direction":8}),
        ] {
            assert!(engine
                .call(
                    "prepare_move",
                    &json!({"key":key(),"start":pos(0),"end":end,"lease_active":true})
                )
                .is_err());
        }
        assert!(engine
            .call(
                "prepare_move",
                &json!({"key":key(),"start":pos(0),"end":pos(1),"lease_active":false})
            )
            .is_err());
        assert_eq!(
            engine.call("entry", &json!({"key":key()})).unwrap()["current"],
            pos(0)
        );
    }

    #[test]
    fn returning_to_baseline_keeps_exact_pending_ack_until_matching_completion() {
        let mut engine = attached();
        let first = prepare_move(&mut engine, 5);
        engine
            .call(
                "commit_move",
                &json!({"token":first["token"],"encoded":"first"}),
            )
            .unwrap();
        let back = engine
            .call(
                "prepare_move",
                &json!({"key":key(),"start":pos(5),"end":pos(0),"lease_active":true}),
            )
            .unwrap();
        engine
            .call(
                "commit_move",
                &json!({"token":back["token"],"encoded":"second"}),
            )
            .unwrap();
        engine
            .call("ack_complete", &json!({"key":key(),"encoded":"first"}))
            .unwrap();
        let snapshot = engine.call("entry", &json!({"key":key()})).unwrap();
        assert_eq!(snapshot["dirty"], false);
        assert_eq!(snapshot["pending_ack"], "second");
        engine
            .call("ack_complete", &json!({"key":key(),"encoded":"second"}))
            .unwrap();
        assert!(engine
            .call("pending_acks", &json!({"accounts":[1]}))
            .unwrap()
            .as_array()
            .unwrap()
            .is_empty());
    }

    #[test]
    fn failed_checkpoint_preserves_dirty_state_and_committed_checkpoint_retains_ack_work() {
        let mut engine = attached();
        let m = prepare_move(&mut engine, 4);
        engine
            .call(
                "commit_move",
                &json!({"token":m["token"],"encoded":"journal"}),
            )
            .unwrap();
        let request = json!({"account_id":1,"leases":[{"key":key(),"selected_character_id":10,"lease_active":true}]});
        let plan = engine.call("prepare_checkpoint", &request).unwrap();
        engine.call("abort", &plan).unwrap();
        assert_eq!(
            engine.call("entry", &json!({"key":key()})).unwrap()["dirty"],
            true
        );
        let plan = engine.call("prepare_checkpoint", &request).unwrap();
        assert_eq!(engine.call("commit_checkpoint", &plan).unwrap(), 1);
        let pending = engine
            .call(
                "pending_acks",
                &json!({"accounts":[1],"mark_clean_mirrors":true}),
            )
            .unwrap();
        assert_eq!(pending[0]["encoded"], "journal");
        assert_eq!(engine.call("has_dirty", &json!({})).unwrap(), false);
    }

    #[test]
    fn stale_selected_character_is_evicted_only_after_checkpoint_commit() {
        let mut engine = attached();
        let m = prepare_move(&mut engine, 3);
        engine.call("commit_move", &m).unwrap();
        let plan = engine
            .call(
                "prepare_checkpoint",
                &json!({"leases":[{"key":key(),"selected_character_id":11,"lease_active":false}]}),
            )
            .unwrap();
        assert!(!engine
            .call("entry", &json!({"key":key()}))
            .unwrap()
            .is_null());
        engine.call("commit_checkpoint", &plan).unwrap();
        assert!(engine
            .call("entry", &json!({"key":key()}))
            .unwrap()
            .is_null());
        assert_eq!(
            engine.call("evictions", &json!({})).unwrap(),
            json!([key()])
        );
        assert_eq!(engine.call("evictions", &json!({})).unwrap(), json!([]));
    }

    #[test]
    fn staged_adoption_is_invisible_until_commit_and_cannot_repeat() {
        let mut engine = attached();
        let stage = engine
            .call(
                "stage_prepare",
                &json!({"key":key(),"start":pos(0),"end":pos(8),"lease_active":true}),
            )
            .unwrap();
        assert_eq!(stage["current"], pos(0));
        assert_eq!(stage["result"], pos(8));
        assert_eq!(
            engine.call("entry", &json!({"key":key()})).unwrap()["current"],
            pos(0)
        );
        engine
            .call(
                "stage_validate",
                &json!({"token":stage["token"],"lease_active":true}),
            )
            .unwrap();
        let entry = engine.call("stage_commit", &stage).unwrap();
        assert_eq!(entry["current"], pos(8));
        assert_eq!(entry["persisted"], pos(8));
        assert_eq!(entry["dirty"], false);
        assert!(engine.call("stage_commit", &stage).is_err());
    }

    #[test]
    fn journal_unicode_bytes_and_512_character_lease_match_python_v2() {
        let mut engine = PositionEngine::new();
        let owner = json!([1, "é😀", 2]);
        assert_eq!(
            engine.call("identity", &json!({"key":owner})).unwrap(),
            r#"[1,"\u00e9\ud83d\ude00",2]"#
        );
        assert!(engine
            .call("identity", &json!({"key":[1,"é".repeat(512),2]}))
            .is_ok());
        assert!(engine
            .call("identity", &json!({"key":[1,"é".repeat(513),2]}))
            .is_err());
        let record=engine.call("encode_record",&json!({"key":owner,"entry":{"current":pos(3),"persisted":pos(0)},"revision":"a".repeat(32)})).unwrap();
        let decoded = engine.call("validate_record", &record).unwrap();
        assert_eq!(decoded["key"], owner);
        assert_eq!(engine.call("record_status",&json!({"key":owner,"value":decoded["value"],"saved":pos(3),"selected_character_id":2})).unwrap(),"already_committed");
        assert_eq!(engine.call("record_status",&json!({"key":owner,"value":decoded["value"],"saved":pos(0),"selected_character_id":2})).unwrap(),"recoverable");
        assert_eq!(engine.call("record_status",&json!({"key":owner,"value":decoded["value"],"saved":pos(8),"selected_character_id":2})).unwrap(),"conflict");
        assert_eq!(engine.call("record_status",&json!({"key":owner,"value":decoded["value"],"saved":pos(0),"selected_character_id":3})).unwrap(),"stale");
    }

    #[test]
    fn cursor_rotates_dirty_accounts_and_clean_journals_remain_background_work() {
        let mut engine = attached();
        let p = prepare_move(&mut engine, 1);
        engine.call("commit_move", &p).unwrap();
        for account in [2, 3] {
            let k = json!([account, "lease", account * 10]);
            engine.call("attach",&json!({"key":k,"selected_character_id":account*10,"current":pos(0),"persisted":pos(0)})).unwrap();
            let p = engine
                .call(
                    "prepare_move",
                    &json!({"key":k,"start":pos(0),"end":pos(1),"lease_active":true}),
                )
                .unwrap();
            engine.call("commit_move", &p).unwrap();
        }
        engine
            .call("cursor_advance", &json!({"account_id":2}))
            .unwrap();
        assert_eq!(
            engine.call("background_accounts", &json!({})).unwrap(),
            json!([3, 1, 2])
        );
    }

    #[test]
    fn checkpoint_scope_budget_and_eviction_peek_preserve_unrelated_accounts() {
        let mut engine = attached();
        let moved = prepare_move(&mut engine, 1);
        engine.call("commit_move", &moved).unwrap();
        let other = json!([2, "lease", 20]);
        engine.call("attach",&json!({"key":other,"selected_character_id":20,"current":pos(0),"persisted":pos(0)})).unwrap();
        assert_eq!(
            engine.call("accounts", &json!({"account_id":1})).unwrap(),
            json!([1])
        );
        assert!(engine
            .call(
                "background_plan",
                &json!({"max_accounts":true,"max_seconds":1})
            )
            .is_err());
        assert!(engine
            .call(
                "background_plan",
                &json!({"max_accounts":1,"max_seconds":true})
            )
            .is_err());
        assert_eq!(
            engine
                .call(
                    "background_plan",
                    &json!({"max_accounts":1,"max_seconds":1})
                )
                .unwrap()["accounts"],
            json!([1])
        );
        let plan = engine
            .call(
                "prepare_checkpoint",
                &json!({"account_id":1,"leases":[{"key":key(),"selected_character_id":null}]}),
            )
            .unwrap();
        engine.call("commit_checkpoint", &plan).unwrap();
        assert_eq!(
            engine.call("evictions", &json!({"drain":false})).unwrap(),
            json!([key()])
        );
        assert_eq!(
            engine.call("evictions", &json!({"drain":true})).unwrap(),
            json!([key()])
        );
        assert_eq!(
            engine.call("evictions", &json!({"drain":false})).unwrap(),
            json!([])
        );
        assert!(!engine
            .call("entry", &json!({"key":other}))
            .unwrap()
            .is_null());
    }

    #[test]
    fn committed_transition_ack_failure_never_makes_old_source_dirty_again() {
        let mut engine = attached();
        let moved = prepare_move(&mut engine, 4);
        engine
            .call(
                "commit_move",
                &json!({"token":moved["token"],"encoded":"old-journal"}),
            )
            .unwrap();
        let destination = json!({"map_id":1134,"instance_id":9,"x":8,"y":7,"z":3});
        let transition = engine
            .call(
                "transition_prepare",
                &json!({"key":key(),"source":pos(4),"destination":destination,"saved":destination}),
            )
            .unwrap();
        assert_eq!(transition["key"], key());
        engine.call("abort", &transition).unwrap();
        let entry = engine.call("entry", &json!({"key":key()})).unwrap();
        assert_eq!(entry["dirty"], false);
        assert_eq!(entry["current"], pos(4));
        assert_eq!(entry["pending_ack"], "old-journal");
        assert_eq!(
            engine.call("entries", &json!({"dirty_only":true})).unwrap(),
            json!([])
        );
    }

    #[test]
    fn journal_del_escape_and_full_sql_row_recovery_match_legacy_wire() {
        let mut engine = PositionEngine::new();
        let owner = json!([1, "\u{7f}", 2]);
        assert_eq!(
            engine.call("identity", &json!({"key":owner})).unwrap(),
            r#"[1,"\u007f",2]"#
        );
        let mut saved = pos(0);
        saved["account_id"] = json!(1);
        saved["hp"] = json!(100);
        let value = json!({"baseline":pos(0),"current":pos(1)});
        assert_eq!(
            engine
                .call(
                    "record_status",
                    &json!({"key":owner,"value":value,"saved":saved,"selected_character_id":2})
                )
                .unwrap(),
            "recoverable"
        );
    }
}
