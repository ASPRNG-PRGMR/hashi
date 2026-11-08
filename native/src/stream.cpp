#include "hashi/stream.hpp"

#include "hashi/startup.hpp"

namespace hashi::stream {

Bytes encode_image_record(const Bytes& payload) {
  if (payload.empty()) throw ProtocolError("image record payload is empty");
  Bytes out = startup::encode_header(
      kTypeImage, static_cast<std::uint32_t>(payload.size()));
  append(out, payload);
  return out;
}

std::uint32_t frame_interval_ms(int fps) {
  if (fps <= 0) {
    throw ProtocolError("fps must be positive, got " + std::to_string(fps));
  }
  return kPacingWrapMs / static_cast<std::uint32_t>(fps);
}

bool tlv_payload_is_network_order(std::uint8_t tlv_type) {
  return tlv_type == kTlvType7;
}

TlvRecord parse_tlv_record(const std::uint8_t* header, std::size_t header_len,
                           const std::uint8_t* payload,
                           std::size_t payload_len) {
  const startup::HeaderFields fields = startup::decode_header(header, header_len);
  if (fields.payload_len == 0) {
    throw ProtocolError("TLV record announces a zero-length payload");
  }
  const std::uint32_t kept = std::min(fields.payload_len, kTlvPayloadClamp);
  if (payload_len < kept) {
    throw ProtocolError("TLV payload short: need " + std::to_string(kept) +
                        " bytes, got " + std::to_string(payload_len));
  }

  std::uint8_t body[kTlvPayloadClamp] = {0};
  for (std::uint32_t i = 0; i < kept; ++i) body[i] = payload[i];

  const bool network = tlv_payload_is_network_order(fields.record_type);
  TlvRecord out{};
  out.tlv_type = fields.record_type;
  out.field0 = network ? get_be32(body) : get_le32(body);
  out.field1 = network ? get_be32(body + 4) : get_le32(body + 4);
  out.field2 = network ? get_be32(body + 8) : get_le32(body + 8);
  out.handled = fields.record_type == kTlvType3 || fields.record_type == kTlvType7;
  out.truncated = fields.payload_len > kTlvPayloadClamp;
  return out;
}

std::vector<TlvRecord> InboundDemuxer::feed(const std::uint8_t* data,
                                            std::size_t len) {
  buffer_.insert(buffer_.end(), data, data + len);
  bytes_seen_ += len;

  std::vector<TlvRecord> out;
  for (;;) {
    if (buffer_.size() < kHeaderLen) break;
    const startup::HeaderFields fields =
        startup::decode_header(buffer_.data(), kHeaderLen);
    if (fields.payload_len == 0) {
      throw ProtocolError("TLV record announces a zero-length payload");
    }
    if (fields.payload_len > kMaxPayload) {
      throw ProtocolError(
          "TLV record announces " + std::to_string(fields.payload_len) +
          " payload bytes, above the " + std::to_string(kMaxPayload) +
          "-byte sanity limit; the stream is probably desynchronised");
    }
    const std::size_t total = kHeaderLen + fields.payload_len;
    if (buffer_.size() < total) break;

    out.push_back(parse_tlv_record(buffer_.data(), kHeaderLen,
                                   buffer_.data() + kHeaderLen,
                                   fields.payload_len));
    buffer_.erase(buffer_.begin(),
                  buffer_.begin() + static_cast<std::ptrdiff_t>(total));
    ++records_seen_;
  }
  return out;
}

std::optional<std::int32_t> evdev_button_for(std::uint32_t field0) {
  switch (field0) {
    case 5: case 6: return kBtnLeft;
    case 8: case 9: return kBtnRight;
    case 14: case 15: return kBtnMiddle;
    default: return std::nullopt;
  }
}

std::optional<bool> button_is_press(std::uint32_t field0) {
  switch (field0) {
    case 5: case 8: case 14: return true;
    case 6: case 9: case 15: return false;
    default: return std::nullopt;
  }
}

bool is_pointer_motion(std::uint32_t field0) {
  // 10 was observed live (1,531 of 1,540 records in one run). 4 and 7 are the
  // statically decoded movement-only values and have never been seen.
  return field0 == kPointerMotion || field0 == 4 || field0 == 7;
}

}  // namespace hashi::stream
