//! The startup handshake (FED-START-E001).
//!
//! The whole exchange is one function in the agent, `CProbeUsbmuxd::DoHandshake`
//! at RVA `0x303f0`. The host side reproduces the captured outgoing startup
//! bytes byte-for-byte.

use crate::bytes::*;
use crate::{protocol_error, Result};

/// Record type for a control record in the network-order dialect.
pub const TYPE_CONTROL: u8 = 5;
/// The legacy native-order dialect's record type. Decoded, never observed.
pub const TYPE_CONTROL_LEGACY: u8 = 1;
pub const CONTROL_PAYLOAD_LEN: u32 = 12;

pub const MSG_HELLO: u32 = 1;
pub const MSG_HELLO_ACK: u32 = 2;
pub const MSG_READY: u32 = 0xFE;
pub const MSG_READY_ACK: u32 = 0xFF;
pub const MSG_EXTRA_REQUEST: u32 = 0xFC;

pub const CAPABILITY_DIFF_JPEG: &str = "diff_jpeg";

/// A record header: one type byte then a 24-bit big-endian payload length.
pub fn encode_header(record_type: u8, payload_len: u32) -> Result<Vec<u8>> {
    if payload_len > 0xFF_FFFF {
        return Err(protocol_error!(
            "payload length {payload_len} does not fit in 24 bits"
        ));
    }
    let mut out = Vec::with_capacity(4);
    out.push(record_type);
    put_be24(&mut out, payload_len);
    Ok(out)
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct HeaderFields {
    pub record_type: u8,
    pub payload_len: u32,
}

pub fn decode_header(header: &[u8]) -> Result<HeaderFields> {
    if header.len() != 4 {
        return Err(protocol_error!(
            "header must be exactly 4 bytes, got {}",
            header.len()
        ));
    }
    Ok(HeaderFields {
        record_type: header[0],
        payload_len: get_be24(&header[1..])?,
    })
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct ControlRecord {
    pub record_type: u8,
    pub field0: u32,
    pub field1: u32,
    pub field2: u32,
}

/// A 16-byte control record.
///
/// `raw_field1` reproduces a real inconsistency: the `0xfc` record's field 1 is
/// stored with **no** `htonl` (RVA `0x30829`) while its siblings are
/// big-endian, which is why the capture carries a little-endian 5. Reproduce
/// it; do not fix it.
pub fn encode_control(
    field0: u32,
    field1: u32,
    field2: u32,
    network_order: bool,
    raw_field1: bool,
) -> Result<Vec<u8>> {
    let record_type = if network_order {
        TYPE_CONTROL
    } else {
        TYPE_CONTROL_LEGACY
    };
    let mut out = encode_header(record_type, CONTROL_PAYLOAD_LEN)?;
    if network_order {
        put_be32(&mut out, field0);
    } else {
        put_le32(&mut out, field0);
    }
    if network_order && !raw_field1 {
        put_be32(&mut out, field1);
    } else {
        put_le32(&mut out, field1);
    }
    if network_order {
        put_be32(&mut out, field2);
    } else {
        put_le32(&mut out, field2);
    }
    Ok(out)
}

/// `encode_control` with the common defaults: no fields, network order.
pub fn control(field0: u32) -> Result<Vec<u8>> {
    encode_control(field0, 0, 0, true, false)
}

pub fn decode_control(record: &[u8], network_order: bool) -> Result<ControlRecord> {
    if record.len() != 4 + CONTROL_PAYLOAD_LEN as usize {
        return Err(protocol_error!(
            "control record must be 16 bytes, got {}",
            record.len()
        ));
    }
    let header = decode_header(&record[..4])?;
    if header.payload_len != CONTROL_PAYLOAD_LEN {
        return Err(protocol_error!(
            "control record announces {} payload bytes, expected 12",
            header.payload_len
        ));
    }
    let p = &record[4..];
    let read = if network_order { get_be32 } else { get_le32 };
    Ok(ControlRecord {
        record_type: header.record_type,
        field0: read(&p[0..4])?,
        field1: read(&p[4..8])?,
        field2: read(&p[8..12])?,
    })
}

/// The byte-order probe: a little-endian DWORD 4.
pub fn encode_byte_order_probe() -> Vec<u8> {
    let mut out = Vec::with_capacity(4);
    put_le32(&mut out, 4);
    out
}

/// **Only byte 0 of the reply is checked**, which is what the agent does.
pub fn probe_reply_accepted(reply: &[u8]) -> bool {
    !reply.is_empty() && reply[0] == 4
}

/// The four records a host sends, in order.
pub fn host_startup_sequence(network_order: bool) -> Result<Vec<Vec<u8>>> {
    Ok(vec![
        encode_byte_order_probe(),
        encode_control(MSG_HELLO, 0, 0, network_order, false)?,
        encode_control(MSG_READY, 0, 0, network_order, false)?,
        // The raw field1 oddity lives here.
        encode_control(MSG_EXTRA_REQUEST, 5, 0, network_order, true)?,
    ])
}

/// Round a client dimension up to a multiple of 4, as the agent does:
/// `((value - 1) & ~3) + 4`.
pub fn align_client_dimension(value: u32) -> u32 {
    if value == 0 {
        return 0;
    }
    ((value - 1) & !3u32) + 4
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct Dimensions {
    pub width: u32,
    pub height: u32,
}

pub fn parse_hello_ack(record: &[u8], network_order: bool) -> Result<Dimensions> {
    let control = decode_control(record, network_order)?;
    if control.field0 != MSG_HELLO_ACK {
        return Err(protocol_error!(
            "hello ack unknown type: expected 2, got {}",
            control.field0
        ));
    }
    Ok(Dimensions {
        width: align_client_dimension(control.field1),
        height: align_client_dimension(control.field2),
    })
}

pub fn parse_ready_ack(record: &[u8], network_order: bool) -> Result<()> {
    let control = decode_control(record, network_order)?;
    if control.field0 != MSG_READY_ACK {
        return Err(protocol_error!(
            "ready ack unknown type: expected 255, got {}",
            control.field0
        ));
    }
    Ok(())
}

/// The announced length of the handshake's trailing extra-data block.
pub fn extra_data_length(header: &[u8]) -> Result<u32> {
    let fields = decode_header(header)?;
    if fields.payload_len == 0 {
        return Err(protocol_error!(
            "recv extra data length failed: announced length is zero"
        ));
    }
    Ok(fields.payload_len)
}

// ---------------------------------------------------------------------------
// The diff_jpeg capability gate
// ---------------------------------------------------------------------------
//
// A JSON scanner just large enough for the gate. It needs three things: that
// the block is a valid JSON document, that it holds a `diff_jpeg` member, and
// that the member is boolean true. A full parser is more than that needs, but
// string-matching would be less faithful: the agent genuinely parses, and a
// malformed document must fail the gate rather than appear to contain a key.
// So this validates structure while recording only the one member that matters.

struct JsonScanner<'a> {
    text: &'a [u8],
    pos: usize,
    found: bool,
    is_bool: bool,
    value: bool,
    depth: i32,
}

impl<'a> JsonScanner<'a> {
    fn new(text: &'a [u8]) -> Self {
        Self {
            text,
            pos: 0,
            found: false,
            is_bool: false,
            value: false,
            depth: 0,
        }
    }

    fn skip_space(&mut self) {
        while self.pos < self.text.len() && self.text[self.pos].is_ascii_whitespace() {
            self.pos += 1;
        }
    }

    fn literal(&mut self, word: &str) -> bool {
        let end = self.pos + word.len();
        if end <= self.text.len() && &self.text[self.pos..end] == word.as_bytes() {
            self.pos = end;
            return true;
        }
        false
    }

    fn parse_string(&mut self) -> Result<String> {
        if self.pos >= self.text.len() || self.text[self.pos] != b'"' {
            return Err(protocol_error!("expected a string"));
        }
        self.pos += 1;
        let mut out = String::new();
        while self.pos < self.text.len() {
            let c = self.text[self.pos];
            self.pos += 1;
            match c {
                b'"' => return Ok(out),
                b'\\' => {
                    if self.pos >= self.text.len() {
                        break;
                    }
                    let esc = self.text[self.pos];
                    self.pos += 1;
                    match esc {
                        b'n' => out.push('\n'),
                        b't' => out.push('\t'),
                        b'r' => out.push('\r'),
                        b'b' => out.push('\u{8}'),
                        b'f' => out.push('\u{c}'),
                        b'/' => out.push('/'),
                        b'"' => out.push('"'),
                        b'\\' => out.push('\\'),
                        b'u' => {
                            if self.pos + 4 > self.text.len() {
                                return Err(protocol_error!("bad \\u escape"));
                            }
                            // Not decoded; no key this gate cares about uses one.
                            self.pos += 4;
                            out.push('?');
                        }
                        _ => return Err(protocol_error!("bad escape in string")),
                    }
                }
                _ => out.push(c as char),
            }
        }
        Err(protocol_error!("unterminated string"))
    }

    fn parse_number(&mut self) -> Result<()> {
        let start = self.pos;
        if self.pos < self.text.len()
            && (self.text[self.pos] == b'-' || self.text[self.pos] == b'+')
        {
            self.pos += 1;
        }
        let mut digits = false;
        while self.pos < self.text.len() && self.text[self.pos].is_ascii_digit() {
            self.pos += 1;
            digits = true;
        }
        if self.pos < self.text.len() && self.text[self.pos] == b'.' {
            self.pos += 1;
            while self.pos < self.text.len() && self.text[self.pos].is_ascii_digit() {
                self.pos += 1;
                digits = true;
            }
        }
        if self.pos < self.text.len()
            && (self.text[self.pos] == b'e' || self.text[self.pos] == b'E')
        {
            self.pos += 1;
            if self.pos < self.text.len()
                && (self.text[self.pos] == b'-' || self.text[self.pos] == b'+')
            {
                self.pos += 1;
            }
            while self.pos < self.text.len() && self.text[self.pos].is_ascii_digit() {
                self.pos += 1;
            }
        }
        if !digits {
            return Err(protocol_error!("bad number at offset {start}"));
        }
        Ok(())
    }

    fn parse_value(&mut self) -> Result<()> {
        self.skip_space();
        if self.pos >= self.text.len() {
            return Err(protocol_error!("unexpected end of document"));
        }
        match self.text[self.pos] {
            b'{' => self.parse_object(),
            b'[' => self.parse_array(),
            b'"' => self.parse_string().map(|_| ()),
            _ => {
                if self.literal("true") || self.literal("false") || self.literal("null") {
                    Ok(())
                } else {
                    self.parse_number()
                }
            }
        }
    }

    fn parse_object(&mut self) -> Result<()> {
        self.pos += 1; // '{'
        self.depth += 1;
        self.skip_space();
        if self.pos < self.text.len() && self.text[self.pos] == b'}' {
            self.pos += 1;
            self.depth -= 1;
            return Ok(());
        }
        loop {
            self.skip_space();
            let key = self.parse_string()?;
            self.skip_space();
            if self.pos >= self.text.len() || self.text[self.pos] != b':' {
                return Err(protocol_error!("expected ':'"));
            }
            self.pos += 1;
            self.skip_space();

            // Only a top-level member counts: the agent reads the key off the
            // root document, not out of a nested object.
            if self.depth == 1 && key == CAPABILITY_DIFF_JPEG {
                self.found = true;
                let before = self.pos;
                if self.literal("true") {
                    self.is_bool = true;
                    self.value = true;
                } else if self.literal("false") {
                    self.is_bool = true;
                    self.value = false;
                } else {
                    self.pos = before;
                    self.is_bool = false;
                    self.parse_value()?;
                }
            } else {
                self.parse_value()?;
            }

            self.skip_space();
            if self.pos < self.text.len() && self.text[self.pos] == b',' {
                self.pos += 1;
                continue;
            }
            if self.pos < self.text.len() && self.text[self.pos] == b'}' {
                self.pos += 1;
                self.depth -= 1;
                return Ok(());
            }
            return Err(protocol_error!("expected ',' or '}}' in object"));
        }
    }

    fn parse_array(&mut self) -> Result<()> {
        self.pos += 1; // '['
        self.depth += 1;
        self.skip_space();
        if self.pos < self.text.len() && self.text[self.pos] == b']' {
            self.pos += 1;
            self.depth -= 1;
            return Ok(());
        }
        loop {
            self.parse_value()?;
            self.skip_space();
            if self.pos < self.text.len() && self.text[self.pos] == b',' {
                self.pos += 1;
                continue;
            }
            if self.pos < self.text.len() && self.text[self.pos] == b']' {
                self.pos += 1;
                self.depth -= 1;
                return Ok(());
            }
            return Err(protocol_error!("expected ',' or ']' in array"));
        }
    }
}

/// Whether the handshake's extra-data block enables differential JPEG.
///
/// The captured block is `000000fd` followed by zeros, which is not valid
/// JSON, so the parse fails and the gate stays closed — which is exactly why
/// ordinary JPEG ran. All three steps must hold: valid document, key present
/// at the top level, value boolean true.
pub fn diff_jpeg_enabled(body: &[u8]) -> bool {
    if body.is_empty() {
        return false;
    }
    let mut scanner = JsonScanner::new(body);
    scanner.skip_space();
    if scanner.pos >= body.len() {
        return false;
    }
    // "A valid JSON document must be either an array or an object value."
    let first = body[scanner.pos];
    if first != b'{' && first != b'[' {
        return false;
    }
    if scanner.parse_value().is_err() {
        return false;
    }
    scanner.found && scanner.is_bool && scanner.value
}
