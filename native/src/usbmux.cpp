#include "hashi/usbmux.hpp"

namespace hashi::usbmux {
namespace {

plist::Dict client_identity() {
  return plist::Dict{
      {"ClientVersionString", plist::Value(kClientVersionString)},
      {"ProgName", plist::Value(kProgName)},
      {"kLibUSBMuxVersion", plist::Value(kLibUsbMuxVersion)},
  };
}

}  // namespace

std::uint16_t htons_port(std::uint16_t port) {
  if (port == 0) throw ProtocolError("port must be 1..65535, got 0");
  return swap16(port);
}

Bytes encode_message(const plist::Value& payload, std::uint32_t tag) {
  const std::string body = plist::dumps(payload);
  Bytes out;
  out.reserve(kHeaderLen + body.size());
  put_le32(out, static_cast<std::uint32_t>(kHeaderLen + body.size()));
  put_le32(out, kVersionPlist);
  put_le32(out, kMessagePlist);
  put_le32(out, tag);
  append(out, body);
  return out;
}

Header decode_header(const std::uint8_t* header, std::size_t len) {
  if (len != kHeaderLen) {
    throw ProtocolError("header must be exactly 16 bytes, got " +
                        std::to_string(len));
  }
  Header out{get_le32(header), get_le32(header + 4), get_le32(header + 8),
             get_le32(header + 12)};
  if (out.length < kHeaderLen) {
    throw ProtocolError("length " + std::to_string(out.length) +
                        " is shorter than the header");
  }
  return out;
}

std::pair<std::uint32_t, plist::Value> decode_message(const Bytes& data) {
  if (data.size() < kHeaderLen) throw ProtocolError("message is shorter than a header");
  const Header header = decode_header(data.data(), kHeaderLen);
  if (header.version != kVersionPlist) {
    throw ProtocolError("unsupported usbmux version " +
                        std::to_string(header.version));
  }
  if (header.message != kMessagePlist) {
    throw ProtocolError("unsupported usbmux message type " +
                        std::to_string(header.message));
  }
  if (data.size() < header.length) {
    throw ProtocolError("truncated message: need " +
                        std::to_string(header.length) + " bytes, got " +
                        std::to_string(data.size()));
  }
  const std::string body(data.begin() + kHeaderLen, data.begin() + header.length);
  plist::Value value = plist::loads(body);
  if (value.type() != plist::Type::Dictionary) {
    throw ProtocolError("usbmux payload is not a dictionary");
  }
  return {header.tag, value};
}

Bytes build_list_devices(std::uint32_t tag) {
  plist::Dict payload = client_identity();
  payload.emplace("MessageType", plist::Value("ListDevices"));
  return encode_message(plist::Value(std::move(payload)), tag);
}

Bytes build_connect(std::int64_t device_id, std::uint16_t port,
                    std::uint32_t tag, std::optional<std::string> bundle_id) {
  if (device_id < 0) {
    throw ProtocolError("device_id must be non-negative, got " +
                        std::to_string(device_id));
  }
  plist::Dict payload = client_identity();
  payload.emplace("MessageType", plist::Value("Connect"));
  payload.emplace("DeviceID", plist::Value(device_id));
  payload.emplace("PortNumber",
                  plist::Value(static_cast<std::int64_t>(htons_port(port))));
  if (bundle_id) payload.emplace("BundleID", plist::Value(*bundle_id));
  return encode_message(plist::Value(std::move(payload)), tag);
}

std::int64_t parse_result(const plist::Value& payload) {
  const plist::Value& type = payload.get("MessageType");
  if (type.is_null() || type.as_string() != "Result") {
    throw ProtocolError("expected a Result message");
  }
  const plist::Value& number = payload.get("Number");
  if (number.type() != plist::Type::Integer) {
    throw ProtocolError("Result has no integer Number");
  }
  return number.as_integer();
}

bool result_is_success(const plist::Value& payload) {
  return parse_result(payload) == 0;
}

std::string result_name(const plist::Value& payload) {
  switch (parse_result(payload)) {
    case 0: return "OK";
    case 1: return "BADCOMMAND";
    case 2: return "BADDEV";
    case 3: return "CONNREFUSED";
    case 6: return "BADVERSION";
    default: return "UNKNOWN(" + std::to_string(parse_result(payload)) + ")";
  }
}

std::vector<Device> parse_device_list(const plist::Value& payload) {
  const plist::Value& list = payload.get("DeviceList");
  if (list.is_null()) return {};
  if (list.type() != plist::Type::List) {
    throw ProtocolError("DeviceList is not an array");
  }
  std::vector<Device> out;
  for (const plist::Value& entry : list.as_array()) {
    Device device;
    const plist::Value& id = entry.get("DeviceID");
    if (id.type() == plist::Type::Integer) device.device_id = id.as_integer();
    const plist::Value& properties = entry.get("Properties");
    if (properties.type() == plist::Type::Dictionary) {
      const plist::Value& serial = properties.get("SerialNumber");
      if (serial.type() == plist::Type::String) device.serial = serial.as_string();
      const plist::Value& product = properties.get("ProductID");
      if (product.type() == plist::Type::Integer) {
        device.product_id = product.as_integer();
      }
      const plist::Value& connection = properties.get("ConnectionType");
      if (connection.type() == plist::Type::String) {
        device.connection_type = connection.as_string();
      }
    }
    out.push_back(std::move(device));
  }
  return out;
}

std::int64_t select_device(const std::vector<Device>& devices,
                           std::optional<std::uint16_t> product_id) {
  if (devices.empty()) {
    throw ProtocolError(
        "usbmuxd reports no devices. The iPad can be enumerated on USB and "
        "still be absent here - unlock it, make sure it trusts this host, and "
        "reopen the app; replugging the cable re-attaches it.");
  }
  std::vector<const Device*> candidates;
  for (const Device& d : devices) candidates.push_back(&d);

  if (product_id) {
    std::vector<const Device*> matching;
    for (const Device* d : candidates) {
      if (d->product_id == static_cast<std::int64_t>(*product_id)) {
        matching.push_back(d);
      }
    }
    if (!matching.empty()) candidates = std::move(matching);
  }

  std::vector<const Device*> usb;
  for (const Device* d : candidates) {
    if (d->connection_type == "USB") usb.push_back(d);
  }
  if (!usb.empty()) candidates = std::move(usb);

  return candidates.front()->device_id;
}

}  // namespace hashi::usbmux
