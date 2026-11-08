// Emits the C++ core's wire bytes as `name hex` lines, for conformance.cpp's
// Python counterpart to diff against.
//
// The point is not that the two implementations pass similar tests, but that
// they produce the same bytes. The Python side is the reference: it is what
// reproduced the captured 130,375,177-byte stream byte-for-byte and what
// drove the device in FED-LIVE-E001 and FED-HOST-E001.
#include <cstdio>
#include <string>

#include "hashi/startup.hpp"
#include "hashi/stream.hpp"
#include "hashi/usbmux.hpp"

using namespace hashi;

namespace {

void emit(const std::string& name, const Bytes& bytes) {
  std::printf("%s ", name.c_str());
  for (std::uint8_t b : bytes) std::printf("%02x", b);
  std::printf("\n");
}

}  // namespace

int main() {
  // --- startup ----------------------------------------------------------
  emit("probe", startup::encode_byte_order_probe());
  emit("hello", startup::encode_control(startup::kMsgHello));
  emit("ready", startup::encode_control(startup::kMsgReady));
  emit("extra_request",
       startup::encode_control(startup::kMsgExtraRequest, 5, 0, true, true));
  emit("hello_ack_2048x1536",
       startup::encode_control(startup::kMsgHelloAck, 2048, 1536));
  emit("ready_ack", startup::encode_control(startup::kMsgReadyAck));
  emit("legacy_hello", startup::encode_control(startup::kMsgHello, 0, 0, false));
  emit("header_5_12", startup::encode_header(5, 12));
  emit("header_6_19827", startup::encode_header(6, 19827));
  emit("header_6_max", startup::encode_header(6, 0xFFFFFF));

  // --- stream -----------------------------------------------------------
  emit("image_record_small", stream::encode_image_record(Bytes{0xFF, 0xD8, 0xFF, 0xD9}));
  {
    Bytes payload(1000, 0xAB);
    Bytes record = stream::encode_image_record(payload);
    record.resize(8);  // header plus a few bytes is enough to compare framing
    emit("image_record_1000_head", record);
  }

  // --- usbmux header framing -------------------------------------------
  // The plist body itself is not compared: usbmuxd parses XML, and the two
  // writers legitimately differ in whitespace. The header is what the
  // protocol pins, so that is what is checked, with the body length removed.
  {
    const Bytes connect = usbmux::build_connect(1);
    Bytes header(connect.begin() + 4, connect.begin() + 16);  // skip length
    emit("connect_header_tail", header);
  }
  std::printf("port_swapped %u\n", usbmux::htons_port(usbmux::kApplicationPort));
  std::printf("align_2048 %u\n", startup::align_client_dimension(2048));
  std::printf("align_1 %u\n", startup::align_client_dimension(1));
  std::printf("align_5 %u\n", startup::align_client_dimension(5));
  std::printf("interval_30 %u\n", stream::frame_interval_ms(30));
  std::printf("interval_60 %u\n", stream::frame_interval_ms(60));
  return 0;
}
