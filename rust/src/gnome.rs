//! Mutter's D-Bus contracts: argument construction and injection planning
//! (FED-DBUS-E001).
//!
//! Every signature and default here is the one verified three ways against
//! mutter-51.1-1.fc45 — live introspection, the `GDBusMethodInfo` tables
//! inside `libmutter-51.so.0`, and the unpatched Fedora source RPM.
//!
//! This crate links no GLib, so what it holds is the half that can be checked
//! with no compositor, no bus and no session: the arguments, and the plan a
//! single inbound input record turns into.

use std::collections::BTreeMap;

use crate::{protocol_error, Result};

pub const TARGET_WIDTH: i32 = 1280;
pub const TARGET_HEIGHT: i32 = 960;
pub const TARGET_REFRESH: f64 = 30.0;

pub const SCREEN_CAST_BUS_NAME: &str = "org.gnome.Mutter.ScreenCast";
pub const SCREEN_CAST_OBJECT_PATH: &str = "/org/gnome/Mutter/ScreenCast";
pub const REMOTE_DESKTOP_BUS_NAME: &str = "org.gnome.Mutter.RemoteDesktop";
pub const REMOTE_DESKTOP_OBJECT_PATH: &str = "/org/gnome/Mutter/RemoteDesktop";

/// The interface versions FED-DBUS-E001 verified against.
pub const VERIFIED_SCREEN_CAST_VERSION: i32 = 4;
pub const VERIFIED_REMOTE_DESKTOP_VERSION: i32 = 1;

pub const CURSOR_MODE_HIDDEN: u32 = 0;
pub const CURSOR_MODE_EMBEDDED: u32 = 1;
pub const CURSOR_MODE_METADATA: u32 = 2;

pub const DEVICE_TYPE_KEYBOARD: i32 = 1;
pub const DEVICE_TYPE_POINTER: i32 = 2;
pub const DEVICE_TYPE_TOUCHSCREEN: i32 = 4;

/// Published Linux UAPI values from `<linux/input-event-codes.h>`.
pub const BTN_LEFT: i32 = 0x110;
pub const BTN_RIGHT: i32 = 0x111;
pub const BTN_MIDDLE: i32 = 0x112;

/// One D-Bus argument or dictionary entry, carrying its signature.
///
/// Signatures are part of the data rather than inferred from the Rust type: a
/// `uint32` cursor mode and an `int32` button code are different wire types,
/// and getting those right is the whole point of this layer.
#[derive(Debug, Clone, PartialEq)]
pub enum PropValue {
    Bool(bool),
    UInt32(u32),
    Int32(i32),
    Double(f64),
    Str(String),
    /// A `(uu)` width/height pair.
    Size(u32, u32),
    /// An `aa{sv}` array of dictionaries.
    DictList(Vec<PropDict>),
}

impl PropValue {
    pub fn signature(&self) -> &'static str {
        match self {
            PropValue::Bool(_) => "b",
            PropValue::UInt32(_) => "u",
            PropValue::Int32(_) => "i",
            PropValue::Double(_) => "d",
            PropValue::Str(_) => "s",
            PropValue::Size(..) => "(uu)",
            PropValue::DictList(_) => "aa{sv}",
        }
    }
}

/// An `a{sv}`. A `BTreeMap`, so the canonical form is sorted without sorting.
pub type PropDict = BTreeMap<String, PropValue>;

/// A deterministic text form, for diffing against the other implementations.
///
/// Doubles use `{:.6}` rather than a shortest representation: the three
/// languages disagree about how to print a float, and that disagreement would
/// otherwise read as a protocol difference.
pub fn canonical_value(value: &PropValue) -> String {
    let body = match value {
        PropValue::Bool(v) => (if *v { "true" } else { "false" }).to_string(),
        PropValue::UInt32(v) => v.to_string(),
        PropValue::Int32(v) => v.to_string(),
        PropValue::Double(v) => format!("{v:.6}"),
        PropValue::Str(v) => format!("\"{v}\""),
        PropValue::Size(w, h) => format!("({w},{h})"),
        PropValue::DictList(dicts) => {
            let inner: Vec<String> = dicts.iter().map(canonical_dict).collect();
            format!("[{}]", inner.join(","))
        }
    };
    format!("{}:{}", value.signature(), body)
}

pub fn canonical_dict(dict: &PropDict) -> String {
    let body: Vec<String> = dict
        .iter()
        .map(|(key, value)| format!("{key}={}", canonical_value(value)))
        .collect();
    format!("{{{}}}", body.join(","))
}

/// Refuse to drive a Mutter whose API versions were never verified.
///
/// These are private APIs with no compatibility promise, so a mismatch is a
/// reason to stop rather than to hope. A **higher** version is rejected too:
/// Mutter could have changed the `modes` contract, and a host would have no
/// way to notice except by producing wrong-sized frames.
pub fn check_versions(screen_cast_version: i32, remote_desktop_version: i32) -> Result<()> {
    if screen_cast_version != VERIFIED_SCREEN_CAST_VERSION {
        return Err(protocol_error!(
            "ScreenCast API version {screen_cast_version} was never verified; \
             FED-DBUS-E001 checked version {VERIFIED_SCREEN_CAST_VERSION} on \
             mutter-51.1. These are private APIs with no compatibility \
             promise - re-verify the contracts before proceeding."
        ));
    }
    if remote_desktop_version != VERIFIED_REMOTE_DESKTOP_VERSION {
        return Err(protocol_error!(
            "RemoteDesktop API version {remote_desktop_version} was never \
             verified; FED-DBUS-E001 checked version \
             {VERIFIED_REMOTE_DESKTOP_VERSION} on mutter-51.1."
        ));
    }
    Ok(())
}

pub fn supports_device_types(supported: i32, required: i32) -> bool {
    supported & required == required
}

/// One entry of `RecordVirtual`'s `modes` array.
///
/// A refresh rate of 0 omits the key, which makes Mutter default it to 60.0.
pub fn virtual_monitor_mode(
    width: i32,
    height: i32,
    refresh_rate: f64,
    is_preferred: bool,
) -> Result<PropDict> {
    if width <= 0 || height <= 0 {
        return Err(protocol_error!(
            "mode {width}x{height} has a non-positive dimension; Mutter \
             rejects these as 'Invalid mode'"
        ));
    }
    let mut mode = PropDict::new();
    mode.insert("size".into(), PropValue::Size(width as u32, height as u32));
    if refresh_rate != 0.0 {
        if refresh_rate < 0.0 {
            return Err(protocol_error!("refresh rate must be positive"));
        }
        mode.insert("refresh-rate".into(), PropValue::Double(refresh_rate));
    }
    mode.insert("is-preferred".into(), PropValue::Bool(is_preferred));
    Ok(mode)
}

/// The observed default mode: 1280x960 at 30 Hz, preferred.
pub fn observed_mode() -> Result<PropDict> {
    virtual_monitor_mode(TARGET_WIDTH, TARGET_HEIGHT, TARGET_REFRESH, true)
}

/// The properties dictionary for `Session.RecordVirtual`.
///
/// **The `modes` key pins the size.** Without it the PipeWire stream is
/// resizable and the monitor is created at whatever size the *consumer*
/// negotiates; with it the monitor is created up front and negotiation cannot
/// resize it. The JPEG prelude hard-codes 1280x960, so a pinned mode turns a
/// whole class of size mismatch into an impossibility.
///
/// *Embedded* is the right cursor default here, not Mutter's own default of
/// hidden: the protocol has no cursor channel, so compositing the cursor into
/// the frames is the only way the iPad can show one.
///
/// `is_platform` is three-state — `None` leaves the key out, which is the
/// default. Setting it true asks Mutter to treat the output as a real monitor
/// rather than a shared screen, but that also suppresses the sharing
/// indicator, so it stays the user's decision rather than this layer's.
pub fn record_virtual_properties(
    modes: &[PropDict],
    cursor_mode: u32,
    is_platform: Option<bool>,
) -> Result<PropDict> {
    if ![
        CURSOR_MODE_HIDDEN,
        CURSOR_MODE_EMBEDDED,
        CURSOR_MODE_METADATA,
    ]
    .contains(&cursor_mode)
    {
        return Err(protocol_error!(
            "unknown cursor mode {cursor_mode}; Mutter accepts 0, 1 or 2"
        ));
    }
    let effective: Vec<PropDict> = if modes.is_empty() {
        vec![observed_mode()?]
    } else {
        modes.to_vec()
    };

    // Mutter's create_mode_infos rejects both 'Multiple preferred modes' and
    // 'No preferred modes', so the count is checked here where the message can
    // name the caller's mistake.
    let preferred = effective
        .iter()
        .filter(|mode| matches!(mode.get("is-preferred"), Some(PropValue::Bool(true))))
        .count();
    if preferred != 1 {
        return Err(protocol_error!(
            "exactly one mode must be preferred, got {preferred}; Mutter \
             rejects 'Multiple preferred modes' and 'No preferred modes'"
        ));
    }

    let mut properties = PropDict::new();
    properties.insert("modes".into(), PropValue::DictList(effective));
    properties.insert("cursor-mode".into(), PropValue::UInt32(cursor_mode));
    if let Some(flag) = is_platform {
        properties.insert("is-platform".into(), PropValue::Bool(flag));
    }
    Ok(properties)
}

/// The properties dictionary for `ScreenCast.CreateSession`.
///
/// The XML documents exactly two keys: `remote-desktop-session-id` (s) and
/// `disable-animations` (b). `RemoteDesktop.CreateSession` by contrast takes
/// **no arguments at all**.
pub fn screen_cast_session_properties(
    remote_desktop_session_id: &str,
    disable_animations: Option<bool>,
) -> PropDict {
    let mut properties = PropDict::new();
    if !remote_desktop_session_id.is_empty() {
        properties.insert(
            "remote-desktop-session-id".into(),
            PropValue::Str(remote_desktop_session_id.to_string()),
        );
    }
    if let Some(flag) = disable_animations {
        properties.insert("disable-animations".into(), PropValue::Bool(flag));
    }
    properties
}

/// One call to make on `org.gnome.Mutter.RemoteDesktop.Session`.
///
/// Kept as data rather than performed immediately, so a plan can be asserted
/// against the observed records with no session and no compositor.
#[derive(Debug, Clone, PartialEq)]
pub struct InjectionCall {
    pub method: String,
    pub args: Vec<PropValue>,
}

pub fn canonical_call(call: &InjectionCall) -> String {
    let args: Vec<String> = call.args.iter().map(canonical_value).collect();
    format!("{}({})", call.method, args.join(","))
}

pub fn canonical_plan(calls: &[InjectionCall]) -> String {
    let inner: Vec<String> = calls.iter().map(canonical_call).collect();
    format!("[{}]", inner.join(","))
}

/// The evdev button code for a field0, if it carries one.
///
/// 5 and 6 are left down/up, statically decoded and observed live. 8/9 and
/// 14/15 are **static only** and have never been seen on the wire.
pub fn evdev_button_for_field0(field0: i32) -> Option<i32> {
    match field0 {
        5 | 6 => Some(BTN_LEFT),
        8 | 9 => Some(BTN_RIGHT),
        14 | 15 => Some(BTN_MIDDLE),
        _ => None,
    }
}

fn field0_pressed(field0: i32) -> bool {
    matches!(field0, 5 | 8 | 14)
}

/// Translate one inbound input record into RemoteDesktop calls.
///
/// `x` and `y` are monitor-relative pixels in the display's own 1280x960 space
/// and **pass straight through**: for a virtual stream the whole of
/// `meta_stream_transform_position` is a translation by the monitor's position
/// in the stage, with no scaling and no normalisation. The Windows agent's
/// 65535 virtual-desktop transform has no Linux equivalent to reproduce.
///
/// A button event is preceded by a motion call, because the iPad sends
/// coordinates with every record and a tap arrives as a bare 5 -> 6 with no
/// motion record before it. Pressing without moving first would land the press
/// wherever the pointer happened to be.
///
/// Returns an empty plan for a field0 with no pointer meaning. Those values
/// are decoded but unexercised, and a host does not invent behaviour for them.
pub fn plan_injection(
    field0: i32,
    x: i32,
    y: i32,
    stream_path: &str,
    width: i32,
    height: i32,
) -> Result<Vec<InjectionCall>> {
    if stream_path.is_empty() {
        return Err(protocol_error!(
            "stream_path is required; it is the 'stream' argument"
        ));
    }
    if x < 0 || x > width || y < 0 || y > height {
        return Err(protocol_error!(
            "coordinate ({x}, {y}) is outside the {width}x{height} display; \
             FED-LIVE-E001 observed every value inside it, so this is a decode \
             or configuration fault rather than something to clamp"
        ));
    }

    let motion = InjectionCall {
        method: "NotifyPointerMotionAbsolute".into(),
        args: vec![
            PropValue::Str(stream_path.to_string()),
            PropValue::Double(x as f64),
            PropValue::Double(y as f64),
        ],
    };

    if let Some(button) = evdev_button_for_field0(field0) {
        return Ok(vec![
            motion,
            InjectionCall {
                method: "NotifyPointerButton".into(),
                args: vec![
                    PropValue::Int32(button),
                    PropValue::Bool(field0_pressed(field0)),
                ],
            },
        ]);
    }

    // field0 10 is motion (1,368 of 1,449 records in one observed run). 4 and
    // 7 are the statically decoded movement-only values, which take the same
    // mouse path with no button stub; neither has been observed.
    if field0 == 10 || field0 == 4 || field0 == 7 {
        return Ok(vec![motion]);
    }

    Ok(Vec::new())
}
