// The steady-state loop — FED-STREAM-E001, CConnectBase.
//
// Outbound image records and the inbound TLV input channel. The outbound side
// reproduces the captured stream byte-for-byte; the inbound side was decoded
// statically and then confirmed live (FED-LIVE-E001, FED-HOST-E001).
#pragma once

#include <cstdint>
#include <optional>
#include <string>
#include <vector>

#include "hashi/bytes.hpp"

namespace hashi::stream {

/// Image record type, as observed for all 1,903 captured frames.
inline constexpr std::uint8_t kTypeImage = 6;

inline constexpr std::uint8_t kTlvType3 = 3;
inline constexpr std::uint8_t kTlvType7 = 7;

/// Payload bytes retained per record: the announced length is clamped to 12
/// (RVA 0x2fb45), so a longer record is truncated rather than rejected.
inline constexpr std::uint32_t kTlvPayloadClamp = 12;
inline constexpr std::uint32_t kTlvRingSlots = 64;

/// The agent samples only GetSystemTime's wMilliseconds, so its own elapsed
/// measurement wraps every second.
inline constexpr std::uint32_t kPacingWrapMs = 1000;

/// Pointer event kinds. **Observed live:** 5 = down, 6 = up, 10 = motion.
inline constexpr std::uint32_t kPointerDown = 5;
inline constexpr std::uint32_t kPointerUp = 6;
inline constexpr std::uint32_t kPointerMotion = 10;

/// Published Linux UAPI button codes from <linux/input-event-codes.h>.
inline constexpr std::int32_t kBtnLeft = 0x110;
inline constexpr std::int32_t kBtnRight = 0x111;
inline constexpr std::int32_t kBtnMiddle = 0x112;

Bytes encode_image_record(const Bytes& payload);

/// Target milliseconds per frame: ``1000 / fps``, truncated as the agent's
/// signed integer division truncates.
std::uint32_t frame_interval_ms(int fps);

/// Whether the agent byte-swaps a payload of this type.
///
/// ntohl is applied to all three fields **only** for type 7, and
/// unconditionally — it does not consult the negotiated byte-order flag the
/// way the header decode does. An asymmetry worth not smoothing over.
bool tlv_payload_is_network_order(std::uint8_t tlv_type);

struct TlvRecord {
  std::uint8_t tlv_type;
  std::uint32_t field0;
  std::uint32_t field1;
  std::uint32_t field2;
  bool handled;
  bool truncated;
};

TlvRecord parse_tlv_record(const std::uint8_t* header, std::size_t header_len,
                           const std::uint8_t* payload, std::size_t payload_len);

/// Reassembles TLV records from a byte stream.
///
/// A socket delivers arbitrary chunks, so records arrive split and coalesced.
/// An overlong record is consumed in full while only the first 12 bytes are
/// parsed: keeping *and* consuming 12 would leave the remainder in the stream
/// and desynchronise every later record.
class InboundDemuxer {
 public:
  static constexpr std::size_t kHeaderLen = 4;
  /// Sanity bound, not a protocol fact: 24 bits allows 16 MB, and a corrupt
  /// length would otherwise stall the loop waiting for bytes never sent.
  static constexpr std::uint32_t kMaxPayload = 4096;

  std::vector<TlvRecord> feed(const std::uint8_t* data, std::size_t len);
  std::size_t pending_bytes() const { return buffer_.size(); }
  std::uint64_t records_seen() const { return records_seen_; }
  std::uint64_t bytes_seen() const { return bytes_seen_; }

 private:
  Bytes buffer_;
  std::uint64_t records_seen_ = 0;
  std::uint64_t bytes_seen_ = 0;
};

/// The evdev button code for a field0, if it is a button event at all.
///
/// **Fact:** Mutter's NotifyPointerButton takes an evdev code
/// (meta_evdev_button_to_clutter), not a Win32 MOUSEEVENTF_* flag. 5 and 6
/// are left down/up and were observed live; 8/9 and 14/15 come from the same
/// decoded stubs but have never been seen on the wire.
std::optional<std::int32_t> evdev_button_for(std::uint32_t field0);

/// Whether a field0 presses rather than releases.
std::optional<bool> button_is_press(std::uint32_t field0);

/// Whether a field0 should produce pointer motion.
bool is_pointer_motion(std::uint32_t field0);

}  // namespace hashi::stream
