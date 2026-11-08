//! The steady-state loop: outbound image records and the inbound TLV input
//! channel (FED-STREAM-E001).

use crate::bytes::*;
use crate::startup;
use crate::{protocol_error, Result};

/// Record type for an outbound JPEG frame.
pub const TYPE_IMAGE: u8 = 6;

/// The two inbound TLV types the agent dispatches. Only 7 was ever observed.
pub const TLV_TYPE_3: u8 = 3;
pub const TLV_TYPE_7: u8 = 7;

/// The agent keeps only 12 bytes of an inbound payload, whatever its length.
pub const TLV_PAYLOAD_CLAMP: u32 = 12;
/// The agent's 64-slot ring of 12-byte records.
pub const TLV_RING_SLOTS: u32 = 64;

/// The agent's pacing numerator: it computes 1000 / fps.
pub const PACING_WRAP_MS: u32 = 1000;

pub const HEADER_LEN: usize = 4;
/// A sanity limit on an announced inbound payload. Not the agent's — it has
/// none — but a desynchronised stream should be reported rather than used to
/// allocate. 4096 matches the Python reference and the C++ port; every record
/// ever observed inbound was 16 bytes.
pub const MAX_PAYLOAD: u32 = 4096;

/// field0 values observed live.
pub const POINTER_DOWN: u32 = 5;
pub const POINTER_UP: u32 = 6;
pub const POINTER_MOTION: u32 = 10;

/// Published Linux UAPI values from `<linux/input-event-codes.h>`.
pub const BTN_LEFT: i32 = 0x110;
pub const BTN_RIGHT: i32 = 0x111;
pub const BTN_MIDDLE: i32 = 0x112;

/// Wrap a JPEG payload in its record header.
pub fn encode_image_record(payload: &[u8]) -> Result<Vec<u8>> {
    if payload.is_empty() {
        return Err(protocol_error!("image record payload is empty"));
    }
    let mut out = startup::encode_header(TYPE_IMAGE, payload.len() as u32)?;
    out.extend_from_slice(payload);
    Ok(out)
}

/// The decoded frame interval: integer division, so 30 fps gives 33 ms.
///
/// The truncation is the agent's and is kept. What is *not* kept is its clock:
/// the agent measures elapsed time from `GetSystemTime`'s `wMilliseconds`
/// alone, so its own measurement wraps every second. See [`crate::pacer`].
pub fn frame_interval_ms(fps: i32) -> Result<u32> {
    if fps <= 0 {
        return Err(protocol_error!("fps must be positive, got {fps}"));
    }
    Ok(PACING_WRAP_MS / fps as u32)
}

/// **Only type 7 payloads are byte-swapped**, and unconditionally — the decode
/// does not consult the negotiated byte-order flag the way the header decode
/// does. That asymmetry is the agent's.
pub fn tlv_payload_is_network_order(tlv_type: u8) -> bool {
    tlv_type == TLV_TYPE_7
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct TlvRecord {
    pub tlv_type: u8,
    pub field0: u32,
    pub field1: u32,
    pub field2: u32,
    /// Whether the agent dispatches this type at all.
    pub handled: bool,
    /// Whether the announced payload was longer than the 12 bytes kept.
    pub truncated: bool,
}

pub fn parse_tlv_record(header: &[u8], payload: &[u8]) -> Result<TlvRecord> {
    let fields = startup::decode_header(header)?;
    if fields.payload_len == 0 {
        return Err(protocol_error!(
            "TLV record announces a zero-length payload"
        ));
    }
    let kept = fields.payload_len.min(TLV_PAYLOAD_CLAMP) as usize;
    if payload.len() < kept {
        return Err(protocol_error!(
            "TLV payload short: need {kept} bytes, got {}",
            payload.len()
        ));
    }

    // Short payloads are zero-filled to 12, which is what reading a
    // partially-written 12-byte slot amounts to.
    let mut body = [0u8; TLV_PAYLOAD_CLAMP as usize];
    body[..kept].copy_from_slice(&payload[..kept]);

    let network = tlv_payload_is_network_order(fields.record_type);
    let read = if network { get_be32 } else { get_le32 };
    Ok(TlvRecord {
        tlv_type: fields.record_type,
        field0: read(&body[0..4])?,
        field1: read(&body[4..8])?,
        field2: read(&body[8..12])?,
        handled: fields.record_type == TLV_TYPE_3 || fields.record_type == TLV_TYPE_7,
        truncated: fields.payload_len > TLV_PAYLOAD_CLAMP,
    })
}

/// Reassembles inbound TLV records from a byte stream.
///
/// **An overlong record is consumed in full** while only the 12 bytes the
/// agent keeps are parsed. Keeping and consuming 12 would desynchronise every
/// later record — the fault that makes a stream look corrupt from the second
/// record onward.
#[derive(Debug, Default)]
pub struct InboundDemuxer {
    buffer: Vec<u8>,
    records_seen: u64,
    bytes_seen: u64,
}

impl InboundDemuxer {
    pub fn new() -> Self {
        Self::default()
    }

    pub fn feed(&mut self, data: &[u8]) -> Result<Vec<TlvRecord>> {
        self.buffer.extend_from_slice(data);
        self.bytes_seen += data.len() as u64;

        let mut out = Vec::new();
        loop {
            if self.buffer.len() < HEADER_LEN {
                break;
            }
            let fields = startup::decode_header(&self.buffer[..HEADER_LEN])?;
            if fields.payload_len == 0 {
                return Err(protocol_error!(
                    "TLV record announces a zero-length payload"
                ));
            }
            if fields.payload_len > MAX_PAYLOAD {
                return Err(protocol_error!(
                    "TLV record announces {} payload bytes, above the {}-byte \
                     sanity limit; the stream is probably desynchronised",
                    fields.payload_len,
                    MAX_PAYLOAD
                ));
            }
            let total = HEADER_LEN + fields.payload_len as usize;
            if self.buffer.len() < total {
                break;
            }
            out.push(parse_tlv_record(
                &self.buffer[..HEADER_LEN],
                &self.buffer[HEADER_LEN..total],
            )?);
            self.buffer.drain(..total);
            self.records_seen += 1;
        }
        Ok(out)
    }

    pub fn records_seen(&self) -> u64 {
        self.records_seen
    }
    pub fn bytes_seen(&self) -> u64 {
        self.bytes_seen
    }
    pub fn pending_bytes(&self) -> usize {
        self.buffer.len()
    }
}

/// The evdev button code for a field0, if it carries one.
///
/// 5 and 6 are left down/up: statically decoded from the agent's
/// MOUSEEVENTF_LEFTDOWN/LEFTUP constants and observed live. 8/9 and 14/15 are
/// **static only** — they match the documented Win32 right/middle constants
/// exactly, but no such record has ever been seen on the wire.
pub fn evdev_button_for(field0: u32) -> Option<i32> {
    match field0 {
        5 | 6 => Some(BTN_LEFT),
        8 | 9 => Some(BTN_RIGHT),
        14 | 15 => Some(BTN_MIDDLE),
        _ => None,
    }
}

pub fn button_is_press(field0: u32) -> Option<bool> {
    match field0 {
        5 | 8 | 14 => Some(true),
        6 | 9 | 15 => Some(false),
        _ => None,
    }
}

/// 10 was observed live (1,531 of 1,540 records in one run). 4 and 7 are the
/// statically decoded movement-only values and have never been seen.
pub fn is_pointer_motion(field0: u32) -> bool {
    field0 == POINTER_MOTION || field0 == 4 || field0 == 7
}
