// C++ core tests, mirroring the Python suite's vectors.
//
// Where the Python tests assert against values taken from the captures, these
// assert the same values, so the two implementations are checked against one
// source of truth rather than against each other.
#include "testing.hpp"

#include "hashi/plist.hpp"
#include "hashi/startup.hpp"
#include "hashi/stream.hpp"
#include "hashi/usbmux.hpp"

using namespace hashi;

// ---------------------------------------------------------------------------
// plist
// ---------------------------------------------------------------------------

TEST("plist: a dict round-trips") {
  plist::Dict dict;
  dict.emplace("MessageType", plist::Value("Connect"));
  dict.emplace("DeviceID", plist::Value(static_cast<std::int64_t>(1)));
  const std::string xml = plist::dumps(plist::Value(dict));
  const plist::Value back = plist::loads(xml);
  CHECK_EQ(back.get("MessageType").as_string(), std::string("Connect"));
  CHECK_EQ(back.get("DeviceID").as_integer(), 1);
}

TEST("plist: the document carries the XML declaration and DOCTYPE") {
  const std::string xml = plist::dumps(plist::Value(plist::Dict{}));
  CHECK(xml.rfind("<?xml version=\"1.0\" encoding=\"UTF-8\"?>", 0) == 0);
  CHECK(xml.find("<!DOCTYPE plist PUBLIC") != std::string::npos);
  CHECK(xml.find("<plist version=\"1.0\">") != std::string::npos);
}

TEST("plist: booleans and nesting round-trip") {
  plist::Dict inner;
  inner.emplace("ConnectionType", plist::Value("USB"));
  inner.emplace("ProductID", plist::Value(static_cast<std::int64_t>(0x12AB)));
  plist::Dict outer;
  outer.emplace("Properties", plist::Value(inner));
  outer.emplace("Flag", plist::Value(true));
  const plist::Value back = plist::loads(plist::dumps(plist::Value(outer)));
  CHECK_EQ(back.get("Properties").get("ConnectionType").as_string(),
           std::string("USB"));
  CHECK_EQ(back.get("Properties").get("ProductID").as_integer(), 0x12AB);
  CHECK_EQ(back.get("Flag").as_bool(), true);
}

TEST("plist: an array of dicts parses, as ListDevices replies need") {
  const std::string xml =
      "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n"
      "<plist version=\"1.0\"><dict><key>DeviceList</key><array>"
      "<dict><key>DeviceID</key><integer>7</integer>"
      "<key>Properties</key><dict>"
      "<key>SerialNumber</key><string>abc</string>"
      "<key>ProductID</key><integer>4779</integer>"
      "<key>ConnectionType</key><string>USB</string>"
      "</dict></dict></array></dict></plist>";
  const plist::Value value = plist::loads(xml);
  const plist::Array& list = value.get("DeviceList").as_array();
  CHECK_EQ(list.size(), std::size_t{1});
  CHECK_EQ(list[0].get("DeviceID").as_integer(), 7);
}

TEST("plist: an empty DeviceList parses to an empty array") {
  const plist::Value value = plist::loads(
      "<plist version=\"1.0\"><dict><key>DeviceList</key><array/>"
      "</dict></plist>");
  CHECK_EQ(value.get("DeviceList").as_array().size(), std::size_t{0});
}

TEST("plist: escaping survives a round trip") {
  plist::Dict dict;
  dict.emplace("k", plist::Value("a & b < c > d"));
  const plist::Value back = plist::loads(plist::dumps(plist::Value(dict)));
  CHECK_EQ(back.get("k").as_string(), std::string("a & b < c > d"));
}

TEST("plist: a missing key reads as null rather than throwing") {
  const plist::Value value = plist::loads(
      "<plist version=\"1.0\"><dict><key>a</key><integer>1</integer>"
      "</dict></plist>");
  CHECK(value.get("absent").is_null());
}

TEST("plist: malformed documents are rejected") {
  CHECK_THROWS(plist::loads("not xml at all"));
  CHECK_THROWS(plist::loads("<plist version=\"1.0\"><dict><key>a</key>"));
}

// ---------------------------------------------------------------------------
// usbmux
// ---------------------------------------------------------------------------

TEST("usbmux: the application port becomes the captured value") {
  // 6789 (0x1a85) -> 34074 (0x851a), exactly as the capture shows.
  CHECK_EQ(usbmux::htons_port(usbmux::kApplicationPort), std::uint16_t{34074});
}

TEST("usbmux: the swap is its own inverse") {
  CHECK_EQ(usbmux::htons_port(usbmux::htons_port(6789)), std::uint16_t{6789});
}

TEST("usbmux: port zero is rejected") {
  CHECK_THROWS(usbmux::htons_port(0));
}

TEST("usbmux: the header matches the observed shape") {
  const Bytes msg = usbmux::build_list_devices(1);
  const usbmux::Header header = usbmux::decode_header(msg.data(), 16);
  CHECK_EQ(header.length, static_cast<std::uint32_t>(msg.size()));
  CHECK_EQ(header.version, usbmux::kVersionPlist);
  CHECK_EQ(header.message, usbmux::kMessagePlist);
  CHECK_EQ(header.tag, std::uint32_t{1});
}

TEST("usbmux: the header is little-endian") {
  const Bytes msg = usbmux::build_list_devices(0x01020304);
  CHECK_EQ(msg[12], std::uint8_t{0x04});
  CHECK_EQ(msg[15], std::uint8_t{0x01});
}

TEST("usbmux: a short header is rejected") {
  const Bytes msg = usbmux::build_list_devices();
  CHECK_THROWS(usbmux::decode_header(msg.data(), 15));
}

TEST("usbmux: Connect round-trips with the swapped port") {
  const Bytes msg = usbmux::build_connect(1);
  const auto [tag, payload] = usbmux::decode_message(msg);
  CHECK_EQ(tag, std::uint32_t{14});
  CHECK_EQ(payload.get("MessageType").as_string(), std::string("Connect"));
  CHECK_EQ(payload.get("DeviceID").as_integer(), 1);
  CHECK_EQ(payload.get("PortNumber").as_integer(), 34074);
}

TEST("usbmux: Connect identifies the client as observed") {
  const auto [tag, payload] = usbmux::decode_message(usbmux::build_connect(1));
  (void)tag;
  CHECK_EQ(payload.get("ClientVersionString").as_string(),
           std::string(usbmux::kClientVersionString));
  CHECK_EQ(payload.get("ProgName").as_string(), std::string(usbmux::kProgName));
  CHECK_EQ(payload.get("kLibUSBMuxVersion").as_integer(), 3);
}

TEST("usbmux: BundleID is optional") {
  auto [t1, without] = usbmux::decode_message(usbmux::build_connect(1));
  (void)t1;
  CHECK(without.get("BundleID").is_null());
  auto [t2, with] = usbmux::decode_message(
      usbmux::build_connect(1, usbmux::kApplicationPort, 14, std::string("x")));
  (void)t2;
  CHECK_EQ(with.get("BundleID").as_string(), std::string("x"));
}

TEST("usbmux: a negative device id is rejected") {
  CHECK_THROWS(usbmux::build_connect(-1));
}

TEST("usbmux: a wrong version or message type is rejected") {
  Bytes msg = usbmux::build_list_devices();
  Bytes bad_version = msg;
  bad_version[4] = 9;
  CHECK_THROWS(usbmux::decode_message(bad_version));
  Bytes bad_message = msg;
  bad_message[8] = 9;
  CHECK_THROWS(usbmux::decode_message(bad_message));
}

TEST("usbmux: a truncated message is rejected") {
  Bytes msg = usbmux::build_list_devices();
  msg.resize(msg.size() - 5);
  CHECK_THROWS(usbmux::decode_message(msg));
}

TEST("usbmux: zero is success and non-zero is not") {
  const plist::Value ok = plist::loads(
      "<plist version=\"1.0\"><dict><key>MessageType</key><string>Result"
      "</string><key>Number</key><integer>0</integer></dict></plist>");
  CHECK(usbmux::result_is_success(ok));
  CHECK_EQ(usbmux::result_name(ok), std::string("OK"));

  const plist::Value bad = plist::loads(
      "<plist version=\"1.0\"><dict><key>MessageType</key><string>Result"
      "</string><key>Number</key><integer>2</integer></dict></plist>");
  CHECK(!usbmux::result_is_success(bad));
  // Met live when usbmuxd had reassigned the device id.
  CHECK_EQ(usbmux::result_name(bad), std::string("BADDEV"));
}

TEST("usbmux: a non-Result reply is rejected") {
  const plist::Value other = plist::loads(
      "<plist version=\"1.0\"><dict><key>MessageType</key>"
      "<string>Attached</string></dict></plist>");
  CHECK_THROWS(usbmux::parse_result(other));
}

TEST("usbmux: the device list is flattened") {
  const plist::Value value = plist::loads(
      "<plist version=\"1.0\"><dict><key>DeviceList</key><array><dict>"
      "<key>DeviceID</key><integer>7</integer><key>Properties</key><dict>"
      "<key>SerialNumber</key><string>abc</string>"
      "<key>ProductID</key><integer>4779</integer>"
      "<key>ConnectionType</key><string>USB</string>"
      "</dict></dict></array></dict></plist>");
  const auto devices = usbmux::parse_device_list(value);
  CHECK_EQ(devices.size(), std::size_t{1});
  CHECK_EQ(devices[0].device_id, 7);
  CHECK_EQ(devices[0].product_id, 0x12AB);
  CHECK_EQ(devices[0].connection_type, std::string("USB"));
  CHECK_EQ(usbmux::select_device(devices), 7);
}

TEST("usbmux: selecting from no devices explains how to fix it") {
  bool threw = false;
  try {
    usbmux::select_device({});
  } catch (const ProtocolError& e) {
    threw = true;
    CHECK(std::string(e.what()).find("unlock") != std::string::npos);
  }
  CHECK(threw);
}

TEST("usbmux: selection prefers the iPad and USB") {
  std::vector<usbmux::Device> devices = {
      {3, "a", 0x1234, "USB"},
      {9, "b", 0x12AB, "USB"},
  };
  CHECK_EQ(usbmux::select_device(devices), 9);

  std::vector<usbmux::Device> mixed = {
      {4, "a", 0x12AB, "Network"},
      {5, "b", 0x12AB, "USB"},
  };
  CHECK_EQ(usbmux::select_device(mixed), 5);
}

// ---------------------------------------------------------------------------
// startup
// ---------------------------------------------------------------------------

TEST("startup: the header is type byte then BE24 length") {
  const Bytes header = startup::encode_header(5, 12);
  CHECK_EQ(header, (Bytes{0x05, 0x00, 0x00, 0x0C}));
  const auto fields = startup::decode_header(header.data(), 4);
  CHECK_EQ(fields.record_type, std::uint8_t{5});
  CHECK_EQ(fields.payload_len, std::uint32_t{12});
}

TEST("startup: a length above 24 bits is rejected") {
  CHECK_THROWS(startup::encode_header(6, 0x1000000));
}

TEST("startup: the byte-order probe is a little-endian DWORD 4") {
  CHECK_EQ(startup::encode_byte_order_probe(),
           (Bytes{0x04, 0x00, 0x00, 0x00}));
}

TEST("startup: only byte 0 of the probe reply is checked") {
  CHECK(startup::probe_reply_accepted(Bytes{4, 0xFF, 0xFF, 0xFF}));
  CHECK(!startup::probe_reply_accepted(Bytes{5, 0, 0, 0}));
  CHECK(!startup::probe_reply_accepted(Bytes{}));
}

TEST("startup: HELLO encodes big-endian in network order") {
  const Bytes hello = startup::encode_control(startup::kMsgHello);
  CHECK_EQ(hello, (Bytes{0x05, 0x00, 0x00, 0x0C,
                         0x00, 0x00, 0x00, 0x01,
                         0x00, 0x00, 0x00, 0x00,
                         0x00, 0x00, 0x00, 0x00}));
}

TEST("startup: the 0xfc record writes field1 little-endian") {
  // The agent's own inconsistency: field 0 is big-endian 0xfc while field 1
  // is a plain store of the literal 5 with no htonl. Reproduce, do not fix.
  const Bytes record =
      startup::encode_control(startup::kMsgExtraRequest, 5, 0, true, true);
  CHECK_EQ(record, (Bytes{0x05, 0x00, 0x00, 0x0C,
                          0x00, 0x00, 0x00, 0xFC,
                          0x05, 0x00, 0x00, 0x00,
                          0x00, 0x00, 0x00, 0x00}));
}

TEST("startup: the legacy native-order record uses type 1") {
  const Bytes record = startup::encode_control(startup::kMsgHello, 0, 0, false);
  CHECK_EQ(record[0], startup::kTypeControlLegacy);
  CHECK_EQ(record[4], std::uint8_t{0x01});  // little-endian field0
}

TEST("startup: the host sequence is the four captured messages in order") {
  const auto sequence = startup::host_startup_sequence();
  CHECK_EQ(sequence.size(), std::size_t{4});
  CHECK_EQ(sequence[0], startup::encode_byte_order_probe());
  CHECK_EQ(startup::decode_control(sequence[1]).field0, startup::kMsgHello);
  CHECK_EQ(startup::decode_control(sequence[2]).field0, startup::kMsgReady);
  CHECK_EQ(startup::decode_control(sequence[3]).field0, startup::kMsgExtraRequest);
}

TEST("startup: client dimensions align as ((v-1) & ~3) + 4") {
  CHECK_EQ(startup::align_client_dimension(2048), std::uint32_t{2048});
  CHECK_EQ(startup::align_client_dimension(1536), std::uint32_t{1536});
  CHECK_EQ(startup::align_client_dimension(1), std::uint32_t{4});
  CHECK_EQ(startup::align_client_dimension(5), std::uint32_t{8});
  CHECK_EQ(startup::align_client_dimension(8), std::uint32_t{8});
}

TEST("startup: HELLO ACK yields the observed 2048x1536") {
  Bytes record = startup::encode_control(startup::kMsgHelloAck, 2048, 1536);
  const auto dims = startup::parse_hello_ack(record);
  CHECK_EQ(dims.width, std::uint32_t{2048});
  CHECK_EQ(dims.height, std::uint32_t{1536});
}

TEST("startup: a HELLO ACK with the wrong field0 is rejected") {
  Bytes record = startup::encode_control(99, 2048, 1536);
  CHECK_THROWS(startup::parse_hello_ack(record));
}

TEST("startup: READY ACK requires 0xff") {
  startup::parse_ready_ack(startup::encode_control(startup::kMsgReadyAck));
  CHECK_THROWS(startup::parse_ready_ack(startup::encode_control(1)));
}

TEST("startup: a zero extra-data length is rejected") {
  const Bytes header = startup::encode_header(5, 0);
  CHECK_THROWS(startup::extra_data_length(header.data(), 4));
  const Bytes ok = startup::encode_header(5, 12);
  CHECK_EQ(startup::extra_data_length(ok.data(), 4), std::uint32_t{12});
}

TEST("startup: the captured extra-data block does not enable diff_jpeg") {
  // 000000fd followed by zeros - not valid JSON, so the gate cannot pass.
  // This is why ordinary JPEG is the operative path, confirmed three times
  // on the wire.
  Bytes observed{0x00, 0x00, 0x00, 0xFD, 0, 0, 0, 0, 0, 0, 0, 0};
  CHECK(!startup::diff_jpeg_enabled(observed));
}

TEST("startup: the diff_jpeg gate needs present, boolean and true") {
  auto body = [](const char* s) {
    return Bytes(s, s + std::char_traits<char>::length(s));
  };
  CHECK(startup::diff_jpeg_enabled(body("{\"diff_jpeg\": true}")));
  CHECK(!startup::diff_jpeg_enabled(body("{\"diff_jpeg\": false}")));
  CHECK(!startup::diff_jpeg_enabled(body("{\"diff_jpeg\": 1}")));
  CHECK(!startup::diff_jpeg_enabled(body("{\"diff_jpeg\": \"true\"}")));
  CHECK(!startup::diff_jpeg_enabled(body("{\"other\": true}")));
  CHECK(!startup::diff_jpeg_enabled(body("{}")));
  CHECK(!startup::diff_jpeg_enabled(body("")));
  // "A valid JSON document must be either an array or an object value."
  CHECK(!startup::diff_jpeg_enabled(body("true")));
  CHECK(!startup::diff_jpeg_enabled(body("{\"diff_jpeg\": true")));
}

TEST("startup: a nested diff_jpeg does not pass the gate") {
  const char* s = "{\"caps\": {\"diff_jpeg\": true}}";
  CHECK(!startup::diff_jpeg_enabled(Bytes(s, s + std::char_traits<char>::length(s))));
}

// ---------------------------------------------------------------------------
// stream
// ---------------------------------------------------------------------------

TEST("stream: an image record carries tag 6 and a BE24 length") {
  const Bytes payload{0xFF, 0xD8, 0x00, 0xFF, 0xD9};
  const Bytes record = stream::encode_image_record(payload);
  CHECK_EQ(record[0], stream::kTypeImage);
  CHECK_EQ(get_be24(record.data() + 1), std::uint32_t{5});
  CHECK_EQ(record.size(), std::size_t{9});
}

TEST("stream: the frame interval truncates as the agent's division does") {
  CHECK_EQ(stream::frame_interval_ms(30), std::uint32_t{33});
  CHECK_EQ(stream::frame_interval_ms(60), std::uint32_t{16});
  CHECK_THROWS(stream::frame_interval_ms(0));
}

TEST("stream: only type 7 payloads are byte-swapped") {
  CHECK(stream::tlv_payload_is_network_order(7));
  CHECK(!stream::tlv_payload_is_network_order(3));
}

TEST("stream: the observed inbound record parses") {
  // 07 00 00 0c | field0 | x | y, big-endian - the exact shape of all 1,540
  // records observed in FED-HOST-E001.
  const std::uint8_t header[4] = {0x07, 0x00, 0x00, 0x0C};
  const std::uint8_t payload[12] = {0, 0, 0, 5, 0, 0, 0x01, 0xDB, 0, 0, 0, 0x9C};
  const auto record = stream::parse_tlv_record(header, 4, payload, 12);
  CHECK_EQ(record.tlv_type, std::uint8_t{7});
  CHECK_EQ(record.field0, stream::kPointerDown);
  CHECK_EQ(record.field1, std::uint32_t{475});
  CHECK_EQ(record.field2, std::uint32_t{156});
  CHECK(record.handled);
  CHECK(!record.truncated);
}

TEST("stream: a type 3 payload is left in native order") {
  const std::uint8_t header[4] = {0x03, 0x00, 0x00, 0x0C};
  const std::uint8_t payload[12] = {1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0};
  const auto record = stream::parse_tlv_record(header, 4, payload, 12);
  CHECK_EQ(record.field0, std::uint32_t{1});
}

TEST("stream: evdev buttons, not Win32 flags") {
  CHECK_EQ(*stream::evdev_button_for(5), stream::kBtnLeft);
  CHECK_EQ(*stream::evdev_button_for(6), stream::kBtnLeft);
  CHECK_EQ(*stream::evdev_button_for(8), stream::kBtnRight);
  CHECK_EQ(*stream::evdev_button_for(14), stream::kBtnMiddle);
  CHECK(!stream::evdev_button_for(10).has_value());
  CHECK_EQ(stream::kBtnLeft, 272);
  CHECK_EQ(*stream::button_is_press(5), true);
  CHECK_EQ(*stream::button_is_press(6), false);
  CHECK(stream::is_pointer_motion(10));
  CHECK(!stream::is_pointer_motion(5));
}

// ---------------------------------------------------------------------------
// InboundDemuxer
// ---------------------------------------------------------------------------

namespace {

Bytes tlv7(std::uint32_t field0, std::uint32_t x, std::uint32_t y) {
  Bytes out{0x07, 0x00, 0x00, 0x0C};
  put_be32(out, field0);
  put_be32(out, x);
  put_be32(out, y);
  return out;
}

}  // namespace

TEST("demuxer: one whole record") {
  stream::InboundDemuxer demuxer;
  const Bytes data = tlv7(5, 100, 200);
  const auto records = demuxer.feed(data.data(), data.size());
  CHECK_EQ(records.size(), std::size_t{1});
  CHECK_EQ(records[0].field1, std::uint32_t{100});
  CHECK_EQ(demuxer.pending_bytes(), std::size_t{0});
}

TEST("demuxer: several records in one chunk") {
  stream::InboundDemuxer demuxer;
  Bytes data = tlv7(5, 1, 2);
  append(data, tlv7(10, 3, 4));
  append(data, tlv7(6, 5, 6));
  const auto records = demuxer.feed(data.data(), data.size());
  CHECK_EQ(records.size(), std::size_t{3});
  CHECK_EQ(records[1].field0, stream::kPointerMotion);
}

TEST("demuxer: a record split at every offset still reassembles") {
  const Bytes whole = tlv7(10, 640, 480);
  for (std::size_t cut = 1; cut < whole.size(); ++cut) {
    stream::InboundDemuxer demuxer;
    CHECK_EQ(demuxer.feed(whole.data(), cut).size(), std::size_t{0});
    const auto records = demuxer.feed(whole.data() + cut, whole.size() - cut);
    CHECK_EQ(records.size(), std::size_t{1});
    CHECK_EQ(records[0].field1, std::uint32_t{640});
  }
}

TEST("demuxer: byte-at-a-time delivery") {
  stream::InboundDemuxer demuxer;
  Bytes data = tlv7(5, 7, 8);
  append(data, tlv7(6, 7, 8));
  std::vector<stream::TlvRecord> produced;
  for (std::uint8_t b : data) {
    for (const auto& r : demuxer.feed(&b, 1)) produced.push_back(r);
  }
  CHECK_EQ(produced.size(), std::size_t{2});
  CHECK_EQ(produced[0].field0, stream::kPointerDown);
  CHECK_EQ(produced[1].field0, stream::kPointerUp);
}

TEST("demuxer: a trailing partial record is held") {
  stream::InboundDemuxer demuxer;
  Bytes data = tlv7(5, 1, 2);
  const Bytes partial = tlv7(6, 3, 4);
  data.insert(data.end(), partial.begin(), partial.begin() + 9);
  CHECK_EQ(demuxer.feed(data.data(), data.size()).size(), std::size_t{1});
  CHECK_EQ(demuxer.pending_bytes(), std::size_t{9});
}

TEST("demuxer: an overlong record is consumed whole, not desynchronised") {
  // Keeping 12 but consuming 12 would leave 8 bytes in the stream and every
  // later record would start mid-payload.
  Bytes data{0x07, 0x00, 0x00, 0x14};
  for (std::uint8_t i = 0; i < 20; ++i) data.push_back(i);
  append(data, tlv7(6, 9, 9));

  stream::InboundDemuxer demuxer;
  const auto records = demuxer.feed(data.data(), data.size());
  CHECK_EQ(records.size(), std::size_t{2});
  CHECK(records[0].truncated);
  CHECK_EQ(records[1].field0, stream::kPointerUp);
  CHECK_EQ(demuxer.pending_bytes(), std::size_t{0});
}

TEST("demuxer: zero and absurd lengths are rejected") {
  stream::InboundDemuxer zero;
  const Bytes bad_zero{0x07, 0x00, 0x00, 0x00};
  CHECK_THROWS(zero.feed(bad_zero.data(), bad_zero.size()));

  stream::InboundDemuxer huge;
  const Bytes bad_huge{0x07, 0xFF, 0xFF, 0xFF};
  CHECK_THROWS(huge.feed(bad_huge.data(), bad_huge.size()));
}

TEST("demuxer: counters track the stream") {
  stream::InboundDemuxer demuxer;
  Bytes data = tlv7(5, 1, 2);
  append(data, tlv7(6, 1, 2));
  demuxer.feed(data.data(), data.size());
  CHECK_EQ(demuxer.records_seen(), std::uint64_t{2});
  CHECK_EQ(demuxer.bytes_seen(), static_cast<std::uint64_t>(data.size()));
}

TEST("demuxer: a full observed drag reassembles") {
  stream::InboundDemuxer demuxer;
  Bytes data = tlv7(5, 100, 100);
  for (std::uint32_t i = 0; i < 20; ++i) append(data, tlv7(10, 100 + i, 100 + i));
  append(data, tlv7(6, 120, 120));
  const auto records = demuxer.feed(data.data(), data.size());
  CHECK_EQ(records.size(), std::size_t{22});
  CHECK_EQ(records.front().field0, stream::kPointerDown);
  CHECK_EQ(records.back().field0, stream::kPointerUp);
}

int main() { return ::testing::run_all(); }
