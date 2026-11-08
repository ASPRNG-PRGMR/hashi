// Byte helpers for the HASHI wire formats.
//
// The protocol mixes byte orders deliberately — big-endian record lengths and
// control fields, little-endian usbmux headers, and one field the agent writes
// with no byte swap at all. Nothing here guesses; each helper names the order
// it applies so a caller cannot pick one by accident.
#pragma once

#include <cstddef>
#include <cstdint>
#include <stdexcept>
#include <string>
#include <vector>

namespace hashi {

using Bytes = std::vector<std::uint8_t>;

/// Raised when bytes do not match the decoded protocol.
class ProtocolError : public std::runtime_error {
 public:
  explicit ProtocolError(const std::string& what) : std::runtime_error(what) {}
};

inline void put_be16(Bytes& out, std::uint16_t value) {
  out.push_back(static_cast<std::uint8_t>(value >> 8));
  out.push_back(static_cast<std::uint8_t>(value));
}

inline void put_be24(Bytes& out, std::uint32_t value) {
  out.push_back(static_cast<std::uint8_t>(value >> 16));
  out.push_back(static_cast<std::uint8_t>(value >> 8));
  out.push_back(static_cast<std::uint8_t>(value));
}

inline void put_be32(Bytes& out, std::uint32_t value) {
  out.push_back(static_cast<std::uint8_t>(value >> 24));
  out.push_back(static_cast<std::uint8_t>(value >> 16));
  out.push_back(static_cast<std::uint8_t>(value >> 8));
  out.push_back(static_cast<std::uint8_t>(value));
}

inline void put_le32(Bytes& out, std::uint32_t value) {
  out.push_back(static_cast<std::uint8_t>(value));
  out.push_back(static_cast<std::uint8_t>(value >> 8));
  out.push_back(static_cast<std::uint8_t>(value >> 16));
  out.push_back(static_cast<std::uint8_t>(value >> 24));
}

inline std::uint32_t get_be24(const std::uint8_t* p) {
  return (static_cast<std::uint32_t>(p[0]) << 16) |
         (static_cast<std::uint32_t>(p[1]) << 8) |
         static_cast<std::uint32_t>(p[2]);
}

inline std::uint32_t get_be32(const std::uint8_t* p) {
  return (static_cast<std::uint32_t>(p[0]) << 24) |
         (static_cast<std::uint32_t>(p[1]) << 16) |
         (static_cast<std::uint32_t>(p[2]) << 8) |
         static_cast<std::uint32_t>(p[3]);
}

inline std::uint32_t get_le32(const std::uint8_t* p) {
  return static_cast<std::uint32_t>(p[0]) |
         (static_cast<std::uint32_t>(p[1]) << 8) |
         (static_cast<std::uint32_t>(p[2]) << 16) |
         (static_cast<std::uint32_t>(p[3]) << 24);
}

/// Byte-swap a 16-bit value, i.e. what ``htons`` does on a little-endian host.
///
/// The capture shows port 6789 carried as 34074, which is this swap. It is
/// written explicitly rather than calling ``htons`` so the value is the same
/// on a big-endian host, where ``htons`` would be a no-op and would therefore
/// produce the wrong bytes for this protocol.
inline std::uint16_t swap16(std::uint16_t value) {
  return static_cast<std::uint16_t>((value << 8) | (value >> 8));
}

inline void append(Bytes& out, const Bytes& more) {
  out.insert(out.end(), more.begin(), more.end());
}

inline void append(Bytes& out, const std::string& text) {
  out.insert(out.end(), text.begin(), text.end());
}

}  // namespace hashi
