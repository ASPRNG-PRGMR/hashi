//! Byte helpers for the HASHI wire formats.
//!
//! The protocol mixes byte orders deliberately — big-endian record lengths and
//! control fields, little-endian usbmux headers, and one field the agent
//! writes with no byte swap at all. Nothing here guesses; each helper names
//! the order it applies so a caller cannot pick one by accident.

use crate::{protocol_error, Result};

pub fn put_be16(out: &mut Vec<u8>, value: u16) {
    out.extend_from_slice(&value.to_be_bytes());
}

pub fn put_be24(out: &mut Vec<u8>, value: u32) {
    out.push((value >> 16) as u8);
    out.push((value >> 8) as u8);
    out.push(value as u8);
}

pub fn put_be32(out: &mut Vec<u8>, value: u32) {
    out.extend_from_slice(&value.to_be_bytes());
}

pub fn put_le32(out: &mut Vec<u8>, value: u32) {
    out.extend_from_slice(&value.to_le_bytes());
}

pub fn get_be24(data: &[u8]) -> Result<u32> {
    if data.len() < 3 {
        return Err(protocol_error!(
            "need 3 bytes for a BE24, got {}",
            data.len()
        ));
    }
    Ok(((data[0] as u32) << 16) | ((data[1] as u32) << 8) | data[2] as u32)
}

pub fn get_be32(data: &[u8]) -> Result<u32> {
    if data.len() < 4 {
        return Err(protocol_error!(
            "need 4 bytes for a BE32, got {}",
            data.len()
        ));
    }
    Ok(u32::from_be_bytes([data[0], data[1], data[2], data[3]]))
}

pub fn get_le32(data: &[u8]) -> Result<u32> {
    if data.len() < 4 {
        return Err(protocol_error!(
            "need 4 bytes for an LE32, got {}",
            data.len()
        ));
    }
    Ok(u32::from_le_bytes([data[0], data[1], data[2], data[3]]))
}

/// Byte-swap a 16-bit value, i.e. what `htons` does on a little-endian host.
///
/// The capture shows port 6789 carried as 34074, which is this swap. It is
/// written explicitly rather than calling a host-order helper so the value is
/// the same on a big-endian machine, where `htons` would be a no-op and would
/// therefore produce the wrong bytes for this protocol. `swap_bytes` is
/// unconditional, which is exactly what is wanted.
pub fn swap16(value: u16) -> u16 {
    value.swap_bytes()
}
