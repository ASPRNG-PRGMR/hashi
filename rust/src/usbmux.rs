//! The usbmux transport: a 16-byte little-endian header plus an XML plist.
//!
//! Validated against the captured control exchange, including the byte-swapped
//! `PortNumber`: 6789 is carried as 34074.

use crate::bytes::*;
use crate::plist::{self, Dict, Value};
use crate::{protocol_error, Result};

pub const VERSION_PLIST: u32 = 1;
pub const MESSAGE_PLIST: u32 = 8;
pub const HEADER_LEN: usize = 16;

/// The port the Splashtop app listens on inside the device.
pub const APPLICATION_PORT: u16 = 6789;
pub const IPAD_PRODUCT_ID: u16 = 0x12AB;

/// Where usbmuxd listens on Linux.
pub const LINUX_SOCKET: &str = "/var/run/usbmuxd";

pub const CLIENT_VERSION_STRING: &str = "usbmuxd built for freedom";
pub const PROG_NAME: &str = "libusbmuxd";
pub const LIB_USBMUX_VERSION: i64 = 3;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct Header {
    pub length: u32,
    pub version: u32,
    pub message: u32,
    pub tag: u32,
}

/// The `PortNumber` a Connect plist must carry: the port byte-swapped.
///
/// Written as an unconditional swap rather than a host-order helper, so the
/// value is right on a big-endian machine too — where `htons` would be a
/// no-op and would produce the wrong bytes for this protocol.
pub fn htons_port(port: u16) -> Result<u16> {
    if port == 0 {
        return Err(protocol_error!("port must be 1..65535, got 0"));
    }
    Ok(swap16(port))
}

fn client_identity() -> Dict {
    let mut dict = Dict::new();
    dict.insert(
        "ClientVersionString".into(),
        Value::String(CLIENT_VERSION_STRING.into()),
    );
    dict.insert("ProgName".into(), Value::String(PROG_NAME.into()));
    dict.insert(
        "kLibUSBMuxVersion".into(),
        Value::Integer(LIB_USBMUX_VERSION),
    );
    dict
}

pub fn encode_message(payload: &Value, tag: u32) -> Vec<u8> {
    let body = plist::dumps(payload);
    let mut out = Vec::with_capacity(HEADER_LEN + body.len());
    put_le32(&mut out, (HEADER_LEN + body.len()) as u32);
    put_le32(&mut out, VERSION_PLIST);
    put_le32(&mut out, MESSAGE_PLIST);
    put_le32(&mut out, tag);
    out.extend_from_slice(body.as_bytes());
    out
}

pub fn decode_header(header: &[u8]) -> Result<Header> {
    if header.len() != HEADER_LEN {
        return Err(protocol_error!(
            "header must be exactly 16 bytes, got {}",
            header.len()
        ));
    }
    let out = Header {
        length: get_le32(&header[0..4])?,
        version: get_le32(&header[4..8])?,
        message: get_le32(&header[8..12])?,
        tag: get_le32(&header[12..16])?,
    };
    if (out.length as usize) < HEADER_LEN {
        return Err(protocol_error!(
            "length {} is shorter than the header",
            out.length
        ));
    }
    Ok(out)
}

/// Parse one complete message.
///
/// Rejects a version or message type other than the observed 1 and 8, since
/// anything else is the binary protocol this does not speak.
pub fn decode_message(data: &[u8]) -> Result<(u32, Value)> {
    if data.len() < HEADER_LEN {
        return Err(protocol_error!("message shorter than its header"));
    }
    let header = decode_header(&data[..HEADER_LEN])?;
    if header.version != VERSION_PLIST {
        return Err(protocol_error!(
            "unexpected usbmux version {}, expected {VERSION_PLIST}",
            header.version
        ));
    }
    if header.message != MESSAGE_PLIST {
        return Err(protocol_error!(
            "unexpected usbmux message type {}, expected {MESSAGE_PLIST} \
             (plist); the binary protocol is not implemented",
            header.message
        ));
    }
    if data.len() < header.length as usize {
        return Err(protocol_error!(
            "message announces {} bytes, got {}",
            header.length,
            data.len()
        ));
    }
    let body = std::str::from_utf8(&data[HEADER_LEN..header.length as usize])
        .map_err(|_| protocol_error!("message body is not UTF-8"))?;
    Ok((header.tag, plist::loads(body)?))
}

pub fn build_list_devices(tag: u32) -> Vec<u8> {
    let mut payload = client_identity();
    payload.insert("MessageType".into(), Value::String("ListDevices".into()));
    encode_message(&Value::Dict(payload), tag)
}

pub fn build_connect(
    device_id: i64,
    port: u16,
    tag: u32,
    bundle_id: Option<&str>,
) -> Result<Vec<u8>> {
    if device_id < 0 {
        return Err(protocol_error!(
            "device_id must be non-negative, got {device_id}"
        ));
    }
    let mut payload = client_identity();
    payload.insert("MessageType".into(), Value::String("Connect".into()));
    payload.insert("DeviceID".into(), Value::Integer(device_id));
    payload.insert(
        "PortNumber".into(),
        Value::Integer(htons_port(port)? as i64),
    );
    if let Some(bundle) = bundle_id {
        payload.insert("BundleID".into(), Value::String(bundle.into()));
    }
    Ok(encode_message(&Value::Dict(payload), tag))
}

pub fn parse_result(payload: &Value) -> Result<i64> {
    let number = payload.get("Number");
    if number.is_null() {
        return Err(protocol_error!("reply has no Number field"));
    }
    number.as_integer()
}

pub fn result_is_success(payload: &Value) -> bool {
    matches!(parse_result(payload), Ok(0))
}

/// A readable name for a Result's Number.
///
/// Only 0 was ever captured; the rest are usbmuxd's published enum, and
/// BADDEV was met live when the daemon had reassigned the device id.
pub fn result_name(payload: &Value) -> String {
    match parse_result(payload) {
        Ok(0) => "OK".into(),
        Ok(1) => "BADCOMMAND".into(),
        Ok(2) => "BADDEV".into(),
        Ok(3) => "CONNREFUSED".into(),
        Ok(6) => "BADVERSION".into(),
        Ok(other) => format!("UNKNOWN({other})"),
        Err(_) => "NO-RESULT".into(),
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Default)]
pub struct Device {
    pub device_id: i64,
    pub serial: String,
    pub product_id: i64,
    pub connection_type: String,
}

pub fn parse_device_list(payload: &Value) -> Result<Vec<Device>> {
    let list = payload.get("DeviceList");
    if list.is_null() {
        return Err(protocol_error!("reply has no DeviceList"));
    }
    let mut out = Vec::new();
    for entry in list.as_array()? {
        let properties = entry.get("Properties");
        let mut device = Device {
            device_id: entry.get("DeviceID").as_integer().unwrap_or(0),
            ..Default::default()
        };
        if !properties.is_null() {
            device.serial = properties
                .get("SerialNumber")
                .as_string()
                .unwrap_or("")
                .to_string();
            device.product_id = properties.get("ProductID").as_integer().unwrap_or(0);
            device.connection_type = properties
                .get("ConnectionType")
                .as_string()
                .unwrap_or("")
                .to_string();
        }
        out.push(device);
    }
    Ok(out)
}

/// Pick the device to connect to.
///
/// usbmuxd **reassigns DeviceID on every attach**, so a host must discover it
/// rather than assume one; a hard-coded id worked once here and then failed
/// with BADDEV after a reconnect.
pub fn select_device(devices: &[Device], product_id: Option<u16>) -> Result<i64> {
    if devices.is_empty() {
        return Err(protocol_error!("usbmuxd reports no attached devices"));
    }
    if let Some(wanted) = product_id {
        if let Some(found) = devices.iter().find(|d| d.product_id == wanted as i64) {
            return Ok(found.device_id);
        }
    }
    Ok(devices[0].device_id)
}
