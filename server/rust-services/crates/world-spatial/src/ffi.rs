//! Owned-buffer C ABI. Handles retain Arc ownership across concurrent close.
use crate::engine::{Engine, NativeError};
use serde_json::{json, Value};
use std::{
    collections::HashMap,
    mem::ManuallyDrop,
    panic::{catch_unwind, AssertUnwindSafe},
    slice,
    sync::{
        atomic::{AtomicBool, AtomicU64, Ordering},
        Arc, Condvar, Mutex, OnceLock, TryLockError,
    },
};
const MAX: usize = 64 * 1024 * 1024;
struct Handle {
    engine: Mutex<Engine>,
    changed: Condvar,
    closed: AtomicBool,
}
static HANDLES: OnceLock<Mutex<HashMap<u64, Arc<Handle>>>> = OnceLock::new();
static NEXT: AtomicU64 = AtomicU64::new(1);
fn handles() -> &'static Mutex<HashMap<u64, Arc<Handle>>> {
    HANDLES.get_or_init(|| Mutex::new(HashMap::new()))
}
#[repr(C)]
pub struct NativeBuffer {
    pub data: *mut u8,
    pub len: usize,
    pub capacity: usize,
}
#[repr(C)]
pub struct NativeSlice {
    pub data: *const u8,
    pub len: usize,
}
fn wire_buffer(status: u8, payload: &[u8]) -> NativeBuffer {
    let mut bytes = Vec::with_capacity(payload.len() + 1);
    bytes.push(status);
    bytes.extend_from_slice(payload);
    let mut bytes = ManuallyDrop::new(bytes);
    NativeBuffer { data: bytes.as_mut_ptr(), len: bytes.len(), capacity: bytes.capacity() }
}
/// Borrowed binary inputs remain owned by the caller for the complete call.
/// Codec work never takes the live actor engine mutex.
#[no_mangle]
pub unsafe extern "C" fn wakemu_wire_call(
    id: u64,
    op: u32,
    buffers: *const NativeSlice,
    buffer_count: usize,
    integers: *const i64,
    integer_count: usize,
) -> NativeBuffer {
    let result = catch_unwind(AssertUnwindSafe(|| -> Result<Vec<u8>, (u8, String)> {
        if buffer_count > 131072 || integer_count > 1000000
            || (buffer_count != 0 && (buffers.is_null() || (buffers as usize) % std::mem::align_of::<NativeSlice>() != 0))
            || (integer_count != 0 && (integers.is_null() || (integers as usize) % std::mem::align_of::<i64>() != 0)) {
            return Err((1, "Invalid native wire input descriptors".into()));
        }
        let handle = handles().lock()
            .map_err(|_| (2, "Native registry poisoned".into()))?
            .get(&id).cloned().ok_or_else(|| (2, "Native engine is closed".into()))?;
        if handle.closed.load(Ordering::Acquire) {
            return Err((2, "Native engine is closed".into()));
        }
        let descriptors = if buffer_count == 0 { &[][..] }
            else { unsafe { slice::from_raw_parts(buffers, buffer_count) } };
        let mut borrowed = Vec::with_capacity(buffer_count);
        let mut total = integer_count * std::mem::size_of::<i64>();
        for descriptor in descriptors {
            total = total.checked_add(descriptor.len)
                .filter(|total| *total <= MAX)
                .ok_or_else(|| (1, "Native wire input exceeds limit".into()))?;
            if descriptor.len != 0 && descriptor.data.is_null() {
                return Err((1, "Invalid native wire input buffer".into()));
            }
            borrowed.push(if descriptor.len == 0 { &[][..] }
                else { unsafe { slice::from_raw_parts(descriptor.data, descriptor.len) } });
        }
        let integers = if integer_count == 0 { &[][..] }
            else { unsafe { slice::from_raw_parts(integers, integer_count) } };
        let output = crate::wire_codec::call(op, &borrowed, integers)
            .map_err(|error| {
                if matches!(error.code.as_str(), "internal" | "panic" | "closed") {
                    (2, error.message)
                } else {
                    (1, format!("{}\0{}", error.code, error.message))
                }
            })?;
        if output.len() > MAX {
            return Err((1, "Native wire response exceeds limit".into()));
        }
        Ok(output)
    }));
    match result {
        Ok(Ok(mut bytes)) => {
            // Codec allocation reserves one extra byte for this prefix. Retain
            // that allocation instead of duplicating the complete packet body.
            bytes.insert(0, 0);
            let mut bytes = ManuallyDrop::new(bytes);
            NativeBuffer { data: bytes.as_mut_ptr(), len: bytes.len(), capacity: bytes.capacity() }
        }
        Ok(Err((1, message))) if !message.contains('\0') =>
            wire_buffer(1, format!("invalid\0{message}").as_bytes()),
        Ok(Err((status, message))) => wire_buffer(status, message.as_bytes()),
        Err(_) => wire_buffer(2, b"Native wire operation panicked"),
    }
}
fn buffer(value: Value) -> NativeBuffer {
    let bytes = serde_json::to_vec(&value).unwrap_or_else(|_| {
        b"{\"ok\":false,\"error\":{\"code\":\"internal\",\"message\":\"Encoding failed\"}}".to_vec()
    });
    let bytes = if bytes.len() > MAX {
        serde_json::to_vec(
            &NativeError::new("capacity", "Native response exceeds limit").response(),
        )
        .unwrap()
    } else {
        bytes
    };
    let mut bytes = ManuallyDrop::new(bytes);
    NativeBuffer {
        data: bytes.as_mut_ptr(),
        len: bytes.len(),
        capacity: bytes.capacity(),
    }
}
unsafe fn input<'a>(p: *const u8, len: usize) -> Result<&'a [u8], NativeError> {
    if p.is_null() || len == 0 || len > MAX {
        return Err(NativeError::new("invalid", "Invalid native input buffer"));
    }
    Ok(unsafe { slice::from_raw_parts(p, len) })
}
#[no_mangle]
pub extern "C" fn wakemu_spatial_abi_version() -> u32 {
    1
}
#[no_mangle]
pub unsafe extern "C" fn wakemu_spatial_create(
    epoch: *const u8,
    len: usize,
    capacity: usize,
) -> u64 {
    catch_unwind(AssertUnwindSafe(|| {
        let bytes = unsafe { input(epoch, len) }.ok()?;
        let epoch = std::str::from_utf8(bytes).ok()?.to_owned();
        let engine = Engine::new(epoch, capacity).ok()?;
        let mut registry = handles().lock().ok()?;
        if registry.len() >= 4096 {
            return None;
        }
        let id = NEXT.load(Ordering::Relaxed);
        NEXT.store(id.checked_add(1)?, Ordering::Relaxed);
        registry.insert(
            id,
            Arc::new(Handle {
                engine: Mutex::new(engine),
                changed: Condvar::new(),
                closed: AtomicBool::new(false),
            }),
        );
        Some(id)
    }))
    .ok()
    .flatten()
    .unwrap_or(0)
}
fn execute(id: u64, bytes: &[u8]) -> Result<Value, NativeError> {
    let request: Value = serde_json::from_slice(bytes)
        .map_err(|_| NativeError::new("invalid", "Malformed native JSON request"))?;
    let op = request
        .get("op")
        .and_then(Value::as_str)
        .filter(|s| !s.is_empty() && s.len() <= 128)
        .ok_or_else(|| NativeError::new("invalid", "Missing native operation"))?;
    let args = request
        .get("args")
        .filter(|a| a.is_object())
        .ok_or_else(|| NativeError::new("invalid", "Native arguments must be an object"))?;
    let handle = handles()
        .lock()
        .map_err(|_| NativeError::new("internal", "Native registry poisoned"))?
        .get(&id)
        .cloned()
        .ok_or_else(|| NativeError::new("closed", "Native engine is closed"))?;
    if handle.closed.load(Ordering::Acquire) {
        return Err(NativeError::new("closed", "Native engine is closed"));
    }
    // Immutable parsing/path work must never stall live actor commands.
    if op.starts_with("geometry.") {
        return crate::geometry::call(op, args)
            .map_err(|e| NativeError::new("invalid", e.to_string()));
    }
    if matches!(
        op,
        "navigation.topology_lookup" | "navigation.topology_register" | "navigation.directed_path"
    ) {
        return crate::navigation::immutable_call(op, args)
            .map_err(|e| NativeError::new("invalid", e));
    }
    let owner = std::thread::current().id();
    let mut engine = if matches!(op, "world.try_scope_positions" | "world.try_positions") {
        match handle.engine.try_lock() {
            Ok(e) => e,
            Err(TryLockError::WouldBlock) => return Ok(Value::Null),
            Err(_) => return Err(NativeError::new("internal", "Native engine poisoned")),
        }
    } else {
        handle
            .engine
            .lock()
            .map_err(|_| NativeError::new("internal", "Native engine poisoned"))?
    };
    loop {
        if handle.closed.load(Ordering::Acquire) {
            return Err(NativeError::new("closed", "Native engine is closed"));
        }
        if !engine.blocked(op, args, owner) {
            break;
        }
        engine = handle
            .changed
            .wait(engine)
            .map_err(|_| NativeError::new("internal", "Native engine poisoned"))?;
    }
    let result = engine.call(op, args, owner);
    drop(engine);
    handle.changed.notify_all();
    result
}
#[no_mangle]
pub unsafe extern "C" fn wakemu_spatial_call(id: u64, p: *const u8, len: usize) -> NativeBuffer {
    let result = catch_unwind(AssertUnwindSafe(|| {
        let bytes = unsafe { input(p, len) }?;
        execute(id, bytes)
    }));
    buffer(match result {
        Ok(Ok(value)) => json!({"ok":true,"result":value}),
        Ok(Err(e)) => e.response(),
        Err(_) => NativeError::new("panic", "Native spatial operation panicked").response(),
    })
}
#[no_mangle]
pub unsafe extern "C" fn wakemu_spatial_free(bytes: NativeBuffer) {
    if !bytes.data.is_null() && bytes.len <= bytes.capacity {
        drop(unsafe { Vec::from_raw_parts(bytes.data, bytes.len, bytes.capacity) });
    }
}
#[no_mangle]
pub extern "C" fn wakemu_spatial_drop(id: u64) {
    let _ = catch_unwind(|| {
        let removed = handles()
            .lock()
            .ok()
            .and_then(|mut registry| registry.remove(&id));
        if let Some(handle) = removed {
            handle.closed.store(true, Ordering::Release);
            // Synchronize notification with Condvar::wait's atomic mutex release.
            // No external I/O or callbacks hold this compact-state mutex.
            let _guard = handle.engine.lock();
            handle.changed.notify_all();
        }
    });
}
#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn binary_codec_owns_outputs_and_rejects_invalid_descriptors() {
        unsafe {
            let id = wakemu_spatial_create(b"wire".as_ptr(), 4, 10);
            let source = b"a\0b";
            let input = [NativeSlice { data: source.as_ptr(), len: source.len() }];
            let output = wakemu_wire_call(id, 3, input.as_ptr(), 1, std::ptr::null(), 0);
            assert_eq!(slice::from_raw_parts(output.data, output.len), b"\0a\0b");
            wakemu_spatial_free(output);
            let rejected = wakemu_wire_call(id, 3, std::ptr::null(), 1, std::ptr::null(), 0);
            assert_eq!(*rejected.data, 1);
            wakemu_spatial_free(rejected);
            let rejected = wakemu_wire_call(id, 3, std::ptr::null(), 0, std::ptr::null(), 1);
            assert_eq!(*rejected.data, 1);
            wakemu_spatial_free(rejected);
            wakemu_spatial_drop(id);
            let closed = wakemu_wire_call(id, 3, std::ptr::null(), 0, std::ptr::null(), 0);
            assert_eq!(*closed.data, 2);
            wakemu_spatial_free(closed);
        }
    }
    unsafe fn call(id: u64, r: Value) -> Value {
        let b = serde_json::to_vec(&r).unwrap();
        let out = unsafe { wakemu_spatial_call(id, b.as_ptr(), b.len()) };
        let value =
            serde_json::from_slice(unsafe { slice::from_raw_parts(out.data, out.len) }).unwrap();
        unsafe { wakemu_spatial_free(out) };
        value
    }
    #[test]
    fn scope_waiters_release_engine_mutex_and_close_cancels_them() {
        unsafe {
            let id = wakemu_spatial_create(b"test".as_ptr(), 4, 10);
            assert_eq!(
                call(
                    id,
                    json!({"op":"world.scope_acquire","args":{"map_id":527,"instance_id":0}})
                )["ok"],
                true
            );
            let (started_tx, started_rx) = std::sync::mpsc::channel();
            let (done_tx, done_rx) = std::sync::mpsc::channel();
            let worker = std::thread::spawn(move || {
                started_tx.send(()).unwrap();
                done_tx
                    .send(call(
                        id,
                        json!({"op":"world.scope_acquire","args":{"map_id":527,"instance_id":0}}),
                    ))
                    .unwrap();
            });
            started_rx.recv().unwrap();
            assert!(done_rx
                .recv_timeout(std::time::Duration::from_millis(20))
                .is_err());
            assert_eq!(
                call(
                    id,
                    json!({"op":"world.scope_acquire","args":{"map_id":527,"instance_id":1}})
                )["ok"],
                true
            );
            wakemu_spatial_drop(id);
            assert_eq!(
                done_rx
                    .recv_timeout(std::time::Duration::from_secs(2))
                    .unwrap()["error"]["code"],
                "closed"
            );
            worker.join().unwrap();
        }
    }
    #[test]
    fn abi_owned_buffers_and_closed_handles() {
        unsafe {
            let id = wakemu_spatial_create(b"test".as_ptr(), 4, 10);
            assert_ne!(id, 0);
            assert_eq!(wakemu_spatial_abi_version(), 1);
            assert_eq!(call(id, json!({"op":"engine.stats","args":{}}))["ok"], true);
            wakemu_spatial_drop(id);
            wakemu_spatial_drop(id);
            assert_eq!(
                call(id, json!({"op":"engine.stats","args":{}}))["error"]["code"],
                "closed"
            );
        }
    }
}
