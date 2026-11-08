// The startup handshake — FED-START-E001, CProbeUsbmuxd::DoHandshake, RVA 0x303f0.
//
// Reproduces the captured outgoing startup byte-for-byte and parses the
// incoming side with zero remainder. Decoded in full from the agent; every
// quirk below is the agent's, not a choice.
#pragma once

#include <cstdint>
#include <string>

#include "hashi/bytes.hpp"

namespace hashi::startup {

inline constexpr std::uint8_t kTypeControl = 5;
inline constexpr std::uint8_t kTypeControlLegacy = 1;
inline constexpr std::uint32_t kControlPayloadLen = 12;

inline constexpr std::uint32_t kMsgHello = 1;
inline constexpr std::uint32_t kMsgHelloAck = 2;
inline constexpr std::uint32_t kMsgReady = 0xFE;
inline constexpr std::uint32_t kMsgReadyAck = 0xFF;
inline constexpr std::uint32_t kMsgExtraRequest = 0xFC;

/// The only capability key the agent inspects.
inline constexpr const char* kCapabilityDiffJpeg = "diff_jpeg";

/// 4-byte record header: ``[type, BE24 length]``.
///
/// The agent builds this as ``(htonl(len << 8) << 8) | type`` and stores it
/// little-endian (RVA 0x3055f), which is exactly this layout.
Bytes encode_header(std::uint8_t record_type, std::uint32_t payload_len);

struct HeaderFields {
  std::uint8_t record_type;
  std::uint32_t payload_len;
};
HeaderFields decode_header(const std::uint8_t* header, std::size_t len);

struct ControlRecord {
  std::uint8_t record_type;
  std::uint32_t field0;
  std::uint32_t field1;
  std::uint32_t field2;
};

/// Build one 16-byte control record.
///
/// ``raw_field1`` reproduces a real inconsistency in the agent: for the 0xfc
/// record, field 1 is written as a plain store of the literal 5 with **no**
/// htonl (RVA 0x30829), unlike every sibling field. The captured bytes show
/// field 0 big-endian and field 1 little-endian. Reproduce it; do not fix it.
Bytes encode_control(std::uint32_t field0, std::uint32_t field1 = 0,
                     std::uint32_t field2 = 0, bool network_order = true,
                     bool raw_field1 = false);

ControlRecord decode_control(const Bytes& record, bool network_order = true);

/// The 4-byte byte-order probe: the literal DWORD 4, little-endian.
Bytes encode_byte_order_probe();

/// Whether the agent would accept the probe reply. Only byte 0 is checked
/// (RVA 0x304d2); the rest of the reply is ignored.
bool probe_reply_accepted(const Bytes& reply);

/// The four host->device startup messages, in order, exactly as captured.
std::vector<Bytes> host_startup_sequence(bool network_order = true);

/// Align a client dimension as the agent does: ``((v - 1) & ~3) + 4``.
std::uint32_t align_client_dimension(std::uint32_t value);

struct Dimensions {
  std::uint32_t width;
  std::uint32_t height;
};

Dimensions parse_hello_ack(const Bytes& record, bool network_order = true);
void parse_ready_ack(const Bytes& record, bool network_order = true);

/// Announced length of the trailing extra-data block. Rejects zero, which the
/// agent logs as "recv extra data length failed".
std::uint32_t extra_data_length(const std::uint8_t* header, std::size_t len);

/// Whether the agent would enable differential JPEG from this block.
///
/// The gate is: the block parses as JSON, contains ``diff_jpeg``, that member
/// is a boolean, and it is true. The captured block (``000000fd`` + zeros) is
/// not valid JSON, so the gate cannot pass and ordinary JPEG is selected —
/// confirmed on the wire three times.
bool diff_jpeg_enabled(const Bytes& body);

}  // namespace hashi::startup
