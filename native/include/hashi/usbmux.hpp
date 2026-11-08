// usbmux transport framing — FED-USBMUX-E001.
//
// 16-byte little-endian header (length including the header, version 1,
// message 8, tag echoed) followed by an XML plist. Validated against the
// captured control exchange and used live against the device.
//
// No I/O: this builds and parses byte strings only.
#pragma once

#include <cstdint>
#include <optional>
#include <string>
#include <vector>

#include "hashi/bytes.hpp"
#include "hashi/plist.hpp"

namespace hashi::usbmux {

inline constexpr std::uint32_t kVersionPlist = 1;
inline constexpr std::uint32_t kMessagePlist = 8;
inline constexpr std::size_t kHeaderLen = 16;

/// The application port the agent connects to, in host byte order.
inline constexpr std::uint16_t kApplicationPort = 6789;

/// The iPad's USB product id (05ac:12ab).
inline constexpr std::uint16_t kIpadProductId = 0x12AB;

/// Where usbmuxd listens on Linux.
inline constexpr const char* kLinuxSocket = "/var/run/usbmuxd";

inline constexpr const char* kClientVersionString = "usbmuxd built for freedom";
inline constexpr const char* kProgName = "libusbmuxd";
inline constexpr std::int64_t kLibUsbMuxVersion = 3;

struct Header {
  std::uint32_t length;
  std::uint32_t version;
  std::uint32_t message;
  std::uint32_t tag;
};

/// The ``PortNumber`` a Connect plist must carry: the port byte-swapped.
/// 6789 becomes 34074, exactly as the capture shows.
std::uint16_t htons_port(std::uint16_t port);

Bytes encode_message(const plist::Value& payload, std::uint32_t tag);
Header decode_header(const std::uint8_t* header, std::size_t len);

/// Parse one complete message. Rejects a version or message type other than
/// the observed 1 and 8, since anything else is the binary protocol this does
/// not speak.
std::pair<std::uint32_t, plist::Value> decode_message(const Bytes& data);

Bytes build_list_devices(std::uint32_t tag = 1);
Bytes build_connect(std::int64_t device_id,
                    std::uint16_t port = kApplicationPort,
                    std::uint32_t tag = 14,
                    std::optional<std::string> bundle_id = std::nullopt);

std::int64_t parse_result(const plist::Value& payload);
bool result_is_success(const plist::Value& payload);

/// A readable name for a Result's Number. Only 0 was ever captured; the rest
/// are usbmuxd's published enum, and BADDEV was met live when the daemon had
/// reassigned the device id.
std::string result_name(const plist::Value& payload);

struct Device {
  std::int64_t device_id = 0;
  std::string serial;
  std::int64_t product_id = 0;
  std::string connection_type;
};

std::vector<Device> parse_device_list(const plist::Value& payload);

/// Pick the device to connect to. usbmuxd reassigns DeviceID on every attach,
/// so a host must discover it rather than assume one.
std::int64_t select_device(const std::vector<Device>& devices,
                           std::optional<std::uint16_t> product_id =
                               kIpadProductId);

}  // namespace hashi::usbmux
