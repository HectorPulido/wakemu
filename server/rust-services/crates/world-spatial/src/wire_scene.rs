//! Bounded immutable scene indexes and binary snapshot/resource encoders.
use crate::engine::NativeError;
use sha2::{Digest, Sha256};
use std::collections::{BTreeMap, BTreeSet, VecDeque};
use std::sync::{Arc, Mutex, OnceLock};

const LIMIT: usize = 64 * 1024 * 1024;
const CACHE_BYTES: usize = 32 * 1024 * 1024;
const FRAME_BODY: usize = 327670 - 6;
#[derive(Clone)]
struct Record {
    id: i64,
    payload: Vec<u8>,
}
struct Index {
    chunks: BTreeMap<(i64, i64), Vec<Vec<u8>>>,
    bytes: usize,
}
#[derive(Default)]
struct Cache {
    rows: VecDeque<([u8; 32], Arc<Index>)>,
    bytes: usize,
}
static CACHE: OnceLock<Mutex<Cache>> = OnceLock::new();
fn invalid(message: &str) -> NativeError {
    NativeError::new("invalid_scene", message)
}
fn list<T: AsRef<[u8]>>(rows: &[T]) -> Result<Vec<u8>, NativeError> {
    let size = 4usize
        .checked_add(rows.iter().map(|r| r.as_ref().len() + 4).sum::<usize>())
        .ok_or_else(|| invalid("Scene output overflow"))?;
    if size > LIMIT {
        return Err(invalid("Scene output exceeds binary limit"));
    }
    let mut out = Vec::with_capacity(size);
    out.extend_from_slice(&(rows.len() as u32).to_be_bytes());
    for row in rows {
        let row = row.as_ref();
        out.extend_from_slice(&(row.len() as u32).to_be_bytes());
        out.extend_from_slice(row);
    }
    Ok(out)
}
fn snapshots<'a>(
    records: impl IntoIterator<Item = &'a Record>,
) -> Result<Vec<Vec<u8>>, NativeError> {
    let mut result = Vec::new();
    let mut body = vec![0, 0];
    let mut count = 0i16;
    for record in records {
        if record.payload.len() > i16::MAX as usize {
            return Err(invalid("Interactive payload exceeds signed codec limit"));
        }
        if count == i16::MAX || body.len() + 10 + record.payload.len() > FRAME_BODY {
            body[..2].copy_from_slice(&count.to_be_bytes());
            result.push(body);
            body = vec![0, 0];
            count = 0;
        }
        body.extend_from_slice(&record.id.to_be_bytes());
        body.extend_from_slice(&(record.payload.len() as i16).to_be_bytes());
        body.extend_from_slice(&record.payload);
        count += 1;
    }
    if count > 0 {
        body[..2].copy_from_slice(&count.to_be_bytes());
        result.push(body);
    }
    Ok(result)
}
fn records(body: &[u8], allow_empty: bool) -> Result<Vec<(i64, &[u8])>, NativeError> {
    if body.len() < 2 {
        return Err(invalid("Truncated interactive snapshot count"));
    }
    let count = i16::from_be_bytes(body[..2].try_into().unwrap());
    if count < 0 {
        return Err(invalid("Negative interactive snapshot count"));
    }
    let mut cursor = 2;
    let mut rows = Vec::with_capacity(count as usize);
    for _ in 0..count {
        if cursor + 10 > body.len() {
            return Err(invalid("Truncated interactive snapshot record"));
        }
        let id = i64::from_be_bytes(body[cursor..cursor + 8].try_into().unwrap());
        let size = u16::from_be_bytes(body[cursor + 8..cursor + 10].try_into().unwrap()) as usize;
        cursor += 10;
        if (!allow_empty && size == 0) || size > body.len() - cursor {
            return Err(invalid("Invalid interactive snapshot payload length"));
        }
        rows.push((id, &body[cursor..cursor + size]));
        cursor += size;
    }
    if cursor != body.len() {
        return Err(invalid("Trailing interactive snapshot data"));
    }
    Ok(rows)
}
fn register(buffers: &[&[u8]], ints: &[i64]) -> Result<Vec<u8>, NativeError> {
    if ints.len() < 3 || ints[0] <= 0 || ints[1] < 0 || ints[2] < 0 {
        return Err(invalid("Invalid scene index header"));
    }
    let n = ints[1] as usize;
    let entrances = ints[2] as usize;
    if n > 131070
        || entrances > 131070
        || buffers.len() != n + 3
        || ints.len() != 3 + n + entrances
        || buffers.get(2).map_or(true, |b| b.len() != n * 16)
    {
        return Err(invalid("Invalid scene index records"));
    }
    let mut digest = Sha256::new();
    for value in ints {
        digest.update(value.to_be_bytes());
    }
    for value in buffers {
        digest.update((value.len() as u64).to_be_bytes());
        digest.update(value);
    }
    let key: [u8; 32] = digest.finalize().into();
    let mut cache = CACHE
        .get_or_init(|| Mutex::new(Cache::default()))
        .lock()
        .map_err(|_| invalid("Scene index cache poisoned"))?;
    if let Some(pos) = cache.rows.iter().position(|(k, _)| *k == key) {
        let row = cache.rows.remove(pos).unwrap();
        cache.rows.push_back(row);
        return Ok(key.to_vec());
    }
    let overrides: BTreeSet<i64> = ints[3 + n..].iter().copied().collect();
    let mut grouped: BTreeMap<(i64, i64), Vec<Record>> = BTreeMap::new();
    let mut index = Index {
        chunks: BTreeMap::new(),
        bytes: 0,
    };
    for row in 0..n {
        let id = ints[3 + row];
        let at = row * 16;
        let x = f64::from_be_bytes(buffers[2][at..at + 8].try_into().unwrap());
        let y = f64::from_be_bytes(buffers[2][at + 8..at + 16].try_into().unwrap());
        if !x.is_finite()
            || !y.is_finite()
            || x.abs() > i32::MAX as f64
            || y.abs() > i32::MAX as f64
        {
            return Err(invalid("Invalid scene object coordinates"));
        }
        let chunk = ((x / 18.0).floor() as i64, (y / 18.0).floor() as i64);
        let payload = if overrides.contains(&id) {
            buffers[1]
        } else {
            buffers[row + 3]
        };
        if payload.len() > 32767 {
            return Err(invalid("Interactive payload exceeds signed codec limit"));
        }
        index.bytes += payload.len() + 32;
        grouped.entry(chunk).or_default().push(Record {
            id,
            payload: payload.to_vec(),
        });
    }
    for (chunk, rows) in grouped {
        index.chunks.insert(chunk, snapshots(&rows)?);
    }
    if index.bytes > CACHE_BYTES {
        return Err(invalid("Scene index exceeds bounded cache capacity"));
    }
    while cache.rows.len() >= 64 || cache.bytes + index.bytes > CACHE_BYTES {
        if let Some((_, old)) = cache.rows.pop_front() {
            cache.bytes -= old.bytes;
        } else {
            break;
        }
    }
    cache.bytes += index.bytes;
    cache.rows.push_back((key, Arc::new(index)));
    Ok(key.to_vec())
}
fn selected(buffers: &[&[u8]], ints: &[i64]) -> Result<Vec<u8>, NativeError> {
    if buffers.len() != 1 || buffers[0].len() != 32 || ints.len() % 2 != 0 {
        return Err(invalid("Invalid selected scene partitions"));
    }
    let key: [u8; 32] = buffers[0].try_into().unwrap();
    let index = {
        let mut cache = CACHE
            .get_or_init(|| Mutex::new(Cache::default()))
            .lock()
            .map_err(|_| invalid("Scene index cache poisoned"))?;
        let pos = cache
            .rows
            .iter()
            .position(|(k, _)| *k == key)
            .ok_or_else(|| NativeError::new("scene_cache_miss", "Scene index was evicted"))?;
        let row = cache.rows.remove(pos).unwrap();
        let index = row.1.clone();
        cache.rows.push_back(row);
        index
    };
    let chunks: BTreeSet<(i64, i64)> = ints.chunks_exact(2).map(|p| (p[0], p[1])).collect();
    let mut bodies = Vec::new();
    for chunk in chunks {
        if let Some(rows) = index.chunks.get(&chunk) {
            bodies.extend(rows.iter().map(Vec::as_slice));
        }
    }
    list(&bodies)
}
fn varint(mut value: u64, out: &mut Vec<u8>) {
    while value >= 128 {
        out.push((value as u8 & 127) | 128);
        value >>= 7;
    }
    out.push(value as u8);
}
fn resources(buffers: &[&[u8]], ints: &[i64]) -> Result<Vec<u8>, NativeError> {
    if !buffers.is_empty() || ints.len() < 2 || ints[0] < -1 || ints[1] < 0 {
        return Err(invalid("Invalid resource snapshot header"));
    }
    let count = ints[1] as usize;
    let nc = ints[0].max(0) as usize;
    if count > 200000 || nc > 200000 {
        return Err(invalid("Resource snapshot exceeds capacity"));
    }
    let start = 2 + nc * 2;
    if ints.len() != start + count * 5 {
        return Err(invalid("Invalid resource snapshot rows"));
    }
    let chunks: BTreeSet<(i64, i64)> = ints[2..start]
        .chunks_exact(2)
        .map(|p| (p[0], p[1]))
        .collect();
    let mut bodies = Vec::new();
    for row in ints[start..].chunks_exact(5) {
        if row[0] <= 0
            || row[0] > i32::MAX as i64
            || row[1] < i32::MIN as i64
            || row[1] > i32::MAX as i64
            || row[2] < i32::MIN as i64
            || row[2] > i32::MAX as i64
            || row[3] < i16::MIN as i64
            || row[3] > i16::MAX as i64
            || row[4] < 0
            || row[4] > 127
        {
            return Err(invalid("Invalid native resource appearance"));
        }
        if ints[0] >= 0 && !chunks.contains(&(row[1].div_euclid(18), row[2].div_euclid(18))) {
            continue;
        }
        let mut body = Vec::with_capacity(64);
        for (tag, value) in [
            (8, row[0]),
            (16, row[1]),
            (24, row[2]),
            (32, row[3]),
            (40, row[4]),
            (48, 0),
            (56, 0),
            (64, 0),
        ] {
            body.push(tag);
            varint(value as u64, &mut body);
        }
        bodies.push(body);
    }
    list(&bodies)
}
pub fn call(op: u32, buffers: &[&[u8]], integers: &[i64]) -> Result<Vec<u8>, NativeError> {
    match op {
        10 => register(buffers, integers),
        11 => selected(buffers, integers),
        12 => {
            if buffers.len() != integers.len() {
                return Err(invalid("Invalid interactive record descriptors"));
            }
            let rows: Vec<Record> = buffers
                .iter()
                .zip(integers)
                .map(|(p, id)| Record {
                    id: *id,
                    payload: p.to_vec(),
                })
                .collect();
            list(&snapshots(&rows)?)
        }
        13 => {
            if !integers.is_empty() {
                return Err(invalid("Unexpected snapshot ID integers"));
            }
            let mut out = Vec::new();
            for body in buffers {
                for record in records(body, true)? {
                    out.extend_from_slice(&record.0.to_be_bytes());
                }
            }
            Ok(out)
        }
        14 => {
            if buffers.len() != 1 || !integers.is_empty() {
                return Err(invalid("Invalid refresh batch"));
            }
            let rows = records(buffers[0], false)?;
            let output: Vec<Vec<u8>> = rows
                .into_iter()
                .map(|(id, payload)| {
                    let mut b = Vec::with_capacity(payload.len() + 10);
                    b.extend_from_slice(&id.to_be_bytes());
                    b.extend_from_slice(&(payload.len() as u16).to_be_bytes());
                    b.extend_from_slice(payload);
                    b
                })
                .collect();
            list(&output)
        }
        15 => resources(buffers, integers),
        _ => Err(invalid("Unknown scene binary operation")),
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    fn unpack(data: &[u8]) -> Vec<&[u8]> {
        let count = u32::from_be_bytes(data[..4].try_into().unwrap()) as usize;
        let mut at = 4;
        let mut out = Vec::new();
        for _ in 0..count {
            let n = u32::from_be_bytes(data[at..at + 4].try_into().unwrap()) as usize;
            at += 4;
            out.push(&data[at..at + n]);
            at += n;
        }
        assert_eq!(at, data.len());
        out
    }
    #[test]
    fn index_identity_tracks_revision_actual_payload_coordinates_and_entrances() {
        let pos = [(-19f64).to_be_bytes(), 18f64.to_be_bytes()].concat();
        let first = call(
            10,
            &[b"revision-a", b"entrance", &pos, b"state"],
            &[527, 1, 0, 7],
        )
        .unwrap();
        let repeated = call(
            10,
            &[b"revision-a", b"entrance", &pos, b"state"],
            &[527, 1, 0, 7],
        )
        .unwrap();
        assert_eq!(first, repeated);
        for changed in [
            call(
                10,
                &[b"revision-b", b"entrance", &pos, b"state"],
                &[527, 1, 0, 7],
            )
            .unwrap(),
            call(
                10,
                &[b"revision-a", b"entrance", &pos, b"new"],
                &[527, 1, 0, 7],
            )
            .unwrap(),
            call(
                10,
                &[b"revision-a", b"entrance", &pos, b"state"],
                &[527, 1, 1, 7, 7],
            )
            .unwrap(),
        ] {
            assert_ne!(first, changed);
        }
        let selected = call(11, &[&first], &[-2, 1, -2, 1]).unwrap();
        let rows = unpack(&selected);
        assert_eq!(rows.len(), 1);
        assert_eq!(records(rows[0], false).unwrap(), vec![(7, &b"state"[..])]);
        assert_eq!(unpack(&call(11, &[&first], &[-1, 1]).unwrap()).len(), 0);
    }
    #[test]
    fn batch_resource_encoding_preserves_signed_varints_order_and_negative_chunks() {
        let all = call(15, &[], &[-1, 2, 4275, -19, 18, -4, 2, 99, 0, 0, 0, 1]).unwrap();
        let allrows = unpack(&all);
        assert_eq!(allrows.len(), 2);
        assert_eq!(
            allrows[0],
            &[
                8, 179, 33, 16, 237, 255, 255, 255, 255, 255, 255, 255, 255, 1, 24, 18, 32, 252,
                255, 255, 255, 255, 255, 255, 255, 255, 1, 40, 2, 48, 0, 56, 0, 64, 0
            ]
        );
        let selected = call(
            15,
            &[],
            &[1, 2, -2, 1, 4275, -19, 18, -4, 2, 99, 0, 0, 0, 1],
        )
        .unwrap();
        assert_eq!(unpack(&selected), vec![allrows[0]]);
    }
    #[test]
    fn snapshot_ids_refresh_validation_and_frame_caps_share_one_codec() {
        let bodies = call(12, &[b"first", b"second"], &[7, 8]).unwrap();
        let rows = unpack(&bodies);
        assert_eq!(rows.len(), 1);
        assert_eq!(
            call(13, &[rows[0]], &[]).unwrap(),
            [7i64.to_be_bytes(), 8i64.to_be_bytes()].concat()
        );
        let refresh = call(14, &[rows[0]], &[]).unwrap();
        assert_eq!(
            unpack(&refresh)[0],
            [
                7i64.to_be_bytes().to_vec(),
                5u16.to_be_bytes().to_vec(),
                b"first".to_vec()
            ]
            .concat()
        );
        for malformed in [&b""[..], &b"\xff\xff"[..], &b"\0\x01"[..]] {
            assert!(call(14, &[malformed], &[]).is_err());
        }
        let payload = vec![0; 32767];
        let buffers = vec![payload.as_slice(); 12];
        let ids: Vec<i64> = (1..=12).collect();
        let encoded = call(12, &buffers, &ids).unwrap();
        let frames = unpack(&encoded);
        assert!(frames.len() > 1);
        assert!(frames.iter().all(|body| body.len() <= FRAME_BODY));
        assert!(call(12, &[&vec![0; 32768]], &[7]).is_err());
    }
}
