//! Borrowed-buffer wire assembly. Domain encoders supply bytes and verified spans.
use crate::engine::NativeError;

pub const MAX_BYTES: usize = 64 * 1024 * 1024;

fn invalid(message: &'static str) -> NativeError {
    NativeError::new("invalid", message)
}

fn add_size(total: usize, size: usize) -> Result<usize, NativeError> {
    total
        .checked_add(size)
        .filter(|n| *n <= MAX_BYTES)
        .ok_or_else(|| NativeError::new("capacity", "Wire payload exceeds 64 MiB"))
}

fn allocate(size: usize) -> Result<Vec<u8>, NativeError> {
    // The binary ABI adds a status byte without allocating another payload.
    let mut result = Vec::new();
    result
        .try_reserve_exact(size + 1)
        .map_err(|_| NativeError::new("capacity", "Cannot allocate wire payload"))?;
    Ok(result)
}

fn patched_size(
    base: &[u8],
    replacements: &[&[u8]],
    integers: &[i64],
) -> Result<usize, NativeError> {
    if integers.len()
        != replacements
            .len()
            .checked_mul(2)
            .ok_or_else(|| invalid("Too many wire patches"))?
    {
        return Err(invalid(
            "Wire patch requires one start/end pair per replacement",
        ));
    }
    let mut previous = 0;
    let mut size = base.len();
    if size > MAX_BYTES {
        return Err(NativeError::new("capacity", "Wire base exceeds 64 MiB"));
    }
    for (replacement, range) in replacements.iter().zip(integers.chunks_exact(2)) {
        let start = usize::try_from(range[0]).map_err(|_| invalid("Negative wire patch offset"))?;
        let end = usize::try_from(range[1]).map_err(|_| invalid("Negative wire patch offset"))?;
        if start < previous || end < start || end > base.len() {
            return Err(invalid(
                "Wire patch ranges overlap or exceed the original base",
            ));
        }
        size -= end - start;
        size = add_size(size, replacement.len())?;
        previous = end;
    }
    Ok(size)
}

fn write_patches(result: &mut Vec<u8>, base: &[u8], replacements: &[&[u8]], integers: &[i64]) {
    let mut cursor = 0;
    for (replacement, range) in replacements.iter().zip(integers.chunks_exact(2)) {
        let start = range[0] as usize;
        let end = range[1] as usize;
        result.extend_from_slice(&base[cursor..start]);
        result.extend_from_slice(replacement);
        cursor = end;
    }
    result.extend_from_slice(&base[cursor..]);
}

fn patch(buffers: &[&[u8]], integers: &[i64]) -> Result<Vec<u8>, NativeError> {
    let Some((base, replacements)) = buffers.split_first() else {
        return Err(invalid("Wire patch requires a base buffer"));
    };
    let size = patched_size(base, replacements, integers)?;
    let mut result = allocate(size)?;
    write_patches(&mut result, base, replacements, integers);
    Ok(result)
}

fn flag(value: i64) -> Result<bool, NativeError> {
    match value {
        0 => Ok(false),
        1 => Ok(true),
        _ => Err(invalid("Invalid entity phase flag")),
    }
}

fn replace_fixed(body: &mut [u8], from: [u8; 8], to: [u8; 8]) {
    let mut offset = 0;
    while offset + 8 <= body.len() {
        if body[offset..offset + 8] == from {
            body[offset..offset + 8].copy_from_slice(&to);
            offset += 8;
        } else {
            offset += 1;
        }
    }
}

/// Sections, visible position and captured header share one reserved payload.
fn entity(buffers: &[&[u8]], integers: &[i64]) -> Result<Vec<u8>, NativeError> {
    if integers.len() < 12 {
        return Err(invalid("Missing entity pipeline arguments"));
    }
    let count =
        usize::try_from(integers[0]).map_err(|_| invalid("Invalid entity section count"))?;
    if count > 131_067 || buffers.len() != count + 5 || integers.len() != 12 + count * 2 {
        return Err(invalid("Invalid entity pipeline argument counts"));
    }
    let has_header = flag(integers[1])?;
    let has_position = flag(integers[2])?;
    let wrapper = integers[3];
    let has_map = flag(integers[8])?;
    let has_direction = flag(integers[10])?;
    if !matches!(wrapper, 0..=3) {
        return Err(invalid("Invalid entity carrier"));
    }
    let direction = if has_direction {
        Some(
            u8::try_from(integers[11])
                .ok()
                .filter(|v| *v <= 7)
                .ok_or_else(|| invalid("Invalid native world direction"))?,
        )
    } else {
        None
    };
    let base = buffers[0];
    let replacements = &buffers[1..count + 1];
    let ranges = &integers[12..];
    let expected = buffers[count + 1];
    let name = buffers[count + 2];
    let marker = buffers[count + 3];
    let new_position = buffers[count + 4];
    if has_header {
        std::str::from_utf8(expected)
            .map_err(|_| invalid("Invalid captured character name UTF-8"))?;
        std::str::from_utf8(name).map_err(|_| invalid("Invalid character name UTF-8"))?;
        if name.len() > u16::MAX as usize {
            return Err(invalid("Character name exceeds unsigned 16-bit length"));
        }
    }
    if has_position && (marker.len() != 10 || new_position.len() != 10) {
        return Err(invalid("Invalid native world position bytes"));
    }
    let size = patched_size(base, replacements, ranges)?;
    let prefix = match wrapper {
        1 => 13,
        2 => 10,
        3 => 4,
        _ => 0,
    };
    let header_size = if has_header {
        size.saturating_sub(expected.len())
            .checked_add(name.len())
            .ok_or_else(|| invalid("Invalid entity name size"))?
    } else {
        size
    };
    let capacity = add_size(size.max(header_size), prefix)?;
    let mut result = allocate(capacity)?;
    result.resize(prefix, 0);
    write_patches(&mut result, base, replacements, ranges);
    if has_position {
        let mut found = None;
        let mut offset = prefix;
        // Match bytes.count's non-overlapping semantics, including new section bytes.
        while offset + marker.len() <= result.len() {
            if &result[offset..offset + marker.len()] == marker {
                if found.is_some() {
                    return Err(invalid("Ambiguous captured position"));
                }
                found = Some(offset);
                offset += marker.len();
            } else {
                offset += 1;
            }
        }
        let offset = found.ok_or_else(|| invalid("Ambiguous captured position"))?;
        result[offset..offset + 10].copy_from_slice(new_position);
        if has_map {
            if offset + 18 > result.len() {
                return Err(invalid("Truncated native world position"));
            }
            result[offset + 10..offset + 18].copy_from_slice(&integers[9].to_be_bytes());
        }
        if let Some(direction) = direction {
            if offset + 18 >= result.len() {
                return Err(invalid("Truncated native world position"));
            }
            result[offset + 18] = direction;
        }
    }
    if has_header {
        if result.len() - prefix < 20 {
            return Err(invalid("Truncated captured character header"));
        }
        let length = u16::from_be_bytes([result[prefix + 18], result[prefix + 19]]) as usize;
        let old_end = prefix + 20 + length;
        if old_end > result.len() {
            return Err(invalid("Truncated captured character header"));
        }
        let captured = &result[prefix + 20..old_end];
        std::str::from_utf8(captured)
            .map_err(|_| invalid("Invalid captured character name UTF-8"))?;
        if captured != expected {
            return Err(invalid("Unexpected captured character header"));
        }
        replace_fixed(
            &mut result[prefix..prefix + 18],
            integers[4].to_be_bytes(),
            integers[5].to_be_bytes(),
        );
        replace_fixed(
            &mut result[prefix..prefix + 18],
            integers[6].to_be_bytes(),
            integers[7].to_be_bytes(),
        );
        let old_total = result.len();
        let new_end = prefix + 20 + name.len();
        if new_end > old_end {
            result.resize(old_total + new_end - old_end, 0);
            result.copy_within(old_end..old_total, new_end);
        } else if new_end < old_end {
            result.copy_within(old_end..old_total, new_end);
            result.truncate(old_total - (old_end - new_end));
        }
        result[prefix + 18..prefix + 20].copy_from_slice(&(name.len() as u16).to_be_bytes());
        result[prefix + 20..new_end].copy_from_slice(name);
    }
    let length = result.len() - prefix;
    match wrapper {
        1 => {
            let length = u16::try_from(length)
                .map_err(|_| invalid("Spawn entity exceeds unsigned 16-bit length"))?;
            result[..3].copy_from_slice(&[0, 1, 0]);
            result[3..11].copy_from_slice(&integers[7].to_be_bytes());
            result[11..13].copy_from_slice(&length.to_be_bytes());
        }
        2 => {
            if integers[7] <= 0 || length == 0 || length > 32767 {
                return Err(invalid("Invalid mount entity refresh"));
            }
            result[..8].copy_from_slice(&integers[7].to_be_bytes());
            result[8..10].copy_from_slice(&(length as i16).to_be_bytes());
        }
        3 => result[..4].copy_from_slice(&(length as u32).to_be_bytes()),
        _ => {}
    }
    Ok(result)
}

/// A complete character roster uses the same entity kernel in one ABI call.
fn roster(buffers: &[&[u8]], integers: &[i64]) -> Result<Vec<u8>, NativeError> {
    let count = integers
        .first()
        .copied()
        .and_then(|n| usize::try_from(n).ok())
        .filter(|n| *n <= 127)
        .ok_or_else(|| invalid("Invalid native roster count"))?;
    // Fixed bounded metadata avoids another heap allocation for row ownership.
    let mut rows: [Vec<u8>; 127] = std::array::from_fn(|_| Vec::new());
    let mut integer_cursor = 1usize;
    let mut buffer_cursor = 0usize;
    let mut size = 2;
    for row in rows.iter_mut().take(count) {
        let sections = integers
            .get(integer_cursor)
            .copied()
            .and_then(|n| usize::try_from(n).ok())
            .filter(|n| *n <= 131_067)
            .ok_or_else(|| invalid("Invalid roster entity section count"))?;
        let integer_end = integer_cursor
            .checked_add(12 + sections * 2)
            .ok_or_else(|| invalid("Invalid roster entity arguments"))?;
        let buffer_end = buffer_cursor
            .checked_add(sections + 5)
            .ok_or_else(|| invalid("Invalid roster entity arguments"))?;
        let row_integers = integers
            .get(integer_cursor..integer_end)
            .ok_or_else(|| invalid("Truncated roster entity arguments"))?;
        let row_buffers = buffers
            .get(buffer_cursor..buffer_end)
            .ok_or_else(|| invalid("Truncated roster entity buffers"))?;
        if row_integers[3] != 3 {
            return Err(invalid("Roster entity requires a length-prefixed carrier"));
        }
        *row = entity(row_buffers, row_integers)?;
        size = add_size(size, row.len())?;
        integer_cursor = integer_end;
        buffer_cursor = buffer_end;
    }
    if integer_cursor != integers.len() || buffer_cursor != buffers.len() {
        return Err(invalid("Unexpected trailing roster arguments"));
    }
    let mut result = allocate(size)?;
    result.push(count as u8);
    for row in rows.iter().take(count) {
        result.extend_from_slice(row);
    }
    result.push(0);
    Ok(result)
}

fn concatenate(buffers: &[&[u8]], integers: &[i64]) -> Result<Vec<u8>, NativeError> {
    if !integers.is_empty() {
        return Err(invalid("Wire assembly takes no integer arguments"));
    }
    let size = buffers
        .iter()
        .try_fold(0, |size, buffer| add_size(size, buffer.len()))?;
    let mut result = allocate(size)?;
    for buffer in buffers {
        result.extend_from_slice(buffer);
    }
    Ok(result)
}

/// Opcodes 2/3 assemble bytes, 4 fuses an entity, 5 batches its roster; 10..15 encode scenes.
pub fn call(op: u32, buffers: &[&[u8]], integers: &[i64]) -> Result<Vec<u8>, NativeError> {
    // This API is also called directly by Rust consumers, so retain ABI bounds here.
    if buffers.len() > 131_072 || integers.len() > 1_000_000 {
        return Err(invalid("Too many wire arguments"));
    }
    buffers
        .iter()
        .try_fold(0, |size, buffer| add_size(size, buffer.len()))?;
    let output = match op {
        2 => patch(buffers, integers),
        3 => concatenate(buffers, integers),
        4 => entity(buffers, integers),
        5 => roster(buffers, integers),
        10..=15 => crate::wire_scene::call(op, buffers, integers),
        _ => Err(invalid("Unknown native wire operation")),
    }?;
    if output.len() > MAX_BYTES {
        return Err(NativeError::new("capacity", "Wire response exceeds 64 MiB"));
    }
    Ok(output)
}

#[cfg(test)]
mod tests {
    use super::*;
    fn entity_fixture() -> (Vec<u8>, [u8; 10], [u8; 10]) {
        let marker = [0xff, 0xff, 0xff, 0xf4, 0xff, 0xff, 0xff, 0xf8, 0xff, 0xff];
        let moved = [0, 0, 0, 5, 0, 0, 0, 6, 0, 7];
        let mut base = vec![2];
        base.extend_from_slice(&2i64.to_be_bytes());
        base.push(1);
        base.extend_from_slice(&1i64.to_be_bytes());
        base.extend_from_slice(&3u16.to_be_bytes());
        base.extend_from_slice(b"old");
        base.extend_from_slice(&marker);
        base.extend_from_slice(&527i64.to_be_bytes());
        base.push(0);
        base.extend_from_slice(b"tail");
        (base, marker, moved)
    }
    #[test]
    fn fused_entity_updates_one_reserved_payload_and_all_carriers() {
        let (base, marker, moved) = entity_fixture();
        let name = "New 🦀".as_bytes();
        for wrapper in 0..=3 {
            let result = call(
                4,
                &[&base, b"old", name, &marker, &moved],
                &[0, 1, 1, wrapper, 1, 2, 2, 9, 1, -42, 1, 7],
            )
            .unwrap();
            let prefix = match wrapper {
                1 => 13,
                2 => 10,
                3 => 4,
                _ => 0,
            };
            let body = &result[prefix..];
            // Sequential replacements intentionally convert owned account 2 to actor 9.
            assert_eq!(&body[1..9], &9i64.to_be_bytes());
            assert_eq!(&body[10..18], &9i64.to_be_bytes());
            assert_eq!(
                u16::from_be_bytes([body[18], body[19]]) as usize,
                name.len()
            );
            assert_eq!(&body[20..20 + name.len()], name);
            let position = 20 + name.len();
            assert_eq!(&body[position..position + 10], &moved);
            assert_eq!(&body[position + 10..position + 18], &(-42i64).to_be_bytes());
            assert_eq!(body[position + 18], 7);
            assert_eq!(&body[position + 19..], b"tail");
            if wrapper == 1 {
                assert_eq!(&result[..3], &[0, 1, 0]);
                assert_eq!(&result[3..11], &9i64.to_be_bytes());
                assert_eq!(
                    u16::from_be_bytes([result[11], result[12]]) as usize,
                    body.len()
                );
            }
            if wrapper == 2 {
                assert_eq!(&result[..8], &9i64.to_be_bytes());
                assert_eq!(
                    i16::from_be_bytes([result[8], result[9]]) as usize,
                    body.len()
                );
            }
            if wrapper == 3 {
                assert_eq!(
                    u32::from_be_bytes(result[..4].try_into().unwrap()) as usize,
                    body.len()
                );
            }
        }
        let shorter = call(
            4,
            &[&base, b"old", b"", &marker, b""],
            &[0, 1, 0, 0, 1, 1, 2, 2, 0, 0, 0, 0],
        )
        .unwrap();
        assert_eq!(shorter.len(), base.len() - 3);
        assert_eq!(&shorter[20..30], &marker);
    }
    #[test]
    fn fused_entity_checks_patched_markers_headers_and_position_bounds() {
        let (base, marker, moved) = entity_fixture();
        let mut ints = vec![1, 1, 1, 0, 1, 1, 2, 2, 0, 0, 0, 0];
        ints.extend_from_slice(&[base.len() as i64, base.len() as i64]);
        let error = call(
            4,
            &[&base, &marker, b"wrong", b"new", &marker, &moved],
            &ints,
        )
        .unwrap_err();
        assert_eq!(error.message, "Ambiguous captured position");
        assert!(call(
            4,
            &[&base, b"wrong", b"new", &marker, &moved],
            &[0, 1, 1, 0, 1, 1, 2, 2, 0, 0, 0, 0]
        )
        .is_err());
        assert!(call(
            4,
            &[&base, b"old", b"\xff", &marker, &moved],
            &[0, 1, 1, 0, 1, 1, 2, 2, 0, 0, 0, 0]
        )
        .is_err());
        let truncated = &base[..33];
        assert!(call(
            4,
            &[truncated, b"old", b"new", &marker, &moved],
            &[0, 1, 1, 0, 1, 1, 2, 2, 1, 527, 1, 0]
        )
        .is_err());
        assert!(call(
            4,
            &[&base, b"old", b"new", &marker, &moved],
            &[0, 1, 1, 2, 1, 1, 2, 0, 0, 0, 0, 0]
        )
        .is_err());
        assert!(call(
            4,
            &[&base, b"old", b"new", &marker, &moved],
            &[0, 1, 1, 0, 1, 1, 2, 2, 0, 0, 1, 8]
        )
        .is_err());
    }
    #[test]
    fn batched_roster_reuses_entity_bytes_and_rejects_partial_or_trailing_rows() {
        let (base, marker, _) = entity_fixture();
        let row = [0, 1, 0, 3, 1, 5, 2, 7, 0, 0, 0, 0];
        let mut integers = vec![2];
        integers.extend_from_slice(&row);
        integers.extend_from_slice(&row);
        let buffers: [&[u8]; 10] = [
            &base, b"old", b"new", &marker, b"", &base, b"old", b"new", &marker, b"",
        ];
        let entry = call(4, &buffers[..5], &row).unwrap();
        assert_eq!(
            call(5, &buffers, &integers).unwrap(),
            [vec![2], entry.clone(), entry, vec![0]].concat()
        );
        assert_eq!(call(5, &[], &[0]).unwrap(), b"\0\0");
        assert!(call(5, &[], &[-1]).is_err());
        assert!(call(5, &[], &[128]).is_err());
        assert!(call(5, &buffers, &[0]).is_err());
        assert!(call(5, &[], &[0, 1]).is_err());
        assert!(call(5, &buffers[..9], &integers).is_err());
        let mut bad = integers.clone();
        bad[16] = 1;
        assert!(call(5, &buffers, &bad).is_err());
        let mut wrong_name = buffers;
        wrong_name[6] = b"other";
        assert!(call(5, &wrong_name, &integers).is_err());
        let mut extra = integers;
        extra.push(0);
        assert!(call(5, &buffers, &extra).is_err());
    }
    #[test]
    fn patches_use_original_offsets_and_allow_insertion_and_deletion() {
        assert_eq!(
            call(2, &[b"abcdefgh", b"XY", b"", b"!"], &[1, 3, 4, 6, 8, 8]).unwrap(),
            b"aXYdgh!"
        );
        assert_eq!(
            call(2, &[b"abc", b"x", b"y"], &[1, 1, 1, 1]).unwrap(),
            b"axybc"
        );
        assert_eq!(call(2, &[b"abc"], &[]).unwrap(), b"abc");
        for args in [vec![-1, 0], vec![2, 1], vec![0, 4], vec![0, i64::MAX]] {
            assert!(call(2, &[b"abc", b"x"], &args).is_err());
        }
        assert!(call(2, &[b"abc", b"x", b"y"], &[1, 3, 2, 3]).is_err());
        assert!(call(2, &[b"abc", b"x"], &[1]).is_err());
        assert!(call(2, &[], &[]).is_err());
    }
    #[test]
    fn binary_assembly_preserves_every_byte_and_rejects_unknown_operations() {
        assert_eq!(
            call(3, &[b"\x00\xff", b"", b"\x80"], &[]).unwrap(),
            b"\x00\xff\x80"
        );
        assert!(call(3, &[b"x"], &[0]).is_err());
        assert!(call(0, &[], &[]).is_err());
        assert!(add_size(MAX_BYTES, 1).is_err());
        assert!(add_size(usize::MAX, 1).is_err());
    }
}
