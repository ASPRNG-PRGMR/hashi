//! The capture pipeline description.
//!
//! This crate does not link GStreamer, so what lives here is the part that is
//! pure: the pipeline string and the geometry check. Both are compared against
//! the other two implementations, which matters more than it looks — a drifted
//! property here, a missing `always-copy` or a dropped `drop=true`, changes
//! the capture's behaviour without changing a single byte on the wire, so no
//! protocol test would ever catch it.

use crate::jpeg::{OBSERVED_HEIGHT, OBSERVED_WIDTH};
use crate::{protocol_error, Result};

pub const TARGET_FPS: i32 = 30;

/// The GStreamer pipeline that turns a PipeWire node into RGB frames.
///
/// `node_id` is what `Stream.PipeWireStreamAdded` hands back; it is the `path`
/// property of `pipewiresrc`. Node ids start at 0, so 0 is valid.
///
/// `videoconvert` is unconditional: the compositor's buffers are typically
/// BGRx or BGRA. `max-buffers=1 drop=true` keeps the loop on the newest frame
/// rather than accumulating latency, which suits a display far more than
/// completeness would.
pub fn pipeline_description(node_id: i32, width: i32, height: i32, fps: i32) -> Result<String> {
    if node_id < 0 {
        return Err(protocol_error!(
            "node_id must be non-negative, got {node_id}"
        ));
    }
    if width <= 0 || height <= 0 {
        return Err(protocol_error!("invalid geometry {width}x{height}"));
    }
    if fps <= 0 {
        return Err(protocol_error!("fps must be positive, got {fps}"));
    }
    Ok(format!(
        "pipewiresrc path={node_id} always-copy=true ! videoconvert ! \
         video/x-raw,format=RGB,width={width},height={height} ! \
         appsink name=sink emit-signals=false max-buffers=1 drop=true sync=false"
    ))
}

/// Refuse a frame whose size does not match the protocol's declared size.
///
/// The 623-byte prelude encodes 1280x960 in its SOF0, so a frame of any other
/// size would be a JPEG whose dimensions disagree with the stream the device
/// was told to expect.
pub fn validate_frame_geometry(
    width: i32,
    height: i32,
    expected_width: i32,
    expected_height: i32,
) -> Result<()> {
    if width != expected_width || height != expected_height {
        return Err(protocol_error!(
            "captured frame is {width}x{height}, expected \
             {expected_width}x{expected_height}; the JPEG prelude hard-codes \
             the expected size, so this frame cannot be sent. Check the \
             virtual monitor's pinned mode and whether the compositor applied \
             a scale."
        ));
    }
    Ok(())
}

/// The observed geometry, as a convenience for callers.
pub fn observed_geometry() -> (i32, i32) {
    (OBSERVED_WIDTH, OBSERVED_HEIGHT)
}
