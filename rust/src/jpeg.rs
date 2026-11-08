//! The JPEG frame prelude (FED-JPEG-E001).
//!
//! All 1,903 captured image records open with an identical 623-byte prelude: a
//! 609-byte header (APP0, two DQT, SOF0, four DHT) whose SHA-256 is
//! `3aa000d1d348c7176c24fc4c1cbb12b2172bb5e95689cfeb68008d38dc5f65ad`,
//! followed by a 14-byte SOS. Only the entropy-coded scan data and the
//! trailing EOI differ between frames.
//!
//! Every byte is derivable from published standards plus two parameters, which
//! is what keeps this clean-room: the four Huffman tables are exactly the
//! ISO/IEC 10918-1 Annex K tables, the two quantization tables are the Annex K
//! base tables scaled by the standard IJG formula at quality 80, and the frame
//! is 1280x960 at 4:2:0. Nothing here transcribes vendor data.
//!
//! The table literals below were **generated from the Python reference module**
//! rather than retyped, so the implementations cannot drift by transcription.
//!
//! This module builds and parses marker bytes only. The entropy coder is
//! libjpeg-turbo, which this crate deliberately does not link.

use crate::bytes::*;
use crate::{protocol_error, Result};

pub const OBSERVED_QUALITY: i32 = 80;
pub const OBSERVED_WIDTH: i32 = 1280;
pub const OBSERVED_HEIGHT: i32 = 960;
/// JFIF APP0 density observed in every frame (units = 1, i.e. dpi).
pub const OBSERVED_DENSITY: i32 = 120;
pub const OBSERVED_HEADER_LEN: usize = 609;
pub const OBSERVED_PRELUDE_LEN: usize = 623;

pub const DC_LUMA_COUNTS: [u8; 16] = [
    0x00, 0x01, 0x05, 0x01, 0x01, 0x01, 0x01, 0x01, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
];

pub const DC_LUMA_VALUES: [u8; 12] = [
    0x00, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08, 0x09, 0x0a, 0x0b,
];

pub const DC_CHROMA_COUNTS: [u8; 16] = [
    0x00, 0x03, 0x01, 0x01, 0x01, 0x01, 0x01, 0x01, 0x01, 0x01, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00,
];

pub const DC_CHROMA_VALUES: [u8; 12] = [
    0x00, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08, 0x09, 0x0a, 0x0b,
];

pub const AC_LUMA_COUNTS: [u8; 16] = [
    0x00, 0x02, 0x01, 0x03, 0x03, 0x02, 0x04, 0x03, 0x05, 0x05, 0x04, 0x04, 0x00, 0x00, 0x01, 0x7d,
];

pub const AC_LUMA_VALUES: [u8; 162] = [
    0x01, 0x02, 0x03, 0x00, 0x04, 0x11, 0x05, 0x12, 0x21, 0x31, 0x41, 0x06, 0x13, 0x51, 0x61, 0x07,
    0x22, 0x71, 0x14, 0x32, 0x81, 0x91, 0xa1, 0x08, 0x23, 0x42, 0xb1, 0xc1, 0x15, 0x52, 0xd1, 0xf0,
    0x24, 0x33, 0x62, 0x72, 0x82, 0x09, 0x0a, 0x16, 0x17, 0x18, 0x19, 0x1a, 0x25, 0x26, 0x27, 0x28,
    0x29, 0x2a, 0x34, 0x35, 0x36, 0x37, 0x38, 0x39, 0x3a, 0x43, 0x44, 0x45, 0x46, 0x47, 0x48, 0x49,
    0x4a, 0x53, 0x54, 0x55, 0x56, 0x57, 0x58, 0x59, 0x5a, 0x63, 0x64, 0x65, 0x66, 0x67, 0x68, 0x69,
    0x6a, 0x73, 0x74, 0x75, 0x76, 0x77, 0x78, 0x79, 0x7a, 0x83, 0x84, 0x85, 0x86, 0x87, 0x88, 0x89,
    0x8a, 0x92, 0x93, 0x94, 0x95, 0x96, 0x97, 0x98, 0x99, 0x9a, 0xa2, 0xa3, 0xa4, 0xa5, 0xa6, 0xa7,
    0xa8, 0xa9, 0xaa, 0xb2, 0xb3, 0xb4, 0xb5, 0xb6, 0xb7, 0xb8, 0xb9, 0xba, 0xc2, 0xc3, 0xc4, 0xc5,
    0xc6, 0xc7, 0xc8, 0xc9, 0xca, 0xd2, 0xd3, 0xd4, 0xd5, 0xd6, 0xd7, 0xd8, 0xd9, 0xda, 0xe1, 0xe2,
    0xe3, 0xe4, 0xe5, 0xe6, 0xe7, 0xe8, 0xe9, 0xea, 0xf1, 0xf2, 0xf3, 0xf4, 0xf5, 0xf6, 0xf7, 0xf8,
    0xf9, 0xfa,
];

pub const AC_CHROMA_COUNTS: [u8; 16] = [
    0x00, 0x02, 0x01, 0x02, 0x04, 0x04, 0x03, 0x04, 0x07, 0x05, 0x04, 0x04, 0x00, 0x01, 0x02, 0x77,
];

pub const AC_CHROMA_VALUES: [u8; 162] = [
    0x00, 0x01, 0x02, 0x03, 0x11, 0x04, 0x05, 0x21, 0x31, 0x06, 0x12, 0x41, 0x51, 0x07, 0x61, 0x71,
    0x13, 0x22, 0x32, 0x81, 0x08, 0x14, 0x42, 0x91, 0xa1, 0xb1, 0xc1, 0x09, 0x23, 0x33, 0x52, 0xf0,
    0x15, 0x62, 0x72, 0xd1, 0x0a, 0x16, 0x24, 0x34, 0xe1, 0x25, 0xf1, 0x17, 0x18, 0x19, 0x1a, 0x26,
    0x27, 0x28, 0x29, 0x2a, 0x35, 0x36, 0x37, 0x38, 0x39, 0x3a, 0x43, 0x44, 0x45, 0x46, 0x47, 0x48,
    0x49, 0x4a, 0x53, 0x54, 0x55, 0x56, 0x57, 0x58, 0x59, 0x5a, 0x63, 0x64, 0x65, 0x66, 0x67, 0x68,
    0x69, 0x6a, 0x73, 0x74, 0x75, 0x76, 0x77, 0x78, 0x79, 0x7a, 0x82, 0x83, 0x84, 0x85, 0x86, 0x87,
    0x88, 0x89, 0x8a, 0x92, 0x93, 0x94, 0x95, 0x96, 0x97, 0x98, 0x99, 0x9a, 0xa2, 0xa3, 0xa4, 0xa5,
    0xa6, 0xa7, 0xa8, 0xa9, 0xaa, 0xb2, 0xb3, 0xb4, 0xb5, 0xb6, 0xb7, 0xb8, 0xb9, 0xba, 0xc2, 0xc3,
    0xc4, 0xc5, 0xc6, 0xc7, 0xc8, 0xc9, 0xca, 0xd2, 0xd3, 0xd4, 0xd5, 0xd6, 0xd7, 0xd8, 0xd9, 0xda,
    0xe2, 0xe3, 0xe4, 0xe5, 0xe6, 0xe7, 0xe8, 0xe9, 0xea, 0xf2, 0xf3, 0xf4, 0xf5, 0xf6, 0xf7, 0xf8,
    0xf9, 0xfa,
];

pub const BASE_LUMA_QTABLE: [u16; 64] = [
    16, 11, 10, 16, 24, 40, 51, 61, 12, 12, 14, 19, 26, 58, 60, 55, 14, 13, 16, 24, 40, 57, 69, 56,
    14, 17, 22, 29, 51, 87, 80, 62, 18, 22, 37, 56, 68, 109, 103, 77, 24, 35, 55, 64, 81, 104, 113,
    92, 49, 64, 78, 87, 103, 121, 120, 101, 72, 92, 95, 98, 112, 100, 103, 99,
];

pub const BASE_CHROMA_QTABLE: [u16; 64] = [
    17, 18, 24, 47, 99, 99, 99, 99, 18, 21, 26, 66, 99, 99, 99, 99, 24, 26, 56, 99, 99, 99, 99, 99,
    47, 66, 99, 99, 99, 99, 99, 99, 99, 99, 99, 99, 99, 99, 99, 99, 99, 99, 99, 99, 99, 99, 99, 99,
    99, 99, 99, 99, 99, 99, 99, 99, 99, 99, 99, 99, 99, 99, 99, 99,
];

pub const ZIGZAG: [u8; 64] = [
    0x00, 0x01, 0x08, 0x10, 0x09, 0x02, 0x03, 0x0a, 0x11, 0x18, 0x20, 0x19, 0x12, 0x0b, 0x04, 0x05,
    0x0c, 0x13, 0x1a, 0x21, 0x28, 0x30, 0x29, 0x22, 0x1b, 0x14, 0x0d, 0x06, 0x07, 0x0e, 0x15, 0x1c,
    0x23, 0x2a, 0x31, 0x38, 0x39, 0x32, 0x2b, 0x24, 0x1d, 0x16, 0x0f, 0x17, 0x1e, 0x25, 0x2c, 0x33,
    0x3a, 0x3b, 0x34, 0x2d, 0x26, 0x1f, 0x27, 0x2e, 0x35, 0x3c, 0x3d, 0x36, 0x2f, 0x37, 0x3e, 0x3f,
];

/// Scale an Annex K base table by the standard IJG quality formula.
///
/// At quality 80 this reproduces the captured tables exactly, on all 64
/// coefficients of both tables — an exact match, not an approximation.
pub fn scale_qtable(base: &[u16; 64], quality: i32) -> Result<[u8; 64]> {
    if !(1..=100).contains(&quality) {
        return Err(protocol_error!("quality must be 1..100, got {quality}"));
    }
    let scale = if quality < 50 {
        5000 / quality
    } else {
        200 - 2 * quality
    };
    let mut out = [0u8; 64];
    for (i, &value) in base.iter().enumerate() {
        // The floor of 1 keeps the table legal: a zero quantizer would be a
        // division by zero in a decoder.
        out[i] = ((value as i32 * scale + 50) / 100).clamp(1, 255) as u8;
    }
    Ok(out)
}

fn segment(marker: u8, body: &[u8]) -> Vec<u8> {
    let mut out = Vec::with_capacity(body.len() + 4);
    out.push(0xFF);
    out.push(marker);
    put_be16(&mut out, (body.len() + 2) as u16);
    out.extend_from_slice(body);
    out
}

/// One DQT segment: 8-bit precision, coefficients in zig-zag order.
pub fn build_dqt(base: &[u16; 64], table_id: u8, quality: i32) -> Result<Vec<u8>> {
    if table_id > 1 {
        return Err(protocol_error!("table_id must be 0 or 1, got {table_id}"));
    }
    let scaled = scale_qtable(base, quality)?;
    let mut body = Vec::with_capacity(65);
    body.push(table_id);
    for i in 0..64 {
        body.push(scaled[ZIGZAG[i] as usize]);
    }
    Ok(segment(0xDB, &body))
}

/// One DHT segment. `table_class` 0 = DC, 1 = AC.
pub fn build_dht(table_class: u8, table_id: u8, counts: &[u8], values: &[u8]) -> Result<Vec<u8>> {
    let total: u32 = counts.iter().map(|&c| c as u32).sum();
    if total as usize != values.len() {
        return Err(protocol_error!(
            "counts sum {total} != {} values",
            values.len()
        ));
    }
    let mut body = Vec::with_capacity(1 + counts.len() + values.len());
    body.push((table_class << 4) | table_id);
    body.extend_from_slice(counts);
    body.extend_from_slice(values);
    Ok(segment(0xC4, &body))
}

/// SOF0 for 8-bit, three-component, 4:2:0 content.
///
/// The captured SOF0 declares precision 8 and sampling factors
/// `0x22`/`0x11`/`0x11` with quantization selectors 0, 1, 1. Height precedes
/// width, which is the opposite of how the rest of this protocol orders a size.
pub fn build_sof0(width: i32, height: i32) -> Result<Vec<u8>> {
    if !(1..=0xFFFF).contains(&width) || !(1..=0xFFFF).contains(&height) {
        return Err(protocol_error!("invalid dimensions {width}x{height}"));
    }
    let mut body = Vec::with_capacity(15);
    body.push(8); // sample precision
    put_be16(&mut body, height as u16);
    put_be16(&mut body, width as u16);
    body.push(3); // three components
    body.extend_from_slice(&[1, 0x22, 0, 2, 0x11, 1, 3, 0x11, 1]);
    Ok(segment(0xC0, &body))
}

/// JFIF APP0 as observed: version 1.01, units = 1 (dpi), no thumbnail.
pub fn build_app0(density: i32) -> Result<Vec<u8>> {
    if !(1..=0xFFFF).contains(&density) {
        return Err(protocol_error!("invalid density {density}"));
    }
    let mut body = Vec::with_capacity(14);
    body.extend_from_slice(b"JFIF\0");
    body.extend_from_slice(&[1, 1, 1]); // version 1.01, units = 1
    put_be16(&mut body, density as u16);
    put_be16(&mut body, density as u16);
    body.extend_from_slice(&[0, 0]); // no thumbnail
    Ok(segment(0xE0, &body))
}

/// SOS as observed: three components, DC/AC selectors 0/0, 1/1, 1/1.
pub fn build_sos() -> Vec<u8> {
    segment(0xDA, &[3, 1, 0x00, 2, 0x11, 3, 0x11, 0, 0x3F, 0])
}

/// The full SOI..SOS prelude in the observed segment order.
///
/// That order is APP0, DQT(0), DQT(1), SOF0, DHT(0x00), DHT(0x10), DHT(0x01),
/// DHT(0x11), SOS. With the observed arguments this returns the captured 623
/// bytes exactly.
pub fn build_prelude(width: i32, height: i32, quality: i32, density: i32) -> Result<Vec<u8>> {
    let mut out = vec![0xFF, 0xD8]; // SOI
    out.extend(build_app0(density)?);
    out.extend(build_dqt(&BASE_LUMA_QTABLE, 0, quality)?);
    out.extend(build_dqt(&BASE_CHROMA_QTABLE, 1, quality)?);
    out.extend(build_sof0(width, height)?);
    out.extend(build_dht(0, 0, &DC_LUMA_COUNTS, &DC_LUMA_VALUES)?);
    out.extend(build_dht(1, 0, &AC_LUMA_COUNTS, &AC_LUMA_VALUES)?);
    out.extend(build_dht(0, 1, &DC_CHROMA_COUNTS, &DC_CHROMA_VALUES)?);
    out.extend(build_dht(1, 1, &AC_CHROMA_COUNTS, &AC_CHROMA_VALUES)?);
    out.extend(build_sos());
    Ok(out)
}

/// The prelude with every observed default.
pub fn observed_prelude() -> Result<Vec<u8>> {
    build_prelude(
        OBSERVED_WIDTH,
        OBSERVED_HEIGHT,
        OBSERVED_QUALITY,
        OBSERVED_DENSITY,
    )
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct Segment {
    pub marker: u8,
    pub offset: usize,
    pub length: usize,
}

/// Walk a frame's marker segments up to and including SOS.
pub fn parse_segments(data: &[u8]) -> Result<Vec<Segment>> {
    if data.len() < 2 || data[0] != 0xFF || data[1] != 0xD8 {
        return Err(protocol_error!("missing SOI"));
    }
    let mut out = vec![Segment {
        marker: 0xD8,
        offset: 0,
        length: 2,
    }];
    let mut i = 2usize;
    while i + 1 < data.len() {
        if data[i] != 0xFF {
            return Err(protocol_error!("expected marker at offset {i}"));
        }
        let marker = data[i + 1];
        if i + 4 > data.len() {
            return Err(protocol_error!("truncated segment at offset {i}"));
        }
        let length = ((data[i + 2] as usize) << 8) | data[i + 3] as usize;
        if length < 2 || i + 2 + length > data.len() {
            return Err(protocol_error!("bad segment length at offset {i}"));
        }
        out.push(Segment {
            marker,
            offset: i,
            length,
        });
        if marker == 0xDA {
            return Ok(out);
        }
        i += 2 + length;
    }
    Err(protocol_error!("no SOS found"))
}
