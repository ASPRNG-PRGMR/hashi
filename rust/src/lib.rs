//! HASHI's protocol core, in Rust.
//!
//! This is the **third** implementation of the same decoded protocol. The
//! Python modules under `python/` are the reference: they reproduced the
//! captured 130,375,177-byte outgoing stream byte-for-byte and they are what
//! drove the device in FED-LIVE-E001 and FED-HOST-E001. `native/` is the
//! C++17 port. All three are checked against each other by
//! `native/tools/conformance.py`, which diffs the **bytes** they emit rather
//! than trusting that three test suites assert similar things.
//!
//! Why a third implementation at all: three implementations agreeing on bytes
//! is worth far more than a third test suite. A test asserts what its author
//! believed; an independent implementation that lands on the same bytes is
//! evidence the decode is right.
//!
//! # Scope
//!
//! This crate covers what can be verified with no device, no compositor and
//! no bus — which is to say everything the 65 conformance byte vectors touch:
//!
//! - the usbmux header and its XML-plist subset,
//! - the startup handshake, including its deliberate byte-order oddities,
//! - record framing and the inbound TLV input decode,
//! - the JPEG frame prelude, built from published Annex K tables,
//! - Mutter's D-Bus argument construction and injection planning,
//! - the capture pipeline description, and the frame pacer.
//!
//! It does **not** contain the JPEG entropy coder (that is libjpeg-turbo), the
//! live D-Bus session, PipeWire capture, or any I/O. Those need libraries this
//! crate deliberately does not take.
//!
//! # Fidelity over tidiness
//!
//! Several things here look like bugs and are reproductions. They are marked
//! at each site. The clearest is the `0xfc` record's field 1, which the agent
//! writes with no byte swap while its siblings are big-endian. Do not "fix"
//! any of them; the captures say otherwise.

pub mod bytes;
pub mod capture;
pub mod gnome;
pub mod jpeg;
pub mod pacer;
pub mod plist;
pub mod startup;
pub mod stream;
pub mod usbmux;

/// The error type for every decode and every rejected argument.
///
/// One type, because every failure in this crate means the same thing: bytes
/// or arguments that do not match the decoded protocol.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ProtocolError(pub String);

impl std::fmt::Display for ProtocolError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(f, "{}", self.0)
    }
}

impl std::error::Error for ProtocolError {}

/// Shorthand for the crate's fallible operations.
pub type Result<T> = std::result::Result<T, ProtocolError>;

/// Build a `ProtocolError` from a format string.
#[macro_export]
macro_rules! protocol_error {
    ($($arg:tt)*) => {
        $crate::ProtocolError(format!($($arg)*))
    };
}
