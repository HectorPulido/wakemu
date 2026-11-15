//! Compact authoritative dispatch. External I/O never executes while this state is locked.
use crate::{navigation::NavigationState, positions::PositionEngine, world_state::WorldState};
use serde_json::{json, Value};
use std::{collections::HashMap, thread::ThreadId};

#[derive(Debug)]
pub struct NativeError {
    pub code: String,
    pub message: String,
}
impl NativeError {
    pub fn new(code: impl Into<String>, message: impl Into<String>) -> Self {
        Self {
            code: code.into(),
            message: message.into(),
        }
    }
    pub fn response(&self) -> Value {
        json!({"ok":false,"error":{"code":self.code,"message":self.message}})
    }
}
struct Permit {
    owner: ThreadId,
    tokens: Vec<u64>,
}
pub struct Engine {
    pub world: WorldState,
    positions: PositionEngine,
    navigation: NavigationState,
    epoch: String,
    permits: HashMap<String, Permit>,
}
fn position_write(op: &str) -> bool {
    matches!(
        op,
        "positions.attach"
            | "positions.prepare_move"
            | "positions.stage_prepare"
            | "positions.prepare_checkpoint"
            | "positions.release_prepare"
            | "positions.transition_prepare"
            | "positions.ack_complete"
    )
}
fn prepared(op: &str) -> bool {
    matches!(
        op,
        "positions.prepare_move"
            | "positions.stage_prepare"
            | "positions.prepare_checkpoint"
            | "positions.release_prepare"
            | "positions.transition_prepare"
    )
}
fn completed(op: &str) -> bool {
    matches!(
        op,
        "positions.commit_move"
            | "positions.stage_commit"
            | "positions.commit_checkpoint"
            | "positions.release_commit"
            | "positions.abort"
    )
}
impl Engine {
    pub fn new(epoch: String, capacity: usize) -> Result<Self, NativeError> {
        if epoch.is_empty() || epoch.len() > 128 || capacity == 0 || capacity > 1_000_000 {
            return Err(NativeError::new(
                "invalid",
                "Invalid native engine configuration",
            ));
        }
        Ok(Self {
            world: WorldState::new(capacity),
            positions: PositionEngine::new(),
            navigation: NavigationState::new(),
            epoch,
            permits: HashMap::new(),
        })
    }
    pub fn blocked(&self, op: &str, a: &Value, owner: ThreadId) -> bool {
        let scopes = if op.starts_with("world.") {
            self.world.requested_scopes(op, a)
        } else if position_write(op) {
            self.positions.request_scopes(op, a)
        } else {
            Vec::new()
        };
        scopes
            .into_iter()
            .any(|s| self.world.reserved_by_other(s, owner))
    }
    pub fn call(&mut self, op: &str, a: &Value, owner: ThreadId) -> Result<Value, NativeError> {
        if !a.is_object() {
            return Err(NativeError::new(
                "invalid",
                "Native arguments must be an object",
            ));
        }
        if !completed(op) && a.get("world_epoch").is_some_and(|e| e != &self.epoch) {
            return Err(NativeError::new("stale", "Native engine epoch differs"));
        }
        if op.starts_with("world.") {
            return self.world.call(op, a, owner);
        }
        if op.starts_with("navigation.") {
            return self
                .navigation
                .call(op, a)
                .map_err(|e| NativeError::new("invalid", e));
        }
        if op == "engine.stats" {
            return Ok(
                json!({"epoch":self.epoch,"world":self.world.call("world.stats",&json!({}),owner)?}),
            );
        }
        if !op.starts_with("positions.") {
            return Err(NativeError::new(
                "invalid",
                format!("Unknown native operation: {op}"),
            ));
        }
        let token = a.get("token").and_then(Value::as_str).map(str::to_owned);
        if token
            .as_ref()
            .and_then(|t| self.permits.get(t))
            .is_some_and(|p| p.owner != owner)
        {
            return Err(NativeError::new(
                "stale",
                "Position token belongs to another thread",
            ));
        }
        let scopes = if prepared(op) {
            self.positions.request_scopes(op, a)
        } else {
            Vec::new()
        };
        let keys = if matches!(op, "positions.commit_move" | "positions.stage_commit") {
            self.positions.request_keys(op, a)
        } else {
            Vec::new()
        };
        // Admit every touched scope before creating a token or doing external I/O.
        let mut tokens = Vec::new();
        for (map, instance) in scopes {
            match self.world.call(
                "world.scope_acquire",
                &json!({"map_id":map,"instance_id":instance}),
                owner,
            ) {
                Ok(r) => tokens.push(r["token"].as_u64().unwrap()),
                Err(error) => {
                    for token in tokens {
                        let _ =
                            self.world
                                .call("world.scope_release", &json!({"token":token}), owner);
                    }
                    return Err(error);
                }
            }
        }
        let result = match self.positions.call(op, a) {
            Ok(result) => result,
            Err(error) => {
                for token in tokens {
                    let _ = self
                        .world
                        .call("world.scope_release", &json!({"token":token}), owner);
                }
                return Err(NativeError::new(error.kind, error.message));
            }
        };
        if let Some(token) = result
            .get("token")
            .and_then(Value::as_str)
            .filter(|_| prepared(op))
        {
            self.permits
                .insert(token.to_owned(), Permit { owner, tokens });
        } else {
            for token in tokens {
                let _ = self
                    .world
                    .call("world.scope_release", &json!({"token":token}), owner);
            }
        }
        for (account, generation, id) in keys {
            if let Ok(entry) = self
                .positions
                .call("positions.entry", &json!({"key":[account,generation,id]}))
            {
                self.world
                    .adopt_public_position(account, &generation, id, &entry["current"]);
            }
        }
        if completed(op) {
            if let Some(permit) = token.and_then(|t| self.permits.remove(&t)) {
                for token in permit.tokens {
                    let _ = self
                        .world
                        .call("world.scope_release", &json!({"token":token}), owner);
                }
            }
        }
        Ok(result)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    fn pos(x: i64) -> Value {
        json!({"map_id":527,"instance_id":0,"x":x,"y":0,"z":0,"direction":0})
    }
    #[test]
    fn journal_prepare_holds_scope_through_irreversible_commit_and_adopts_world_atomically() {
        let owner = std::thread::current().id();
        let other = std::thread::spawn(|| std::thread::current().id())
            .join()
            .unwrap();
        let mut engine = Engine::new("epoch".into(), 10).unwrap();
        let join=engine.call("world.join_prepare",&json!({"generation":"lease","peer_id":1,"character":{"id":10,"account_id":1,"map_id":527,"instance_id":0,"x":0,"y":0,"z":0,"direction":0}}),owner).unwrap();
        engine
            .call("world.join_ready", &json!({"token":join["token"]}), owner)
            .unwrap();
        engine
            .call("world.join_commit", &json!({"token":join["token"]}), owner)
            .unwrap();
        engine.call("positions.attach",&json!({"key":[1,"lease",10],"selected_character_id":10,"current":pos(0),"persisted":pos(0)}),owner).unwrap();
        let prepared = engine
            .call(
                "positions.prepare_move",
                &json!({"key":[1,"lease",10],"start":pos(0),"end":pos(7),"lease_active":true}),
                owner,
            )
            .unwrap();
        assert!(engine.blocked(
            "world.scope_acquire",
            &json!({"map_id":527,"instance_id":0}),
            other
        ));
        assert!(!engine.blocked(
            "world.scope_acquire",
            &json!({"map_id":527,"instance_id":1}),
            other
        ));
        assert!(engine
            .call("positions.commit_move", &prepared, other)
            .is_err());
        let mut commit = prepared;
        commit["world_epoch"] = json!("stale-after-SQL");
        engine
            .call("positions.commit_move", &commit, owner)
            .unwrap();
        assert!(!engine.blocked(
            "world.scope_acquire",
            &json!({"map_id":527,"instance_id":0}),
            other
        ));
        assert_eq!(
            engine.call("world.get", &json!({"id":10}), owner).unwrap()["x"],
            7
        );
    }
    #[test]
    fn failed_prepare_does_not_leak_scope_admission() {
        let owner = std::thread::current().id();
        let mut engine = Engine::new("epoch".into(), 10).unwrap();
        assert!(engine
            .call(
                "positions.prepare_move",
                &json!({"key":[1,"lease",10],"start":pos(0),"end":pos(1),"lease_active":true}),
                owner
            )
            .is_err());
        assert_eq!(
            engine.call("world.stats", &json!({}), owner).unwrap()["scope_reservations"],
            0
        );
    }
}
